"""Independent continuous-rod reference for the simplified ISAE Pazy inputs.

No OpenSwing imports, fitted properties, shared force assembly or mesh. The
force is integrated analytically; quaternion kinematics and spatial moment
balance are integrated by DOP853, with a shooting condition at the tip pylon.
"""
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import root
from scipy.spatial.transform import Rotation

LENGTH = .55
MASS_PER_LENGTH = .3745
GRAVITY = 9.81


def compliance(kind, outboard):
    gj = 6.5 * (2.6 if kind == 'torsion' and outboard else 1.)
    coupling = -.12 if kind == 'torsion' else 0.
    b = np.linalg.inv([[4.4, 0., coupling], [0., gj, 0.], [coupling, 0., 3300.]])
    cea = -.005 if kind == 'torsion' else 0.
    h = np.array([[0., 0., 0.], [0., 0., cea], [0., 0., 0.]])
    return np.block([[np.diag([0., 1 / 9.6e6, 0.]) + h.T @ b @ h, h.T @ b],
                     [b @ h, b]])


def solve(kind, mass, point, *, stations=None, rtol=2e-11, atol=2e-13):
    assert kind in ('bending', 'torsion')
    point = np.asarray(point)
    pylon = point - [0., LENGTH, 0.]
    ftip = np.array([0., 0., -GRAVITY * mass])
    distributed = np.array([0., 0., -GRAVITY * MASS_PER_LENGTH])
    boundaries = [0., .52, LENGTH] if kind == 'torsion' else [0., LENGTH]
    matrices = [compliance(kind, i == 1) for i in range(len(boundaries) - 1)]

    def integrate(moment, dense=False):
        initial = np.r_[np.zeros(3), [0., 0., 0., 1.], moment]
        pieces = []
        for a, b, sm in zip(boundaries[:-1], boundaries[1:], matrices):
            def rhs(s, state):
                quat = state[3:7]
                q = Rotation.from_quat(quat).as_matrix()
                force = ftip + (LENGTH - s) * distributed
                strain = sm @ np.r_[q.T @ force, q.T @ state[7:]]
                dr = q @ (np.array([0., 1., 0.]) + strain[:3])
                k = strain[3:]
                dq = .5 * np.r_[quat[3] * k + np.cross(quat[:3], k), -quat[:3] @ k]
                return np.r_[dr, dq, -np.cross(dr, force)]
            sol = solve_ivp(rhs, [a, b], initial, method='DOP853', rtol=rtol, atol=atol, dense_output=dense)
            assert sol.success, sol.message
            initial = sol.y[:, -1]
            pieces.append(sol)
        return pieces

    def mismatch(moment):
        end = integrate(moment)[-1].y[:, -1]
        q = Rotation.from_quat(end[3:7]).as_matrix()
        return end[7:] - np.cross(q @ pylon, ftip)

    guess = np.cross([0., LENGTH, 0.], ftip) + np.cross([0., LENGTH / 2, 0.], LENGTH * distributed) + np.cross(pylon, ftip)
    answer = root(mismatch, guess, method='hybr', options={'xtol': 2e-10})
    error = float(np.max(abs(mismatch(answer.x))))
    assert error < 2e-9, (answer.message, error)
    pieces = integrate(answer.x, True)
    s = np.linspace(0., LENGTH, 101) if stations is None else np.asarray(stations)
    states = np.array([pieces[min(np.searchsorted(boundaries[1:], x, side='left'), len(pieces)-1)].sol(x) for x in s])
    qerr = float(np.max(abs(np.linalg.norm(states[:, 3:7], axis=1) - 1)))
    assert qerr < 2e-9
    return dict(kind=kind, mass_kg=mass, point_xyz_m=point.tolist(), boundary_error_Nm=error,
        quaternion_norm_error=qerr, rtol=rtol, atol=atol, stations_m=s.tolist(),
        positions=states[:, :3].tolist(), rotations=Rotation.from_quat(states[:, 3:7]).as_matrix().tolist(),
        moments=states[:, 7:].tolist(), root_internal_moment=answer.x.tolist())
