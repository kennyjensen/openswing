"""Owned Euler histories for the source BDF time discretization.

Unsteady Eqs. 2--4, 14--15 and 123--125 difference the physical material
and aircraft Euler angles. Newton may still use local SO(3) trial charts;
only the accepted temporal derivative is defined here. This helper neither
evaluates mechanics nor changes the source spatial Euler-cut restrictions.
"""
import numpy as np

from .aero import AnalysisError


EULER_BDF_SCHEME = 'drela-euler-bdf-v1'
EULER_CHART = 'source-material-and-aircraft-euler-v1'
_POLE = 1e-8
_MATRIX_TOL = 2e-12
_JIG_TOL = 128*np.finfo(float).eps
_STEP_LIMIT = np.pi-.05
_FIELDS = ('source_angles', 'source_attitude')


def _array(value, shape, name):
    try:
        result = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as error:
        raise AnalysisError(f'Invalid source time {name}.') from error
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise AnalysisError(f'Source time {name} must have shape {shape} and finite values.')
    return result


def _rotations(value, shape, name):
    result = _array(value, shape, name)
    if (np.max(abs(np.swapaxes(result, -1, -2)@result-np.eye(3))) > _MATRIX_TOL
            or np.max(abs(np.linalg.det(result)-1)) > _MATRIX_TOL):
        raise AnalysisError(f'Source time {name} must contain proper rotation matrices.')
    return result


def surface_frame_from_angles(angles):
    """Steady Eq. 4 local-to-body surface frame; angles are radians."""
    q = np.asarray(angles, dtype=float)
    phi, theta, psi = np.moveaxis(q, -1, 0)
    cp, sp, ct, st, cs, ss = (np.cos(phi), np.sin(phi), np.cos(theta),
                              np.sin(theta), np.cos(psi), np.sin(psi))
    c0 = np.stack([cs, ss*cp, ss*sp], axis=-1)
    n0 = np.stack([np.zeros_like(phi), -sp, cp], axis=-1)
    span = np.stack([-ss, cs*cp, cs*sp], axis=-1)
    return np.stack([c0*ct[..., None]-n0*st[..., None], span,
                     c0*st[..., None]+n0*ct[..., None]], axis=-1)


def _surface_angles(frame):
    # Same principal Eq. 4 chart as source_discrete.angles_from_frame, with
    # atan2 instead of asin for psi to retain accuracy near the chart pole.
    span = frame[..., :, 1]
    phi = np.arctan2(span[..., 2], span[..., 1])
    horizontal = np.hypot(span[..., 1], span[..., 2])
    if np.any(horizontal < _POLE):
        raise AnalysisError('Source time material Euler chart is singular; this beam orientation is outside the supported chart.')
    psi = np.arctan2(-span[..., 0], horizontal)
    c0 = np.stack([np.cos(psi), np.sin(psi)*np.cos(phi), np.sin(psi)*np.sin(phi)], axis=-1)
    n0 = np.stack([np.zeros_like(phi), -np.sin(phi), np.cos(phi)], axis=-1)
    theta = np.arctan2(-np.sum(frame[..., :, 0]*n0, axis=-1),
                      np.sum(frame[..., :, 0]*c0, axis=-1))
    return np.stack([phi, theta, psi], axis=-1)


def _aircraft_frame(angles):
    # Unsteady Eq. 7, exactly the ground.body_to_earth convention, in radians.
    phi, theta, psi = angles
    cp, sp, ct, st, cs, ss = (np.cos(phi), np.sin(phi), np.cos(theta),
                              np.sin(theta), np.cos(psi), np.sin(psi))
    return np.array([[cs*ct, ss*cp-cs*st*sp, ss*sp+cs*st*cp],
                     [-ss*ct, cs*cp+ss*st*sp, cs*sp-ss*st*cp],
                     [-st, -ct*sp, ct*cp]])


def _aircraft_angles(frame):
    horizontal = np.hypot(frame[0, 0], frame[1, 0])
    if horizontal < _POLE:
        raise AnalysisError('Source time aircraft Euler chart is singular; this aircraft attitude is outside the supported chart.')
    return np.array([-np.arctan2(frame[2, 1], frame[2, 2]),
                     np.arctan2(-frame[2, 0], horizontal),
                     -np.arctan2(frame[1, 0], frame[0, 0])])


