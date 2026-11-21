"""Prescribed SA-11 geometry sensitivity, one bounded serial solve per call.

Translate each whole upper winglet, preserving its local shape, section data,
physical index and Joint parameters. These are diagnostic geometries, not
authenticated replacements for the ISAE input. No fitted cores or guards.
"""
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import difflib
import hashlib
import importlib.util
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
ANGLES = ROOT/'artifacts/isae/sa11-angle-conventions-20261108'
OLD = ROOT/'artifacts/isae/sa11-angle-response-20261108/report_minus4'
MESH = ROOT/'artifacts/isae/sa11-winglet-receivers-20261108/whole-beam-a1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def check(pins):
    for name, digest in pins.items():
        assert sha(ROOT/name) == digest, name


def prepare(out):
    assert not out.exists(), 'Preserve prior evidence; use a new output directory.'
    audit = read(ANGLES/'geometry-audit.json')
    check(audit['source_pins'])
    for name, digest in audit['file_sha256'].items():
        assert sha(ANGLES/name) == digest, name
    check(read(OLD/'inputs.json')['pins'])
    old = read(OLD/'report.json')
    for name, digest in old['artifacts'].items():
        assert sha(OLD/name) == digest, name
    catalog = read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for item in catalog['files']:
        if item['id'] in ('isae-part-1', 'drela-steady'):
            assert sha(ROOT/item['local_pdf']) == item['sha256']
    # The pinned source-only preparation supplies a strict fixture scanner.
    path = ROOT/'scripts/prepare-sa11-angle-conventions.py'
    assert sha(path) == audit['file_sha256']['prepare-used.py']
    spec = importlib.util.spec_from_file_location('angles', path)
    scalar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scalar)
    source = (ANGLES/'report_minus4.asw').read_text()
    blocks = scalar.geometry_blocks(source)
    s = scalar.basis(blocks[2])[0]
    transverse = math.hypot(s[1], s[2])
    radial = [0., s[1]/transverse, s[2]/transverse]
    offset = audit['retained_geometry']['frozen_body_x_quarter_chord_root_offset_m']
    variants = [dict(id=name, dx_m=dx, radial_m=dr) for name,dx,dr in [
        ('control', 0., 0.), ('forward1mm', -.001, 0.), ('aft1mm', .001, 0.),
        ('inward025mm', 0., -.00025), ('outward025mm', 0., .00025),
        ('aligned_roots', -offset, 0.)]]
    out.mkdir(parents=True)
    for variant in variants:
        lines = source.splitlines(keepends=True)
        translations = {}
        for beam, side in [(2, 1), (3, -1)]:
            delta = [variant['dx_m'], side*variant['radial_m']*radial[1], variant['radial_m']*radial[2]]
            translations[str(beam)] = delta
            for row in blocks[beam]:
                index = row['line']
                # Geometry blocks use a literal .1 multiplier on x/y/z.
                for column,key,shift in reversed(list(zip([1,2,3], ['x','y','z'], delta))):
                    if shift == 0:
                        continue
                    tokens = list(re.finditer(r'\S+', lines[index]))
                    a,b = tokens[column].span()
                    value = (row[key]+shift)/.1
                    lines[index] = lines[index][:a]+f'{value:.17g}'+lines[index][b:]
        text = (f"# SA-11 root-translation diagnostic: {variant['id']}.\n"
                "# Based on report-minus4 with Joint correction; not an authenticated ISAE input.\n"
                "# Whole-winglet translations are disclosed in plan.json; original benchmark retained.\n"
                + ''.join(lines[3:]))
        new = scalar.geometry_blocks(text)
        for beam,rows in blocks.items():
            delta = translations.get(str(beam), [0.,0.,0.])
            for before,after in zip(rows,new[beam],strict=True):
                for key in scalar.GEOMETRY:
                    expected = before[key]+(delta[['x','y','z'].index(key)] if key in ['x','y','z'] else 0)
                    assert abs(after[key]-expected) < 5e-15, (beam,key)
        variant['translations'] = translations
        model = out/f"{variant['id']}.asw"
        # Preserve the source body except the explicit coordinate tokens;
        # replace its preparation-only comments with this variant's identity.
        model.write_text(text)
        (out/f"{variant['id']}.diff").write_text(''.join(difflib.unified_diff(
            source.splitlines(True), text.splitlines(True), fromfile='report_minus4.asw', tofile=model.name)))
    settings = read(MESH/'mesh-settings.json')
    fine = {beam:dict(nodes=[v for a,b in zip(row['nodes'][:-1],row['nodes'][1:])
                             for v in (a, .5*(a+b))]+[row['nodes'][-1]])
            for beam,row in settings.items()}
    write(out/'mesh64.json', settings)
    write(out/'mesh128.json', fine)
    cases = [dict(id=f"{v['id']}-{n}", variant=v['id'], panels=n)
             for n in (64,128) for v in variants]
    source_files = [Path(__file__), path, ANGLES/'geometry-audit.json', ANGLES/'report_minus4.asw',
                   OLD/'report.json', OLD/'state.npz', OLD/'inputs.json', MESH/'condition.json',
                   MESH/'mesh-settings.json', MESH/'geometry.npz',
                   ROOT/'docs/validation/aswing-authoritative-sources.json', ROOT/'reference/aswing_doc.txt']
    pins = {str(p.relative_to(ROOT)):sha(p) for p in [*sorted((ROOT/'openswing').glob('*.py')), *source_files]}
    pins.update(audit['source_pins'])
    write(out/'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        previous_goal_turn='Progress: three production incidence checks rule out angle convention alone as the root-flow repair.',
        variants=variants, cases=cases, pins=pins,
        generated_pins={p.name:sha(p) for p in out.iterdir() if p.is_file()},
        condition=read(MESH/'condition.json'), reference=old['reference'],
        protocol='One solve per process, BLAS1, 512MiB AS, 15s CPU, 25s wall. Preserve physical1 zero-core and all physics. Symmetric whole-winglet translations. Fine mesh bisects each original parameter interval; physical geometry is fixed across meshes.',
        reason='Separate finite-origin streamwise offsets from transverse distance to the main-wing wake. Aligned roots change geometry deliberately; no snapping inside the solver.',
        reference_basis='Drela user guide Joint and Physical index; steady Eqs64-74,150-161; Jan PartI Fig22 and Fig40. NASA rounded junction does not specify native treatment.',
        limits='Alternative report-minus4 model and diagnostic grids; no new primary scope or passes. Small translation gaps are sensitivity experiments, not reconstructed physical fillets.'))
    shutil.copyfile(__file__,out/'driver-used.py')
    print(json.dumps(dict(prepared=True,cases=cases)),flush=True)


