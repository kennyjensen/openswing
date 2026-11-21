"""Compare Newton assembly paths on a retained 40-step stalled-heave segment."""
import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

import numpy as np
from isae_ua_artifacts import write_trajectory

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/ua-time-source-mechanics-20261102'
PRIOR = ROOT/'artifacts/isae/ua1-stall-20261102-r1'
sys.path.insert(0, str(ROOT))


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['direct','differences'], required=True)
    parser.add_argument('--repeat', type=int, required=True)
    args = parser.parse_args()
    folder = BASE/f'benchmark-{args.mode}-{args.repeat}'
    folder.mkdir()
    current = {str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'openswing').glob('*.py')}
    before = read(BASE/'before/sha256.json')
    changed = [p for p,v in current.items() if v != before[p]]
    assert sorted(changed) == ['openswing/mechanical_tangent.py','openswing/structured_time.py','openswing/time_integration.py']
    saved = read(PRIOR/'n160-part000/checkpoint.json')
    request = read(PRIOR/'n160-part001/request.json')
    assert request['checkpoint'] == saved
    inputs = {str(p.relative_to(ROOT)):digest(p) for p in
        [PRIOR/'n160-part000/checkpoint.json',PRIOR/'n160-part001/request.json',PRIOR/'n160-part001/trajectory.json.gz']}
    plan = dict(mode=args.mode,repeat=args.repeat,source_sha256=current,input_sha256=inputs,
        benchmark_script_sha256=digest(Path(__file__)),physical_difference_limit=1e-8,
        unchanged_equations_and_nonlinear_tolerance=True,registered_pass_count_change=0)
    (folder/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    from openswing.bridge import dispatch
    import openswing.structured_time as assembly
    original = assembly.jacobian
    matrices = []
    def track(*a, **kw):
        kw['direct_mechanics'] = args.mode == 'direct'
        result = original(*a, **kw)
        matrices.append(result[2])
        return result
    assembly.jacobian = track
    start = time.monotonic()
    try:
        raw = dispatch(request)
    finally:
        assembly.jacobian = original
    elapsed = time.monotonic()-start
    write_trajectory(folder/'trajectory.json.gz',raw)
    assert raw['converged'] and raw['accepted_steps'] == 40 and raw['rejected_steps'] == 0
    assert matrices
    assert all((m['mechanical_derivative'] is not None) == (args.mode == 'direct') for m in matrices)
    with gzip.open(PRIOR/'n160-part001/trajectory.json.gz','rt') as stream:
        old = json.load(stream)
    assert len(raw['snapshots']) == len(old['snapshots']) == 41
    # Fixed physical scales avoid magnifying cancellation in zero net moments.
    force_scale = .5*1.225*10**2*200000
    scales = dict(force=force_scale,moment=force_scale*200000,CL=1.,CDp=1.,
        circulation_rate=10.,local_velocity=10.,local_rates=10.,time=1.)
    differences = {}
    for key,scale in scales.items():
        a,b = [np.array([row[key] for row in group['snapshots']]) for group in (raw,old)]
        differences[key] = float(np.max(abs(a-b))/scale)
    gamma = [np.array([[r['circulation'] for r in row['strips']] for row in group['snapshots']]) for group in (raw,old)]
    differences['circulation'] = float(np.max(abs(gamma[0]-gamma[1]))/10.)
    for key in ('position_earth','velocity_origin_body','body_to_earth','rates_body'):
        a,b = [np.array([row['frame'][key] for row in group['snapshots']]) for group in (raw,old)]
        differences['frame/'+key] = float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
    passed = max(differences.values()) < plan['physical_difference_limit']
    assert all(digest(ROOT/name) == value for name,value in {**current,**inputs}.items())
    report = dict(passed=passed,seconds=elapsed,physical_difference_fractions=differences,
        matrices=matrices,jacobian_builds=raw['jacobian_builds'],newton_iterations=raw['newton_iterations'],
        residual=max(s['residual'] for s in raw['snapshots']),accepted_steps=40,rejected_steps=0,
        matrix_residual_evaluations=sum(m['evaluations'] for m in matrices), registered_pass_count_change=0)
    (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'matrices'}),flush=True)
    assert passed


if __name__ == '__main__':
    main()
