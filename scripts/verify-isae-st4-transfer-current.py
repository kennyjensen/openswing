"""Independent six-state audit of the completed literal ST-4 vacuum runs.

No OpenSwing imports or new OpenSwing solves. Implements the straight, uniform
beam specialization of Drela Eqs. 48/50/54--56/80, with exact point-mass jumps.
This is a diagnostic, not a replacement for archived-ASWING or mesh gates.
Run one --case at a time with one BLAS thread.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from scipy.optimize import brentq

from isae_st4_transfer import boundary as continuous_boundary

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/isae/st1-st6-current-20261103/modes'
OUT = ROOT / 'artifacts/isae/st4-transfer-diagnostic-20261103'
L, T0, MASS, ROTARY = 1.2192, .0001, 1.2947, .0078
EI, GJ, EA, CG = 41.1744*9.81, 20.2506*9.81, .437*.2032, .454*.2032
CASES = {
    'Weight7a': (.7237, 17, [-.0709, .0823]),
    'Weight7c': (.7419, 21, [-.0158, .1203]),
    'Weight7d': (.7466, 48, [.0089, .1403]),
    'Weight7e': (.7529, 48, [.0253, .1592]),
    'Weight7f': (.7237, 48, [.0746, .2046]),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def audited_inputs(source, case):
    """Check literal table scalers without using the production ASW parser.

    This deliberately accepts only the pinned two-row uniform models here.
    It is not a second general ASW parser.
    """
    lines = [line.split('#', 1)[0].split() for line in source.splitlines()]
    lines = [line for line in lines if line]
    assert lines.count(['Beam', '1']) == 1
    assert lines.count(['Ground']) == 1
    assert lines[lines.index(['Ground'])+1] == ['1', '0.0001', '0']
    assert not any(row[0].lower() in ('joint', 'strut', 'load', 'engine') for row in lines)

    def table(header, count):
        start = lines.index(header.split())
        scales = lines[start+1]
        assert scales[0] == '*' and len(scales)-1 == len(header.split())
        scales = list(map(Decimal, scales[1:]))
        rows = lines[start+2:start+2+count]
        assert all(len(row) == len(scales) for row in rows)
        return [[float(Decimal(value)*scale) for value, scale in zip(row, scales)] for row in rows]

    header = 't x y z chord Xax EIcc GJ EInn GKc EA GKn mg mgcc mgnn'
    beam = table(header, 2)
    expected = [[t, 0, 0, z, .2032, 0, EI, GJ, 0, 0, 0, 0, MASS*9.81, ROTARY*9.81, 0]
                for t, z in [(T0, 0), (L, L)]]
    np.testing.assert_allclose(beam, expected, rtol=2e-15, atol=2e-15)
    # Zero stiffness entries are the documented rigid directions, not zero
    # restoring stiffness. The material point coordinate t is not arc length.
    offsets = table('t Cea Nea Cta Nta Ccg Ncg', 2)
    np.testing.assert_allclose(offsets, [[t, EA, 0, EA, 0, CG, 0] for t in (T0, L)],
                               rtol=2e-15, atol=2e-15)
    start = lines.index(['Weight'])
    assert lines[start+1] == ['*', '0.0254', '1.0', '1.', '0.0254', '9.81']
    records = lines[start+2:start+4]
    assert lines[start+4][0].lower() == 'end'
    weight, inches, xs = CASES[case]
    points = []
    for record, x in zip(records, xs):
        assert len(record) == 6 and record[0] == '1'
        actual = [float(Decimal(v)*Decimal(s)) for v, s in zip(record[1:], ['.0254', '1', '1', '.0254', '9.81'])]
        expected = [inches*.0254, x, 0, inches*.0254, weight*9.81]
        np.testing.assert_allclose(actual, expected, rtol=2e-15, atol=2e-15)
        points.append([weight, actual[0], x, 0., actual[3]])
    assert float(lines[lines.index(['Constant'])+1][0]) == 9.81
    return points


def station(t):
    return (t-T0)*L/(L-T0)


def discrete_boundary(frequency, points, nodes, *, rotary=ROTARY, cg=CG):
    """Cayley propagation of averaged first-order beam equations.

    State [h, beta, phi, B, N, T] uses elastic-axis translation h, bending
    slope beta, torsion phi, B=EI beta', shear N and T=GJ phi'. For each
    interval the bending inertia is Icc + mu*ds**2/12 (Eq.80); torsional
    inertia remains Icc + Inn. Concentrated masses retain their full pylon.
    """
    w2 = (2*np.pi*frequency)**2
    offset = cg-EA
    scale = np.array([L, 1., 1., EI/L, EI/L**2, GJ/L])
    transfer = np.eye(6)
    for left, right in zip(nodes[:-1], nodes[1:]):
        ds = right-left
        generator = np.zeros((6, 6))
        generator[0, 1] = 1.
        generator[1, 3] = 1/EI
        generator[2, 5] = 1/GJ
        generator[3, 4] = 1.
        generator[3, 1] = -w2*(rotary+MASS*ds*ds/12)
        generator[4, 0] = w2*MASS
        generator[4, 2] = w2*MASS*offset
        generator[5, 0] = -w2*MASS*offset
        generator[5, 2] = -w2*(rotary+MASS*offset*offset)
        scaled = generator*scale[None, :]/scale[:, None]
        transfer = np.linalg.solve(np.eye(6)-scaled*ds/2, np.eye(6)+scaled*ds/2)@transfer
        for weight, t, x, y, z in points:
            s = station(t)
            assert y == 0
            if abs(s-right) > 1e-14:
                continue
            # Point transverse motion: h + (z-s)*beta + (x-EA)*phi.
            v = np.array([1., z-s, x-EA])
            jump = np.eye(6)
            jump[3, :3] -= w2*weight*v[1]*v
            jump[4, :3] += w2*weight*v[0]*v
            jump[5, :3] -= w2*weight*v[2]*v
            transfer = (jump*scale[None, :]/scale[:, None])@transfer
    block = transfer[3:, 3:]
    return block/np.maximum(np.linalg.norm(block, axis=1), 1.)[:, None]


def roots(boundary, centers):
    values, witnesses = [], []
    for i, center in enumerate(centers):
        low = max(.99*center, 0 if i == 0 else (centers[i-1]+center)/2)
        high = min(1.01*center, np.inf if i+1 == len(centers) else (centers[i+1]+center)/2)
        root, info = brentq(lambda f: np.linalg.det(boundary(f)), low, high,
                           xtol=2e-12, rtol=2e-14, full_output=True)
        singular = np.linalg.svd(boundary(root), compute_uv=False)
        ratio = float(singular[-1]/singular[0])
        assert info.converged and ratio < 1e-8
        values.append(root)
        witnesses.append(dict(bracket_Hz=[low, high], iterations=info.iterations,
                              relative_boundary_singular_value=ratio))
    return np.asarray(values), witnesses


def analytic_controls():
    controls = []
    # Uncoupled fixed/free torsion has an exact finite-difference spectrum.
    for n in (16, 32, 64):
        exact = n/(np.pi*L)*np.sqrt(GJ/ROTARY)*np.tan(np.array([1, 3, 5])*np.pi/(4*n))
        found, witness = roots(lambda f: discrete_boundary(f, [], np.linspace(0, L, n+1), cg=EA), exact)
        errors = abs(found/exact-1)
        assert np.max(errors) < 1e-9
        controls.append(dict(name=f'discrete_torsion_n{n}', expected_Hz=exact.tolist(),
                             found_Hz=found.tolist(), relative_errors=errors.tolist(), witnesses=witness))
    # Euler cantilever roots give an independent continuous bending control.
    beta = np.array([1.875104068711961, 4.694091132974175, 7.854757438237612])
    exact = beta**2/(2*np.pi*L*L)*np.sqrt(EI/MASS)
    found, witness = roots(lambda f: continuous_boundary(f, [], 0., cg_x=EA), exact)
    errors = abs(found/exact-1)
    assert np.max(errors) < 1e-9
    controls.append(dict(name='continuous_euler_bending', expected_Hz=exact.tolist(),
                         found_Hz=found.tolist(), relative_errors=errors.tolist(), witnesses=witness))
    return controls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=CASES, required=True)
    args = parser.parse_args()
    start = time.perf_counter()
    plan = read(BASE/'plan.json')
    recovery = read(BASE/'grid-recovery/plan.json')
    job_id = f'ST-4:{args.case}:vaccum'
    job = next(j for j in plan['jobs'] if j['id'] == job_id)
    model_path = Path(job['model_path'])
    source = model_path.read_text()
    points = audited_inputs(source, args.case)
    pins = {str(model_path.relative_to(ROOT)): digest(model_path)}
    for path in (Path(__file__), ROOT/'scripts/isae_st4_transfer.py',
                 ROOT/'.reference/asw_theory.txt', ROOT/'.reference/asw_uns_theory.txt',
                 BASE/'plan.json', BASE/'grid-recovery/plan.json'):
        pins[str(path.relative_to(ROOT))] = digest(path)
    for name, expected in plan['code_sha256'].items():
        assert digest(ROOT/name) == expected, f'Changed original source: {name}'
    controls = analytic_controls()
    rows = []
    for n in (16, 32, 64):
        folder = ROOT/recovery['grid_folders'][job_id][str(n)]
        report, request = read(folder/'report.json'), read(folder/'request.json')
        assert request['source'] == source and report['numerical_status'] == 'PASS'
        assert request['numerics']['structural_operator'] == 'drela-fixed-vacuum-v1'
        assert request['condition'] is None and request['modes']['vacuum'] is True
        assert request['modes']['frame'] == 'fixed' and request['modes']['gravity_magnitude'] == 0
        assert request['panels']['beams']['1'] == dict(count=n, spacing='uniform')
        for name in ('report.json', 'request.json', 'plan.json'):
            path = folder/name
            pins[str(path.relative_to(ROOT))] = digest(path)
        nodes = np.unique(np.r_[np.linspace(0, L, n+1), [station(p[1]) for p in points]])
        assert len(nodes)-1 == report['mesh']['actual_elements']
        samples = report['mesh']['mesh_discretization']['beams'][0]['nodes']
        np.testing.assert_allclose([sample['s'] for sample in samples], nodes, rtol=0, atol=3e-14)
        comparisons = report['reference_comparison']
        actual = np.array([r['actual_frequency_Hz'] for r in comparisons])
        found, witness = roots(lambda f: discrete_boundary(f, points, nodes), actual)
        relative = found/actual-1
        row = dict(nominal_intervals=n, actual_intervals=len(nodes)-1,
                   retained_frequencies_Hz=actual.tolist(), independent_frequencies_Hz=found.tolist(),
                   relative_differences=relative.tolist(), passed=(abs(relative) <= 1e-8).tolist(),
                   witnesses=witness)
        rows.append(row)
        print(args.case, n, 'max relative difference', float(max(abs(relative))), flush=True)
    continuum, witness = roots(lambda f: continuous_boundary(f, points, ROTARY), actual)
    archive = np.array([r['reference']['frequency_Hz'] for r in comparisons])
    errors = np.array([abs(np.array(r['independent_frequencies_Hz'])/continuum-1) for r in rows])
    result = dict(case=args.case, status='PASS_INDEPENDENT_DISCRETE_DIAGNOSTIC' if all(all(r['passed']) for r in rows) else 'FAIL',
        scope='Selected original ordinals in one straight uniform, unloaded, fixed vacuum model; not a full modal census or new archived-ASWING acceptance.',
        branch_selection='Retained frequencies locate isolated 1% brackets only; roots are computed from independent determinants, without fitting physical parameters.',
        original_pass_counts_changed=False, full_family_validated=False, new_openswing_solves=0,
        gate=1e-8, input_sha256=pins, retained_kernel_sha256=plan['code_sha256'],
        parameters=dict(length=L, t0=T0, mass_per_length=MASS, rotary_per_length=ROTARY,
                        EI=EI, GJ=GJ, elastic_axis_x=EA, centroid_x=CG, points=points),
        analytic_controls=controls, grids=rows, continuum_frequencies_Hz=continuum.tolist(),
        continuum_witnesses=witness, archive_frequencies_Hz=archive.tolist(),
        continuum_archive_relative_differences=(continuum/archive-1).tolist(),
        relative_discretization_errors=errors.tolist(),
        error_reduction_factors=(errors[:-1]/errors[1:]).tolist(),
        seconds=time.perf_counter()-start)
    assert all(digest(ROOT/name) == value for name, value in pins.items())
    OUT.mkdir(exist_ok=True)
    (OUT/(args.case+'.json')).write_text(json.dumps(result, indent=2)+'\n')
    assert result['status'] == 'PASS_INDEPENDENT_DISCRETE_DIAGNOSTIC'


if __name__ == '__main__':
    main()
