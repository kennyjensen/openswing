"""Audit retained Durrant studies and compare local oscillatory eigenmodes.

This postprocessor never changes the solver or calls a sampled stable spectrum
a complete stability result. Its MAC thresholds reject ambiguous assignments.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def modes(case, search=0):
    # Keep the selection explicit: real and near-real roots are not assessed
    # by the oscillatory mechanical-shape metric below.
    return [m for m in case['searches'][search]['modes'] if m['frequency_Hz'] > .1]


def root(mode):
    return complex(*mode['eigenvalue_per_s'])


def match(before, after, first_search=0, second_search=0):
    a, b = modes(before, first_search), modes(after, second_search)
    za = np.asarray(before['jig_positions'])[:, 2]
    zb = np.asarray(after['jig_positions'])[:, 2]
    assert np.all(np.diff(za) > 0) and np.all(np.diff(zb) > 0)
    assert abs(za[0]-zb[0]) < 1e-12 and abs(za[-1]-zb[-1]) < 1e-12
    span = np.unique(np.r_[za, zb])
    ds = np.diff(span)
    weights = np.r_[ds[0], ds[:-1]+ds[1:], ds[-1]]/2
    metric = np.sqrt(weights[:, None])*[1., 1., 1., .09446, .09446, .09446]

    def vector(mode, original_span):
        v = np.asarray(mode['mechanical_shape']['real'])+1j*np.asarray(mode['mechanical_shape']['imag'])
        v = np.stack([np.interp(span, original_span, v[:, j]) for j in range(6)], axis=1)
        v = (v*metric).ravel()
        return v/np.linalg.norm(v)

    va = np.asarray([vector(m, za) for m in a])
    vb = np.asarray([vector(m, zb) for m in b])
    mac = abs(va.conj()@vb.T)**2
    rows, cols = linear_sum_assignment(1-mac)
    pairs = []
    for i, j in zip(rows, cols):
        row_margin = mac[i, j]-np.max(np.delete(mac[i], j), initial=0.)
        col_margin = mac[i, j]-np.max(np.delete(mac[:, j], i), initial=0.)
        r0, r1 = root(a[i]), root(b[j])
        pairs.append(dict(before=a[i]['eigenvalue_per_s'], after=b[j]['eigenvalue_per_s'],
            modal_assurance=float(mac[i, j]), row_margin=float(row_margin), column_margin=float(col_margin),
            resolved=bool(mac[i, j] > .8 and row_margin > .1 and col_margin > .1),
            scaled_root_change=float(abs(r1-r0)/max(1., abs(r0))),
            frequency_change_Hz=float((r1.imag-r0.imag)/(2*np.pi)),
            growth_change_per_s=float(r1.real-r0.real)))
    return dict(pairs=pairs, unmatched_before=[a[i]['eigenvalue_per_s'] for i in range(len(a)) if i not in rows],
                unmatched_after=[b[j]['eigenvalue_per_s'] for j in range(len(b)) if j not in cols])


def model_spec(case):
    defaults = dict(variant='tables', nea=.001, mach=0., aero_lag=True, gravity_m_s2=9.805,
                    stall=True, freeze_influences=False, time_unit_s=1., step=1e-5)
    return {**defaults, **{k: v for k, v in case['spec'].items() if k not in ('shifts', 'count')}}


def compare(before, after, kind):
    return dict(kind=kind, before_id=before['id'], after_id=after['id'], **match(before, after))


def summary(case):
    b = case['base']
    s = case['spec']
    strips = b['strips']
    q = np.asarray(b['nodes'][-1]['rotation'])
    gj = {'25': .7101, '75': .6887}[s['wing']]
    approximate_twist = .5*1.225*s['speed_m_s']**2*.09446**2*(-.1)*.718**2/(2*gj)
    lower_derivative = 40/(1+np.exp((np.array([x['cl'] for x in strips])+.3)/.05))
    return dict(id=case['id'], spec=s, actual_elements=case['actual_elements'],
        continuous_residual=b['modal_base']['continuous_residual'],
        maximum_pencil_error=max(max(m['right_backward_error'], m['left_backward_error'])
                                for search in case['searches'] for m in search['modes']),
        maximum_displacement_m=b['max_displacement'],
        body_z_tip_angle_deg=float(np.rad2deg(np.arctan2(q[1, 0], q[0, 0]))),
        uniform_torque_tip_twist_deg=float(np.rad2deg(approximate_twist)),
        cl_range=[min(x['cl'] for x in strips), max(x['cl'] for x in strips)],
        lower_leakage_slope_range=[float(min(lower_derivative)), float(max(lower_derivative))],
        sampled_positive_growth_roots=[m['eigenvalue_per_s'] for m in modes(case) if root(m).real > 0],
        finite_dimension=case['searches'][0]['metadata'].get('finite_dimension'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='append', required=True, help='label=directory')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cases, runs, rejected = [], [], []
    for item in args.run:
        label, path = item.split('=', 1)
        directory = Path(path)
        manifest_raw = (directory/'run.json').read_bytes()
        run = json.loads(manifest_raw)
        runs.append(dict(label=label, directory=str(directory), observed_manifest=run,
                         observed_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest()))
        for entry in run['cases']:
            p = directory/entry['file']
            assert sha(p) == entry['sha256'], str(p)
            case = json.loads(p.read_text())
            case['id'] = label+'/'+entry['file']
            case['case_sha256'] = entry['sha256']
            if case['status'] != 'computed':
                rejected.append(case)
                continue
            assert case['base']['modal_base']['continuous_residual'] < 1e-7
            assert all(max(m['right_backward_error'], m['left_backward_error']) < 1e-9
                       for search in case['searches'] for m in search['modes'])
            cases.append(case)

    search_checks, comparisons = [], []
    for case in cases:
        for j in range(1, len(case['searches'])):
            same = match(case, case, 0, j)
            # Shape assignment is independently checked by eigenvalue proximity.
            common = [p for p in same['pairs'] if p['resolved'] and p['scaled_root_change'] < 1e-7]
            search_checks.append(dict(id=case['id'], first_shift=case['searches'][0]['shift'],
                second_shift=case['searches'][j]['shift'], matched_common_count=len(common),
                maximum_common_root_change=max((p['scaled_root_change'] for p in common), default=None), **same))

    # Only pairs differing in the named parameter are called its sensitivity.
    parameters = ('step', 'panels', 'time_unit_s', 'stall', 'freeze_influences', 'nea')
    for i, before in enumerate(cases):
        for after in cases[i+1:]:
            a, b = model_spec(before), model_spec(after)
            changed = [k for k in set(a)|set(b) if a.get(k) != b.get(k)]
            if len(changed) == 1 and changed[0] in parameters:
                comparisons.append(compare(before, after, changed[0]))

    # Neighboring speeds in each unchanged mesh/model group, without silently
    # selecting a different tangent step, influence convention or input units.
    groups = {}
    for case in cases:
        spec = model_spec(case)
        spec.pop('speed_m_s')
        groups.setdefault(json.dumps(spec, sort_keys=True), []).append(case)
    paths = []
    for group in groups.values():
        group.sort(key=lambda c: c['spec']['speed_m_s'])
        for before, after in zip(group[:-1], group[1:]):
            pair = compare(before, after, 'speed_m_s')
            u0, u1 = before['spec']['speed_m_s'], after['spec']['speed_m_s']
            pair['speed_interval_m_s'] = [u0, u1]
            for p in pair['pairs']:
                lo, hi = p['before'][0], p['after'][0]
                p['growth_sign_change'] = bool(lo*hi < 0)
                if p['growth_sign_change']:
                    p['secant_seed_m_s'] = u0-lo*(u1-u0)/(hi-lo)
            paths.append(pair)

    record = dict(status='diagnostic evidence; no flutter-validation claim',
        analyzer_sha256=sha(Path(__file__)), runs=runs, cases=[summary(c) for c in cases],
        rejected=rejected, search_comparisons=search_checks, parameter_comparisons=comparisons,
        speed_paths=paths, scope={
            'mode_selection': 'Positive oscillatory roots above 0.1 Hz. Real roots and unreturned roots are outside this matching assessment.',
            'shape_metric': 'Trapezoidal integral over the union of physical jig-span stations, with linearly interpolated complex displacements and chord-scaled rotations. Phase invariant; Hungarian one-to-one assignment.',
            'matching_gate': 'MAC > 0.8 and row/column margins > 0.1. Unresolved matches cannot establish a critical-speed bracket.',
            'static_approximation': 'Uniform Cm torque: theta_tip=rho U^2 c^2 Cm L^2/(4 GJ). Omits offset lift, finite-rotation transport and local Mach correction; not a full equilibrium reference.',
            'lower_leakage_slope': 'Independent derivative of the lower term in equation 204 at the saved CL, multiplied by the default factor 40. Reported as a diagnostic even for the deliberately stall-disabled setting.',
            'coverage': 'Full-descriptor searches leave total finite dimension unclassified. A sampled damped spectrum does not prove stability.',
            'reference': 'Source/setup conflicts remain. Experimental destruction speeds differ from linear eigenvalue crossings.'})
    args.output.write_text(json.dumps(record, indent=2, allow_nan=False)+'\n')
    print('Recorded', len(cases), 'computed cases,', len(rejected), 'rejections;', args.output)
    for item in comparisons:
        pairs=[p for p in item['pairs'] if p['resolved']]
        print(item['kind'],item['before_id'],item['after_id'],'resolved',len(pairs),
              'max relative root change',max((p['scaled_root_change'] for p in pairs),default=None))
    for item in paths:
        for p in item['pairs']:
            if p['growth_sign_change']:
                print('SIGN CHANGE',item['before_id'],item['after_id'],p)


if __name__ == '__main__':
    main()
