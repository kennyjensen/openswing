#!/usr/bin/env python3
"""Check shared station-rounding uncertainty with an independent continuous rod.

This is a diagnostic of printed precision, not an ASWING discrete-system replay.
Each row has one common station for every output. No material/load fit is made.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.optimize import brentq
from isae_st3_static_reference import solve, observables

ROOT = Path(__file__).resolve().parents[1]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, d):
    p.write_text(json.dumps(d, indent=2, allow_nan=False)+'\n')


def main(stage, native):
    stage.mkdir(parents=True, exist_ok=False)
    target_path = ROOT/'docs/validation/isae-st3-reference-target.json'
    target = json.loads(target_path.read_text())
    fine = json.loads((native/'n176/comparison.json').read_text())
    helper = ROOT/'scripts/isae_st3_static_reference.py'
    # Known endpoints/break override their printed station intervals.
    windows = []
    samples = []
    for i, row in enumerate(target['rows']):
        t, h = row['physical_values'][0], row['printed_half_ulp_physical'][0]
        if i in (0, 44) or t == .335:
            t = .6*.558 if t == .335 else t
            a = b = t
            knots = [t]
        else:
            a, b = t-h, t+h
            knots = np.linspace(a, b, 33).tolist()
        windows.append(dict(lower=a, upper=b, knots=knots))
        samples.extend(knots)
    samples.extend(f['t'] for f in fine['fields'])
    stations = np.array(sorted(set(samples)))
    physical_s = .558*(stations-.0001)/(.558-.0001)
    plan = dict(native=str(native), target_sha256=sha(target_path), helper_sha256=sha(helper),
        native_sha256=sha(native/'n176/comparison.json'), script_sha256=sha(__file__),
        independent_boundary_value_solves=1, source_model_sha256=target['files'][0]['sha256'],
        signed_pair_couple_argument_Nm=-.14*.5451*9.81, rtol=2e-11, atol=2e-13,
        windows=windows, diagnostic_rule='Intersection of all five nonzero structural output rounding intervals at one shared t per row.',
        limitations=['Independent continuum, not the unknown historical discrete equations/mesh.',
            'Dense ODE interpolation and 33-point local cubic interpolation are numerical diagnostics, not rigorous interval enclosures.',
            'No absolute tolerance is added to an archived printed interval; near-zero ASWING residual artifacts therefore remain visible.'])
    write(stage/'plan.json', plan)
    start = time.monotonic()
    continuum = solve('m15_0', couple=plan['signed_pair_couple_argument_Nm'], stations=physical_s)
    seconds = time.monotonic()-start
    write(stage/'continuum.json', continuum)
    r = np.array(continuum['positions'])
    q = np.array(continuum['rotations'])
    m = np.array(continuum['internal_moments'])
    local_m = np.einsum('nji,nj->ni', q, m)
    values = np.column_stack([r[:, 1], r[:, 2],
        [observables(p, rot)['twist_asw_deg'] for p, rot in zip(r, q)], local_m[:, :2]])
    rows = []
    for ref, window in zip(target['rows'], windows):
        a, b = window['lower'], window['upper']
        indices = np.searchsorted(stations, window['knots'])
        v = values[indices]
        expected = np.array(ref['physical_values'][1:6])
        half = np.array(ref['printed_half_ulp_physical'][1:6])
        intervals = []
        interpolation_check = 0.
        if a == b:
            for j in range(5):
                ok = abs(v[0, j]-expected[j]) <= half[j]
                intervals.append([a, b] if ok else None)
        else:
            splines = [CubicSpline(window['knots'], v[:, j]) for j in range(5)]
            # Half-density interpolation predicts the other 16 directly evaluated ODE samples.
            for j, f in enumerate(splines):
                coarse = CubicSpline(window['knots'][::2], v[::2, j])
                interpolation_check = max(interpolation_check,
                    float(np.max(abs(coarse(window['knots'][1::2])-v[1::2, j]))/half[j]))
                increasing = v[-1, j] > v[0, j]
                assert np.all(np.diff(v[:, j])*(1 if increasing else -1) >= 0)
                lo, hi = expected[j]-half[j], expected[j]+half[j]
                if max(v[0, j], v[-1, j]) < lo or min(v[0, j], v[-1, j]) > hi:
                    intervals.append(None)
                    continue
                roots = [a, b]
                for bound in (lo, hi):
                    if (v[0, j]-bound)*(v[-1, j]-bound) < 0:
                        roots.append(float(brentq(lambda t: float(f(t))-bound, a, b, xtol=1e-15)))
                roots.sort()
                acceptable = []
                for left, right in zip(roots[:-1], roots[1:]):
                    if lo <= f((left+right)/2) <= hi:
                        acceptable.append([left, right])
                intervals.append([acceptable[0][0], acceptable[-1][1]] if acceptable else None)
        common = None if any(x is None for x in intervals) else [max(x[0] for x in intervals), min(x[1] for x in intervals)]
        consistent = common is not None and common[0] <= common[1]
        rows.append(dict(source_line=ref['source_line'], t_printed=ref['physical_values'][0],
            station_window=[a, b], column_intervals=intervals, common_interval=common,
            jointly_consistent=bool(consistent), interpolation_half_density_max_printed_half_ulp=interpolation_check))
    current = []
    for field in fine['fields']:
        i = int(np.searchsorted(stations, field['t']))
        trace = field['traces'].get('left', field['traces'].get('right'))
        predicted = np.array([field['position'][1], field['position'][2], field['twist_deg'], *trace['moment_local'][:2]])
        current.append((predicted-values[i]).tolist())
    result = dict(status='ROUNDING_DIAGNOSTIC_COMPLETE_NOT_DISCRETE_PARITY', seconds=seconds,
        reference_plan_sha256=sha(stage/'plan.json'), boundary_residual_Nm=continuum['boundary_residual_Nm'],
        columns=['y_m', 'z_m', 'twist_deg', 'Mc_prime_Nm', 'Ms_prime_Nm'], rows=rows,
        jointly_consistent_rows=sum(row['jointly_consistent'] for row in rows),
        independent_column_consistent_counts=[sum(row['column_intervals'][j] is not None for row in rows) for j in range(5)],
        native_minus_continuum_max_abs=np.max(abs(np.array(current)), axis=0).tolist(),
        max_interpolation_half_density_printed_half_ulp=max(row['interpolation_half_density_max_printed_half_ulp'] for row in rows),
        limitations=plan['limitations'])
    write(stage/'summary.json', result)
    print(json.dumps({k: result[k] for k in ['status', 'seconds', 'jointly_consistent_rows', 'independent_column_consistent_counts', 'native_minus_continuum_max_abs', 'max_interpolation_half_density_printed_half_ulp']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--native', type=Path, required=True)
    args = parser.parse_args()
    main(args.stage, args.native)
