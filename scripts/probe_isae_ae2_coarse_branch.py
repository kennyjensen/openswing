"""AE-2 nominal-80 branch check from an already verified nominal-80 state.

Repeat the original 1-degree, IAS14 control before changing speed/incidence.
No cross-mesh interpolation or identity substitution is used. Subsequent
deflection-controlled states retain all physical and augmented rank checks.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import probe_isae_ae2_deflection_branch as branch
from scripts.probe_isae_ae2_deflection_trace import sensor_y
from scripts.probe_isae_ae2_cold_trace import read, write, pin


def prepare(out, seed, speed, target):
    assert not out.exists()
    paths = [Path(__file__), ROOT / 'scripts/probe_isae_ae2_deflection_branch.py',
        ROOT / 'scripts/probe_isae_ae2_deflection_trace.py',
        ROOT / 'scripts/probe_isae_ae2_stalled_tangent.py',
        ROOT / 'scripts/probe_isae_ae2_centered_incidence.py']
    control = seed is None
    if control:
        from scripts.execute_isae_ae2_staged import verify_saved
        snapshot = ROOT / 'artifacts/isae/ae2-beta1-sweeps-current-20261110/snapshot-0048'
        entry = next(j for j in read(snapshot / 'report.json')['jobs']
            if j['id'] == 'AE-2-m15_02-b01-ias014-m80')
        job = {k: v for k, v in entry.items() if k != 'result'}
        result = entry['result']
        assert result['status'] == 'computed' and result['numerical_pass']
        verified = verify_saved(job, result)
        paths += [Path(p['path']) for p in verified]
        paths += [Path(p['path']) for p in job['source_pins'] + job['kernel_pins']]
        paths += [snapshot / 'plan.json', snapshot / 'report.json',
            ROOT / 'scripts/execute_isae_ae2_staged.py']
        seed = Path(result['artifact_directory']) / 'cases/m80'
        request = read(seed / 'request.json')
        saved = read(seed / 'result.json')
        assert request['condition']['speed'] == 14 and request['condition']['beta'] == 1
        speed = 14.
        target = saved['sensors'][0]['position_earth'][1]
    else:
        old = branch.base.checked(seed)
        branch.base.receipt(seed, 'verify')
        report = read(seed / 'report.json')
        assert report['status'] == 'VERIFIED_WARM_EQUILIBRIUM'
        assert report['result'] == pin(seed / 'result.json')
        assert all(c['passed'] for c in report['checks'])
        request = read(seed / 'request.json')
        saved = read(seed / 'result.json')
        paths += [Path(p['path']) for p in old['pins']]
        paths += [seed / f for f in ('plan.json', 'verify/terminal.json', 'verify/sources-verified.json')]
    assert saved['converged'] and saved['residual'] <= 1e-12
    paths += [seed / f for f in ('request.json', 'result.json', 'report.json')]
    catalog = ROOT / 'docs/validation/aswing-authoritative-sources.json'
    paths.append(catalog)
    for reference in read(catalog)['files']:
        if reference['id'] in ('isae-part-4', 'drela-steady'):
            for kind, checksum in [('pdf', 'sha256'), ('text', 'text_sha256')]:
                path = ROOT / reference['local_' + kind]
                assert pin(path)['sha256'] == reference[checksum]
                paths.append(path)
    request = deepcopy(request)
    request.update(initial_state=saved['equilibrium_state'], tolerance=1e-12)
    request['condition']['speed'] = speed
    write(out / 'initial-request.json', request)
    paths.append(out / 'initial-request.json')
    write(out / 'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        method=__doc__, seed=str(seed), seed_result=str(seed / 'result.json'),
        original_control=control, target_sensor_Y_m=target, base_request=request,
        physical_residual_gate=1e-12, expected_elements=81,
        pins=[pin(p) for p in sorted(set(paths))], limits=branch.base.LIMITS,
        phases=['solve', 'tangent', 'verify'], geometry_difference_order=4,
        geometry_difference_step=1e-6, beta_difference_step_deg=1e-4,
        sensor_difference_step=1e-5, maximum_iterations=8, maximum_halvings=12,
        primary_votes_added=0, qualifications=[
            'The control repeats an original verified current-kernel nominal80 result at its exact condition.',
            'The original cold execution and native comparison are not replaced or recounted.',
            'All continuation seeds have the same nominal80 mesh and physical identity; no resampling is used.',
            'Sensor targets select diagnostic states only; no missing native row is interpolated.',
            'The existing centered diagnostic assembles every physical and augmented matrix column.']))
    print(dict(prepared=True, original_control=control, speed=speed, target_Y=target), flush=True)


def verify(out, plan):
    original = branch.physical_checks.verify

    def check(parent, specification, case):
        if plan['original_control']:
            case = dict(case, predecessor=None)
        return original(parent, specification, case)

    branch.physical_checks.verify = check
    try:
        branch.verify(out, plan)
    finally:
        branch.physical_checks.verify = original


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'launch'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=Path)
    parser.add_argument('--speed', type=float)
    parser.add_argument('--target', type=float)
    parser.add_argument('--phase', choices=['solve', 'tangent', 'verify'])
    args = parser.parse_args()
    branch.sensor_y = sensor_y
    if args.action == 'prepare':
        prepare(args.output.resolve(), None if args.seed is None else args.seed.resolve(), args.speed, args.target)
    else:
        branch.base.solve = branch.solve
        branch.base.tangent = branch.tangent
        branch.base.verify = verify
        branch.base.launch(args.output.resolve(), args.phase)
