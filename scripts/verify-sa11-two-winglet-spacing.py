"""Transfer the fixed SA-11 spacing rule to upper/lower winglets.

Six prescribed pre-stall sample conditions, one bounded foreground solve per
invocation. Reference and report-derived inputs remain separate. No tuning.
"""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT/'artifacts/isae/sa11-minimum-spacing-20261108'
CACHE = ROOT/'reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865'
FIELDS = dict(lift=75, drag=76, CL=77, CD=78, CDi=79, Cm_origin=80, efficiency=81)
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
utc = lambda: datetime.now(timezone.utc).isoformat()


def write(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def check(pins, root=ROOT):
    for name, digest in pins.items():
        assert sha(root/name) == digest, name


def bounded():
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        assert os.environ.get(key) == '1', key
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    signal.alarm(25)


def prepare(out):
    assert not out.exists(), out
    parent = read(PARENT/'plan.json')
    check(parent['pins']); check(parent['generated_pins'], PARENT)
    catalog = read(ROOT/'docs/validation/isae-sa11-sources.json')
    provenance = read(ROOT/'examples/isae-sa11-winglet-sources.json')
    item = next(x for x in provenance['examples'] if x['variant'] == 'wingtip_up_and_down')
    original = CACHE/item['upstream_path']; source = ROOT/item['bundled_path']
    assert sha(original) == item['upstream_sha256']
    assert sha(source) == item['bundled_sha256']
    for entry in read(ROOT/'docs/validation/aswing-authoritative-sources.json')['files']:
        if entry['id'] in ('isae-part-1', 'drela-steady'):
            assert sha(ROOT/entry['local_pdf']) == entry['sha256']
    # Figure 40, Part I p.68: upper root/tip -4; lower root -7, tip -11.
    # Preserve literal source text except the four upper twist entries.
    lines = source.read_text().splitlines(); beam = None; geometry = False; edits = []
    for i, line in enumerate(lines):
        tokens = line.split()
        if tokens and tokens[0].lower() == 'beam':
            beam = int(tokens[1]); geometry = False
        elif tokens and tokens[0] == 't':
            geometry = tokens[1:4] == ['x', 'y', 'z']
        elif geometry and beam in (2, 3) and tokens and tokens[0][0] in '-0123456789':
            assert len(tokens) == 7 and tokens[4] == '4'
            spans = list(re.finditer(r'\S+', line)); start, end = spans[4].span()
            lines[i] = line[:start]+'-4'+line[end:]
            edits.append(dict(line=i+1, before=line, after=lines[i]))
    assert len(edits) == 4
    model = '\n'.join(lines)+'\n'
    pins = dict(parent['pins'])
    for p in (original, source, ROOT/'examples/isae-sa11-winglet-sources.json',
              PARENT/'plan.json', PARENT/'analysis.json', PARENT/'mesh.json', Path(__file__)):
        pins[str(p.relative_to(ROOT))] = sha(p)
    cases = []; normalization = []
    for label, speed in [('0_70', 240.), ('0_80', 272.)]:
        names = [next(n for n in catalog['sources'] if n.endswith('/Wing_tip_up_and_down/'+name))
                 for name in (f'wingtip_up_and_down_Ma_{label}.txt', f'wingtip_up_and_down_polar_Ma_{label}.sh')]
        table, driver = [CACHE/n for n in names]
        for name, path in zip(names, (table, driver)):
            assert sha(path) == catalog['sources'][name]['sha256']
            pins[str(path.relative_to(ROOT))] = sha(path)
        assert re.findall(r'^!V\s+(.+)$', driver.read_text(), re.M) == [str(int(speed))]
        assert list(map(float, re.findall(r'^!A\s+(.+)$', driver.read_text(), re.M))) == [i/4 for i in range(41)]
        rows = [r.split() for r in table.read_text().splitlines() if len(r.split()) == 82 and r.split()[0].isdigit()]
        assert len(rows) == 41 and [float(r[71]) for r in rows] == [i/4 for i in range(41)]
        for index in (0, 4, 20):
            tokens = rows[index]; row = list(map(float, tokens)); alpha = index/4
            assert row[69] == row[72] == speed and row[70] == row[73] == 0
            assert row[71] == row[74] == alpha and row[2] == 1
            qs = Decimal('1.2256')*Decimal(str(speed))**2*Decimal('0.9329')/2
            intervals = {}
            for f, c in [('lift', 'CL'), ('drag', 'CD')]:
                force, coeff = [Decimal(tokens[FIELDS[k]]) for k in (f, c)]
                hf, hc = [Decimal(5).scaleb(x.as_tuple().exponent-1) for x in (force, coeff)]
                lo, hi = (force-hf)/(coeff+hc), (force+hf)/(coeff-hc)
                assert lo <= qs <= hi, (label, index, f)
                intervals[f] = [str(lo), str(hi)]
            normalization.append(dict(label=label, row=index, qS=str(qs), printed_intervals=intervals))
            condition = dict(parent['cases'][0]['condition'], alpha=alpha, speed=speed, mach=speed/340.21)
            cases.append(dict(id=f'm{label}-a{index:02d}', label=label, row=index, alpha=alpha,
                              condition=condition, table=str(table.relative_to(ROOT)), tokens=tokens,
                              reference={k:row[col] for k,col in FIELDS.items()}))
    mesh = read(PARENT/'mesh.json')
    for key in ('4', '5'):
        mesh[key] = dict(mesh['2'])
    out.mkdir(parents=True)
    (out/'model.asw').write_text(model)
    shutil.copyfile(source, out/'source-joint-corrected.asw')
    shutil.copyfile(__file__, out/'driver-used.py')
    write(out/'mesh.json', mesh)
    write(out/'mesh-import.json', dict(format='openswing-mesh', version=1, panels=dict(default=32, beams=mesh)))
    write(out/'plan.json', dict(observed_utc=utc(), cases=cases, pins=pins,
        generated_pins={p.name:sha(p) for p in out.iterdir()}, edits=edits, normalization=normalization,
        minimum_spacing=parent['minimum_spacing'], previous_goal_turn='Progress: per-beam spacing implemented; upper-only 294/294 diagnostic comparisons and 68 mesh/regression checks pass.',
        protocol='Six prescribed points: alpha0/1/5 at240/272. Joint-corrected bundled upper/lower model, report -4 upper twist, literal -7..-11 lower twist. Parent main32 explicit nodes; same exact 16.4659927127284mm minimum on all4 winglets, uniform32 requests. Frozen x wake, PG V/a, zero shared core, original section/stall/moment laws. No fitted parameters.',
        limits='Diagnostic report-derived model, not authenticated producing input. Other angles/configurations and normalization-conflict tables remain outstanding. All seven reference fields retained even if rejected. No primary scope change.',
        primary_passes_added=0))
    print(json.dumps(dict(prepared=True, cases=len(cases), scalar_targets=7*len(cases))), flush=True)


def run(out, case_id):
    bounded(); begin = time.monotonic()
    plan = read(out/'plan.json'); check(plan['pins']); check(plan['generated_pins'], out)
    case = next(c for c in plan['cases'] if c['id'] == case_id)
    folder = out/case_id; assert not folder.exists(), folder
    print(f'Bounded serial solve: {case_id}', flush=True)
    import numpy as np
    sys.path.insert(0, str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.aero import FlightCondition, AnalysisError, evaluate_aerodynamics
    from openswing.frozen_influence import lifting_geometry
    from openswing.factored_influence import FactoredInfluence
    from openswing.ground import GroundPlane
    from openswing.trefftz import trefftz_for_meshes
    model = parse_asw((out/'model.asw').read_text())
    meshes = model_meshes(model, dict(default=32, beams=read(out/'mesh.json')))
    assert all(b.physical_index == 1 for b in model.beams)
    assert [len(m.tm) for m in meshes[:3]] == [32, 16, 16]
    assert all(np.min(m.length) >= plan['minimum_spacing']-1e-12 for m in meshes)
    condition = FlightCondition(**case['condition'])
    g = lifting_geometry(meshes, np.array([1.,0.,0.])); n = len(g['hv'])
    with np.load(ROOT/'artifacts/isae/sa11-winglet-spacing-20261108/uniform-16/geometry.npz') as old:
        for key in g: np.testing.assert_allclose(g[key][:64], old[key], rtol=0, atol=2e-12)
    folder.mkdir(); np.savez(folder/'geometry.npz', **g)
    span = np.concatenate([m.frames[...,1] for m in meshes]); position = np.concatenate([m.rm for m in meshes])
    beam = np.concatenate([np.full(len(m.tm),m.beam.index) for m in meshes])
    sample = lambda name: np.concatenate([m.beam.value(name,m.tm) for m in meshes])
    accepted = None; clock = time.monotonic()
    try:
        accepted = evaluate_aerodynamics(model, condition, meshes)
    except AnalysisError as exc:
        assert exc.details and exc.details['kind'] == 'section_normal_mach', str(exc)
        tb = exc.__traceback__
        while tb and tb.tb_frame.f_code.co_name != 'evaluate_aerodynamics': tb = tb.tb_next
        assert tb is not None
        local = tb.tb_frame.f_locals
        gamma, velocity, cl = [local[k].copy() for k in ('gamma','v','cl')]
        force = local['flift']+local['frate']+local['fprofile']; section_moment = np.full_like(force, np.nan)
        residual = exc.details['circulation_residual']; values = {k:exc.details['surface_force_diagnostic']['terms']['sum'][k] for k in ('CL','CD')}
        values['Cm_origin'] = None
        write(folder/'rejected.json', dict(message=str(exc), details=exc.details)); status = 'REJECTED_STATE_DIAGNOSTIC'
        del tb, local
    else:
        write(folder/'accepted.json', accepted)
        gamma, velocity, cl, force, section_moment = [np.array([s[k] for s in accepted['strips']]) for k in ('circulation','relative_velocity','cl','force','moment')]
        residual = accepted['residual']; values = {k:accepted[k] for k in ('CL','CD','Cm_origin')}; status = 'COMPUTED_DIAGNOSTIC'
    elapsed = time.monotonic()-clock; assert residual < 1e-8
    mach = np.linalg.norm(velocity-np.sum(velocity*span,axis=1)[:,None]*span,axis=1)/340.21
    invalid = int(np.count_nonzero(mach >= 1)); assert (invalid == 0) == (accepted is not None)
    pg = np.diag([1/np.sqrt(1-condition.mach**2),1.,1.])
    field = FactoredInfluence(g['hv'],g['a'],g['b'],np.array([1.,0.,0.]),pg,0.,GroundPlane(),exclude_bound=np.eye(n,dtype=bool))
    bound = np.einsum('ijk,j->ik',field.bound,gamma); wake = np.einsum('ijk,j->ik',field.rays,field.wake_strengths(gamma))
    replay = float(np.max(abs(condition.speed*condition.vectors()[0]+bound+wake-velocity))); assert replay < 3e-8
    trefftz = trefftz_for_meshes(model,replace(condition,alpha=0.,beta=0.),meshes,gamma,1.2256,GroundPlane()); assert trefftz['available']
    values.update(CDi=trefftz['CDi'],efficiency=trefftz['efficiency'])
    alpha = math.radians(condition.alpha); qs = .5*1.2256*condition.speed**2*.9329
    total = [math.fsum(map(float,force[:,i])) for i in range(3)]
    values.update(lift=-math.sin(alpha)*total[0]+math.cos(alpha)*total[2],drag=math.cos(alpha)*total[0]+math.sin(alpha)*total[2])
    for f,c in [('lift','CL'),('drag','CD')]: assert abs(values[f]/qs-values[c]) < 3e-14
    margin = np.minimum(sample('CLmax')-cl,cl-sample('CLmin'))/condition.stall_width
    np.savez(folder/'state.npz',gamma=gamma,velocity=velocity,cl=cl,force=force,section_moment=section_moment,
             section_moment_available=accepted is not None,position=position,span=span,beam=beam,mach=mach,bound=bound,wake=wake)
    errors = {k:None if values[k] is None else 100*(values[k]/v-1) for k,v in case['reference'].items()}
    passes = {k:bool(accepted is not None and abs(errors[k]) <= 5) for k in FIELDS}
    worst = int(np.argmax(mach))
    report = dict(observed_utc=utc(),case=case,status=status,values=values,reference_error_percent=errors,passes=passes,
        passing_scalar_targets=sum(passes.values()),required_scalar_targets=7,maximum_normal_mach=float(mach.max()),rejected_sections=invalid,
        worst=dict(index=worst,beam=int(beam[worst]),bound_speed=float(np.linalg.norm(bound[worst])),wake_speed=float(np.linalg.norm(wake[worst]))),
        minimum_stall_margin_widths=float(margin.min()),residual=float(residual),flow_replay_error=replay,
        meshes=[dict(beam=m.beam.index,intervals=len(m.tm),minimum_interval=float(min(m.length)),maximum_normal_mach=float(max(mach[beam==m.beam.index]))) for m in meshes],
        solve_seconds=elapsed,total_seconds=time.monotonic()-begin,maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        primary_passes_added=0,artifacts={p.name:sha(p) for p in folder.iterdir()})
    write(folder/'report.json', report); signal.alarm(0)
    print(json.dumps({k:report[k] for k in ('case','status','passing_scalar_targets','reference_error_percent','maximum_normal_mach','meshes','total_seconds','maxrss_kib') if k!='case'}),flush=True)


def summarize(out):
    plan = read(out/'plan.json'); check(plan['pins']); check(plan['generated_pins'],out)
    results = []
    for case in plan['cases']:
        folder = out/case['id']; r = read(folder/'report.json')
        assert r['case'] == case; check(r['artifacts'],folder)
        results.append(dict(**r,report_sha256=sha(folder/'report.json')))
    groups = {label:dict(computed=sum(r['status']=='COMPUTED_DIAGNOSTIC' for r in results if r['case']['label']==label),
                        passing_scalar_targets=sum(r['passing_scalar_targets'] for r in results if r['case']['label']==label)) for label in ('0_70','0_80')}
    result = dict(observed_utc=utc(),cases=results,groups=groups,plan_sha256=sha(out/'plan.json'),primary_passes_added=0,
                  passing_scalar_targets=sum(r['passing_scalar_targets'] for r in results),required_scalar_targets=7*len(results))
    write(out/'analysis.json',result); print(json.dumps(groups,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare',action='store_true'); action.add_argument('--case'); action.add_argument('--summarize',action='store_true')
    args = parser.parse_args(); out = args.output.resolve()
    if args.prepare: prepare(out)
    elif args.case: run(out,args.case)
    else: summarize(out)
