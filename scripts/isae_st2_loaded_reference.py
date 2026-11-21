"""Independent continuous-rod modal reference for the literal ST-2 modal wing.

No OpenSwing imports or native-frequency calibration. On the common elastic,
tension and CG axis, integrate the geometrically exact unshearable rod under
self-weight. Linearize its spatial first-order equations analytically and use
midpoint collocation. Retain axial extension, all spatial rotations, initial
force/moment terms, rotary inertia and optional still-air inertia.

Sources: ASWING Technical Description equations 19--20 and 46--47; Unsteady
Formulation equations 39--44. This continuum reference deliberately uses a
different discretization and coordinate chart from the production residual.
"""
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import root
from scipy.sparse import coo_matrix, diags
from scipy.sparse.linalg import LinearOperator, eigs, norm, splu
from scipy.spatial.transform import Rotation

LENGTH = .55
BREAK = .52
MASS = .6787
EA = 9.6e6
ICC = 6.9567e-5
INN = 4.2793e-4
CHORD = .1
ARM = .005  # elastic/CG axis -> midchord, along +c
STIFFNESS = [np.array([[4.4, 0., -.12], [0., gj, 0.], [-.12, 0., 3300.]])
             for gj in (6.5, 6.5 * 2.6)]
COMPLIANCE = [np.linalg.inv(k) for k in STIFFNESS]


def skew(v):
    x, y, z = v
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


def mesh(elements):
    if not isinstance(elements, int) or isinstance(elements, bool) or elements < 2:
        raise ValueError('At least two integer elements are required.')
    left = min(elements - 1, max(1, round(elements * BREAK / LENGTH)))
    return np.r_[np.linspace(0., BREAK, left + 1),
                 np.linspace(BREAK, LENGTH, elements - left + 1)[1:]]


def equilibrium(gravity=(0., 0., -9.81), *, root_frame=None,
                rtol=2e-12, atol=2e-14):
    """Quaternion shooting; positions are relative to the clamped CG axis."""
    gravity = np.asarray(gravity, dtype=float)
    frame = np.eye(3) if root_frame is None else np.asarray(root_frame, dtype=float)
    if gravity.shape != (3,) or not np.all(np.isfinite(gravity)):
        raise ValueError('Gravity must contain three finite components.')
    if frame.shape != (3, 3) or not np.allclose(frame.T @ frame, np.eye(3), atol=1e-12) or np.linalg.det(frame) < 0:
        raise ValueError('Root frame must be a proper rotation.')
    load = MASS * gravity

    def integrate(moment, dense=False):
        initial = np.r_[np.zeros(3), Rotation.from_matrix(frame).as_quat(), moment]
        pieces = []
        for a, b, compliance in zip((0., BREAK), (BREAK, LENGTH), COMPLIANCE):
            def rhs(s, state):
                quat = state[3:7]
                rotation = Rotation.from_quat(quat).as_matrix()
                force = (LENGTH - s) * load
                tangent = rotation[:, 1]
                dr = tangent * (1 + tangent @ force / EA)
                curvature = compliance @ (rotation.T @ state[7:10])
                dq = .5 * np.r_[quat[3] * curvature + np.cross(quat[:3], curvature),
                                -quat[:3] @ curvature]
                return np.r_[dr, dq, -np.cross(dr, force)]
            solution = solve_ivp(rhs, (a, b), initial, method='DOP853',
                                 rtol=rtol, atol=atol, dense_output=dense)
            if not solution.success:
                raise RuntimeError(solution.message)
            pieces.append(solution)
            initial = solution.y[:, -1]
        return pieces

    def mismatch(moment):
        return integrate(moment)[-1].y[7:10, -1]

    guess = np.cross(.5 * LENGTH * frame[:, 1], LENGTH * load)
    answer = root(mismatch, guess, method='hybr', options={'xtol': 2e-10})
    error = float(np.max(abs(mismatch(answer.x))))
    if error > 2e-10:
        raise RuntimeError(f'Nonzero free-tip moment: {error}; {answer.message}')
    pieces = integrate(answer.x, True)

    def sample(stations):
        stations = np.asarray(stations, dtype=float)
        if stations.ndim != 1 or np.any(stations < 0) or np.any(stations > LENGTH):
            raise ValueError('Stations must lie on the beam.')
        state = np.array([pieces[0 if s <= BREAK else 1].sol(s) for s in stations])
        return dict(positions=state[:, :3], rotations=Rotation.from_quat(state[:, 3:7]).as_matrix(),
                    moments=state[:, 7:10], forces=(LENGTH - stations[:, None]) * load,
                    quaternion_norm_error=float(np.max(abs(np.linalg.norm(state[:, 3:7], axis=1) - 1))))

    return dict(sample=sample, gravity=gravity, root_frame=frame,
                root_moment=answer.x, free_tip_moment_error=error, rtol=rtol, atol=atol)


