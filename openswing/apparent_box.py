"""Endpoint thin-strip apparent loads for the source beam box equations.

Steady Eqs. 55--56 average the completed endpoint force and section couple.
Unsteady Eq. 266 then places the averaged force at the arithmetic beam midpoint.
This is not endpoint averaging of ``r cross force`` and adds no real-mass
finite-segment correction. General varying endpoint properties can produce a
nonsymmetric rigid acceleration response; it is not a spatial mass tensor.

The acceleration-only API retains the stationary operator. The motion API
also includes the velocity/rotation and centrifugal terms in unsteady
Eqs.41--44. It accepts absolute kinematics and a supplied relative fluid
velocity; it does not solve circulation or choose where to sample a wake.
Body volume, wall corrections and gravity are outside this operator. Frames
have physical chord/span/normal vectors in their columns; zero-lift angle
and control deflection do not rotate these material axes.
"""
import numpy as np
from .vector_ops import cross3


def _array(value, trailing, name):
    value = np.asarray(value, dtype=float)
    if trailing and value.shape[-len(trailing):] != trailing:
        raise ValueError(f'{name} must have trailing shape {trailing}.')
    if not np.all(np.isfinite(value)):
        raise ValueError(f'{name} must be finite.')
    return value


def _nonnegative(value, name):
    value = _array(value, (), name)
    if np.any(value < 0):
        raise ValueError(f'{name} must be nonnegative.')
    return value


def endpoint_acceleration_wrench(frame, chord, xax, density, acceleration,
                                 angular_acceleration):
    """Return per-length force/couple reaction about one endpoint beam axis.

    The acceleration is that of the beam axis; the physical midchord offset is
    included here. Arrays broadcast over leading dimensions, with frame shape
    ``(...,3,3)`` and both accelerations ``(...,3)``. Chord and density are
    nonnegative; zero values produce zero reaction. No rate terms are included.

    This is the acceleration-linear part of unsteady Eqs. 41--44, equivalent
    to steady Eqs. 84--85 at zero rates. The sign is reaction: ``w = -K a``.
    """
    frame = _array(frame, (3, 3), 'Frame')
    chord = _nonnegative(chord, 'Chord')
    xax = _array(xax, (), 'Xax')
    density = _nonnegative(density, 'Density')
    acceleration = _array(acceleration, (3,), 'Acceleration')
    angular_acceleration = _array(angular_acceleration, (3,), 'Angular acceleration')
    c, s, n = frame[..., 0], frame[..., 1], frame[..., 2]
    arm = ((.5-xax)*chord)[..., None]*c
    mass = density*np.pi/4*chord**2
    normal_acceleration = np.sum((acceleration+np.cross(angular_acceleration, arm))*n, axis=-1)
    force = -(mass*normal_acceleration)[..., None]*n
    pitch = mass*chord**2/32*np.sum(s*angular_acceleration, axis=-1)
    moment = np.cross(arm, force)-pitch[..., None]*s
    return force, moment


def _section_wrench(frame, chord, xax, density, midchord_acceleration,
                    rate_term, angular_acceleration, measure=1.):
    """Shared Eqs.43--44 arithmetic on already validated section fields.

    ``rate_term`` is (relative axis air velocity cross absolute section rate)
    dot n. ``measure`` is one for a force density or the declared interval
    measure for an integrated strip. No real-mass rotary correction is added.
    """
    c, s, n = frame[..., 0], frame[..., 1], frame[..., 2]
    offset = ((.5-xax)*chord)[..., None]*c
    mass = density*np.pi/4*chord**2*measure
    force = (mass*(rate_term-np.sum(midchord_acceleration*n, axis=-1)))[..., None]*n
    pitch = -mass*(chord/4*rate_term+chord**2/32*np.sum(s*angular_acceleration, axis=-1))
    return force, pitch[..., None]*s+cross3(offset, force)


def endpoint_motion_wrench(frame, chord, xax, density, velocity, acceleration,
                           rates, angular_acceleration):
    """Return the full thin-strip force/couple density about the beam axis.

    All vectors use the same instantaneous Cartesian axes. ``velocity`` is
    fluid velocity relative to the beam-axis point. ``acceleration`` is the
    absolute acceleration of that point. ``rates`` and
    ``angular_acceleration`` are the absolute section angular velocity and
    acceleration, not simply derivatives of components in a moving frame.

    For frame rate Omega and relative section rate omega, callers must use
    rates = Omega + omega and alpha = alpha_frame + omega_dot + Omega cross
    omega. This transport term is required by rigid-point kinematics and is
    consistent with the source moving real-inertia operator. The midchord
    acceleration is a_axis + alpha cross arm + rates cross (rates cross arm).

    Leading dimensions broadcast. Chord/density may be zero; no division by
    airspeed is used. This is noncirculatory loading only, not a complete
    zero-speed lifting-line or nonlinear still-air network implementation.
    """
    frame = _array(frame, (3, 3), 'Frame')
    chord = _nonnegative(chord, 'Chord')
    xax = _array(xax, (), 'Xax')
    density = _nonnegative(density, 'Density')
    velocity = _array(velocity, (3,), 'Relative fluid velocity')
    acceleration = _array(acceleration, (3,), 'Absolute acceleration')
    rates = _array(rates, (3,), 'Absolute angular velocity')
    angular_acceleration = _array(angular_acceleration, (3,), 'Absolute angular acceleration')
    arm = ((.5-xax)*chord)[..., None]*frame[..., 0]
    midchord = acceleration+cross3(angular_acceleration, arm)+cross3(rates, cross3(rates, arm))
    rate_term = np.sum(cross3(velocity, rates)*frame[..., 2], axis=-1)
    return _section_wrench(frame, chord, xax, density, midchord, rate_term, angular_acceleration)


