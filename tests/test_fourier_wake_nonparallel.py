"""Arbitrary straight wake orientations checked against logarithmic energy."""
import math
import numpy as np
import pytest
from scipy.integrate import quad
from scipy.spatial.transform import Rotation
from openswing.fourier_wake import fourier_wake_forces


def trace(span, angle, coefficients, center=(0., 0., 0.)):
    direction = np.array([0., math.cos(angle), math.sin(angle)])
    center = np.asarray(center)
    return dict(start=center-span/2*direction, end=center+span/2*direction,
                coefficients=np.array(coefficients))


def report(traces, **kwargs):
    settings = dict(wind=[1., 0., 0.], side=[0., 1., 0.], lift=[0., 0., 1.],
                    speed=20., density=1.2, reference=[[4., 1., 4.], [0., 0., 0.]])
    return fourier_wake_forces(traces, **(settings | kwargs))


def log_energy(first, second):
    """Independent double integral of Gamma' Gamma' log(distance²).

    Integration by parts of the Biot–Savart work gives
    D_ij=-rho/(8*pi) integral integral Gamma_i' Gamma_j' log(r²) dtheta dphi.
    This uses no production velocity kernel or source resolvent.
    """
    centers = [.5*(t['start'][1:]+t['end'][1:]) for t in (first, second)]
    halves = [.5*(t['end'][1:]-t['start'][1:]) for t in (first, second)]
    coefficients = [np.arange(1, len(t['coefficients'])+1)*t['coefficients'] for t in (first, second)]
    def derivative(theta, values):
        return sum(value*math.cos((n+1)*theta) for n, value in enumerate(values))
    def outer(theta):
        receiver = centers[0]+halves[0]*math.cos(theta)
        eta = float((receiver-centers[1])@halves[1]/(halves[1]@halves[1]))
        points = [math.acos(eta)] if -1 < eta < 1 else []
        def inner(phi):
            delta = receiver-centers[1]-halves[1]*math.cos(phi)
            return derivative(phi, coefficients[1])*math.log(float(delta@delta))
        return derivative(theta, coefficients[0])*quad(inner, 0., math.pi, points=points,
                                                       epsabs=2e-10, epsrel=2e-10, limit=180)[0]
    return -1.2/(8*math.pi)*quad(outer, 0., math.pi, points=[math.pi/2],
                                epsabs=2e-10, epsrel=2e-10, limit=180)[0]


@pytest.mark.parametrize('case', ['crossing', 'separated', 'joined'])
def test_nonparallel_mutual_energy_matches_independent_log_integral(case):
    if case == 'crossing':
        first = trace(2.4, 0., [1.1, .2, -.04])
        second = trace(1.6, .87, [.6, -.13, .02], (8., 0., 0.))
    elif case == 'separated':
        first = trace(4., 0., [1., .2])
        second = trace(2., .56, [.8, -.1], (3., .5, 1.6))
    else:
        first = trace(2., 0., [1., .1], (0., -1., 0.))
        second = trace(math.sqrt(2), math.pi/4, [.7, -.2], (0., .5, .5))
    expected = log_energy(first, second)
    r = report([first, second])
    assert r['available'], r
    matrix = np.asarray(r['drag_matrix'])
    assert matrix[0, 1] == pytest.approx(expected, rel=2e-8, abs=2e-10)
    assert matrix[1, 0] == pytest.approx(expected, rel=2e-8, abs=2e-10)
    assert r['induced_drag'] > 0
    expected_force = np.zeros(3)
    for t in (first, second):
        direction = (t['end']-t['start'])/np.linalg.norm(t['end']-t['start'])
        integral = math.pi*np.linalg.norm(t['end']-t['start'])*t['coefficients'][0]/4
        expected_force += 1.2*20*integral*np.cross([1., 0., 0.], direction)
    np.testing.assert_allclose(r['force_transverse_body'], expected_force, atol=1e-12)


def test_centered_perpendicular_elliptic_wakes_have_zero_mutual_energy():
    r = report([trace(4., 0., [2.]), trace(3., math.pi/2, [.7], (9., 0., 0.))])
    assert r['available'], r
    matrix = np.asarray(r['drag_matrix'])
    np.testing.assert_allclose(matrix, np.diag([1.2*math.pi/8*4, 1.2*math.pi/8*.7**2]), atol=2e-13)


def test_nonparallel_reversal_and_rigid_frame_transform_preserve_forces():
    traces = [trace(3., -.3, [1., .1, -.2], (9., .4, -.1)), trace(2., .8, [.8, -.2], (-7., -.2, .7))]
    original = report(traces)
    assert original['available'], original
    reversed_trace = dict(start=traces[1]['end'], end=traces[1]['start'],
                          coefficients=traces[1]['coefficients']*(-1.)**np.arange(1, 3))
    reversed_result = report([traces[0], reversed_trace])
    q = Rotation.from_rotvec([.7, -.4, .3]).as_matrix()
    shift = np.array([17., -11., 3.])
    transformed = [dict(start=q@t['start']+shift, end=q@t['end']+shift, coefficients=t['coefficients']) for t in traces]
    rotated = report(transformed, wind=q[:, 0], side=q[:, 1], lift=q[:, 2], reference=[[4., 1., 4.], shift])
    for result in (reversed_result, rotated):
        assert result['available'], result
        for name in ('CLi', 'CYi', 'CDi', 'efficiency', 'rolling_moment_wind'):
            assert result[name] == pytest.approx(original[name], rel=2e-10, abs=1e-12)


def test_nearly_aligned_opposite_wakes_approach_exact_cancellation():
    energy = []
    for angle in (.02, .005, .00125):
        r = report([trace(4., 0., [1., .2]), trace(4., angle, [-1., -.2])])
        assert r['available'], r
        assert r['induced_drag'] > 0
        energy.append(r['induced_drag'])
        mirrored = report([trace(4., 0., [1., .2]), trace(4., -angle, [-1., -.2])])
        assert mirrored['available'], mirrored
        assert mirrored['induced_drag'] == pytest.approx(r['induced_drag'], rel=2e-10)
    assert energy[0] > energy[1] > energy[2]
    exact = report([trace(4., 0., [1., .2]), trace(4., 0., [-1., -.2])])
    assert exact['induced_drag'] == 0 and exact['efficiency'] is None
