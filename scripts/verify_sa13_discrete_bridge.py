"""Verify saved full JSON results using original ordinates and Decimal integrals.

No producer helper, OpenSwing import, numerical library or fresh solve.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
import math
from pathlib import Path
import resource
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    signal.alarm(25)
    source_path = ROOT/'docs/validation/isae-sa13-sources.json'
    assert sha(source_path) == '439c59ead8599f99417ea53db7d146567cd6f4918e672c339ca0694f76499397'
    source = json.loads(source_path.read_text())
    prior_path = ROOT/'artifacts/isae/sa13-discrete-loads-20261109/analysis.json'
    prior = json.loads(prior_path.read_text())
    for path, expected in prior['sources'].items():
        assert sha(ROOT/path) == expected, path
    modules = {p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    D = lambda x: Decimal.from_float(float(x))
    checks = []
    with localcontext() as ctx:
        ctx.prec = 60
        for case in source['cases'][:3]:
            name = case['name']; path = args.directory/f'{name}.json'
            record = json.loads(path.read_text())
            assert record['modules'] == modules
            assert record['script_sha256'] == sha(ROOT/'scripts/check_sa13_discrete_bridge.py')
            assert record['source_analysis_sha256'] == sha(prior_path)
            for key in ('request', 'response'):
                assert sha(ROOT/record[f'{key}_path']) == record[f'{key}_sha256']
            request = json.loads((ROOT/record['request_path']).read_text())
            result = json.loads((ROOT/record['response_path']).read_text())['result']
            assert result['converged'] and result['residual'] <= 1e-8 and not result['lifting_panels']
            assert request['action'] == 'solve' and request['mode'] == 'rigid'
            assert request['condition'] == dict(speed=1., alpha=case['primary_alpha'], mach=0., freeze_influences=True)
            assert hashlib.sha256(request['source'].encode()).hexdigest() == record['model_sha256']
            outline = [(D(a[0]), (D(a[1])-D(b[1]))/2) for a, b in zip(case['series'][3]['xy'],case['series'][4]['xy'])
                       if None not in a+b and a[1] >= b[1]]
            nodes = request['panels']['beams']['1']['nodes']
            assert list(map(D, nodes)) == [x for x, _ in outline]
            table = request['source'].split('t radius\n')[1].split('\nEnd')[0].strip().splitlines()
            actual_table = [tuple(D(v) for v in line.split()) for line in table]
            expected_table = [row for pair in zip(outline,outline[1:]) for row in pair]
            assert actual_table == expected_table
            assert len(result['strips']) == len(outline)-1 == len(record['rows'])
            diameter = 2*max(r for _, r in outline); qd = diameter/2
            angle = math.radians(case['primary_alpha'])
            k = D(math.sin(angle))*D(math.cos(angle)); pi = D(math.pi)
            force_error = moment_error = station_error = Decimal(0)
            bad_reference_error = Decimal(0)
            total_f = total_m = Decimal(0)
            for i, strip in enumerate(result['strips']):
                (x0,r0),(x1,r1) = outline[i:i+2]
                h = x1-x0; mid = (x0+x1)/2; ref = D(strip['position'][0])
                f, m = D(strip['force'][2]), D(strip['moment'][1])
                assert x0 < ref < x1 and abs(D(strip['length'])-h) < D(2e-14)
                assert abs(ref-D(strip['t'])) < D(2e-14)
                target_x, target = case['series'][2]['xy'][i]
                assert D(target_x) == x0 and target is not None
                # Force and first moment uniquely determine an affine density.
                slope = -12*(m+(mid-ref)*f)/h**3
                recovered = (f/h-slope*h/2)/qd
                native_error = abs(recovered-D(target))
                station_error = max(station_error,native_error)
                assert native_error < D(2e-12), (name,i,native_error)
                assert abs(recovered-D(record['rows'][i]['station_density_from_public_wrench'])) < D(2e-12)
                bad_reference_error = max(bad_reference_error, abs((f/h+6*m/h**2)/qd-D(target)))
                a0,a1 = pi*r0*r0,pi*r1*r1
                vol = pi*h*(r0*r0+r0*r1+r1*r1)/3
                exact_f = k*(a1-a0)
                exact_m = -k*((x1-ref)*a1-(x0-ref)*a0-vol)
                force_error = max(force_error,abs(f-exact_f))
                moment_error = max(moment_error,abs(m-exact_m))
                assert abs(f-exact_f) < D(2e-14) and abs(m-exact_m) < D(2e-14)
                total_f += f; total_m += m-ref*f
            assert abs(total_f-D(result['force'][2])) < D(2e-14)
            assert abs(total_m-D(result['moment'][1])) < D(2e-14)
            assert result['moment_definitions']['reference'] == [0.,0.,0.]
            assert result['body_shoulders'] == []
            assert bad_reference_error > D('.001'), 'Control must expose the moment-reference mismatch.'
            checks.append(dict(case=name, stations=len(record['rows']),
                               maximum_decimal_station_error=str(station_error),
                               maximum_decimal_force_error=str(force_error),
                               maximum_decimal_local_moment_error=str(moment_error),
                               maximum_error_if_moment_reference_ignored=str(bad_reference_error),
                               record_sha256=sha(path)))
    assert sum(c['stations'] for c in checks) == 180
    assert not any(n == 'numpy' or n.startswith('openswing') for n in sys.modules)
    output = dict(observed_utc=datetime.now(timezone.utc).isoformat(), status='VERIFIED_PUBLIC_JSON_WRENCH_AND_NATIVE_STATIONS',
                  checks=checks, verified_stations=180, modules_unchanged=len(modules),
                  original_source_sha256=sha(source_path), verifier_sha256=sha(Path(__file__)),
                  physical_solves=0, browser_or_wasm_runs=0, native_passes_added=0,
                  retained_native_scope=dict(passed=0,total=612,unavailable=136))
    with (args.directory/'verification.json').open('x') as handle:
        json.dump(output,handle,indent=2);handle.write('\n')
    print(json.dumps(output))


if __name__ == '__main__':
    main()