def run(out, case_id):
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        assert os.environ.get(key) == '1', key
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(15,15))
    def timeout(*_):
        raise TimeoutError('SA11 root-translation job exceeded25 seconds')
    signal.signal(signal.SIGALRM,timeout); signal.alarm(25)
    begin = time.monotonic()
    plan = read(out/'plan.json'); check(plan['pins'])
    for name,digest in plan['generated_pins'].items():
        assert sha(out/name)==digest,name
    case = next(c for c in plan['cases'] if c['id']==case_id)
    variant = next(v for v in plan['variants'] if v['id']==case['variant'])
    folder = out/case_id; assert not folder.exists()
    print(f"Importing single-process solver for {case_id}.",flush=True)
    import numpy as np
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.aero import FlightCondition, AnalysisError, evaluate_aerodynamics
    from openswing.frozen_influence import lifting_geometry
    from openswing.factored_influence import FactoredInfluence
    from openswing.ground import GroundPlane
    from openswing.trefftz import trefftz_for_meshes
    model = parse_asw((out/f"{case['variant']}.asw").read_text())
    baseline = parse_asw((out/'control.asw').read_text())
    for key in ('constants','reference'):
        np.testing.assert_array_equal(getattr(model,key),getattr(baseline,key))
    assert model.records.keys()==baseline.records.keys()
    for key in model.records:
        for a,b in zip(model.records[key],baseline.records[key],strict=True):
            np.testing.assert_array_equal(a,b)
    settings = read(out/f"mesh{case['panels']}.json")
    meshes = model_meshes(model,dict(default=16,beams=settings))
    base_meshes = model_meshes(baseline,dict(default=16,beams=settings))
    position_error = frame_error = 0.
    for mesh,base in zip(meshes,base_meshes,strict=True):
        delta = variant['translations'].get(str(mesh.beam.index),[0.,0.,0.])
        assert mesh.beam.physical_index==1
        assert mesh.beam.distributions.keys()==base.beam.distributions.keys()
        for name,distribution in mesh.beam.distributions.items():
            original = base.beam.distributions[name]
            np.testing.assert_array_equal(distribution.t,original.t)
            shift = delta[['x','y','z'].index(name)] if name in ['x','y','z'] else 0.
            np.testing.assert_allclose(distribution.values,original.values+shift,rtol=0,atol=5e-15)
        for name in ('t0','t1','tm','length'):
            np.testing.assert_allclose(getattr(mesh,name),getattr(base,name),rtol=0,atol=2e-13)
        for name in ('r0','r1','rm'):
            position_error=max(position_error,float(np.max(abs(getattr(mesh,name)-getattr(base,name)-delta))))
        frame_error=max(frame_error,float(np.max(abs(mesh.frames-base.frames))))
    assert max(position_error,frame_error)<2e-13
    condition=FlightCondition(**plan['condition'])
    g=lifting_geometry(meshes,np.array([1.,0.,0.])); n=len(g['hv'])
    assert n==case['panels']
    folder.mkdir()
    np.savez(folder/'geometry.npz',**g)
    print(f'Solving {case_id}: alpha1 speed240; original Mach guard.',flush=True)
    solve_start=time.monotonic(); accepted=None
    try:
        accepted=evaluate_aerodynamics(model,condition,meshes)
    except AnalysisError as exc:
        assert exc.details and exc.details['kind']=='section_normal_mach',str(exc)
        tb=exc.__traceback__
        while tb and tb.tb_frame.f_code.co_name!='evaluate_aerodynamics': tb=tb.tb_next
        assert tb is not None
        local=tb.tb_frame.f_locals
        gamma,v,cl=[local[k].copy() for k in ('gamma','v','cl')]
        force=local['flift']+local['frate']+local['fprofile']
        details=exc.details; residual=details['circulation_residual']
        coefficients={k:details['surface_force_diagnostic']['terms']['sum'][k] for k in ('CL','CD')}
        write(folder/'rejected.json',dict(message=str(exc),details=details))
        status='REJECTED_STATE_DIAGNOSTIC'
    else:
        write(folder/'accepted.json',accepted)
        gamma,v,cl,force=[np.array([s[k] for s in accepted['strips']])
                         for k in ('circulation','relative_velocity','cl','force')]
        residual=accepted['residual']
        coefficients={k:accepted[k] for k in ('CL','CD','CDi','Cm_origin','efficiency')}
        status='COMPUTED_ALTERNATIVE_GEOMETRY_NOT_ISAE_PASS'
    solve_seconds=time.monotonic()-solve_start
    assert residual<1e-8
    span=np.concatenate([m.frames[...,1] for m in meshes])
    beam=np.concatenate([np.full(len(m.tm),m.beam.index) for m in meshes])
    station=np.concatenate([m.tm for m in meshes])
    sample=lambda name:np.concatenate([m.beam.value(name,m.tm) for m in meshes])
    vp=v-np.sum(v*span,axis=1)[:,None]*span
    mach=np.linalg.norm(vp,axis=1)/340.21
    pg=np.diag([1/np.sqrt(1-condition.mach**2),1.,1.]); direction=np.array([1.,0.,0.])
    field=FactoredInfluence(g['hv'],g['a'],g['b'],direction,pg,0.,GroundPlane(),exclude_bound=np.eye(n,dtype=bool))
    bound=np.einsum('ijk,j->ik',field.bound,gamma)
    wake=np.einsum('ijk,j->ik',field.rays,field.wake_strengths(gamma))
    replay_error=float(np.max(abs(condition.speed*condition.vectors()[0]+bound+wake-v)))
    assert replay_error<3e-8,replay_error
    e,ey,ez=condition.vectors(); scale=.5*1.2256*condition.speed**2*model.reference[0,0]
    for k,axis in [('CL',ez),('CD',e)]:
        scalar=sum(sum(float(f)*float(a) for f,a in zip(row,axis)) for row in force)/scale
        assert abs(scalar-coefficients[k])<2e-13
    trefftz=trefftz_for_meshes(model,replace(condition,alpha=0.,beta=0.),meshes,gamma,1.2256,GroundPlane())
    assert trefftz['available'],trefftz['reason']
    if accepted is not None: assert abs(trefftz['CDi']-accepted['CDi'])<2e-13
    coefficients['CDi']=trefftz['CDi']; coefficients['efficiency']=trefftz['efficiency']
    coefficients.setdefault('Cm_origin',None)
    rejected=int(np.count_nonzero(mach>=1))
    assert (rejected==0)==(accepted is not None)
    margin=np.minimum(sample('CLmax')-cl,cl-sample('CLmin'))/condition.stall_width
    assert margin.min()>0
    worst=int(np.argmax(mach))
    roots=[]
    for owner in (2,3):
        ids=np.flatnonzero(beam==owner)
        i=int(ids[np.argmin(abs(station[ids])-1.2426)])
        # Locate corresponding main-wing endpoint using body y, independent of
        # the translated winglet's parameter and moment reference.
        main=np.flatnonzero(beam==1)
        j=int(main[-1] if owner==2 else main[0]); endpoint='b' if owner==2 else 'a'
        origin=g[endpoint][j]
        winglet_endpoint=g['a' if owner==2 else 'b'][i]
        r=g['hv'][i]-origin; along=float(r@direction)
        distance=float(np.linalg.norm(r-max(along,0.)*direction))
        roots.append(dict(beam=owner,panel=i,t=float(station[i]),normal_mach=float(mach[i]),
            wake_speed=float(np.linalg.norm(wake[i])),bound_speed=float(np.linalg.norm(bound[i])),
            wake_velocity=wake[i].tolist(),bound_velocity=bound[i].tolist(),
            main_wake_distance_m=distance,root_endpoint_delta_m=(winglet_endpoint-origin).tolist(),
            endpoint_exactly_equal=bool(np.array_equal(winglet_endpoint,origin)),
            root_gamma=float(gamma[i]),adjacent_main_gamma=float(gamma[j])))
    np.savez(folder/'state.npz',gamma=gamma,velocity=v,cl=cl,mach=mach,force=force,
             span=span,beam=beam,t=station,bound=bound,wake=wake)
    if case_id=='control-64':
        with np.load(OLD/'state.npz') as old:
            for value,key in [(gamma,'gamma'),(v,'v'),(cl,'cl')]:
                np.testing.assert_array_equal(value,old[key])
    report=dict(observed_utc=datetime.now(timezone.utc).isoformat(),case=case,status=status,
        coefficients=coefficients,reference_error_percent={k:100*(coefficients[k]/target-1) for k,target in plan['reference'].items()},
        maximum_normal_mach=float(mach.max()),rejected_sections=rejected,
        worst=dict(beam=int(beam[worst]),t=float(station[worst]),
            bound_speed=float(np.linalg.norm(bound[worst])),wake_speed=float(np.linalg.norm(wake[worst]))),
        roots=roots,circulation_residual=float(residual),minimum_stall_margin_widths=float(margin.min()),
        rigid_translation_position_error=position_error,frame_error=frame_error,
        flow_replay_error=replay_error,solve_seconds=solve_seconds,total_seconds=time.monotonic()-begin,
        maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        primary_passes_added=0,artifact_sha256={p.name:sha(p) for p in folder.iterdir() if p.is_file()})
    write(folder/'report.json',report); signal.alarm(0)
    print(json.dumps({k:report[k] for k in ('case','status','reference_error_percent','maximum_normal_mach',
        'rejected_sections','worst','solve_seconds','total_seconds','maxrss_kib')}),flush=True)