def _lift(principal, previous, periodic):
    result = principal.copy()
    for index in periodic:
        difference = principal[..., index]-previous[..., index]
        result[..., index] = previous[..., index]+np.arctan2(np.sin(difference), np.cos(difference))
    if np.any(abs(result-previous) >= _STEP_LIMIT):
        raise AnalysisError('Source time Euler step is ambiguous or approaches pi; reduce the time step.')
    return result


class SourceTimeChart:
    """Physical, uniquely oriented material nodes and owned Euler lifts.

    A single-Q node with distinct incident jig frames is not a single csn_i
    node of the source time equations. No frame averaging or topology repair
    is performed. Newton's spatial rotation increments remain external.
    """
    def __init__(self, network):
        self.nn = int(network.nn)
        if self.nn <= 0:
            raise AnalysisError('Source time requires at least one material node.')
        self.jig_frames = np.empty((self.nn, 3, 3))
        self.fuselage = np.zeros(self.nn, dtype=bool)
        element_fuselage = np.asarray(getattr(network, 'source_fuselage',
            np.zeros(len(network.a), dtype=bool)), dtype=bool)
        if element_fuselage.shape != (len(network.a),):
            raise AnalysisError('Invalid source time material chart layout.')
        present = np.zeros(self.nn, dtype=bool)
        for ids, frames in ((network.a, network.R0a), (network.b, network.R0b)):
            ids = np.asarray(ids)
            if ids.ndim != 1 or not np.issubdtype(ids.dtype, np.integer):
                raise AnalysisError('Invalid source time endpoint node indices.')
            frames = _rotations(frames, (len(ids), 3, 3), 'endpoint jig frames')
            for node, frame, body in zip(ids, frames, element_fuselage):
                if node < 0 or node >= self.nn:
                    raise AnalysisError('Invalid source time endpoint node index.')
                if present[node] and np.max(abs(frame-self.jig_frames[node])) > _JIG_TOL:
                    raise AnalysisError('Source Euler time integration requires one physical material frame per node; '
                                        f'node {node} has different incident jig frames. The shared-node material '
                                        'orientation break is unsupported by this time formulation.')
                if present[node] and self.fuselage[node] != body:
                    raise AnalysisError('Source time node has inconsistent surface/fuselage material charts.')
                if not present[node]:
                    self.jig_frames[node] = frame
                    self.fuselage[node] = body
                    present[node] = True
        if not np.all(present):
            raise AnalysisError('Source time material node has no incident jig frame.')
        self.jig_frames.setflags(write=False)
        self.fuselage.setflags(write=False)

    def _material_angles(self, frames):
        if not np.any(self.fuselage):
            return _surface_angles(frames)
        from .source_fuselage import angles_from_frame
        result = np.empty((self.nn, 3))
        result[self.fuselage] = angles_from_frame(frames[self.fuselage])
        result[~self.fuselage] = _surface_angles(frames[~self.fuselage])
        return result

    def _material_frames(self, angles):
        result = surface_frame_from_angles(angles)
        if np.any(self.fuselage):
            from .source_fuselage import frame_from_angles
            result[self.fuselage] = frame_from_angles(angles[self.fuselage])
        return result

    def _material_lift(self, principal, previous):
        if not np.any(self.fuselage):
            return _lift(principal, previous, (0, 1))
        result = np.empty_like(principal)
        for mask, periodic in ((self.fuselage, (1, 2)), (~self.fuselage, (0, 1))):
            result[mask] = _lift(principal[mask], previous[mask], periodic)
        return result

    def _physical(self, state):
        rotations = _rotations(state.Q, (self.nn, 3, 3), 'nodal rotations')
        orientation = _rotations(state.orientation, (3, 3), 'aircraft orientation')
        return rotations@self.jig_frames, orientation

    def validate(self, state):
        """Check owned arrays against physical matrices; do not infer winding."""
        q = _array(getattr(state, 'source_angles', None), (self.nn, 3), 'material Euler history')
        attitude = _array(getattr(state, 'source_attitude', None), (3,), 'aircraft Euler history')
        inclination = np.where(self.fuselage, q[:, 0], q[:, 2])
        if (np.any(abs(inclination) >= np.pi/2) or np.any(np.cos(inclination) < _POLE)
                or abs(attitude[1]) >= np.pi/2 or np.cos(attitude[1]) < _POLE):
            raise AnalysisError('Source time Euler history lies outside its nonsingular principal inclination chart.')
        frames, orientation = self._physical(state)
        if (np.max(abs(self._material_frames(q)-frames)) > _MATRIX_TOL
                or np.max(abs(_aircraft_frame(attitude)-orientation)) > _MATRIX_TOL):
            raise AnalysisError('Source time Euler history does not match its physical rotation matrices.')
        return state

    def bind(self, state, previous=None):
        """Own missing trial/initial angles, preserving validated supplied lifts.

        The entered initial aircraft winding may be supplied without material
        angles. Saved packets must instead use unpack(), which requires both.
        With a predecessor, the unique short Euler lift is checked even when
        the caller already supplied arrays.
        """
        frames, orientation = self._physical(state)
        principal = (self._material_angles(frames), _aircraft_angles(orientation))
        if previous is not None:
            self.validate(previous)
            expected = (self._material_lift(principal[0], np.asarray(previous.source_angles)),
                        _lift(principal[1], np.asarray(previous.source_attitude), (0, 2)))
        else:
            expected = principal
        for field, value, shape in zip(_FIELDS, expected, ((self.nn, 3), (3,))):
            supplied = getattr(state, field, None)
            if supplied is not None:
                value_supplied = _array(supplied, shape, field)
                if previous is not None and np.max(abs(value_supplied-value)) > _MATRIX_TOL:
                    raise AnalysisError('Source time supplied Euler winding disagrees with its predecessor.')
                value = value_supplied
            setattr(state, field, value.copy())
        return self.validate(state)

    def pack(self, state):
        """Own serializable history; matrices alone cannot encode these lifts."""
        self.validate(state)
        return {name: np.asarray(getattr(state, name)).tolist() for name in _FIELDS}

    def unpack(self, state, data):
        """Restore required owned lifts without principal-angle regeneration."""
        if not isinstance(data, dict) or any(name not in data for name in _FIELDS):
            raise AnalysisError('Source time checkpoint is missing its owned Euler histories.')
        for name, shape in zip(_FIELDS, ((self.nn, 3), (3,))):
            setattr(state, name, _array(data[name], shape, name).copy())
        return self.validate(state)

    def rates(self, state, previous, older, coefficients):
        """Unscaled literal Eq. 2/14 BDF residuals (caller divides by W)."""
        self.validate(state)
        self.validate(previous)
        k = _array(coefficients, (3,), 'BDF coefficients')
        if abs(np.sum(k)) > 32*np.finfo(float).eps*max(1., float(np.sum(abs(k)))):
            raise AnalysisError('Source time BDF coefficients must annihilate a constant history.')
        if older is None and k[2] != 0:
            raise AnalysisError('Source time BDF2 requires its owned second predecessor.')
        if older is not None:
            self.validate(older)
        # Validate consecutive lifts, including deliberately retained BDF2
        # histories. Do not impose a principal two-step rotation-log bound.
        for current, past in ((state, previous), (previous, older)):
            if past is not None:
                for name in _FIELDS:
                    if np.any(abs(np.asarray(getattr(current, name))-np.asarray(getattr(past, name))) >= _STEP_LIMIT):
                        raise AnalysisError('Source time Euler history step is ambiguous; reduce the time step.')
        def difference(name):
            before = np.asarray(getattr(previous, name))
            result = k[0]*(np.asarray(getattr(state, name))-before)
            if older is not None:
                result += k[2]*(np.asarray(getattr(older, name))-before)
            return result
        w = _array(state.w, (self.nn, 3), 'local angular velocities')
        omega = _array(state.Omega, (3,), 'aircraft angular velocity')
        q = np.asarray(state.source_angles)
        phi, psi = q[:, 0], np.where(self.fuselage, 0., q[:, 2])
        cp, sp, cs = np.cos(phi), np.sin(phi), np.cos(psi)
        transverse = cp*w[:, 1]+sp*w[:, 2]
        local = np.stack([w[:, 0]+np.tan(psi)*transverse,
                          transverse/cs, -sp*w[:, 1]+cp*w[:, 2]], axis=-1)
        if np.any(self.fuselage):
            from .source_fuselage import euler_rates
            local[self.fuselage] = euler_rates(q[self.fuselage], w[self.fuselage])
        phi, theta, _ = np.asarray(state.source_attitude)
        cp, sp, ct = np.cos(phi), np.sin(phi), np.cos(theta)
        transverse = sp*omega[1]-cp*omega[2]
        frame = np.array([-omega[0]+np.tan(theta)*transverse,
                          cp*omega[1]+sp*omega[2], transverse/ct])
        return difference('source_angles')-local, difference('source_attitude')-frame
