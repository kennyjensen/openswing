"""Geometry-only independent oracles for source Euler-BDF histories.

No network construction, mechanics evaluation, eigensolve or time solve.
Rotation products and their analytic derivatives are independent of the
source chart's component formulas.
"""
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from openswing.aero import AnalysisError
from openswing.source_time import SourceTimeChart, surface_frame_from_angles


def axis(index, angle):
    v = np.eye(3)[index]
    k = np.array([[0., -v[2], v[1]], [v[2], 0., -v[0]], [-v[1], v[0], 0.]])
    return np.eye(3)+np.sin(angle)*k+(1-np.cos(angle))*(k@k), k


def product(angles, rates, *, aircraft=False):
    # Surface Eq4: Rx(phi) Rz(psi) Ry(theta).
    # Aircraft Eq7: Rz(-Psi) Ry(Theta) Rx(-Phi).
    order, signs = ((2, 1, 0), (-1., 1., -1.)) if aircraft else ((0, 2, 1), (1., 1., 1.))
    indices = (2, 1, 0) if aircraft else (0, 2, 1)
    frames, derivatives = [], []
    for which, index, sign in zip(order, indices, signs):
        r, k = axis(which, sign*angles[index])
        frames.append(r)
        derivatives.append(sign*rates[index]*k@r)
    a, b, c = frames
    da, db, dc = derivatives
    r = a@b@c
    rd = da@b@c+a@db@c+a@b@dc
    skew = r.T@rd if aircraft else rd@r.T
    return r, np.array([skew[2, 1], skew[0, 2], skew[1, 0]])


def network(jig=None):
    if jig is None:
        jig = np.array([product(q, np.zeros(3))[0] for q in
                        [[.12, -.07, .04], [-.08, .16, -.03], [.02, .13, .07]]])
    return SimpleNamespace(nn=len(jig), a=np.arange(len(jig)-1), b=np.arange(1, len(jig)),
                           R0a=jig[:-1].copy(), R0b=jig[1:].copy())


def state(chart, angles, attitude, angle_rates=None, attitude_rates=None):
    q = np.asarray(angles)
    if q.shape == (3,):
        q = np.tile(q, (chart.nn, 1))
    qdot = np.zeros_like(q) if angle_rates is None else np.broadcast_to(angle_rates, q.shape)
    frames, rates = zip(*(product(x, v) for x, v in zip(q, qdot)))
    orientation, omega = product(attitude, np.zeros(3) if attitude_rates is None else attitude_rates, aircraft=True)
    return SimpleNamespace(Q=np.asarray(frames)@chart.jig_frames.transpose(0, 2, 1),
                           orientation=orientation, w=np.asarray(rates), Omega=omega)


def test_surface_chart_matches_independent_rotation_product_and_nonidentity_jig():
    chart = SourceTimeChart(network())
    q = np.array([[.31, -.22, .14], [-.42, .18, -.35], [.7, -.6, .25]])
    s = state(chart, q, [.23, -.17, .41])
    np.testing.assert_allclose(surface_frame_from_angles(q), s.Q@chart.jig_frames, atol=3e-16)
    chart.bind(s)
    np.testing.assert_allclose(s.source_angles, q, atol=3e-16)
    np.testing.assert_allclose(s.source_attitude, [.23, -.17, .41], atol=3e-16)
    assert np.max(abs(s.source_angles-Rotation.from_matrix(s.Q).as_rotvec())) > .1


