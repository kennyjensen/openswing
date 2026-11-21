"""Fixed original-extension drag budgets on the new minimum-spacing meshes.

Twenty prescribed calls: sixteen primary-setting replays plus four separately
labelled frozen-influence controls. Each invocation runs one bounded solve.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / 'artifacts/isae/sa11-original-minimum-spacing-20261108'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
utc = lambda: datetime.now(timezone.utc).isoformat()


def write(path, value):
    text = json.dumps(value, indent=2, allow_nan=False)+'\n'
    with path.open('x') as stream:
        stream.write(text)


def bounded():
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        assert os.environ.get(key) == '1'
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    signal.alarm(25)


def check(pins):
    for name, digest in pins.items():
        assert sha(ROOT/name) == digest, name


def prepare(out, reuse=None):
    bounded()
    assert not out.exists()
    parent = read(PARENT/'plan.json')
    check(parent['source_sha256'])
    verification = read(PARENT/'verification.json')
    assert verification['verified'] and verification['analysis_sha256'] == sha(PARENT/'analysis.json')
    pins = dict(parent['source_sha256'])
    catalog = read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for item in catalog['files']:
        for kind, hashkey in [('pdf', 'sha256'), ('text', 'text_sha256')]:
            path = ROOT/item['local_'+kind]
            assert sha(path) == item[hashkey]
            pins[str(path.relative_to(ROOT))] = item[hashkey]
    cases = []
    for index, job in enumerate(parent['jobs']):
        s = job['settings']
        if not (job['variant'] == 'wing_extension' and job['mach_label'] in ('0_70', '0_80')
                and s['alpha'] in (0., 1., 3., 5.)):
            continue
        path = PARENT/'jobs'/f'{index:04d}'/'result.json'
        previous = read(path)
        assert previous['strict']['status'] == 'computed'
        pins[str(path.relative_to(ROOT))] = sha(path)
        for frozen in ([False, True] if s['panels'] == 64 and s['alpha'] in (1., 3.) else [False]):
            cases.append(dict(id=f"m{job['mach_label']}-a{int(s['alpha'])}-n{s['panels']}-{'frozen' if frozen else 'current'}",
                original_job=job, original_result=str(path.relative_to(ROOT)),
                mesh=parent['meshes'][job['model_path']][str(s['panels'])], freeze_influences=frozen))
    assert len(cases) == 20
    recovered = {}
    if reuse is not None:
        prior = read(reuse/'plan.json')
        assert prior['cases'] == cases
        for name, digest in prior['pins'].items():
            source = reuse/'driver-used.py' if ROOT/name == Path(__file__).resolve() else ROOT/name
            assert sha(source) == digest, name
        # The first process is terminal: all physics assertions and field saves
        # completed before a NumPy-integer JSON recording error. Reuse that
        # accepted solution instead of repeating a completed physical call.
        record = read(reuse/'recording-interruption.json')
        assert record['terminal'] is True and record['case_id'] == cases[0]['id']
        for p in (reuse/'plan.json', reuse/'driver-used.py', reuse/'recording-interruption.json',
                  reuse/cases[0]['id']/'accepted.json', reuse/cases[0]['id']/'fields.npz'):
            pins[str(p.relative_to(ROOT))] = sha(p)
        recovered[cases[0]['id']] = str((reuse/cases[0]['id']/'accepted.json').relative_to(ROOT))
    for p in (Path(__file__), PARENT/'plan.json', PARENT/'analysis.json', PARENT/'verification.json'):
        pins[str(p.relative_to(ROOT))] = sha(p)
    out.mkdir(parents=True)
    write(out/'plan.json', dict(observed_utc=utc(), cases=cases, pins=pins, recovered_accepted=recovered,
        minimum_spacing=parent['minimum_spacing'],
        previous_goal_turn='Progress: original SA-11 rerun gained897 checks; 322/328 executable states complete; independent audit passed and primary progress updated to1060/9184.',
        protocol='Original extension, fixed minimum spacing, alpha0/1/3/5 at240/272m/s on original cosine64/128 requests. Sixteen exact primary-setting replays. Four frozen controls atalpha1/3, nominal64, two speeds; all other settings fixed. No fits or modified force laws.',
        interpretation='Reference CD-CDi is a total-minus-Trefftz remainder, not an independently measured native profile-drag coefficient. Algebraic drag budgets do not authorize replacing near-field drag by Trefftz.',
        primary_passes_added=0, limits='BLAS1;512MiB address space;15CPU/25wall seconds;one foreground solve per invocation.'))
    (out/'driver-used.py').write_text(Path(__file__).read_text())
    signal.alarm(0)
    print(json.dumps(dict(prepared=True, cases=len(cases))), flush=True)


def run(out, index):
    bounded()
    started = time.monotonic()
    plan = read(out/'plan.json'); check(plan['pins'])
    case = plan['cases'][index]; folder = out/case['id']; assert not folder.exists()
    import numpy as np
    sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.aero import FlightCondition, evaluate_aerodynamics
    from openswing.frozen_influence import lifting_geometry
    from openswing.factored_influence import FactoredInfluence
    from openswing.ground import GroundPlane
    model = parse_asw((ROOT/case['original_job']['model_path']).read_text(), beam_interpolation='natural-v1')
    s = case['original_job']['settings']
    settings = {k:s[k] for k in ('speed','alpha','beta','density','mach','freeze_influences','stall',
        'stall_factor','stall_width','wake_core_ratio','aero_lag','body_added_mass_factor')}
    settings['freeze_influences'] = case['freeze_influences']
    condition = FlightCondition(**settings)
    meshes = model_meshes(model, case['mesh'])
    assert len(meshes) == 1 and meshes[0].beam.lifting and meshes[0].beam.physical_index == 1
    assert not model.diagnostics and min(meshes[0].length) >= plan['minimum_spacing']-1e-12
    folder.mkdir()
    clock = time.monotonic()
    recovered = plan['recovered_accepted'].get(case['id'])
    if recovered:
        result = read(ROOT/recovered)
        solve_seconds = None
    else:
        result = evaluate_aerodynamics(model, condition, meshes, circulation_method=s['circulation_method'])
        solve_seconds = time.monotonic()-clock
    write(folder/'accepted.json', result)
    assert result['converged'] and result['residual'] < 1e-8
    names = ('lift','drag','CL','CD','CDi','Cm','efficiency')
    actual = {name:result['Cm_origin' if name == 'Cm' else name] for name in names[2:]}
    e, _, ez = condition.vectors()
    actual.update(lift=float(np.dot(result['force'],ez)), drag=float(np.dot(result['force'],e)))
    old = read(ROOT/case['original_result'])['strict']['result']['predicted']
    replay = max(abs(actual[k]-old[k])/max(1.,abs(old[k])) for k in names)
    if not case['freeze_influences']:
        assert replay < 2e-12, replay
    span = meshes[0].frames[...,1]; normal = meshes[0].frames[...,2]; chord_axis = meshes[0].frames[...,0]
    sample = lambda name: meshes[0].beam.value(name,meshes[0].tm)
    alpha0 = np.deg2rad(sample('alpha'))
    tangency_normal = np.sin(alpha0)[:,None]*chord_axis+np.cos(alpha0)[:,None]*normal
    wind = np.array([1.,0.,0.]) if case['freeze_influences'] else e
    g = lifting_geometry(meshes,wind)
    pg = np.eye(3)+(1/np.sqrt(1-result['mach']**2)-1)*np.outer(wind,wind)
    gamma = np.array([row['circulation'] for row in result['strips']])
    velocity = np.array([row['relative_velocity'] for row in result['strips']])
    N = len(gamma)
    hv = FactoredInfluence(g['hv'],g['a'],g['b'],wind,pg,0.,GroundPlane(),exclude_bound=np.eye(N,dtype=bool))
    cp = FactoredInfluence(g['cp'],g['a'],g['b'],wind,pg,0.,GroundPlane())
    bound = np.einsum('ijk,j->ik',hv.bound,gamma)
    wake = np.einsum('ijk,j->ik',hv.rays,hv.wake_strengths(gamma))
    freestream = condition.speed*e
    velocity_error = float(np.max(abs(velocity-(freestream+bound+wake))))
    assert velocity_error < 2e-10
    cp_velocity = freestream+cp.apply(gamma)
    tangency = np.einsum('ij,ij->i',cp_velocity,tangency_normal)
    perp = velocity-np.einsum('ij,ij->i',velocity,span)[:,None]*span
    speed = np.linalg.norm(velocity,axis=1); vp = np.linalg.norm(perp,axis=1)
    rho = condition.density; ds = g['ds']; chord = g['chord']
    parts = dict(vortex=rho*gamma[:,None]*np.cross(velocity,span)*ds[:,None],
        friction=.5*rho*speed[:,None]*velocity*(chord*sample('Cdf')*ds)[:,None],
        pressure=.5*rho*vp[:,None]*perp*(chord*sample('Cdp')*ds)[:,None],
        leakage=2*rho*perp/vp[:,None]*(tangency**2*chord*ds)[:,None])
    strip_force = np.array([row['force'] for row in result['strips']])
    force_error = float(np.max(abs(strip_force-sum(parts.values()))))
    assert force_error < 2e-8
    qS=.5*rho*condition.speed**2*model.reference[0,0]
    cds = {k:float(np.sum(v@e)/qS) for k,v in parts.items()}
    assert abs(cds['vortex']-result['CDi_near']) < 2e-12
    assert abs(sum(cds[k] for k in ('friction','pressure','leakage'))-result['CDp']) < 2e-12
    assert abs(sum(cds.values())-result['CD']) < 2e-12
    assert all(result[k] == 0 for k in ('CDbody','CDam','CDeng','CDrate'))
    reference={k:case['original_job']['reference_row']['fields'][k]['value'] for k in names}
    budget=dict(near_minus_trefftz=result['CDi_near']-result['CDi'],
        trefftz_error=result['CDi']-reference['CDi'],
        profile_minus_reference_remainder=result['CDp']-(reference['CD']-reference['CDi']))
    assert abs(sum(budget.values())-(result['CD']-reference['CD'])) < 2e-12
    cl=np.array([r['cl'] for r in result['strips']])
    stall_margin=float(np.min(np.minimum(sample('CLmax')-cl,cl-sample('CLmin')))/condition.stall_width)
    by_region={}
    for label,mask in [('main',abs(meshes[0].tm)<=1.2426+1e-12),('extension',abs(meshes[0].tm)>1.2426+1e-12)]:
        by_region[label]=dict(intervals=int(mask.sum()),**{k:float(np.sum(v[mask]@e)/qS) for k,v in parts.items()})
    np.savez(folder/'fields.npz',**g,span=span,normal=tangency_normal,gamma=gamma,velocity=velocity,
        cp_velocity=cp_velocity,bound=bound,wake=wake,wind=wind,pg=pg,cdf=sample('Cdf'),cdp=sample('Cdp'),
        t=meshes[0].tm,**{'force_'+k:v for k,v in parts.items()})
    report=dict(id=case['id'],observed_utc=utc(),settings=settings,actual=actual,reference=reference,
        relative_percent_errors={k:100*(actual[k]-reference[k])/abs(reference[k]) for k in names},
        passing=int(sum(abs(actual[k]-reference[k])<=.05*abs(reference[k]) for k in names)),required=7,
        drag_components=cds,reference_total_minus_trefftz=reference['CD']-reference['CDi'],
        budget=budget,regions=by_region,CDi_near=result['CDi_near'],CDp=result['CDp'],
        minimum_stall_margin_widths=stall_margin,maximum_normal_mach=max(r['normal_mach'] for r in result['strips']),
        residual=result['residual'],primary_replay_scaled_difference=replay if not case['freeze_influences'] else None,
        velocity_reconstruction_error=velocity_error,strip_force_reconstruction_error=force_error,
        intervals=N,solve_seconds=solve_seconds,seconds=time.monotonic()-started,
        recovered_accepted=recovered,physical_calls=0 if recovered else 1,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=sha(out/'plan.json'),artifacts={p.name:sha(p) for p in folder.iterdir()})
    write(folder/'report.json',report); signal.alarm(0)
    print(json.dumps({k:report[k] for k in ('id','passing','drag_components','budget','minimum_stall_margin_widths','seconds')}),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('action',choices=('prepare','run'));parser.add_argument('--index',type=int)
    parser.add_argument('--reuse',type=Path)
    args=parser.parse_args()
    if args.action == 'prepare':prepare(args.output.resolve(),args.reuse.resolve() if args.reuse else None)
    else:run(args.output.resolve(),args.index)
