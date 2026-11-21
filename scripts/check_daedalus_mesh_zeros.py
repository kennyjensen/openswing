"""Current coarse/fine response kinematics and independently located zeros.

All frequency solves retain the complete descriptor. Cancellation zeros are
computed at complex s, not fitted to the frequency samples or reference plot.
"""
import argparse
from check_daedalus_load_sensitivity import ROOT, SOURCE, read
from daedalus_bounded_job import run

STUDY = ROOT/'artifacts/daedalus-mesh-zeros-20261114'
FINE = ROOT/'artifacts/daedalus-structural-resolution-20261113'
ZEROS = ROOT/'artifacts/daedalus-transmission-zeros-20261114'
CHANNELS = ['yaw_rate', 'roll_rate', 'sideslip', 'bank']
FREQUENCIES = [.1, 1., 1.1, 1.15737773741517, 1.3, 1.4, 1.5, 1.6]


def paths(mesh):
    if mesh == 'coarse': return SOURCE/'assembled-6.7', SOURCE/'mass-6.7/layout.json', SOURCE/'trim-6.7-1/state.json'
    return FINE/'assembled', FINE/'mass-v3/layout.json', FINE/'trim-correct-v3/state.json'


def load(mesh):
    import numpy as np
    import scipy.sparse as sp
    from openswing.harmonic_structure import ReusableBeamStructure
    folder, layout_file, seed_file = paths(mesh); layout = read(layout_file)
    a, m = (sp.load_npz(folder/name) for name in ('A.npz', 'M.npz'))
    with np.load(folder/'maps.npz') as maps: b, c = maps['B'][:, 0], maps['C']
    for matrix in (a, m):
        for v in (matrix.data, matrix.indices, matrix.indptr): v.flags.writeable = False
    nn, ne = layout['nodes'], layout['elements']; gs = layout['circulation']['start']
    velocities = np.arange(layout['local_velocity']['start'], layout['frame']['start'])
    structure = ReusableBeamStructure(a, m, np.r_[np.arange(6*ne), np.arange(6*(nn+ne), gs)],
        np.arange(6*(nn+ne)), velocities, velocities)
    return a, m, b, c, layout, read(seed_file), structure


def factor_at(a, m, s, structure):
    """Reuse one exact factor for the response and its s derivative."""
    import numpy as np
    import scipy.sparse as sp
    from scipy.sparse.linalg import LinearOperator, onenormest
    k = (s*m-a).tocsc(); k.sum_duplicates(); k.eliminate_zeros()
    rows = np.maximum(abs(k).max(axis=1).toarray().ravel(), 1e-30)
    rowed = sp.diags(1/rows)@k
    columns = np.maximum(abs(rowed).max(axis=0).toarray().ravel(), 1e-30)
    norm = float(abs(rowed@sp.diags(1/columns)).sum(axis=0).max()); del rowed
    factor = structure.factor(a, m, s, rows, columns)
    inverse = LinearOperator(k.shape, matvec=factor.solve, matmat=factor.solve,
        rmatvec=lambda x: factor.solve(x, trans='H'), rmatmat=lambda x: factor.solve(x, trans='H'), dtype=complex)
    rcond = float(1/(norm*onenormest(inverse, t=1))); assert rcond >= 1e-10, rcond
    def solve(rhs):
        rhs = np.asarray(rhs, complex)
        z = factor.solve(rhs/rows)/columns
        z += factor.solve((rhs-k@z)/rows)/columns
        residual = k@z-rhs
        backward = float(np.linalg.norm(residual)/(np.linalg.norm(k.data)*np.linalg.norm(z)+np.linalg.norm(rhs)+1e-30))
        scaled = float(max(abs(residual)/rows)/max(1., max(abs(rhs)/rows)))
        assert backward <= 1e-9 and scaled <= 1e-7 and np.isfinite(z).all(), (backward, scaled)
        return z, dict(backward_error=backward, scaled_residual=scaled, reciprocal_condition=rcond,
            absolute_residual=float(max(abs(residual))), factor_dimension=factor.dimension)
    return solve


def euler(seed):
    import numpy as np
    phi, theta, _ = np.deg2rad(seed['launch']['condition']['attitude'])
    return np.array([[-1., 0., np.sin(theta)], [0., np.cos(phi), np.sin(phi)*np.cos(theta)],
        [0., np.sin(phi), -np.cos(phi)*np.cos(theta)]])