def verify(out):
    plan=read(out/'plan.json');check(plan['pins'])
    rows=[]
    for name,digest in plan['generated_pins'].items(): assert sha(out/name)==digest,name
    for case in plan['cases']:
        p=out/case['id'];r=read(p/'report.json')
        for name,digest in r['artifact_sha256'].items(): assert sha(p/name)==digest,name
        assert r['case']==case and r['primary_passes_added']==0
        assert r['circulation_residual']<1e-8 and r['minimum_stall_margin_widths']>0
        for key in ('CL','CD','CDi'):
            assert abs(r['reference_error_percent'][key]-100*(r['coefficients'][key]/plan['reference'][key]-1))<1e-12
        a,b=r['roots']
        assert abs(a['normal_mach']-b['normal_mach'])<1e-7
        assert abs(a['wake_speed']-b['wake_speed'])<1e-4
        rows.append(dict(**r,report_sha256=sha(p/'report.json')))
    comparisons=[]
    for v in plan['variants']:
        coarse,fine=[next(r for r in rows if r['case']['id']==f"{v['id']}-{n}") for n in (64,128)]
        comparisons.append(dict(variant=v['id'],peak_mach_ratio=fine['maximum_normal_mach']/coarse['maximum_normal_mach'],
            coefficient_change_percent={k:100*(fine['coefficients'][k]/coarse['coefficients'][k]-1) for k in ('CL','CD','CDi')},
            moment_change=None if any(r['coefficients']['Cm_origin'] is None for r in (coarse,fine)) else
                fine['coefficients']['Cm_origin']-coarse['coefficients']['Cm_origin']))
    assert not (out/'analysis.json').exists()
    write(out/'analysis.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        status='VERIFIED_SENSITIVITY_DIAGNOSTIC_NO_PRIMARY_PASSES',cases=rows,refinement=comparisons,
        primary_passes_added=0,source_plan_sha256=sha(out/'plan.json')))
    print(json.dumps(comparisons),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare',action='store_true');action.add_argument('--case');action.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    if args.prepare: prepare(args.output)
    elif args.verify: verify(args.output)
    else: run(args.output,args.case)
