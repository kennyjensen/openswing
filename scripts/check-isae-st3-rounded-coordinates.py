#!/usr/bin/env python3
"""Evaluate saved OpenSwing fields at one allowed shared coordinate per row.

Coordinates are witnesses inside the archive's printed intervals, not recovered
historical nodes. Cubic interpolation is checked on all three native meshes.
No solve or production-kernel import is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.interpolate import CubicSpline


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(native, rounding, output):
    root = Path(__file__).resolve().parents[1]
    target_path = root/'docs/validation/isae-st3-reference-target.json'
    target = json.loads(target_path.read_text())
    reference = json.loads((rounding/'summary.json').read_text())
    t = np.array([sum(row['common_interval'])/2 if row['jointly_consistent'] else sum(row['station_window'])/2
        for row in reference['rows']])
    expected = np.array([row['physical_values'][1:6] for row in target['rows']])
    half = np.array([row['printed_half_ulp_physical'][1:6] for row in target['rows']])
    files = [target_path, rounding/'summary.json', Path(__file__)]
    grids = []
    for count in (44, 88, 176):
        path = native/f'n{count}/comparison.json'
        files.append(path)
        case = json.loads(path.read_text())
        fields = case['fields']
        ts = np.array([f['t'] for f in fields])
        v = []
        for field in fields:
            trace = field['traces'].get('left', field['traces'].get('right'))
            v.append([field['position'][1], field['position'][2], field['twist_deg'], *trace['moment_local'][:2]])
        predictions = CubicSpline(ts, v, axis=0)(t)
        matches = abs(predictions-expected) <= half
        grids.append(dict(intervals=count, values=predictions.tolist(),
            max_abs_difference=np.max(abs(predictions-expected), axis=0).tolist(),
            printed_interval_matches=matches.tolist(), jointly_consistent_rows=int(np.sum(np.all(matches, axis=1))),
            per_column_match_counts=np.sum(matches, axis=0).tolist()))
    windows_ok = all(row['station_window'][0] <= ti <= row['station_window'][1] for ti, row in zip(t, reference['rows']))
    exact_endpoint_and_break = all(t[i] == reference['rows'][i]['station_window'][0]
        for i in range(45) if reference['rows'][i]['station_window'][0] == reference['rows'][i]['station_window'][1])
    assert windows_ok and exact_endpoint_and_break
    differences = [np.max(abs(np.array(b['values'])-a['values']), axis=0).tolist() for a, b in zip(grids[:-1], grids[1:])]
    result = dict(status='SAVED_NATIVE_SHARED_COORDINATE_INTERPOLATION_DIAGNOSTIC',
        source_pins={str(p): sha(p) for p in files}, columns=reference['columns'], coordinates=t.tolist(),
        coordinate_rule='Midpoint of the continuum joint admissible interval, fixed once for all outputs and all meshes. Failing exact tip retained.',
        inside_printed_coordinate_windows=windows_ok, exact_endpoint_and_break=exact_endpoint_and_break,
        mesh_comparisons=grids, consecutive_mesh_max_abs_changes=differences,
        limitations=['These are interpolated native outputs; no new equilibrium or nodal-output replay was run.',
            'Permitted coordinates demonstrate consistency with rounding; they do not recover the historical ASWING mesh.',
            'The strict printed-value rule is retained, including the tiny nonzero archived tip Mc.'])
    output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(status=result['status'], rows=[g['jointly_consistent_rows'] for g in grids],
        per_column_matches=grids[-1]['per_column_match_counts'], fine_mesh_changes=differences[-1])), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--rounding', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    main(args.native, args.rounding, args.output)
