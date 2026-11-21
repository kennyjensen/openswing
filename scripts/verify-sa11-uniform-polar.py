"""Fixed uniform-32 winglets at every archived 0--5 degree row, two speeds.

Use --prepare once, then small --start/--count serial batches, then --summarize.
Each batch has one BLAS thread, 512 MiB address space, 15 CPU / 25 wall seconds.
No production settings, reference targets, primary counts or scopes are changed.
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
PRIOR = ROOT/'artifacts/isae/sa11-winglet-spacing-20261108'
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


def literal_rows(path):
    rows = []
    for line in path.read_text().splitlines():
        tokens = line.split()
        if len(tokens) == 82 and tokens[0].isdigit():
            rows.append(tokens)
    assert len(rows) == 41 and [float(r[71]) for r in rows] == [i/4 for i in range(41)]
    return rows


def prepare(out):
    assert not out.exists(), out
    parent = read(PRIOR/'plan.json'); check(parent['pins']); check(parent['generated_pins'], PRIOR)
    old = read(PRIOR/'uniform-32/report.json'); check(old['artifacts'], PRIOR/'uniform-32')
    catalog = read(ROOT/'docs/validation/isae-sa11-sources.json')
    for item in read(ROOT/'docs/validation/aswing-authoritative-sources.json')['files']:
        if item['id'] in ('isae-part-1', 'drela-steady'):
            assert sha(ROOT/item['local_pdf']) == item['sha256']
    pins = dict(parent['pins']); cases = []; normalization = []
    for label, speed in [('0_70', 240.), ('0_80', 272.)]:
        names = [next(n for n in catalog['sources'] if n.endswith('/Wing_tip_up/'+name)) for name in
                 (f'wingtip_up_Ma_{label}.txt', f'wingtip_up_polar_Ma_{label}.sh')]
        table, driver = [CACHE/n for n in names]
        for name, path in zip(names, (table, driver)):
            assert sha(path) == catalog['sources'][name]['sha256']
            pins[str(path.relative_to(ROOT))] = sha(path)
        text = driver.read_text()
        assert re.findall(r'^!V\s+(.+)$', text, re.M) == [str(int(speed))]
        assert list(map(float, re.findall(r'^!A\s+(.+)$', text, re.M))) == [i/4 for i in range(41)]
        for i, tokens in enumerate(literal_rows(table)[:21]):
            row = list(map(float, tokens)); alpha = i/4
            assert row[69] == row[72] == speed and row[70] == row[73] == 0
            assert row[71] == row[74] == alpha and row[2] == 1
            qs = Decimal('1.2256')*Decimal(str(speed))**2*Decimal('0.9329')/2
            intervals = {}
            for f, c in [('lift', 'CL'), ('drag', 'CD')]:
                force, coeff = [Decimal(tokens[FIELDS[k]]) for k in (f, c)]
                hf, hc = [Decimal(5).scaleb(x.as_tuple().exponent-1) for x in (force, coeff)]
                lo, hi = (force-hf)/(coeff+hc), (force+hf)/(coeff-hc)
                assert lo <= qs <= hi, (label, i, f)
                intervals[f] = [str(lo), str(hi)]
            normalization.append(dict(label=label, row=i, qS=str(qs), printed_intervals=intervals))
            condition = dict(parent['condition'], alpha=alpha, speed=speed, mach=speed/340.21)
            cases.append(dict(id=f'm{label}-a{i:02d}', label=label, row=i, alpha=alpha,
                              condition=condition, table=str(table.relative_to(ROOT)),
                              reference={k:row[col] for k,col in FIELDS.items()}, tokens=tokens))
    assert len(cases) == 42
    for path in (Path(__file__), PRIOR/'plan.json', PRIOR/'analysis.json', PRIOR/'uniform-32/report.json',
                 PRIOR/'uniform-32/geometry.npz', PRIOR/'uniform-32/state.npz',
                 ROOT/'docs/validation/isae-sa11-sources.json', ROOT/'docs/validation/aswing-authoritative-sources.json'):
        pins[str(path.relative_to(ROOT))] = sha(path)
    out.mkdir(parents=True)
    for source, target in [('model.asw', 'model.asw'), ('uniform-32-mesh.json', 'mesh.json')]:
        shutil.copyfile(PRIOR/source, out/target)
    shutil.copyfile(__file__, out/'driver-used.py')
    write(out/'plan.json', dict(observed_utc=utc(), cases=cases, pins=pins,
        generated_pins={p.name:sha(p) for p in out.iterdir()}, normalization=normalization,
        previous_goal_turn='Progress:12 spacing diagnostics produced four complete matching states; documented the successful32-strip comparison and finer-grid sensitivity.',
        protocol='Fixed report-minus4 upper-winglet input and uniform32 winglet intervals, main32. All21 archived0..5degree rows at240/272m/s. Frozen influences, PG V/340.21, whole-beam receivers, zero shared core, unchanged stall and moment laws. No fitting or mesh refinement.',
        limits='This disclosed alternative does not authenticate native producing inputs or default grid. Other configurations, normalization-conflict0.75/0.78 tables and5.25..10degree rows remain in the primary scope; not run here. All7 fields retained even for rejected states. Primary counts/scope unchanged.',
        primary_passes_added=0))
    print(json.dumps(dict(prepared=True, cases=len(cases), scalar_targets=7*len(cases))), flush=True)


def batch(out, start, count):
    assert 1 <= count <= 3 and 0 <= start and start+count <= 42
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        assert os.environ.get(key) == '1', key
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15)); signal.alarm(25)
    begin = time.monotonic(); plan = read(out/'plan.json'); check(plan['pins']); check(plan['generated_pins'], out)
    print(f'Bounded serial batch {start}..{start+count-1}', flush=True)
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
    assert all(b.physical_index == 1 for b in model.beams)
    assert model.reference[0,0] == .9329
    meshes = model_meshes(model, dict(default=16, beams=read(out/'mesh.json')))
    assert [len(m.tm) for m in meshes] == [32,32,32]
    g = lifting_geometry(meshes, np.array([1.,0.,0.]))
    with np.load(PRIOR/'uniform-32/geometry.npz') as old:
        for key in g: np.testing.assert_array_equal(g[key], old[key])
    span = np.concatenate([m.frames[...,1] for m in meshes])
    position = np.concatenate([m.rm for m in meshes])
    beam = np.concatenate([np.full(len(m.tm),m.beam.index) for m in meshes])
    sample = lambda name: np.concatenate([m.beam.value(name,m.tm) for m in meshes])
    reports = {}
    for case in plan['cases'][start:start+count]:
        folder = out/case['id']; assert not folder.exists(), folder; folder.mkdir()
        condition = FlightCondition(**case['condition']); accepted = None; clock = time.monotonic()
        try:
            accepted = evaluate_aerodynamics(model, condition, meshes)
        except AnalysisError as exc:
            assert exc.details and exc.details['kind'] == 'section_normal_mach', str(exc)
            tb = exc.__traceback__
            while tb and tb.tb_frame.f_code.co_name != 'evaluate_aerodynamics': tb = tb.tb_next
            assert tb is not None
            local = tb.tb_frame.f_locals
            gamma, velocity, cl = [local[k].copy() for k in ('gamma','v','cl')]
            force = local['flift']+local['frate']+local['fprofile']
            section_moment = np.zeros_like(force)
            residual = exc.details['circulation_residual']
            values = {k:exc.details['surface_force_diagnostic']['terms']['sum'][k] for k in ('CL','CD')}
            values['Cm_origin'] = None
            write(folder/'rejected.json', dict(message=str(exc), details=exc.details))
            status = 'REJECTED_STATE_DIAGNOSTIC'
            del tb, local
        else:
            write(folder/'accepted.json', accepted)
            gamma, velocity, cl, force, section_moment = [np.array([s[k] for s in accepted['strips']])
                for k in ('circulation','relative_velocity','cl','force','moment')]
            residual = accepted['residual']; values = {k:accepted[k] for k in ('CL','CD','Cm_origin')}
            status = 'COMPUTED_DIAGNOSTIC'
        solve_seconds = time.monotonic()-clock; assert residual < 1e-8
        perp = velocity-np.sum(velocity*span,axis=1)[:,None]*span
        mach = np.linalg.norm(perp,axis=1)/340.21
        rejected = int(np.count_nonzero(mach >= 1)); assert (rejected == 0) == (accepted is not None)
        pg = np.diag([1/np.sqrt(1-condition.mach**2),1.,1.])
        field = FactoredInfluence(g['hv'],g['a'],g['b'],np.array([1.,0.,0.]),pg,0.,GroundPlane(),exclude_bound=np.eye(96,dtype=bool))
        bound = np.einsum('ijk,j->ik',field.bound,gamma)
        wake = np.einsum('ijk,j->ik',field.rays,field.wake_strengths(gamma))
        replay = float(np.max(abs(condition.speed*condition.vectors()[0]+bound+wake-velocity)))
        assert replay < 3e-8
        trefftz = trefftz_for_meshes(model,replace(condition,alpha=0.,beta=0.),meshes,gamma,1.2256,GroundPlane())
        assert trefftz['available']; values.update(CDi=trefftz['CDi'], efficiency=trefftz['efficiency'])
        if accepted is not None:
            for key in ('CDi','efficiency'): assert abs(values[key]-accepted[key]) < 2e-12
        alpha = math.radians(condition.alpha); qS = .5*1.2256*condition.speed**2*.9329
        total = [math.fsum(map(float,force[:,i])) for i in range(3)]
        lift = -math.sin(alpha)*total[0]+math.cos(alpha)*total[2]
        drag = math.cos(alpha)*total[0]+math.sin(alpha)*total[2]
        assert abs(lift/qS-values['CL']) < 3e-14 and abs(drag/qS-values['CD']) < 3e-14
        values.update(lift=lift, drag=drag)
        moment_error = None
        if accepted is not None:
            moment_y = math.fsum(float(m[1])+float(r[2])*float(f[0])-float(r[0])*float(f[2])
                                  for r,f,m in zip(position,force,section_moment))
            moment_error = abs(moment_y/(qS*model.reference[0,1])-values['Cm_origin'])
            assert moment_error < 2e-12
        margin = np.minimum(sample('CLmax')-cl,cl-sample('CLmin'))/condition.stall_width
        np.savez(folder/'state.npz',gamma=gamma,velocity=velocity,cl=cl,force=force,
                 section_moment=section_moment,position=position,span=span,beam=beam,mach=mach,bound=bound,wake=wake)
        if case['label'] == '0_70' and case['alpha'] == 1:
            with np.load(PRIOR/'uniform-32/state.npz') as old:
                for value,key in [(gamma,'gamma'),(velocity,'velocity'),(cl,'cl')]: np.testing.assert_array_equal(value,old[key])
        errors = {k:None if values[k] is None else 100*(values[k]/v-1) for k,v in case['reference'].items()}
        passes = {k:bool(accepted is not None and abs(errors[k]) <= 5) for k in FIELDS}
        worst = int(np.argmax(mach))
        report = dict(observed_utc=utc(),case=case,status=status,values=values,reference_error_percent=errors,
            passes=passes,passing_scalar_targets=sum(passes.values()),required_scalar_targets=7,
            maximum_normal_mach=float(mach.max()),rejected_sections=rejected,
            worst=dict(index=worst,beam=int(beam[worst]),bound_speed=float(np.linalg.norm(bound[worst])),wake_speed=float(np.linalg.norm(wake[worst]))),
            minimum_stall_margin_widths=float(margin.min()),residual=float(residual),flow_replay_error=replay,
            moment_reduction_error=moment_error,solve_seconds=solve_seconds,primary_passes_added=0,
            artifacts={p.name:sha(p) for p in folder.iterdir()})
        write(folder/'report.json',report); reports[case['id']] = sha(folder/'report.json')
        print(json.dumps(dict(case=case['id'],status=status,passes=sum(passes.values()),
            maximum_mach=report['maximum_normal_mach'],errors_percent=errors)),flush=True)
    write(out/f'batch-{start:02d}.json',dict(observed_utc=utc(),start=start,count=count,reports=reports,
        plan_sha256=sha(out/'plan.json'),total_seconds=time.monotonic()-begin,
        maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
    signal.alarm(0)


def summarize(out):
    plan = read(out/'plan.json'); check(plan['pins']); check(plan['generated_pins'],out)
    cases = []
    for case in plan['cases']:
        folder=out/case['id']; r=read(folder/'report.json')
        assert r['case']==case; check(r['artifacts'],folder)
        cases.append(dict(**r,report_sha256=sha(folder/'report.json')))
    batches = [read(p) for p in sorted(out.glob('batch-*.json'))]
    assert sorted(i for b in batches for i in range(b['start'],b['start']+b['count'])) == list(range(42))
    for b in batches:
        assert b['plan_sha256']==sha(out/'plan.json')
        for name,digest in b['reports'].items(): assert sha(out/name/'report.json')==digest
    groups = {}
    for label in ('0_70','0_80'):
        rows=[r for r in cases if r['case']['label']==label]; good=[r for r in rows if r['status']=='COMPUTED_DIAGNOSTIC']
        groups[label]=dict(computed=len(good),rejected=len(rows)-len(good),
            passing_scalar_targets=sum(r['passing_scalar_targets'] for r in rows),required_scalar_targets=7*len(rows),
            complete_matching_angles=[r['case']['alpha'] for r in good if all(r['passes'].values())],
            computed_error_ranges_percent={k:[min(r['reference_error_percent'][k] for r in good),max(r['reference_error_percent'][k] for r in good)] if good else None for k in FIELDS},
            maximum_normal_mach_range=[min(r['maximum_normal_mach'] for r in rows),max(r['maximum_normal_mach'] for r in rows)])
    write(out/'analysis.json',dict(observed_utc=utc(),cases=cases,groups=groups,batches=batches,
        plan_sha256=sha(out/'plan.json'),primary_passes_added=0,
        maximum_residual=max(r['residual'] for r in cases),minimum_stall_margin_widths=min(r['minimum_stall_margin_widths'] for r in cases),
        maximum_flow_replay_error=max(r['flow_replay_error'] for r in cases)))
    print(json.dumps(groups,indent=2),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--output',type=Path,required=True)
    action=p.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare',action='store_true'); action.add_argument('--start',type=int)
    action.add_argument('--summarize',action='store_true'); p.add_argument('--count',type=int,default=3)
    args=p.parse_args()
    if args.prepare: prepare(args.output)
    elif args.start is not None: batch(args.output,args.start,args.count)
    else: summarize(args.output)
