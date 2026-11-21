"""Audit archived SA-13 lift integrals against steady Eq.68 area changes.

No force fit, solver run, native acceptance gate, or denominator change. The
geometry and reference-normalization assumptions remain explicit hypotheses.
"""
import argparse
import bisect
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'docs/validation/isae-sa13-sources.json'
SOURCE_SHA = '439c59ead8599f99417ea53db7d146567cd6f4918e672c339ca0694f76499397'
WINDOWS = [(0.05, 0.25), (0.10, 0.40), (0.40, 0.80), (0.60, 0.90)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite_prefix(rows):
    """Do not sort points or bridge a missing sample within a curve."""
    values = []
    ended = False
    for row in rows:
        if None in row:
            ended = True
        else:
            assert not ended, 'An internal missing value needs explicit treatment'
            assert all(math.isfinite(v) for v in row)
            assert not values or row[0] > values[-1][0]
            values.append(row)
    return values


def interpolate(rows, x):
    assert rows[0][0] <= x <= rows[-1][0], 'No extrapolation permitted'
    i = min(bisect.bisect_right([p[0] for p in rows], x), len(rows)-1)
    p, q = rows[i-1:i+1]
    return p[1] + (q[1]-p[1]) * (x-p[0]) / (q[0]-p[0])


def integrate(rows, lo, hi):
    points = [[lo, interpolate(rows, lo)]]
    points.extend(p for p in rows if lo < p[0] < hi)
    points.append([hi, interpolate(rows, hi)])
    return math.fsum((q[0]-p[0]) * (p[1]+q[1]) / 2
                     for p, q in zip(points, points[1:]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert sha(ROOT / SOURCE) == SOURCE_SHA
    source = json.loads((ROOT / SOURCE).read_text())
    pins = {SOURCE: SOURCE_SHA}
    for name in ['reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
                 'reference/aswing-authoritative-20261108/isae-part-1-aerodynamics.pdf',
                 'reference/isae-sa13/naca-tr-405.pdf', 'openswing/volume.py',
                 'openswing/aero.py', 'scripts/audit_sa13_load_integrals.py']:
        pins[name] = sha(ROOT / name)
    # Authenticate the authoritative PDF copies against their source catalog.
    catalog_name = 'docs/validation/aswing-authoritative-sources.json'
    catalog = json.loads((ROOT / catalog_name).read_text())
    pins[catalog_name] = sha(ROOT / catalog_name)
    for item in catalog['files']:
        name = item['local_pdf']
        if name in pins:
            assert pins[name] == item['sha256']
    assert pins['reference/isae-sa13/naca-tr-405.pdf'] == (
        '89d0d19989635e56faf1aeafb15e93ef4336ef302999344b82d7805e10f67a79')
    comparisons, curve_pairs = [], []
    for case in source['cases']:
        if case['name'] == 'pressure':
            continue
        figure = Path('reference/isae-validation') / source['revision'] / case['path']
        assert sha(ROOT / figure) == case['sha256']
        pins[figure.as_posix()] = case['sha256']
        outline = case['outline']
        nose, length = outline['nose'], outline['raw_reconstructed_length']
        radius = [[nose+length*x, length*r] for x, r in outline['normalized_table']]
        diameter = outline['normalized_diameter'] * length
        series = [(row, finite_prefix(row['xy'])) for row in case['series'][1:3]]
        for lo, hi in WINDOWS:
            x0, x1 = nose+lo*length, nose+hi*length
            continuous, discrete = [integrate(points, x0, x1) for _, points in series]
            curve_pairs.append(dict(case=case['name'], window=[lo, hi],
                                    continuous_integral=continuous,
                                    discrete_integral=discrete,
                                    continuous_over_discrete=continuous/discrete))
        normalizations = [('f_over_qD', 1/diameter)]
        if case['name'] == 'r101':
            # NACA-TR-405 Fig.8: f/q in feet, length 33.01 inches.
            normalizations.append(('f_over_q_in_feet', (33.01/12)/length))
        for alpha in ([9, 10] if case['name'] == 'rs1' else [10]):
            for norm, multiplier in normalizations:
                for raw, points in series:
                    windows = []
                    for lo, hi in WINDOWS:
                        x0, x1 = nose+lo*length, nose+hi*length
                        area_change = math.pi * (interpolate(radius, x1)**2
                                                 - interpolate(radius, x0)**2)
                        # f_z/q = sin(2 alpha) dA/ds for uniform incident flow.
                        predicted = math.sin(math.radians(2*alpha))*area_change*multiplier
                        observed = integrate(points, x0, x1)
                        windows.append(dict(window=[lo, hi], x_raw=[x0, x1],
                                            archived_integral=observed,
                                            equation68_integral=predicted,
                                            archived_over_equation68=observed/predicted))
                    comparisons.append(dict(case=case['name'], alpha_deg=alpha,
                                            ordinate_assumption=norm,
                                            source_label=raw['label'],
                                            finite_samples=len(points),
                                            retained_samples=len(raw['xy']),
                                            windows=windows))
    result = dict(
        observed_utc=datetime.now(timezone.utc).isoformat(),
        status='SOURCE_INTEGRAL_DIAGNOSTIC_NOT_NATIVE_VALIDATION',
        equation='Drela steady Eq.68-69, printed p.16: f_z/q = sin(2 alpha) d(pi R^2)/ds',
        curve_pairs=curve_pairs, comparisons=comparisons, sources=pins,
        assumptions=[
            'Straight isolated body, uniform incident flow, no profile or acceleration loads.',
            'Use body-transverse force, not a wind-axis lift projection.',
            'Piecewise-linear integration of stored plotted ordinates; unsampled curvature is unknown.',
            'Use the pre-existing closed outline, equal axial/radial scale, and linear radius interpolation.',
            'R101 ordinate normalization and RS1 incidence alternatives are not selected by fit quality.',
            'Original and modified ASWING settings are unavailable; these ratios do not establish their inputs.',
        ],
        solver_calls=0, primary_passes_added=0,
        retained_native_scope=dict(passed=0, total=612, unavailable=136))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps(dict(output=str(args.output), curve_pair_windows=len(curve_pairs),
                          equation_windows=sum(len(c['windows']) for c in comparisons),
                          source_pins=len(pins), solver_calls=0)))


if __name__ == '__main__':
    main()
