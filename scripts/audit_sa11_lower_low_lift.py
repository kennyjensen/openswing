"""Account for equal-lift upper/lower drag from independently checked states."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

from sa11_paper_suite import bounded, write_new

ROOT = Path(__file__).resolve().parents[1]
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
bounded()
folder = Path(sys.argv[1]).resolve()
assessment = read(folder / 'analysis.json')
proof = read(folder / 'verification.json')
assert proof['verified'] and proof['analysis_sha256'] == sha(folder / 'analysis.json')
pins = dict(assessment['pins'])
for name, digest in pins.items():
    assert sha(ROOT / name) == digest, name
for path in (Path(__file__), folder / 'analysis.json', folder / 'verification.json'):
    pins[str(path.relative_to(ROOT))] = sha(path)
rows = []
for label in ('0_70', '0_80'):
    speed = 240. if label == '0_70' else 272.
    comparisons = {}
    for config in ('upper_winglet', 'upper_lower_winglets'):
        check = next(c for c in assessment['checks'] if c['configuration'] == config
            and c['label'] == label and c['kind'] == 'drag_at_equal_lift' and c['x'] == .3)
        curve = next(c for c in assessment['curves'] if c['configuration'] == config and c['label'] == label)
        points = [next(p for p in curve['points'] if p['alpha'] == a) for a in check['bracket_alpha']]
        assert len(points) == 2 and all(p['valid'] for p in points)
        fraction = (.3 - points[0]['CL']) / (points[1]['CL'] - points[0]['CL'])
        assert 0 < fraction < 1
        beam_cd = []
        parts = []
        for point in points:
            path = ROOT / point['source']
            accepted = path.parent / 'accepted.json'
            assert sha(accepted) == pins[str(accepted.relative_to(ROOT))]
            raw = read(accepted)
            alpha = math.radians(point['alpha'])
            qs = .5 * 1.2256 * speed**2 * .9329
            by_beam = {beam: math.fsum(s['force'][0] * math.cos(alpha) + s['force'][2] * math.sin(alpha)
                for s in raw['strips'] if s['beam'] == beam) / qs for beam in range(1, 6)}
            assert abs(math.fsum(by_beam.values()) - point['CD']) < 2e-12
            beam_cd.append(by_beam)
            if config == 'upper_lower_winglets':
                audit = read(path.parent / 'verification.json')
                assert audit['verified'] and audit['report_sha256'] == sha(path)
                parts.append(audit['diagnostic']['drag_parts'])
        interp = lambda values: (1 - fraction) * values[0] + fraction * values[1]
        beams = {str(beam): interp([values[beam] for values in beam_cd]) for beam in range(1, 6)}
        assert abs(math.fsum(beams.values()) - check['actual']) < 2e-12
        comparisons[config] = dict(alpha_bracket=check['bracket_alpha'], fraction=fraction,
            CD=check['actual'], target_CD=check['target'], beam_CD=beams)
        if parts:
            summed = {key: interp([part[key] for part in parts]) for key in parts[0]}
            assert abs(math.fsum(summed.values()) - check['actual']) < 2e-12
            comparisons[config]['independent_drag_parts'] = summed
            comparisons[config]['direct_stall_drag_fraction_of_discrepancy'] = summed['stall_leakage'] / (check['actual'] - check['target'])
    upper, lower = (comparisons[c] for c in ('upper_winglet', 'upper_lower_winglets'))
    groups = {name: math.fsum(lower['beam_CD'][str(beam)] - upper['beam_CD'][str(beam)] for beam in beams)
              for name, beams in [('main_wing', (1,)), ('upper_winglets', (2, 3)), ('lower_winglets', (4, 5))]}
    delta = lower['CD'] - upper['CD']
    assert abs(math.fsum(groups.values()) - delta) < 2e-12
    rows.append(dict(label=label, CL=.3, comparisons=comparisons,
        native_lower_minus_upper_CD=lower['target_CD'] - upper['target_CD'],
        openswing_lower_minus_upper_CD=delta, force_group_contributions_to_increment=groups))
result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), verified=True, physical_calls=0,
    rows=rows, pins=pins,
    qualification='Same frozen influences and reference dimensions; compare each model at its own interpolated alpha. Models retain their different CLmax inputs. Component accounting is not a controlled removal experiment, does not isolate indirect stall effects, and has no native per-beam reference. No new primary checks or passes.')
write_new(folder / 'low-lift-diagnostics.json', result)
print(json.dumps(rows, indent=2))