def samples(folder, args):
    import csv
    import numpy as np
    from openswing.frequency_response import harmonic_solve
    a, m, b, c, layout, seed, structure = load(args['mesh'])
    # Obtain the alternate attitude without changing this aircraft or pencil.
    alternate = read(paths('fine' if args['mesh']=='coarse' else 'coarse')[2])
    E = euler(seed); Ea = euler(alternate)
    fs = layout['frame']['start']; W = layout['local_rates']['scale']
    np.testing.assert_allclose(-W*m[fs+9:fs+12, fs+9:fs+12].toarray(), E, atol=2e-13, rtol=0)
    with (SOURCE/'report/comparison.csv').open() as stream: earlier = list(csv.DictReader(stream))
    comparison = read(FINE/'comparison/result.json')
    rows = []; states = []; outputs = []; rate_rows = []; reused = 0; solves = 0
    for f in FREQUENCIES:
        tag = 'response-neighbors' if f in (.1, 1., 1.1) else 'response-final'
        saved = FINE/tag/f'state-{f:.9g}.npz'
        if args['mesh']=='fine' and saved.exists():
            with np.load(saved) as data: z = data['state']; saved_output = data['output']
            checks = dict(reused_source=str(saved.relative_to(ROOT))); reused += 1
            assert max(abs(c@z-saved_output)) < 2e-12
        else:
            z, checks = harmonic_solve(a, m, b, 2*np.pi*f, _structure=structure); solves += 1
        residual = float(max(abs((2j*np.pi*f*m-a)@z-b))); assert residual < 2e-9, residual
        output = c@z; omega = W*z[fs+3:fs+6]
        reconstructed = np.linalg.solve(E, omega)[0]/(2j*np.pi*f)*180/np.pi
        alternate_bank = np.linalg.solve(Ea, omega)[0]/(2j*np.pi*f)*180/np.pi
        assert abs(reconstructed-output[3]) < 2e-10
        assert max(abs(omega[[2, 0]]*180/np.pi-output[[0, 1]])) < 2e-12
        if args['mesh']=='coarse':
            for row in [r for r in earlier if abs(float(r['frequency_hz'])-f)<1e-12]:
                expected = complex(float(row['real_display']), float(row['imag_display']))
                assert abs(output[CHANNELS.index(row['channel'])]-expected) < 2e-10
        rows.append(dict(frequency_hz=f, magnitudes=abs(output).tolist(), full_residual=residual,
            bank_reconstruction_error=float(abs(reconstructed-output[3])),
            alternate_attitude_bank=[float(alternate_bank.real), float(alternate_bank.imag)],
            alternate_attitude_bank_complex_change_percent=float(100*abs(alternate_bank-output[3])/abs(output[3])),
            checks=checks))
        states.append(z); outputs.append(output); rate_rows.append(omega)
    np.savez_compressed(folder/'arrays.npz', frequencies=np.array(FREQUENCIES), states=np.array(states),
        outputs=np.array(outputs), body_rates=np.array(rate_rows), euler_matrix=E, alternate_euler_matrix=Ea)
    return dict(mesh=args['mesh'], size=len(b), samples=rows, new_full_solves=solves, reused_states=reused,
        attitude_degrees=seed['launch']['condition']['attitude'],
        qualification='Only the bank readout is recalculated using the other trim attitude. This isolates that kinematic conversion; it does not remove equilibrium changes from the dynamic matrices.')


