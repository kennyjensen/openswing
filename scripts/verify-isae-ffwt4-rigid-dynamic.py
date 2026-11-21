"""Compare production continuous dynamic pencils for rigid attachments.

This supplements the steady Schur test with velocity, gyroscopic and complete
acceleration terms. Auxiliary nodal velocities are eliminated in BOTH models
before the extension is removed. No finite-BDF identity is implied.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from openswing.linear_dynamics import DynamicSystem, linearize
from isae_ffwt4_evidence import pin, read, require, write
from isae_ffwt4_rigid_extension_v2 import fixture, balanced_state, MASS, INERTIA, SPIN

PAIR_GATE = 2e-7
MASS_GATE = 2e-10
RATE_GATE = 2e-8
POLYNOMIAL_GATE = 2e-10


def skew(v):
    x, y, z = v
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


def rigid_point_coefficients(mass, inertia, spin, arm, frame_rate):
    """Independent spatial inertia and moving-frame gyroscopic coefficients.

    Velocity at the point is u + w x arm. Absolute acceleration adds
    2 Omega x velocity, and absolute angular acceleration adds Omega x w.
    Expand -m*a and -J*alpha - omega x (J*omega + H) at local w=0.
    """
    b, O = skew(arm), skew(frame_rate)
    spatial_mass = np.block([[mass*np.eye(3), -mass*b],
                            [mass*b, inertia-mass*b@b]])
    gyro = -inertia@O+skew(inertia@frame_rate+spin)-O@inertia
    velocity = np.block([[-2*mass*O, 2*mass*O@b],
                         [-2*mass*b@O, 2*mass*b@O@b+gyro]])
    return -spatial_mass, velocity


def units(n):
    columns, rows = np.ones(n.size), np.ones(n.size)
    columns[:6*n.nn].reshape(n.nn, 6)[:, :3] = 1/n.L
    columns[6*n.nn:6*(n.nn+n.ne)].reshape(n.ne, 6)[:, :3] = 1/n.F
    columns[6*n.nn:6*(n.nn+n.ne)].reshape(n.ne, 6)[:, 3:] = 1/(n.F*n.L)
    columns[6*(n.nn+n.ne):].reshape(-1, 6)[:, :3] = 1/n.F
    columns[6*(n.nn+n.ne):].reshape(-1, 6)[:, 3:] = 1/(n.F*n.L)
    rows[:6*n.ne].reshape(n.ne, 6)[:, :3] = n.L
    rows[6*n.ne:6*n.ne+3*n.nn] = n.F
    rows[6*n.ne+3*n.nn:6*(n.ne+n.nn)] = n.F*n.L
    rows[6*(n.ne+n.nn):].reshape(-1, 6)[:, :3] = n.L
    return rows, columns


def schur(matrix, rows, columns):
    drop_rows = np.setdiff1d(np.arange(len(matrix)), rows)
    drop_columns = np.setdiff1d(np.arange(len(matrix)), columns)
    block = matrix[np.ix_(drop_rows, drop_columns)]
    return (matrix[np.ix_(rows, columns)]-matrix[np.ix_(rows, drop_columns)]@
            np.linalg.solve(block, matrix[np.ix_(drop_rows, columns)]))


def keep_extension(f):
    n, nodes, elements = f.network, f.physical_nodes, f.physical_elements
    columns = np.r_[(6*nodes[:, None]+np.arange(6)).ravel(),
        (6*n.nn+6*elements[:, None]+np.arange(6)).ravel(), 6*(n.nn+n.ne)+np.arange(6)]
    rows = np.r_[(6*elements[:, None]+np.arange(6)).ravel(),
        (6*n.ne+3*nodes[:, None]+np.arange(3)).ravel(),
        (6*n.ne+3*n.nn+3*nodes[:, None]+np.arange(3)).ravel(), 6*(n.ne+n.nn)+np.arange(6)]
    return rows, columns


def build(extended, upper, lifting, moving, step):
    f = fixture(extended=extended, upper=upper, lifting=lifting, moving=moving)
    n = f.network
    x, _, residual, *_ = balanced_state(f)
    require(np.max(abs(residual)) < 1e-12, 'Complete source equilibrium required')
    system = DynamicSystem(n, x, frame='fixed')
    zero = np.zeros(system.size)
    require(np.max(abs(system.residual(zero, zero))) < 1e-12, 'Inconsistent dynamic base')
    A, M = linearize(system, step=step, sparse=True)
    A, M = A.toarray(), M.toarray()
    scales_r, scales_c = units(n)
    retained = np.arange(n.size)
    def pencil(s):
        mechanical = schur(A-s*M, retained, retained)
        dimensional = scales_r[:, None]*mechanical*scales_c[None, :]
        return schur(dimensional, *keep_extension(f)) if extended else dimensional
    return f, system, A, M, pencil


def error(actual, expected):
    return float(np.max(abs(actual-expected)/(1+abs(expected))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chart', choices=('body', 'surface'), required=True)
    parser.add_argument('--end', choices=('lower', 'upper'), required=True)
    parser.add_argument('--stationary-frame', action='store_true')
    parser.add_argument('--difference-step', type=float, choices=(1e-5, 3e-6), default=1e-5)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    folder = args.output_dir.resolve(); folder.mkdir(parents=True, exist_ok=False)
    kernel = [pin(p) for p in sorted((ROOT/'openswing').glob('*.py'))]
    helpers = [pin(__file__), pin(ROOT/'scripts/isae_ffwt4_rigid_extension_v2.py'),
               pin(ROOT/'scripts/isae_ffwt4_evidence.py')]
    source_check = ROOT/'artifacts/isae/ffwt4-rigid-time-20261106/assessment.json'
    prior = read(source_check)
    for p in prior['literal_out_of_range_point_properties']:
        require(pin(p['source']['path']) == p['source'], 'Original PM2 source changed')
    plan = dict(schema='isae-ffwt4-rigid-continuous-dynamics-v1', chart=args.chart,
        end=args.end, moving_frame=not args.stationary_frame, difference_step=args.difference_step,
        source_check=pin(source_check), kernel_pins=kernel, helper_pins=helpers,
        gates=dict(pencil=PAIR_GATE, spatial_mass=MASS_GATE, velocity=RATE_GATE, polynomial=POLYNOMIAL_GATE),
        interpretation='Continuous vacuum dynamic matrices at converged zero-local-rate equilibria; no BDF substitution or native input repair.')
    write(folder/'plan.json', plan)
    start = time.monotonic()
    built = [build(extended=e, upper=args.end == 'upper', lifting=args.chart == 'surface',
                   moving=not args.stationary_frame, step=args.difference_step) for e in (True, False)]
    ext, condensed = built
    coefficients = []
    for *_, pencil in built:
        K0, plus, minus = pencil(0.), pencil(1.), pencil(-1.)
        coefficients.append([K0, (plus-minus)/2, (plus+minus)/2-K0])
    frequency_rows = []
    for s in (0., .2, 1j, -.3+2j, 5j, 10j):
        a, b = ext[-1](s), condensed[-1](s)
        pair = error(a, b)
        polynomial = [error(v[-1](s), sum(c[k]*s**k for k in range(3)))
                      for v, c in zip(built, coefficients)]
        require(pair <= PAIR_GATE and max(polynomial) <= POLYNOMIAL_GATE, 'Dynamic-pencil gate failed')
        frequency_rows.append(dict(s=[complex(s).real, complex(s).imag], pair_error=pair,
                                   polynomial_errors=polynomial))
    coefficient_errors = [error(a, b) for a, b in zip(*coefficients)]
    require(max(coefficient_errors) <= PAIR_GATE, 'Reduced coefficient differs')
    f, system = condensed[:2]; n = f.network
    anchor = n.node(1, 2. if args.end == 'upper' else 1.)
    arm = f.point-n.rj[anchor]
    mass_block, rate_block = rigid_point_coefficients(MASS, INERTIA, SPIN, arm, n.motion.rates)
    load_rows = np.r_[6*n.ne+3*anchor+np.arange(3), 6*n.ne+3*n.nn+3*anchor+np.arange(3)]
    pose_columns = 6*anchor+np.arange(6)
    expected_mass, expected_rate = np.zeros((n.size, n.size)), np.zeros((n.size, n.size))
    expected_mass[np.ix_(load_rows, pose_columns)] = mass_block
    expected_rate[np.ix_(load_rows, pose_columns)] = rate_block
    oracle_rows = []
    for label, c in zip(('extension', 'pylon'), coefficients):
        mass_error, rate_error = error(c[2], expected_mass), error(c[1], expected_rate)
        require(mass_error <= MASS_GATE and rate_error <= RATE_GATE, 'Independent inertia/gyroscopic gate failed')
        oracle_rows.append(dict(representation=label, spatial_mass_error=mass_error, velocity_error=rate_error))
    wrong_arm, _ = rigid_point_coefficients(MASS, INERTIA, SPIN, np.zeros(3), n.motion.rates)
    _, wrong_spin = rigid_point_coefficients(MASS, INERTIA, np.zeros(3), arm, n.motion.rates)
    negatives = dict(omitted_arm_error=error(mass_block, wrong_arm), omitted_spin_error=error(rate_block, wrong_spin))
    require(min(negatives.values()) > 1e-3, 'Oracle cannot detect omitted physical terms')
    if not args.stationary_frame:
        _, wrong_frame = rigid_point_coefficients(MASS, INERTIA, SPIN, arm, np.zeros(3))
        negatives['omitted_frame_rate_error'] = error(rate_block, wrong_frame)
        require(negatives['omitted_frame_rate_error'] > 1e-3, 'Coriolis/gyroscopic control is insensitive')
    arrays = dict(extended_A=ext[2], extended_M=ext[3], pylon_A=condensed[2], pylon_M=condensed[3],
        extended_coefficients=np.array(coefficients[0]), pylon_coefficients=np.array(coefficients[1]),
        independent_mass=expected_mass, independent_velocity=expected_rate)
    np.savez_compressed(folder/'matrices.npz', **arrays)
    require(kernel == [pin(p['path']) for p in kernel] and helpers == [pin(p['path']) for p in helpers], 'Source changed')
    result = dict(status='CONTINUOUS_DYNAMIC_PENCILS_VERIFIED', observed_at=datetime.now(timezone.utc).isoformat(),
        seconds=time.monotonic()-start, plan=pin(folder/'plan.json'), arrays=pin(folder/'matrices.npz'),
        sizes=dict(extended_dynamic=ext[1].size, pylon_dynamic=system.size, retained_mechanical=n.size),
        coefficient_pair_errors=coefficient_errors, frequency_checks=frequency_rows, oracle_checks=oracle_rows,
        negative_controls=negatives, base_residuals=[float(np.max(abs(v[1].residual(np.zeros(v[1].size),np.zeros(v[1].size))))) for v in built],
        derivative_diagnostics=[dict(state=v[1].state_derivative_diagnostics, mass=v[1].derivative_diagnostics) for v in built],
        nonlinear_time_steps=0, physical_parameter_fitting=False, native_predictions_added=0,
        production_attachment_rule_changed=False, native_attachment_semantics_established=False,
        general_nonlinear_3d_history_verified=False, browser_verified=False)
    write(folder/'report.json', result)
    print(json.dumps({k: result[k] for k in ('status', 'seconds', 'sizes', 'coefficient_pair_errors', 'oracle_checks', 'negative_controls')}), flush=True)


if __name__ == '__main__':
    main()
