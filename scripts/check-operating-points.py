"""Retain native operating stacks for a packaged-WASM replay; no native ASWING claim."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.bridge import dispatch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--initialization', choices=['cold', 'previous'], default='cold')
    args = parser.parse_args()
    source = lambda name: (ROOT/'examples'/name).read_text()
    base = dict(action='operating_points', panels=4, condition=dict(speed=30, alpha=0, mach=0))
    requests = [
        dict(base, mode='rigid', source=source('rectangular.asw'), operating_points=dict(points=[
            dict(condition=dict(alpha=-2)), dict(condition=dict(alpha=0)),
            dict(condition=dict(alpha=5)), dict(condition=dict(alpha=5)),
            dict(name='Local Mach rejection', condition=dict(speed=400, alpha=0)),
            dict(name='Recovery after failure', condition=dict(speed=30, alpha=3)),
        ])),
        dict(base, mode='mounted', source=source('flexible.asw'), operating_points=dict(points=[
            dict(condition=dict(alpha=1)), dict(condition=dict(alpha=3)),
        ])),
        dict(base, mode='mounted', source=source('rectangular.asw'),
             numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-steady-coupled-v1'),
             operating_points=dict(points=[dict(condition=dict(alpha=1)), dict(condition=dict(alpha=3))])),
    ]
    cases = []
    for request in requests:
        request['operating_points']['initialization'] = args.initialization
        result = dispatch(request)
        cases.append(dict(request=request, result=result))
    assert [c['result']['converged_points'] for c in cases] == [5, 2, 2]
    assert 'Mach' in cases[0]['result']['points'][4]['error']['message']
    assert cases[0]['result']['points'][5]['converged']
    assert all(p['result']['residual'] < 1e-7 for c in cases for p in c['result']['points'] if p['converged'])
    modules = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'openswing').glob('*.py'))}
    report = dict(scope='OpenSwing native/WASM portability; no ASWING acceptance changes', modules=modules, cases=cases)
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(f'Native {args.initialization} stacks retained: 9 converged points, 1 physical Mach rejection, recovery after failure.')


if __name__ == '__main__':
    main()
