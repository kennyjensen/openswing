"""Independent scalar/Decimal audit of the saved paper-focused SA-11 score."""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import resource
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
signal.alarm(25)
folder = Path(sys.argv[1]).resolve()
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
result = read(folder / 'analysis.json')
for path, digest in result['pins'].items():
    assert sha(ROOT / path) == digest, path

maximum_force_error = 0.
for curve in result['curves']:
    speed = 240. if curve['label'] == '0_70' else 272.
    for point in curve['points']:
        row = read(ROOT / point['source'])
        if not point['valid']:
            assert point['CL'] is point['CD'] is None
            continue
        if 'strict' in row:
            raw = row['strict']['result']
            force = raw['force']
            assert row['strict']['numerical_pass'] and raw['residual'] < 1e-8
        else:
            raw = read((ROOT / point['source']).parent / 'accepted.json')
            assert raw['converged'] and raw['residual'] < 1e-8
            assert max(p['normal_mach'] for p in raw['strips']) < 1
            force = [math.fsum(p['force'][i] for p in raw['strips']) for i in range(3)]
        alpha = math.radians(point['alpha'])
        qs = .5 * 1.2256 * speed**2 * .9329
        cl = (force[2]*math.cos(alpha)-force[0]*math.sin(alpha)) / qs
        cd = (force[0]*math.cos(alpha)+force[2]*math.sin(alpha)) / qs
        maximum_force_error = max(maximum_force_error, abs(cl-point['CL']), abs(cd-point['CD']))
assert maximum_force_error < 3e-12


def decimal_value(points, x, xkey, ykey, bracket):
    by_alpha = {p['alpha']:p for p in points}
    rows = [by_alpha[alpha] for alpha in bracket]
    assert all(r['valid'] for r in rows)
    if len(rows) == 1:
        assert abs(rows[0][xkey]-x) < 1e-12
        return Decimal(str(rows[0][ykey]))
    assert len(rows) == 2 and 0 < rows[1]['alpha']-rows[0]['alpha'] <= .25+1e-12
    a, b = rows
    assert a[xkey] < x < b[xkey]
    d = lambda v: Decimal(str(v))
    return d(a[ykey]) + (d(x)-d(a[xkey]))*(d(b[ykey])-d(a[ykey]))/(d(b[xkey])-d(a[xkey]))


keys = set()
maximum_interpolation_error = 0.
for check in result['checks']:
    key = (check['configuration'], check['label'], check['kind'], check['x'])
    assert key not in keys
    keys.add(key)
    curve = next(c for c in result['curves'] if c['configuration'] == key[0] and c['label'] == key[1])
    xkey, ykey = ('alpha', 'CL') if check['kind'] == 'lift' else ('CL', 'CD')
    target = decimal_value(curve['reference'], check['x'], xkey, ykey, check['reference_bracket_alpha'])
    maximum_interpolation_error = max(maximum_interpolation_error, abs(float(target)-check['target']))
    if check['actual'] is None:
        assert check['status'] in ('unavailable', 'rejected') and check['error_percent'] is None
        # Independently ensure no valid consecutive quarter-degree bracket exists.
        ordered = sorted(curve['points'], key=lambda p:p['alpha'])
        assert not any(p['valid'] and abs(p[xkey]-check['x'])<1e-12 for p in ordered)
        assert not any(a['valid'] and b['valid'] and b['alpha']-a['alpha']<=.25+1e-12
                       and a[xkey]<check['x']<b[xkey] for a,b in zip(ordered,ordered[1:]))
        continue
    actual = decimal_value(curve['points'], check['x'], xkey, ykey, check['bracket_alpha'])
    maximum_interpolation_error = max(maximum_interpolation_error, abs(float(actual)-check['actual']))
    error = 100*(actual-target)/abs(target)
    assert abs(float(error)-check['error_percent']) < 2e-10
    assert check['status'] == ('pass' if abs(error)<=5 else 'mismatch')
assert maximum_interpolation_error < 2e-12
spec = result['protocol']
expected = {(c['id'], label, kind, x) for c in spec['configurations'] for label in spec['mach_labels']
            for kind, xs in [('lift',spec['alpha_degrees']),('drag_at_equal_lift',spec['matched_CL'])] for x in xs}
assert keys == expected and len(keys) == result['required'] == 48
assert dict(Counter(c['status'] for c in result['checks'])) == result['counts']
assert sum(result['counts'].values()) == 48
for group in result['groups']:
    rows = [c for c in result['checks'] if c['configuration'] == group['configuration']]
    assert len(rows) == group['required'] == 12
    assert dict(Counter(c['status'] for c in rows)) == group['counts']
assert len(result['drag_increments']) == 18
for increment in result['drag_increments']:
    values = {c['configuration']:c for c in result['checks'] if c['kind']=='drag_at_equal_lift'
              and c['label']==increment['label'] and c['x']==increment['CL']}
    base, tip = values['wing_alone'], values[increment['configuration']]
    assert increment['target_delta_CD'] == tip['target']-base['target']
    if tip['actual'] is not None and base['actual'] is not None:
        assert increment['actual_delta_CD'] == tip['actual']-base['actual']
    if not increment['matched_influence_convention']:
        assert increment['comparable_delta_CD'] is None
    assert not increment['counted_in_primary']
verification = dict(verified_utc=datetime.now(timezone.utc).isoformat(), verified=True,
    required=48, counts=result['counts'], source_pins_verified=len(result['pins']),
    maximum_independent_force_error=maximum_force_error,
    maximum_decimal_interpolation_error=maximum_interpolation_error,
    all_configurations_retained=True, missing_targets_still_required=True,
    physical_calls=0, analysis_sha256=sha(folder/'analysis.json'), checker_sha256=sha(Path(__file__)))
with (folder/'verification.json').open('x') as stream:
    json.dump(verification, stream, indent=2, allow_nan=False)
    stream.write('\n')
signal.alarm(0)
print(json.dumps(verification, indent=2))
