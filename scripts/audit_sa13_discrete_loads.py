"""Identify the exact algebra in SA-13's three archived discrete load curves.

Source-only diagnostic. No fitted scale, substituted reference, solver call,
or native comparison pass. Retain all missing rows and endpoint conventions.
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


def finite_prefix(rows):
    result, ended = [], False
    for row in rows:
        if None in row:
            ended = True
        else:
            assert not ended, 'Do not bridge internal missing coordinates.'
            assert all(math.isfinite(x) for x in row)
            assert not result or row[0] > result[-1][0]
            result.append(row)
    return result


def audit():
    assert sha(ROOT/SOURCE) == SOURCE_SHA
    data = json.loads((ROOT/SOURCE).read_text())
    pins = {SOURCE: SOURCE_SHA}
    catalog_name = 'docs/validation/aswing-authoritative-sources.json'
    catalog = json.loads((ROOT/catalog_name).read_text())
    pins[catalog_name] = sha(ROOT/catalog_name)
    for row in catalog['files']:
        if row['id'] == 'isae-part-1' or row['local_pdf'].endswith('drela-aswing-steady.pdf'):
            for name, expected in ((row['local_pdf'], row['sha256']),
                                   (row['local_text'], row['text_sha256'])):
                assert sha(ROOT/name) == expected
                pins[name] = expected
    pins['scripts/audit_sa13_discrete_loads.py'] = sha(Path(__file__))
    primary = 'reference/isae-sa13/naca-tr-405.pdf'
    assert sha(ROOT/primary) == '89d0d19989635e56faf1aeafb15e93ef4336ef302999344b82d7805e10f67a79'
    pins[primary] = sha(ROOT/primary)
    results = []
    for case in data['cases']:
        figure = Path('reference/isae-validation')/data['revision']/case['path']
        assert sha(ROOT/figure) == case['sha256']
        pins[figure.as_posix()] = case['sha256']
        if case['name'] == 'pressure':
            continue
        series = case['series']
        assert series[2]['label'] == 'Discrete ASWING 5.96'
        upper, lower = [finite_prefix(series[i]['xy']) for i in (3, 4)]
        observed = finite_prefix(series[2]['xy'])
        assert len(upper) == len(lower)
        assert all(a[0] == b[0] and a[1] == -b[1] for a, b in zip(upper, lower))
        assert all(a[0] == b[0] for a, b in zip(observed, upper))
        diameter = 2*max(r for _, r in upper)
        alpha = case['primary_alpha']
        k = 2*math.pi*math.sin(math.radians(2*alpha))/diameter
        rows = []
        for i, (x, value) in enumerate(series[2]['xy']):
            record = dict(row_1based=i+1, x=x, archived=value)
            if value is None:
                record.update(status='unavailable', predicted=None)
            elif i+1 == len(upper):
                assert value == 0.
                record.update(status='terminal_zero_without_successor', predicted=0.,
                              radius=upper[i][1], error=abs(value))
            else:
                assert x == upper[i][0]
                x1, r1 = upper[i+1]
                r = upper[i][1]
                dx, dr = x1-x, r1-r
                predicted = k*r*dr/dx
                average = .5*k*(r+r1)*dr/dx
                record.update(status='adjacent_station_rule', radius=r, next_radius=r1,
                              next_x=x1, derivative=dr/dx, predicted=predicted,
                              error=abs(value-predicted),
                              linear_radius_interval_average=average,
                              average_minus_node=average-predicted,
                              expected_average_minus_node=.5*k*dr*dr/dx,
                              negative_radius_interval=min(r, r1) < 0)
                assert abs(value-predicted) < 2e-14
                assert abs((average-predicted)-.5*k*dr*dr/dx) < 2e-14
            rows.append(record)
        alternatives = []
        for angle in sorted(set([alpha, case['isae_report_alpha']])):
            for rule in ('next_radius_difference', 'previous_radius_difference', 'next_area_difference'):
                errors = []
                for i, (x, value) in enumerate(observed):
                    if not 0 < i < len(upper)-1:
                        continue
                    x0, r0 = upper[i-1]; r = upper[i][1]; x1, r1 = upper[i+1]
                    area_rate = (2*r*(r1-r)/(x1-x) if rule == 'next_radius_difference' else
                                 2*r*(r-r0)/(x-x0) if rule == 'previous_radius_difference' else
                                 (r1*r1-r*r)/(x1-x))
                    predicted = math.pi*math.sin(math.radians(2*angle))*area_rate/diameter
                    errors.append(abs(predicted-value))
                alternatives.append(dict(alpha_deg=angle, rule=rule, interior_rows=len(errors),
                    maximum_absolute_error=max(errors),
                    maximum_error_percent_of_peak=100*max(errors)/max(abs(y) for _, y in observed)))
        results.append(dict(case=case['name'], alpha_deg=alpha, diameter_in_figure_units=diameter,
                            ordinate='f_z/(q_infinity*D_max)', rows=rows,
                            finite=len(observed), retained=len(rows),
                            maximum_absolute_error=max(r['error'] for r in rows if r['predicted'] is not None),
                            alternatives=alternatives))
    assert sum(r['finite'] for r in results) == 183
    assert sum(r['retained'] for r in results) == 203
    return dict(observed_utc=datetime.now(timezone.utc).isoformat(),
                status='EXACT_ARCHIVED_DISCRETE_LOAD_IDENTITY_NOT_FULL_SOLVER_VALIDATION',
                formula='C_i = 2*pi*sin(2*alpha)*R_i*(R_(i+1)-R_i)/((x_(i+1)-x_i)*D_max)',
                rows=results, sources=pins,
                references=['Jan Part I section 6.2, p.40 and Figure 24, p.42.',
                            'Drela steady Eq.68-69, p.16; NACA-TR-405 Figures 6-8.'],
                qualifications=[
                    'The next-station slope in increasing stored x exactly reproduces the values. The report calls its internal method backward differencing; internal station orientation is unknown.',
                    'This identifies an algebraic relation in the stored data, not its generating executable, complete state or modified continuous-radius derivative.',
                    'The R33 final interval crosses a negative signed outline radius. No clipping or parser bypass is permitted.',
                    'R33 and RS1 each append a terminal zero with no next radius; it is a stored endpoint convention, not a derivative prediction.',
                    'Interval-average loads differ from left-station densities even with the same piecewise-linear radius. The archival solver integration rule remains unknown.',
                    'R101 maximum-diameter normalization here differs from the dimensional f/q-in-feet ordinate of the cited experimental figure.',
                    'All 20 missing rows in these three discrete series remain unavailable. All eight native series still total 612 required values.',
                ], solver_calls=0, production_imports=0, native_passes_added=0,
                retained_native_scope=dict(passed=0, total=612, unavailable=136))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps([dict(case=r['case'], finite=r['finite'], retained=r['retained'],
                          maximum_absolute_error=r['maximum_absolute_error']) for r in result['rows']]))
