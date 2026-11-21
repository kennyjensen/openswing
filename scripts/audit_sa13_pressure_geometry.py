"""Identify the exact radius-slope expression in the archived SA-13 red curve.

This is a source-data identity, not a pressure model or an ASWING parity pass.
The observed additive offset is retained explicitly, never fitted into physics.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'docs/validation/isae-sa13-sources.json'
SOURCE_SHA = '439c59ead8599f99417ea53db7d146567cd6f4918e672c339ca0694f76499397'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    assert sha(ROOT/SOURCE) == SOURCE_SHA
    source = json.loads((ROOT/SOURCE).read_text())
    case = next(c for c in source['cases'] if c['name'] == 'pressure')
    figure = Path('reference/isae-validation')/source['revision']/case['path']
    assert sha(ROOT/figure) == case['sha256']
    pins = {SOURCE: SOURCE_SHA, figure.as_posix(): case['sha256'],
            'scripts/audit_sa13_pressure_geometry.py': sha(Path(__file__))}
    catalog_name = 'docs/validation/aswing-authoritative-sources.json'
    catalog = json.loads((ROOT/catalog_name).read_text())
    pins[catalog_name] = sha(ROOT/catalog_name)
    for entry in catalog['files']:
        if entry['id'] in ('isae-part-1', 'drela-steady'):
            for path, expected in ((entry['local_pdf'], entry['sha256']),
                                   (entry['local_text'], entry['text_sha256'])):
                assert sha(ROOT/path) == expected
                pins[path] = expected
    primary = 'reference/isae-sa13/naca-tm-574.pdf'
    expected = next(p['sha256'] for p in source['primary'] if p['path'].endswith('naca-tm-574.pdf'))
    assert sha(ROOT/primary) == expected
    pins[primary] = expected
    curve, upper, lower = [case['series'][i]['xy'] for i in (2, 3, 4)]
    assert len(curve) == len(upper) == len(lower) == 103
    rows, previous, ended = [], None, False
    residuals = []
    for i, ((x, y), high, low) in enumerate(zip(curve, upper, lower)):
        row = dict(source_row_1based=i+1, x=x, archived=y)
        if y is None:
            ended = True
            row.update(status='unavailable', predicted=None)
        else:
            assert not ended and None not in high+low
            assert x == high[0] == low[0]
            radius = (high[1]-low[1])/2
            assert math.isfinite(radius)
            if previous is None:
                slope = 0.
                status = 'initial_zero_slope_convention'
            else:
                assert x > previous[0]
                slope = (radius-previous[1])/(x-previous[0])
                status = 'previous_station_squared_slope'
            unshifted = 100*slope*slope
            predicted = unshifted-5.
            residuals.append(y-unshifted)
            row.update(status=status, radius=radius, backward_radius_slope=slope,
                       unshifted_squared_slope=unshifted, predicted=predicted,
                       implied_additive_offset=y-unshifted,
                       absolute_error=abs(y-predicted),
                       bernoulli_speed_squared_ratio=1-y/100)
            assert row['absolute_error'] < 2e-12
            previous = x, radius
        rows.append(row)
    assert len(residuals) == 56
    return dict(observed_utc=datetime.now(timezone.utc).isoformat(),
                status='EXACT_SQUARED_RADIUS_SLOPE_IDENTITY_PRESSURE_MAPPING_UNRESOLVED',
                formula='Y_i = 100*((R_i-R_(i-1))/(x_i-x_(i-1)))^2 - 5; slope_0=0',
                figure_label=case['series'][2]['label'], rows=rows,
                finite=56, retained=103, unavailable=47,
                maximum_absolute_error=max(r['absolute_error'] for r in rows if r['predicted'] is not None),
                implied_offset_range=[min(residuals), max(residuals)], sources=pins,
                interpretation=[
                    'The additive offset -5 is inferred from the constant residual in all stored ordinates, including the first value. It is not a documented pressure convention or a production calibration.',
                    'Only the two adjacent outline radii and x coordinates are used. No induced-field integration, sensor velocity or airspeed is needed to reproduce the stored curve.',
                    'This relation alone does not prove the generating program or intent. It does not identify the ordinate as full Bernoulli Cp.',
                    'A restricted kinematic model with V_x=U and V_r=U*dR/dx has dynamic-pressure ratio 1+(dR/dx)^2 and static Cp=-(dR/dx)^2; neither equals this shifted positive-square ordinate.',
                    'Original negative signed outline radii are retained as source data, not accepted as valid model radii.',
                    'Continuous pressure, all missing values, original labels and all required comparisons remain separate and unchanged.',
                ],
                source_references=['Jan Part I section 6.2, pp.40-41, Figure 24(d), p.42.',
                                   'Drela steady Eqs.162-163, p.34.',
                                   'NACA-TM-574 printed p.11 (PDF p.13), Figure 3.'],
                solver_calls=0, production_imports=0, native_passes_added=0,
                retained_native_scope=dict(passed=0, total=612, unavailable=136))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2, allow_nan=False); handle.write('\n')
    print(json.dumps({k:result[k] for k in ('status', 'finite', 'retained',
                                         'maximum_absolute_error', 'implied_offset_range')}))