def interval_motion_wrench(positions, frames, chord, xax, length, density,
                           velocity, acceleration, rates, angular_acceleration,
                           reference):
    """Average completed endpoint loads and return the interval total wrench.

    Endpoint vectors have trailing shape (2,3), frames (2,3,3), and chord/Xax
    (2,). Density and unloaded interval length broadcast over interval batch
    axes. The returned couple is about ``reference`` (trailing shape (3,)).

    Eq.266 places the averaged force at the arithmetic beam midpoint. Thus
    the force moment is computed after averaging, not by averaging endpoint
    r cross f. This matches the existing source acceleration response and
    preserves its potentially nonsymmetric varying-property mass operator.
    """
    positions = _array(positions, (2, 3), 'Endpoint positions')
    frames = _array(frames, (2, 3, 3), 'Endpoint frames')
    chord = _nonnegative(_array(chord, (2,), 'Endpoint chord'), 'Endpoint chord')
    xax = _array(xax, (2,), 'Endpoint Xax')
    length = _nonnegative(length, 'Interval length')
    density = _nonnegative(density, 'Density')
    velocity = _array(velocity, (2, 3), 'Endpoint relative fluid velocity')
    acceleration = _array(acceleration, (2, 3), 'Endpoint absolute acceleration')
    rates = _array(rates, (2, 3), 'Endpoint absolute angular velocity')
    angular_acceleration = _array(angular_acceleration, (2, 3), 'Endpoint absolute angular acceleration')
    reference = _array(reference, (3,), 'Moment reference')
    f, m = endpoint_motion_wrench(frames, chord, xax, density[..., None],
                                  velocity, acceleration, rates, angular_acceleration)
    force = length[..., None]/2*np.sum(f, axis=-2)
    couple = length[..., None]/2*np.sum(m, axis=-2)
    midpoint = positions[..., 0, :]/2+positions[..., 1, :]/2
    return force, couple+cross3(midpoint-reference, force)


def _rigid_map(offset):
    """Map reference [linear, angular] acceleration to a beam-axis point."""
    matrix = np.broadcast_to(np.eye(6), offset.shape[:-1]+(6, 6)).copy()
    # Each column is alpha cross offset, i.e. -skew(offset) alpha.
    matrix[..., :3, 3:] = np.swapaxes(np.cross(np.eye(3), offset[..., None, :]), -1, -2)
    return matrix


def rigid_acceleration_response(r0, r1, frame0, frame1, chord0, chord1,
                                xax0, xax1, length, density, reference):
    """Return each interval's ``(...,6,6)`` source acceleration response.

    The integrated force/moment reaction about ``reference`` is
    ``-response @ [a_reference, angular_acceleration]``. Input endpoints and
    reference have trailing shape ``(3,)``; frames have ``(3,3)``. All leading
    dimensions broadcast. ``length`` is the declared material interval measure,
    not an inferred endpoint distance; it and density must be nonnegative.

    With endpoint per-length operators K0/K1 and rigid maps
    H(r)=[[I,-skew(r-reference)],[0,I]], the response is exactly
    ``length/2 * H(midpoint).T @ (K0@H(r0) + K1@H(r1))``.
    K is evaluated through endpoint_acceleration_wrench for six basis inputs.
    Complete endpoint products are averaged before the force moment is taken.
    No symmetrization, PSD assumption, apparent CG or ds**2/12 term is applied.
    """
    r0, r1 = _array(r0, (3,), 'First endpoint'), _array(r1, (3,), 'Second endpoint')
    reference = _array(reference, (3,), 'Reference')
    frame0, frame1 = _array(frame0, (3, 3), 'First frame'), _array(frame1, (3, 3), 'Second frame')
    chord0, chord1 = _nonnegative(chord0, 'First chord'), _nonnegative(chord1, 'Second chord')
    xax0, xax1 = _array(xax0, (), 'First Xax'), _array(xax1, (), 'Second Xax')
    length, density = _nonnegative(length, 'Length'), _nonnegative(density, 'Density')
    shape = np.broadcast_shapes(r0.shape[:-1], r1.shape[:-1], reference.shape[:-1],
                                frame0.shape[:-2], frame1.shape[:-2], chord0.shape,
                                chord1.shape, xax0.shape, xax1.shape, length.shape, density.shape)
    r0, r1, reference = [np.broadcast_to(v, shape+(3,)) for v in (r0, r1, reference)]
    maps = [_rigid_map(r-reference) for r in (r0, r1)]
    response = np.zeros(shape+(6, 6))
    for frame, chord, xax, rigid in zip((frame0, frame1), (chord0, chord1), (xax0, xax1), maps):
        # Basis index is a leading axis to the endpoint vector helper.
        f, m = endpoint_acceleration_wrench(
            np.broadcast_to(frame, shape+(3, 3))[..., None, :, :],
            np.broadcast_to(chord, shape)[..., None], np.broadcast_to(xax, shape)[..., None],
            np.broadcast_to(density, shape)[..., None],
            np.swapaxes(rigid[..., :3, :], -1, -2),
            np.swapaxes(rigid[..., 3:, :], -1, -2))
        response -= np.swapaxes(np.concatenate((f, m), axis=-1), -1, -2)
    midpoint = r0/2+r1/2
    return np.broadcast_to(length, shape)[..., None, None]/2 * (
        np.swapaxes(_rigid_map(midpoint-reference), -1, -2)@response)
