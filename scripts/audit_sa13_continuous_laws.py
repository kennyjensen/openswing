"""Compare published body-force laws on the disclosed SA-13 outline.

This is a conditional source diagnostic, not a native ASWING acceptance test.
No radius, angle, normalization, offset or force-law parameter is fitted.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'docs/validation/isae-sa13-sources.json'
SOURCE_SHA = '439c59ead8599f99417ea53db7d146567cd6f4918e672c339ca0694f76499397'
# NACA-TR-405, captions of Figs.6–8, printed pp.131–132.
MUNK = {'r33': .924, 'r101': .817, 'rs1': .78}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        assert os.environ.get(name) == '1', name
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    signal.alarm(25)
    start = time.perf_counter()
    import numpy as np
    from scipy.interpolate import CubicSpline
    from scipy.io import loadmat

    assert sha(ROOT/SOURCE) == SOURCE_SHA
    source = json.loads((ROOT/SOURCE).read_text())
    catalog_path = 'docs/validation/aswing-authoritative-sources.json'
    catalog = json.loads((ROOT/catalog_path).read_text())
    pins = {SOURCE: SOURCE_SHA, catalog_path: sha(ROOT/catalog_path),
            'scripts/audit_sa13_continuous_laws.py': sha(Path(__file__))}
    for item in catalog['files']:
        if item['id'] in ('drela-steady', 'isae-part-1'):
            name = item['local_pdf']
            assert sha(ROOT/name) == item['sha256']
            pins[name] = item['sha256']
    naca = 'reference/isae-sa13/naca-tr-405.pdf'
    pins[naca] = sha(ROOT/naca)
    assert pins[naca] == '89d0d19989635e56faf1aeafb15e93ef4336ef302999344b82d7805e10f67a79'

    comparisons, geometry = [], []
    native_total = native_unavailable = original_pairs = continuous_total = 0
    formula_difference = 0.
    for case in source['cases']:
        figure = Path('reference/isae-validation')/source['revision']/case['path']
        assert sha(ROOT/figure) == case['sha256']
        pins[figure.as_posix()] = case['sha256']
        original = loadmat(ROOT/figure, simplify_cells=True)
        roots = [v for k, v in original.items() if k.startswith('hgS_')]
        assert len(roots) == 1
        original['root'] = roots[0]
        for saved in case['series']:
            node = original
            for key, index in re.findall(r'([A-Za-z_][A-Za-z_0-9]*)|\[(\d+)\]', saved['location']):
                node = node[key] if key else node[int(index)]
            props = node['properties']
            assert str(props.get('DisplayName', '')) == saved['label']
            x, y = [np.asarray(props[k], dtype=float).ravel() for k in ('XData', 'YData')]
            assert len(x) == len(y) == len(saved['xy'])
            for xy, expected in zip(zip(x, y), saved['xy']):
                for actual, target in zip(xy, expected):
                    assert (not np.isfinite(actual)) if target is None else actual == target
            original_pairs += len(x)
        for series in case['series'][1:3]:
            native_total += len(series['xy'])
            native_unavailable += sum(None in row for row in series['xy'])
        continuous_total += len(case['series'][1]['xy'])
        if case['name'] == 'pressure':
            continue  # No force law is substituted for a pressure observable.

        outline = case['outline']
        table = np.asarray(outline['normalized_table'])
        assert table[0, 0] == 0 and table[-1, 0] == 1
        assert np.all(np.diff(table[:, 0]) > 0) and np.all(table[:, 1] >= 0)
        radius = CubicSpline(table[:, 0], table[:, 1], bc_type='natural', extrapolate=False)
        gap = int(np.argmax(np.diff(table[:, 0])))
        geometry.append(dict(case=case['name'], length_over_tabulated_diameter=outline['length_over_diameter'],
                             reported_aspect_ratio=case['isae_report_aspect_ratio'],
                             largest_radius_knot_gap_fraction=float(table[gap+1, 0]-table[gap, 0]),
                             largest_gap_normalized_stations=table[gap:gap+2, 0].tolist(),
                             interpolation='Existing closed outline, natural cubic radius spline; no fitting.'))
        normals = [('f_over_qD', 1/outline['normalized_diameter'])]
        if case['name'] == 'r101':
            normals.append(('f_over_q_in_feet', 33.01/12))
        for normalization, scale in normals:
            rows = []
            for i, (x, archived) in enumerate(case['series'][1]['xy']):
                row = dict(index=i, x_original=x, archived=archived)
                if x is None or archived is None:
                    row['status'] = 'unavailable_reference'
                else:
                    t = (x-outline['nose'])/outline['raw_reconstructed_length']
                    row['station_fraction'] = t
                    if not 0 <= t <= 1:
                        row['status'] = 'outside_closed_outline_no_extrapolation'
                    else:
                        r, slope = float(radius(t)), float(radius(t, 1))
                        assert r >= 0, 'Do not clip a negative interpolated radius'
                        incidence = math.radians(case['primary_alpha'])
                        base = 2*math.pi*r*slope*math.sin(2*incidence)*scale
                        # Eq.10 uses the local tangent angle, not flight incidence.
                        local = math.pi*r*math.sin(2*math.atan(slope))*math.sin(2*incidence)*scale
                        difference = abs(local-base/(1+slope*slope))
                        formula_difference = max(formula_difference, difference)
                        assert difference < 2e-14
                        row.update(status='compared_conditionally', normalized_radius=r,
                                   radius_slope=slope, prediction={
                                       'drela_eq68': base,
                                       'naca_eq10_no_balance_shift': local,
                                       'naca_munk': MUNK[case['name']]*base})
                rows.append(row)
            available = [r for r in rows if r['status'] == 'compared_conditionally']
            peak = max(abs(r['archived']) for r in available)
            metrics = {}
            for law in available[0]['prediction']:
                errors = [r['prediction'][law]-r['archived'] for r in available]
                rmse = math.sqrt(math.fsum(e*e for e in errors)/len(errors))
                maximum = max(abs(e) for e in errors)
                metrics[law] = dict(rmse=rmse, maximum_absolute_error=maximum,
                                    rmse_percent_of_archived_peak=100*rmse/peak,
                                    max_error_percent_of_archived_peak=100*maximum/peak)
            comparisons.append(dict(case=case['name'], source_label=case['series'][1]['label'],
                                    ordinate_assumption=normalization, alpha_deg=case['primary_alpha'],
                                    munk_factor=MUNK[case['name']], compared=len(available),
                                    retained=len(rows), unavailable=sum(r['status']=='unavailable_reference' for r in rows),
                                    outside_outline=sum(r['status']=='outside_closed_outline_no_extrapolation' for r in rows),
                                    archived_peak=peak, metrics=metrics, rows=rows))

    assert native_total == 612 and native_unavailable == 136
    assert continuous_total == 306 and original_pairs == 1530
    assert len(comparisons) == 4
    assert not any(n == 'openswing' or n.startswith('openswing.') for n in sys.modules)
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
                  status='CONDITIONAL_REFERENCE_LAW_COMPARISON_NOT_NATIVE_VALIDATION',
                  comparisons=comparisons, geometry=geometry, sources=pins,
                  formula_check_maximum_difference=formula_difference,
                  original_mat_coordinate_pairs_verified=original_pairs,
                  source_equations=dict(
                      drela='Steady Eqs.68–69, printed p.16: f_z/q = sin(2 theta) d(pi R^2)/dx.',
                      naca_local='TR-405 Eq.10, p.130; Figs.6–8, pp.131–132: f_z/q = pi R sin(2 theta) sin(2 alpha), tan(alpha)=dR/dx.',
                      naca_munk='TR-405 Figs.6–8: f_z/q = (k2-k1) sin(2 theta) d(pi R^2)/dx.'),
                  assumptions=[
                      'The archived plotted outline is a conditional equal-scale geometry, not a recovered original ASWING model.',
                      'All laws use the same existing natural cubic radius reconstruction and primary-source flight incidence.',
                      'NACA local tangent alpha and flight incidence theta are distinct angles.',
                      'NACA local formula is evaluated without the unquantified hydrodynamic-balance shift mentioned for Fig.6.',
                      'R101 dimensional and maximum-diameter normalizations are separate alternatives, not pooled.',
                      'Peak-normalized errors are diagnostics, not the native pointwise relative-error acceptance gate.',
                      'No force-derived geometry, fitted angle, force multiplier or offset; no extrapolation or new missing-value fill.',
                      'This does not establish which equation or geometry generated a Continuous ASWING-labelled curve.',
                  ],
                  solver_calls=0, production_imports=0, primary_passes_added=0,
                  retained_native_scope=dict(passed=0, total=native_total, unavailable=native_unavailable),
                  seconds=time.perf_counter()-start,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  limits=dict(address_space_mib=512, cpu_seconds=15, wall_seconds=25, blas_threads=1))
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2, allow_nan=False); handle.write('\n')
    print(json.dumps({k: result[k] for k in ('status', 'original_mat_coordinate_pairs_verified',
                                            'formula_check_maximum_difference', 'seconds', 'peak_rss_kib')}))
    for item in comparisons:
        print(json.dumps({k: item[k] for k in ('case', 'ordinate_assumption', 'compared', 'retained', 'metrics')}))


if __name__ == '__main__':
    main()