def section_inertia(s, rotation, density):
    """Physical 6x6 kinetic-energy matrix for [CG velocity, spatial omega]."""
    if not np.isfinite(density) or density < 0:
        raise ValueError('Fluid density must be finite and nonnegative.')
    inn = INN + max(0., (s - BREAK) / (LENGTH - BREAK)) * (.0041 - INN)
    inertia = np.zeros((6, 6))
    inertia[:3, :3] = MASS * np.eye(3)
    inertia[3:, 3:] = rotation @ np.diag([ICC, ICC + inn, inn]) @ rotation.T
    if density:
        c, tangent, normal = rotation.T
        direction = np.r_[normal, np.cross(ARM * c, normal)]
        pitch = np.r_[np.zeros(3), tangent]
        mu = density * np.pi * CHORD ** 2 / 4
        inertia += mu * np.outer(direction, direction)
        inertia += mu * CHORD ** 2 / 32 * np.outer(pitch, pitch)
    return inertia


def local_matrices(s, rotation, force, moment, density):
    """Y' = H Y - omega^2 J Y; Y = [u, theta, delta F, delta M]."""
    tangent = rotation[:, 1]
    derivative = tangent * (1 + tangent @ force / EA)
    axial = np.outer(tangent, tangent) / EA
    curvature = rotation @ COMPLIANCE[int(s > BREAK)] @ rotation.T
    ptheta = -skew(derivative) + axial @ skew(force)
    h = np.zeros((12, 12))
    h[:3, 3:6] = ptheta
    h[:3, 6:9] = axial
    h[3:6, 3:6] = curvature @ skew(moment)
    h[3:6, 9:12] = curvature
    h[9:12, 3:6] = skew(force) @ ptheta
    h[9:12, 6:9] = skew(force) @ axial - skew(derivative)
    j = np.zeros((12, 12))
    j[6:12, :6] = section_inertia(s, rotation, density)
    return h, j


def pencil(elements=192, gravity=(0., 0., -9.81), *, density=0., root_frame=None, base=None):
    """Full mixed boundary-value pencil A Y = omega^2 B Y, scaled for solves."""
    # Validate density even if assembly is later generalized to empty subsets.
    section_inertia(0., np.eye(3), density)
    nodes = mesh(elements)
    base = equilibrium(gravity, root_frame=root_frame) if base is None else base
    midpoints = (nodes[:-1] + nodes[1:]) / 2
    states = base['sample'](midpoints)
    size = 12 * len(nodes)
    ai, aj, av, bi, bj, bv = [], [], [], [], [], []

    def append(rows, columns, values, target):
        ii, jj = np.nonzero(values)
        target[0].extend(rows[ii].tolist())
        target[1].extend(columns[jj].tolist())
        target[2].extend(values[ii, jj].tolist())

    # First six rows clamp displacement and spatial rotation at the root.
    ai.extend(range(6)); aj.extend(range(6)); av.extend(np.ones(6))
    for e, (a, b) in enumerate(zip(nodes[:-1], nodes[1:])):
        h, j = local_matrices(midpoints[e], states['rotations'][e], states['forces'][e], states['moments'][e], density)
        rows = 6 + 12 * e + np.arange(12)
        for side, sign in ((0, 1.), (1, -1.)):
            columns = 12 * (e + side) + np.arange(12)
            append(rows, columns, sign * np.eye(12) + .5 * (b - a) * h, (ai, aj, av))
            append(rows, columns, .5 * (b - a) * j, (bi, bj, bv))
    ai.extend(range(size - 6, size)); aj.extend(range(size - 6, size)); av.extend(np.ones(6))
    a = coo_matrix((av, (ai, aj)), shape=(size, size)).tocsc()
    b = coo_matrix((bv, (bi, bj)), shape=(size, size)).tocsc()
    component_scale = np.r_[np.full(3, LENGTH), np.ones(3),
                            np.full(3, 4.4 / LENGTH ** 2), np.full(3, 4.4 / LENGTH)]
    column_scale = np.tile(component_scale, len(nodes))
    row_scale = 1 / np.r_[component_scale[:6], np.tile(component_scale, elements), component_scale[6:]]
    a = (diags(row_scale) @ a @ diags(column_scale)).tocsc()
    b = (diags(row_scale) @ b @ diags(column_scale)).tocsc()
    return dict(A=a, B=b, nodes=nodes, column_scale=column_scale,
                row_scale=row_scale, base=base, density=density)


