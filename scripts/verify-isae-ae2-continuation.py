"""Bounded AE-2 ordered-speed diagnostic using the literal registered inputs.

The original driver builds a stack before XX; its internal initialization is
unknown. This explicitly tests previous-point continuation, not native replay.
Run one mesh/segment at a time. Existing attempts are never overwritten.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'AE-2-m15_02-b05-ias'


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def pin(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def prepare(stage, tolerance=None):
    from isae_suite_aeroelastic import plan as registered_plan
    require(not stage.exists(), 'Use a new evidence directory.')
    jobs = [j for j in registered_plan(ROOT) if j['id'].startswith(PREFIX)]
    require(len(jobs) == 42, 'Expected twenty positive speeds plus the missing zero row on each mesh.')
    require(all(j['condition']['freeze_influences'] is True and j['condition']['mach'] == 0
                and j['condition']['beta'] == 5 and j['condition']['alpha'] == 0 for j in jobs),
            'Registered setup changed.')
    sources = {p['path']:p for job in jobs for p in job['source_pins']+job['kernel_pins']}
    sources[str(Path(__file__).resolve())] = pin(__file__)
    cases = []
    for nominal in (80, 160):
        for speed in range(21):
            job, = [j for j in jobs if j['nominal'] == nominal and j['condition']['speed'] == speed]
            cases.append(dict(name=f'ordered-m{nominal}-v{speed:02d}', route='ordered', job=job,
                predecessor=None if speed < 2 else f'ordered-m{nominal}-v{speed-1:02d}'))
        for speed in (17, 20):
            job, = [j for j in jobs if j['nominal'] == nominal and j['condition']['speed'] == speed]
            cases.append(dict(name=f'cold-m{nominal}-v{speed:02d}', route='cold-control', job=job, predecessor=None))
    for source in sources.values():
        require(pin(source['path']) == source, 'Source changed during preparation.')
        path = Path(source['path'])
        if path.suffix == '.py':
            target = stage/'frozen-code'/path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    if tolerance is not None:
        require(0 < tolerance <= 1e-8, 'Only an explicitly tighter residual is allowed in this diagnostic.')
    write(stage/'plan.json', dict(status='PREPARED', cases=cases, pins=list(sources.values()), solver_tolerance=tolerance,
        source='Exact original negative-coupling layup and beta5 driver/output pairing from the registered adapter.',
        initial_state_policy='IAS1 cold; IAS2..20 use the immediately previous converged state with no field edits.',
        initial_zero_policy='Original NaNs remain unsupported; no zero-speed physical solve or invented target.',
        controls='Separate fresh cold states at IAS17 and20 on both meshes; no reference-guided seed selection.',
        limitations=['Historical XX initialization/iteration history is unknown.',
                     'Local continuation does not establish stability, uniqueness or follow a fold.',
                     'No model, default, reference or acceptance changes.']))
    for case in cases:
        if case['job']['execution_route'] == 'unsupported':
            write(stage/'cases'/case['name']/'report.json', dict(name=case['name'], status='unsupported',
                physical_calls=0, reason=case['job']['blocked_reason'], reference_checks=[dict(o, predicted=None, passed=False)
                    for o in case['job']['observations']]))
    print(json.dumps(dict(status='PREPARED', positive_solves=44, unsupported_records=2)), flush=True)


def run_case(stage, name):
    plan = read(stage/'plan.json')
    case, = [c for c in plan['cases'] if c['name'] == name]
    job = case['job']; folder = stage/'cases'/name
    require(job['execution_route'] == 'worker', 'The zero-speed reference is unavailable.')
    require(not (folder/'started.json').exists(), 'This attempt already started; preserve it without retrying.')
    require(all(pin(p['path']) == p for p in plan['pins']), 'Pinned source changed.')
    request = dict(action='solve', mode='mounted', source=Path(job['source']).read_text(), panels=job['panels'],
        condition=deepcopy(job['condition']), numerics=job['settings'], operating_constraints=[],
        strut_mode='bilateral', controller=None)
    if plan.get('solver_tolerance') is not None:
        request['tolerance'] = plan['solver_tolerance']
    predecessor = None
    if case['predecessor']:
        prior = stage/'cases'/case['predecessor']
        previous = read(prior/'report.json')
        require(previous['status'] == 'computed' and pin(prior/'result.json') == previous['result'],
                'Preceding state is unavailable, failed or changed; no substitution permitted.')
        request['initial_state'] = read(prior/'result.json')['equilibrium_state']
        predecessor = pin(prior/'report.json')
    write(folder/'request.json', request)
    write(folder/'started.json', dict(name=name, time=time.time(), predecessor=predecessor, request=pin(folder/'request.json')))
    sys.path.insert(0, str(ROOT))
    import numpy as np
    from openswing.aero import FlightCondition
    from openswing.asw import parse_asw
    from openswing.bridge import dispatch
    from openswing.source_coupled import SourceCoupledNetwork
    from openswing.equilibrium_state import identity, restore
    from openswing.network import network_snapshot
    checks = []
    def check(label, value, **details):
        checks.append(dict(name=label, passed=bool(value), **details))
    began = time.monotonic()
    last_progress = [0.]
    def progress(label, index, total):
        now = time.monotonic()
        if now-last_progress[0] >= 1.:
            write(folder/'progress.json', dict(stage=label, index=float(index), total=float(total), seconds=now-began))
            last_progress[0] = now
    try:
        result = dispatch(request, progress=progress)
        solve_seconds = time.monotonic()-began
        write(folder/'result.json', result)
        condition = deepcopy(job['condition'])
        for key in ('controls', 'powers'):
            condition[key] = {int(k):v for k,v in condition[key].items()}
        model = parse_asw(request['source'], beam_interpolation=job['settings']['beam_interpolation'])
        net = SourceCoupledNetwork(model, job['panels'], FlightCondition(**condition), None, [])
        check('identity', identity(net) == result['equilibrium_state']['identity'])
        x = restore(net, result['equilibrium_state'])
        check('restore_without_residual', net.nfev == 0)
        residual, data = net.residual(x, detail=True)
        fresh = network_snapshot(net, residual, data)
        maximum = float(np.max(abs(residual)))
        check('one_fresh_full_residual', net.nfev == 1 and maximum <= job['numerical_gates']['residual'], maximum=maximum)
        check('declared_mesh', net.ne == job['expected_elements'] and net.nn == net.ne+1)
        check('source_operator', result['numerics'] == job['settings'] and result['structural_operator'] == job['settings']['structural_operator'])
        check('unchanged_predecessor', predecessor is None or pin(predecessor['path']) == predecessor)
        for kind in ('force','moment'):
            applied = np.asarray(result['applied_'+kind]); support = np.asarray(result['support_'+kind])
            scale = float(np.linalg.norm(applied)+np.linalg.norm(support)); defect = float(np.linalg.norm(applied+support))
            check(kind+'_balance', defect <= job['numerical_gates']['relative_balance']*scale, defect=defect, scale=scale)
        for c in net.constraints:
            if c['kind'] == 'ground':
                check('clamp_position', np.max(abs(data['r'][c['a']]-net.rj[c['a']])) <= job['numerical_gates']['clamp'])
                check('clamp_frame', np.max(abs(data['Q'][c['a']]-np.eye(3))) <= job['numerical_gates']['clamp'])
        def values(snapshot):
            sensor = snapshot['sensors'][0]
            return dict(RY_m=sensor['position_earth'][1], Psi_deg=sensor['heading'],
                sensor_V_m_s=sensor['speed'], sensor_beta_deg=sensor['beta'])
        predicted, recovered = values(result), values(fresh)
        check('restored_sensor_parity', all(abs(predicted[k]-recovered[k]) <= job['numerical_gates']['restored_parity']*(1+abs(predicted[k])) for k in predicted))
        sensor = result['sensors'][0]; flow = np.asarray(sensor['air_velocity_sensor']); speed = float(np.linalg.norm(flow))
        check('sensor_speed', abs(speed-predicted['sensor_V_m_s']) <= 1e-12)
        check('sensor_beta', abs(float(np.rad2deg(np.arcsin(-flow[1]/speed)))-predicted['sensor_beta_deg']) <= 1e-10)
        check('unchanged_sources', all(pin(p['path']) == p for p in plan['pins']))
        write(folder/'restored-result.json', fresh)
        reference = [dict(o, predicted=predicted[o['name']],
            passed=abs(predicted[o['name']]-o['expected']) <= o['tolerance'],
            signed_relative_error_percent=100*(predicted[o['name']]-o['expected'])/abs(o['expected']) if o['expected'] else None)
            for o in job['observations']]
        report = dict(name=name, status='computed' if all(c['passed'] for c in checks) else 'physical_check_failure',
            seconds=time.monotonic()-began, solve_seconds=solve_seconds, checks=checks, values=predicted,
            reference_checks=reference, predecessor=predecessor, result=pin(folder/'result.json'),
            restored_result=pin(folder/'restored-result.json'), request=pin(folder/'request.json'))
        write(folder/'report.json', report)
        require(report['status'] == 'computed', 'Physical checks failed.')
    except Exception as exc:
        if not (folder/'report.json').exists():
            write(folder/'report.json', dict(name=name,status='numerical_failure',seconds=time.monotonic()-began,
                error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()), checks=checks,
                predecessor=predecessor, reference_checks=[dict(o,predicted=None,passed=False) for o in job['observations']]))
        raise
    print(json.dumps(dict(name=name, status=report['status'], seconds=report['seconds'], values=predicted)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','run'))
    parser.add_argument('stage', type=Path)
    parser.add_argument('--case')
    parser.add_argument('--tolerance', type=float, help='Prepare an explicit tighter solve residual; physical/reference gates stay unchanged.')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.stage.resolve(), args.tolerance)
    else:
        require(args.case is not None, 'Specify one exact case.')
        run_case(args.stage.resolve(), args.case)


if __name__ == '__main__':
    main()
