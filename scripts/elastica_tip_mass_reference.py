"""Independent first-branch planar elastica with a massless rod and tip mass.

The elliptic-integral length condition chooses the branch connected to a
positive lateral load. Nonlinear arclength integration and its analytic force
sensitivities give the full tip compliance and both finite vibration modes.
No OpenSwing code, discretization or target spectrum is imported.
"""
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq
from scipy.special import ellipk, ellipkinc


def solve(compression, transverse, *, length=2., ei=100., mass=1., stations=None):
    if (not np.all(np.isfinite([compression, transverse, length, ei, mass]))
            or compression < 0 or transverse == 0 or min(length, ei, mass) <= 0):
        raise ValueError('Finite nonnegative compression, nonzero transverse force and positive parameters are required.')
    stations = np.linspace(0., length, 513) if stations is None else np.asarray(stations, dtype=float)
    if stations.ndim != 1 or np.any(stations < 0) or np.any(stations > length):
        raise ValueError('Stations must lie on the rod.')
    force = np.array([-compression, transverse])
    magnitude = float(np.linalg.norm(force))
    delta = np.arctan2(abs(transverse), compression)
    lower = np.sin(delta / 2)
    target = length * np.sqrt(magnitude / ei)

    def length_condition(k):
        start_angle = np.arcsin(np.clip(lower / k, 0., 1.))
        return ellipk(k * k) - ellipkinc(start_angle, k * k) - target

    k = brentq(length_condition, lower, np.nextafter(1., 0.), xtol=2e-14, rtol=8e-15)
    root_moment = np.sign(transverse) * 2 * np.sqrt(ei * magnitude) * np.sqrt(k * k - lower * lower)
    tip_angle = np.sign(transverse) * (2 * np.arcsin(k) - delta)
    # State [y,z,theta,M], plus sensitivities to root M, applied Fy and Fz.
    initial = np.zeros(16); initial[3] = root_moment
    initial[4:].reshape(4, 3)[3, 0] = 1.

    def rhs(s, state):
        y, z, angle, moment = state[:4]
        sy, sz = np.cos(angle), np.sin(angle)
        sensitivity = state[4:].reshape(4, 3)
        derivative = np.empty_like(sensitivity)
        derivative[0] = -sz * sensitivity[2]
        derivative[1] = sy * sensitivity[2]
        derivative[2] = sensitivity[3] / ei
        derivative[3] = (force[0] * sy + force[1] * sz) * sensitivity[2] + [0., sz, -sy]
        return np.r_[sy, sz, moment / ei, force[0] * sz - force[1] * sy, derivative.ravel()]

    solution = solve_ivp(rhs, (0., length), initial, method='DOP853', rtol=2e-12, atol=2e-14, dense_output=True)
    if not solution.success: raise RuntimeError(solution.message)
    tip = solution.sol(length)
    boundary_error = float(abs(tip[3]))
    if boundary_error > 2e-9 * max(1., magnitude * length):
        raise RuntimeError(f'Free-tip moment failed: {boundary_error}')
    if abs(tip[2] - tip_angle) > 1e-10:
        raise RuntimeError('Elliptic and integrated tip angles disagree.')
    tip_sensitivity = tip[4:].reshape(4, 3)
    correction = -tip_sensitivity[3, 1:] / tip_sensitivity[3, 0]
    states = solution.sol(stations).T
    sensitivities = states[:, 4:].reshape(-1, 4, 3)
    responses = sensitivities[:, :, 1:] + sensitivities[:, :, :1] * correction
    tip_response = tip_sensitivity[:, 1:] + tip_sensitivity[:, :1] * correction
    compliance = tip_response[:2]
    reciprocity = float(np.max(abs(compliance - compliance.T)) / np.max(abs(compliance)))
    if reciprocity > 1e-9:
        raise RuntimeError(f'Tip compliance is not reciprocal: {reciprocity}')
    values, vectors = np.linalg.eig(compliance)
    # The eigensolver may return a complex dtype for exactly real quantities.
    # Check values, not their storage type; retain a strict nonreal rejection.
    if np.any(values.imag != 0) or np.any(vectors.imag != 0) or np.any(values.real <= 0):
        raise RuntimeError(f'Primary branch is not stable: {values}')
    values, vectors = values.real, vectors.real
    order = np.argsort(values)[::-1]; values = values[order]; vectors = vectors[:, order]
    shapes = []
    for c, vector in zip(values, vectors.T):
        vector = vector * np.sign(vector[np.argmax(abs(vector))])
        shape = responses @ (vector / c)
        geometry = np.zeros((len(stations), 6))
        geometry[:, 1:3] = shape[:, :2]
        geometry[:, 3] = shape[:, 2]
        shapes.append(geometry.tolist())
    first_integral = states[:, 3] ** 2 / (2 * ei) + force[0] * np.cos(states[:, 2]) + force[1] * np.sin(states[:, 2])
    return dict(compression=compression, transverse=transverse, length=length, EI=ei, tip_mass=mass,
        stations=stations.tolist(), positions=np.column_stack([np.zeros(len(stations)), states[:, :2]]).tolist(),
        angles=states[:, 2].tolist(), moments=states[:, 3].tolist(), root_moment=float(root_moment),
        elliptic_parameter=float(k * k), elliptic_length_residual=float(length_condition(k)),
        free_tip_moment_error=boundary_error, reciprocity_error=reciprocity,
        energy_first_integral_error=float(np.max(abs(first_integral - first_integral[0]))),
        compliance=compliance.tolist(), angular_frequencies=(1 / np.sqrt(mass * values)).tolist(),
        shapes=shapes, force_sensitivities=responses.tolist(),
        scope='Primary stable planar elastica branch under a dead tip load; massless inextensible rod, two tip-translation modes.')