@pytest.mark.parametrize('order', [1, 2])
def test_literal_euler_bdf_for_varying_axes_uses_current_exact_rate_maps(order):
    chart = SourceTimeChart(network())
    q0 = np.array([[.3, -.25, .21], [-.4, .35, -.17], [.1, .2, -.3]])
    q1 = np.array([[.9, -.6, .7], [-.8, .4, -.9], [.7, .8, .4]])
    q2 = np.array([[.2, .4, -.3], [-.2, .1, .3], [.4, -.1, .2]]) if order == 2 else np.zeros((3, 3))
    a0, a1 = np.array([.2, -.15, .3]), np.array([.7, .6, -.9])
    a2 = np.array([.3, -.2, .1]) if order == 2 else np.zeros(3)
    times = [0., .12, .31]
    samples = []
    for t in times:
        s = state(chart, q0+t*q1+t*t*q2, a0+t*a1+t*t*a2, q1+2*t*q2, a1+2*t*a2)
        chart.bind(s, samples[-1] if samples else None)
        samples.append(s)
    old, previous, current = samples
    h, hp = times[2]-times[1], times[1]-times[0]
    coefficients = np.array([1/h, -1/h, 0.]) if order == 1 else np.array([
        (2*h+hp)/(h*(h+hp)), -(h+hp)/(h*hp), h/(hp*(h+hp))])
    local, frame = chart.rates(current, previous, old if order == 2 else None, coefficients)
    np.testing.assert_allclose(local, 0., atol=8e-15)
    np.testing.assert_allclose(frame, 0., atol=8e-15)
    # An independent old-style log difference is measurably different for
    # these noncommuting rotations, despite the same continuum rate maps.
    spatial = coefficients[1]*Rotation.from_matrix(previous.Q@current.Q.transpose(0, 2, 1)).as_rotvec()
    if order == 2:
        spatial += coefficients[2]*Rotation.from_matrix(old.Q@current.Q.transpose(0, 2, 1)).as_rotvec()
    assert np.linalg.norm(spatial-current.w) > 1e-4


def test_owned_lifts_allow_continuous_turns_and_initial_entered_aircraft_winding():
    chart = SourceTimeChart(network())
    previous = None
    for t in np.arange(0., 8.01, .4):
        q = np.tile([2.9+t, -.4-.8*t, .2], (chart.nn, 1))
        attitude = np.array([4*np.pi+2.8+.9*t, -.2, -2*np.pi-2.7-t])
        s = state(chart, q, attitude, [1., -.8, 0.], [.9, 0., -1.])
        if previous is None:
            s.source_attitude = attitude.copy()
        chart.bind(s, previous)
        np.testing.assert_allclose(s.source_angles, q, atol=6e-15)
        np.testing.assert_allclose(s.source_attitude, attitude, atol=6e-15)
        if previous is not None:
            local, frame = chart.rates(s, previous, None, [2.5, -2.5, 0.])
            np.testing.assert_allclose(local, 0., atol=1e-14)
            np.testing.assert_allclose(frame, 0., atol=1e-14)
        previous = s


def test_two_step_history_can_exceed_pi_without_rotation_log_reinterpretation():
    chart = SourceTimeChart(network())
    samples = []
    for t in (0., 1., 2.):
        s = state(chart, [.2+2*t, .1, .2], [.3+2*t, .1, -.2], [2., 0., 0.], [2., 0., 0.])
        chart.bind(s, samples[-1] if samples else None)
        samples.append(s)
    local, frame = chart.rates(samples[2], samples[1], samples[0], [1.5, -2., .5])
    np.testing.assert_allclose(local, 0., atol=5e-15)
    np.testing.assert_allclose(frame, 0., atol=5e-15)


def test_saved_history_is_owned_and_does_not_regenerate_or_ignore_branch_data():
    chart = SourceTimeChart(network())
    s = state(chart, [.2, -.4, .15], [.3, -.25, .1])
    s.source_attitude = np.array([.3+4*np.pi, -.25, .1-2*np.pi])
    chart.bind(s)
    packet = chart.pack(s)
    restored = state(chart, [.2, -.4, .15], [.3, -.25, .1])
    chart.unpack(restored, packet)
    np.testing.assert_array_equal(restored.source_attitude, s.source_attitude)
    packet['source_angles'][0][0] += .1
    assert restored.source_angles[0, 0] != packet['source_angles'][0][0]
    with pytest.raises(AnalysisError, match='rotation matrices'):
        chart.unpack(deepcopy(restored), packet)
    for field in ('source_angles', 'source_attitude'):
        incomplete = chart.pack(s)
        del incomplete[field]
        with pytest.raises(AnalysisError, match='missing'):
            chart.unpack(deepcopy(restored), incomplete)
    # A full-turn change is physically invisible to a matrix check, but is
    # inconsistent with a declared predecessor and must not be relifted away.
    tampered = deepcopy(s)
    tampered.source_angles[:, 0] += 2*np.pi
    chart.validate(tampered)
    with pytest.raises(AnalysisError, match='winding'):
        chart.bind(tampered, s)
    with pytest.raises(AnalysisError, match='history step'):
        chart.rates(tampered, s, None, [1., -1., 0.])