def modes(elements=192, gravity=(0., 0., -9.81), count=8, *, density=0., root_frame=None):
    assembled = pencil(elements, gravity, density=density, root_frame=root_frame)
    a, b = assembled['A'], assembled['B']
    factor = splu(a)
    # B is singular. Apply A^-1 B as an ordinary operator, never as a positive
    # ARPACK metric. Its nonzero eigenvalues are 1 / omega^2.
    operator = LinearOperator(a.shape, matvec=lambda x: factor.solve(b @ x), dtype=float)
    values, vectors = eigs(operator, k=count, which='LM', tol=1e-12,
                           ncv=min(a.shape[0], max(40, 4 * count + 1)), maxiter=3000,
                           v0=np.random.default_rng(531).normal(size=a.shape[0]))
    squared = 1 / values
    if np.max(abs(squared.imag) / abs(squared)) > 1e-9 or np.any(squared.real <= 0):
        raise RuntimeError(f'Reference is not a stable real spectrum: {squared}')
    order = np.argsort(squared.real)
    squared, vectors = squared.real[order], vectors[:, order]
    residual = a @ vectors - (b @ vectors) * squared
    backward = np.max(abs(residual), axis=0) / ((norm(a, np.inf) + squared * norm(b, np.inf)) * np.max(abs(vectors), axis=0))
    if np.max(backward) > 1e-10:
        raise RuntimeError(f'Full reference pencil residual failed: {backward}')
    physical = (assembled['column_scale'][:, None] * vectors).T.reshape(count, -1, 12)
    # The undamped, stable reference has real physical modes. Preserve and
    # check the small imaginary remainder before storing real shapes.
    shapes = []
    for vector in physical:
        vector = vector * np.exp(-1j * np.angle(vector.ravel()[np.argmax(abs(vector))]))
        if np.max(abs(vector.imag)) > 1e-9 * np.max(abs(vector.real)):
            raise RuntimeError('Complex shape in an undamped stable reference.')
        vector = vector.real
        vector /= np.max(abs(vector[:, :6]))
        shapes.append(vector[:, :6].tolist())
    states = assembled['base']['sample'](assembled['nodes'])
    return dict(elements=elements, nodes=assembled['nodes'].tolist(),
        gravity=assembled['base']['gravity'].tolist(), root_frame=assembled['base']['root_frame'].tolist(),
        fluid_density=density, frequencies_Hz=(np.sqrt(squared) / (2 * np.pi)).tolist(),
        shapes=shapes, eigen_backward_errors=backward.tolist(),
        base={k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in states.items()},
        free_tip_moment_error=assembled['base']['free_tip_moment_error'],
        root_moment=assembled['base']['root_moment'].tolist(),
        eigensolver='Ordinary sparse A^-1 B shift-invert on the complete mixed rod pencil',
        scope='Continuous unshearable elastic/CG-axis rod with axial extension, exact prestress linearization and real/still-air inertia; no OpenSwing imports.')
