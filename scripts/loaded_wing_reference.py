"""Independent spatial rod integration and kinetic-energy quadrature.

Only physical arrays and documented material properties enter this module.
It imports no production geometry, beam, inertia, residual or modal code.
"""
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import root
from scipy.spatial.transform import Rotation


def hat(x):
    a, b, c = x
    return np.array([[0., -c, b], [c, 0., -a], [-b, a, 0.]])


def compliance(table, nea=None):
    ecc, enn, ecn, gj = table['stiffness']
    b = np.linalg.inv([[ecc, 0., ecn], [0., gj, 0.], [ecn, 0., enn]])
    # Complementary energy: .5*(M+H F)^T B (M+H F).
    # Cta=Nta=0; extension/shear stiffnesses are exactly infinite.
    h = np.array([[0., 0., 0.], [-table['Nea_m'] if nea is None else -nea, 0., table['Cea_m']], [0., 0., 0.]])
    return np.block([[h.T@b@h, h.T@b], [b@h, b]])


def frozen_loads(case):
    base = case['base']
    r = np.array([n['position'] for n in base['nodes']])
    n = np.array([e['force'] for e in base['elements']])
    m = np.array([e['moment'] for e in base['elements']])
    f, torque = np.zeros_like(r), np.zeros_like(r)
    f[:-1] -= n
    f[1:] += n
    arm = np.cross(np.diff(r, axis=0), n)/2
    torque[:-1] -= m+arm
    torque[1:] += m-arm
    return f, torque


def continuum(s, S, force, torque, r0, R0, initial_moment, *, rtol=1e-10):
    """Clamped/free continuum under frozen spatial point wrenches at s[1:].

    Integrate r'=R v, R'=R hat(k), N'=0, M'=-r' cross N between
    point loads. Six root-wrench variations integrate the exact spatial tangent
    delta r, theta, delta N, delta M. Point wrenches are dead, so tangent fields
    are continuous across their jumps. No inverse of the singular S is needed.
    """
    initial_force = force[1:].sum(axis=0)
    evaluations = 0

    def integrate(moment):
        nonlocal evaluations
        y = np.r_[r0, R0.ravel(), initial_force, moment,
                  np.r_[np.zeros((6, 6)), np.eye(6)].ravel()]
        states = [y.copy()]

        def ode(_, value):
            R = value[3:12].reshape(3, 3)
            N, M = value[12:15], value[15:18]
            strain = S@np.r_[R.T@N, R.T@M]
            rp = R@(strain[:3]+[0., 1., 0.])
            d = value[18:].reshape(12, 6)
            th, dn, dm = d[3:6], d[6:9], d[9:12]
            ds = S@np.r_[R.T@(dn+hat(N)@th), R.T@(dm+hat(M)@th)]
            du = -hat(rp)@th+R@ds[:3]
            dt = R@ds[3:]
            dmoment = hat(N)@du-hat(rp)@dn
            return np.r_[rp, (R@hat(strain[3:])).ravel(), np.zeros(3), -np.cross(rp, N),
                         np.r_[du, dt, np.zeros((3, 6)), dmoment].ravel()]

        for j, (lo, hi) in enumerate(zip(s[:-1], s[1:]), 1):
            sol = solve_ivp(ode, (lo, hi), y, method='DOP853', rtol=rtol, atol=rtol*.01)
            assert sol.success, sol.message
            evaluations += sol.nfev
            y = sol.y[:, -1].copy()
            y[12:15] -= force[j]
            y[15:18] -= torque[j]
            states.append(y.copy())
        return np.array(states)

    cached = [None, None]

    def evaluate(moment):
        if cached[0] is None or not np.array_equal(moment, cached[0]):
            cached[:] = [moment.copy(), integrate(moment)]
        return cached[1]

    solution = root(lambda m: evaluate(m)[-1, 15:18], initial_moment,
                    jac=lambda m: evaluate(m)[-1, 18:].reshape(12, 6)[9:12, 3:6], tol=1e-10)
    states = evaluate(solution.x)
    error = np.max(abs(states[-1, 12:18]))
    assert error < 1e-9, (solution.message, error)
    fundamental = states[:, 18:].reshape(len(s), 12, 6)
    end = fundamental[-1, 6:12]
    root_map = np.linalg.solve(end, np.eye(6))
    response = fundamental@root_map
    rotations = states[:, 3:12].reshape(-1, 3, 3)
    assert np.max(abs(rotations.transpose(0, 2, 1)@rotations-np.eye(3))) < 1e-9
    return dict(position=states[:, :3], rotation=rotations, profile=response[:, :6],
                compliance=response[-1, :6], root_force=initial_force,
                root_moment=solution.x, free_end_error=float(error),
                tangent_end_error=float(np.max(abs(response[-1, 6:]-np.eye(6)))),
                boundary_condition_number=float(np.linalg.cond(end)), evaluations=evaluations, rtol=rtol)


def interpolate(ra, rb, fractions):
    arc = Rotation.from_matrix(ra.T@rb).as_rotvec()
    return ra@Rotation.from_rotvec(fractions[:, None]*arc).as_matrix()


def projected_mass(s, positions, rotations, fields, common, table, *, step=1e-5, quadrature=12):
    """Kinetic energy from differentiated physical section/CG positions.

    Fields have physical translations and spatial rotation increments at nodes.
    The interpolation derivative uses perturbed rotation matrices, independently
    of the production SO(3) Jacobian and virtual-power transfer implementation.
    """
    x, w = np.polynomial.legendre.leggauss(quadrature)
    fractions, weights = (x+1)/2, w/2
    count = fields.shape[-1]
    result = np.zeros((count, count))
    breaks = np.cumsum(common['segment_lengths_m'])
    for j, (lo, hi) in enumerate(zip(s[:-1], s[1:])):
        row = table['inertia'][min(np.searchsorted(breaks, (lo+hi)/2), len(breaks)-1)]
        mass, ccg, ncg, icc, inn = np.asarray(row)/[common['gravity_m_s2'], 1., 1., common['gravity_m_s2'], common['gravity_m_s2']]
        cg = np.array([ccg, 0., ncg])
        R = interpolate(rotations[j], rotations[j+1], fractions)
        velocity, omega = [], []
        for k in range(count):
            variation = fields[:, :, k]
            values = []
            for sign in (1., -1.):
                ends = positions[j:j+2]+sign*step*variation[j:j+2, :3]
                frames = Rotation.from_rotvec(sign*step*variation[j:j+2, 3:]).as_matrix()@rotations[j:j+2]
                frames = interpolate(*frames, fractions)
                center = (1-fractions[:, None])*ends[0]+fractions[:, None]*ends[1]
                values.append((center+frames@cg, frames))
            velocity.append((values[0][0]-values[1][0])/(2*step))
            spin = (values[0][1]-values[1][1])/(2*step)@R.transpose(0, 2, 1)
            omega.append(np.stack([spin[:, 2, 1]-spin[:, 1, 2], spin[:, 0, 2]-spin[:, 2, 0],
                                   spin[:, 1, 0]-spin[:, 0, 1]], axis=-1)/2)
        velocity, omega = np.asarray(velocity), np.asarray(omega)
        inertia = (R*np.array([icc, icc+inn, inn])[None, None, :])@R.transpose(0, 2, 1)
        result += (hi-lo)*np.einsum('g,agi,bgi->ab', weights*mass, velocity, velocity)
        result += (hi-lo)*np.einsum('g,agi,gij,bgj->ab', weights, omega, inertia, omega)
    return result