def locate(folder, args):
    import numpy as np
    a, m, b, c, layout, seed, structure = load(args['mesh']); ci = CHANNELS.index(args['channel'])
    if args['source']:
        previous = read(STUDY/args['source']/'result.json')
        assert previous['mesh']==args['mesh'] and previous['channel']==args['channel']
        s = complex(*previous['next_candidate']); iteration = previous['last_iteration']+1
    else:
        reference = 'yaw-verify' if args['channel']=='yaw_rate' else 'roll-verify'
        s = complex(*read(ZEROS/reference/'result.json')['zero']); iteration = 0
    history = []; accepted = False
    for _ in range(2):
        solve = factor_at(a, m, s, structure)
        z, first = solve(b); derivative, second = solve(m@z)
        output = c@z; hprime = -(c[ci]@derivative)
        assert abs(hprime)>1e-8
        step = output[ci]/hprime
        history.append(dict(iteration=iteration, s=[s.real, s.imag], output=[output[ci].real, output[ci].imag],
            output_magnitude=float(abs(output[ci])), derivative=[hprime.real, hprime.imag],
            next_step=[step.real, step.imag], response_checks=first, derivative_checks=second))
        accepted = bool(abs(output[ci])<1e-10 and abs(step)<2e-8)
        evaluated = s
        if accepted: break
        assert abs(step)<2. and (s-step).imag>0, step
        s -= step; iteration += 1
        del solve
    np.savez_compressed(folder/'arrays.npz', state=z, output=output, s=np.array(evaluated), transfer_derivative=np.array(hprime))
    return dict(mesh=args['mesh'], channel=args['channel'], converged=accepted, history=history,
        last_iteration=history[-1]['iteration'], evaluated_s=[evaluated.real, evaluated.imag], next_candidate=[s.real, s.imag],
        imaginary_frequency_hz=float(evaluated.imag/(2*np.pi)),
        qualification='A locally tracked transmission zero, not a natural pole or a complete zero census. Complex-s full-state solves use the published descriptor; no response curve, mode count or aircraft property is fitted.')


def verify(folder, args):
    import numpy as np
    a, m, b, c, layout, seed, structure = load(args['mesh']); ci = CHANNELS.index(args['channel'])
    result = read(STUDY/args['source']/'result.json')
    assert result['converged'] and result['mesh']==args['mesh'] and result['channel']==args['channel']
    s = complex(*result['evaluated_s'])
    with np.load(STUDY/args['source']/'arrays.npz') as data:
        expected = complex(data['transfer_derivative']); z = data['state']; output = data['output']
    checks = []
    # A symmetric derivative along the imaginary direction is independent of
    # the analytic M-resolvent derivative used by Newton.
    for width in (args['width'],):
        values = []
        for sign in (-1, 1):
            solve = factor_at(a, m, s+sign*1j*width, structure)
            state, diagnostic = solve(b); values.append(c[ci]@state)
            checks.append(dict(width=width, sign=sign, solve_checks=diagnostic)); del solve
        numerical = (values[1]-values[0])/(2j*width)
        error = float(abs(numerical-expected)/abs(expected)); assert error < 2e-6, error
        checks[-1]['derivative_relative_error'] = error
    residual = float(np.linalg.norm((s*m-a)@z-b)/(np.linalg.norm(b)+np.linalg.norm((s*m-a)@z)))
    assert residual < 1e-9 and abs(output[ci]) < 1e-10
    return dict(mesh=args['mesh'], channel=args['channel'], zero=[s.real, s.imag],
        full_residual_relative=residual, output_magnitude=float(abs(output[ci])), derivative_checks=checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['samples', 'locate', 'verify']); parser.add_argument('--tag', required=True)
    parser.add_argument('--mesh', choices=['coarse', 'fine'], required=True)
    parser.add_argument('--channel', choices=['yaw_rate', 'roll_rate', 'bank'], default='roll_rate')
    parser.add_argument('--width', type=float, choices=[1e-4, 5e-5], default=1e-4)
    parser.add_argument('--source'); args = vars(parser.parse_args())
    folder, layout, seed = paths(args['mesh'])
    inputs = [folder/p for p in ('A.npz', 'M.npz', 'maps.npz')]
    inputs += [layout, seed, ROOT/'docs/validation/ISAE_STATUS.md', ROOT/'examples/dae.asw',
        ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']
    inputs += list((ROOT/'openswing').glob('*.py'))
    if args['stage']=='samples':
        inputs += [paths('fine' if args['mesh']=='coarse' else 'coarse')[2],
            SOURCE/'report/comparison.csv', FINE/'comparison/result.json']
        for tag in ('response-neighbors', 'response-final'): inputs += list((FINE/tag).glob('state-*.npz'))
    elif args['source']:
        inputs += [STUDY/args['source']/p for p in ('result.json', 'arrays.npz', 'terminal.json')]
    else:
        assert args['stage']=='locate'
        inputs += [ZEROS/tag/'result.json' for tag in ('roll-verify', 'yaw-verify')]
    run(STUDY, args['tag'], inputs, globals()[args['stage']], args, __file__)


if __name__ == '__main__': main()
