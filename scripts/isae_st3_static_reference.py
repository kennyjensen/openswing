"""Independent continuous Kirchhoff rod for the archived ST-3 static setup.

No OpenSwing imports or fitted properties. Body coordinates are x/aft, y/span,
z/up; the undeformed material frame is the identity. F>0 acts down; M>0
is a downward/upward dead-force pair on the two rotating chord edges.
"""
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import root
from scipy.spatial.transform import Rotation

LENGTH = .558
CHORD = .14
EA = 1.132e7
PROPERTIES = {
    '0_3_90': (1.42, 1.2, 1.85e4, 0.),
    'p15_0': (1.2947, 1.2, 2.2775e4, .5151),
    'm15_0': (1.2947, 1.2, 2.2775e4, -.5151),
}


def stiffness(name):
    ei, gj, inn, cs = PROPERTIES[name]
    return np.array([[ei, cs, 0.], [cs, gj, 0.], [0., 0., inn]])


def observables(position, q):
    """Dunn displacement and both explicitly distinguished rotation measures."""
    span = q[:, 1]
    phi = np.arctan2(span[2], span[1])
    psi = -np.arcsin(np.clip(span[0], -1., 1.))
    c0 = np.array([np.cos(psi), np.sin(psi)*np.cos(phi), np.sin(psi)*np.sin(phi)])
    n0 = np.array([0., -np.sin(phi), np.cos(phi)])
    theta = np.arctan2(-q[:, 0]@n0, q[:, 0]@c0)
    projected = np.arctan2(-q[2, 0], np.hypot(q[0, 0], q[1, 0]))
    return dict(h_m=float(-position[2]), theta_dunn_deg=float(-np.rad2deg(theta)),
                twist_asw_deg=float(np.rad2deg(theta)),
                chord_vertical_dunn_deg=float(-np.rad2deg(projected)))


def solve(name, force=0., couple=0., *, rtol=2e-11, atol=2e-13, stations=None):
    """Shoot equilibrium r'=Q e_y(1+n_s/EA), m'=-r' cross n, Q'=Q[k]x."""
    compliance = np.linalg.inv(stiffness(name))
    n = np.array([0., 0., -force])
    def rhs(s, state):
        quat = state[3:7]
        q = Rotation.from_quat(quat).as_matrix()
        tangent = q[:, 1]
        dr = tangent*(1.+tangent@n/EA)
        k = compliance@(q.T@state[7:])
        # Quaternion stored [vector, scalar]; right multiplication by [k,0].
        dq = .5*np.r_[quat[3]*k+np.cross(quat[:3], k), -quat[:3]@k]
        return np.r_[dr, dq, -np.cross(dr, n)]
    def integrate(moment, dense=False):
        initial = np.r_[np.zeros(3), [0., 0., 0., 1.], moment]
        sol = solve_ivp(rhs, [0., LENGTH], initial, method='DOP853',
                        rtol=rtol, atol=atol, dense_output=dense)
        assert sol.success, sol.message
        return sol
    def target(state):
        chord = Rotation.from_quat(state[3:7]).as_matrix()[:, 0]
        return np.cross(chord, [0., 0., couple])
    def mismatch(moment):
        end = integrate(moment).y[:, -1]
        return end[7:]-target(end)
    guess = np.cross([0., LENGTH, 0.], n)+[0., -couple, 0.]
    optimum = root(mismatch, guess, method='hybr', options={'xtol': 2e-10})
    error = float(np.max(abs(mismatch(optimum.x))))
    assert error < 2e-10, (optimum.message, error)
    solution = integrate(optimum.x, True)
    s = np.linspace(0., LENGTH, 65) if stations is None else np.asarray(stations)
    states = solution.sol(s).T
    rotations = Rotation.from_quat(states[:, 3:7]).as_matrix()
    qerror = float(np.max(abs(np.linalg.norm(states[:, 3:7], axis=1)-1)))
    assert qerror < 2e-9
    return dict(name=name, force_N=force, couple_Nm=couple,
                boundary_residual_Nm=error, quaternion_norm_error=qerror,
                root_internal_moment=optimum.x.tolist(),
                stations_m=s.tolist(), positions=states[:, :3].tolist(),
                rotations=rotations.tolist(), internal_moments=states[:, 7:].tolist(),
                observables=observables(states[-1, :3], rotations[-1]),
                rtol=rtol, atol=atol)