def test_distinct_incident_material_frames_are_rejected_without_averaging():
    n = network()
    n.R0b[0] = axis(0, .001)[0]@n.R0b[0]
    with pytest.raises(AnalysisError, match='different incident jig frames'):
        SourceTimeChart(n)
    # Mere independent floating point evaluation roundoff remains acceptable.
    n = network()
    n.R0b[0] = axis(0, 4*np.finfo(float).eps)[0]@n.R0b[0]
    chart = SourceTimeChart(n)
    np.testing.assert_array_equal(chart.jig_frames[1], n.R0a[1])
    assert not chart.jig_frames.flags.writeable


@pytest.mark.parametrize('which', ['material', 'aircraft'])
def test_chart_poles_reject_and_nearby_nonsingular_frames_roundtrip(which):
    chart = SourceTimeChart(network())
    q, attitude = np.array([.31, -.22, .14]), np.array([.23, -.17, .41])
    if which == 'material':
        q[2] = np.pi/2
    else:
        attitude[1] = -np.pi/2
    with pytest.raises(AnalysisError, match='singular'):
        chart.bind(state(chart, q, attitude))
    if which == 'material':
        q[2] -= 1e-5
    else:
        attitude[1] += 1e-5
    s = chart.bind(state(chart, q, attitude))
    chart.validate(s)
    np.testing.assert_allclose(s.source_angles, np.tile(q, (chart.nn, 1)), atol=2e-12)
    np.testing.assert_allclose(s.source_attitude, attitude, atol=2e-12)


@pytest.mark.parametrize('which', ['material', 'aircraft'])
def test_pi_step_is_explicitly_ambiguous(which):
    chart = SourceTimeChart(network())
    old = chart.bind(state(chart, [0., 0., 0.], [0., 0., 0.]))
    new = state(chart, [np.pi, 0., 0.] if which == 'material' else [0., 0., 0.],
                [0., 0., np.pi] if which == 'aircraft' else [0., 0., 0.])
    with pytest.raises(AnalysisError, match='ambiguous'):
        chart.bind(new, old)


@pytest.mark.parametrize('kind', ['missing', 'nonfinite', 'shape', 'outside', 'matrix', 'bdf2', 'coefficients'])
def test_invalid_owned_data_and_coefficients_fail_explicitly(kind):
    chart = SourceTimeChart(network())
    s = chart.bind(state(chart, [.1, -.2, .3], [.2, -.1, -.3]))
    old = deepcopy(s)
    if kind == 'missing':
        del s.source_angles
    elif kind == 'nonfinite':
        s.source_attitude[0] = np.nan
    elif kind == 'shape':
        s.source_angles = s.source_angles[:1]
    elif kind == 'outside':
        s.source_attitude[1] = np.pi
    elif kind == 'matrix':
        s.Q[0, 0, 0] += .1
    if kind == 'bdf2':
        with pytest.raises(AnalysisError, match='second predecessor'):
            chart.rates(s, old, None, [1.5, -2., .5])
    elif kind == 'coefficients':
        with pytest.raises(AnalysisError, match='constant history'):
            chart.rates(s, old, None, [1., -2., 0.])
    else:
        with pytest.raises(AnalysisError):
            chart.validate(s)
