"""Prescribed zero acceleration adds coordinate integrators, not wing poles.

The independent oracle uses inertial Cartesian position/velocity and infinitesimal
rotation/angular velocity. In those coordinates the frame generator has six
2-by-2 integrator blocks. This does not identify historical ASWING constraints.
"""
from dataclasses import replace

import numpy as np
import pytest
from scipy.linalg import eig, solve

from openswing.ground import body_to_earth
from openswing.linear_dynamics import DynamicSystem, linearize, make_system
from openswing.source_airflow import AIRFLOW_POLICY
from test_wall_root import configuration, flight


def skew(v):
    x, y, z = v
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


@pytest.fixture(scope='module', params=[(0., 0., 0.), (17., -11., 23.)])
def pencils(request):
    model, panels = configuration(False, intervals=4, interpolation='drela-segspl-v1')
    # Above-ground / free-air scope: actual wall-contact frame derivatives are
    # separately guarded and are not bypassed by this invariant test.
    condition = replace(flight(), ground_effect=0, alpha=2., beta=-3.,
                        attitude=list(request.param))
    fixed, _ = make_system(model, condition, panels, gravity=[0., 0., 0.],
                          structural_operator=AIRFLOW_POLICY, tolerance=1e-10)
    prescribed = DynamicSystem(fixed.network, fixed.base, frame='prescribed')
    assert not fixed.network.operating.constraints
    assert np.array_equal(prescribed.Omega0, np.zeros(3))
    assert np.array_equal(prescribed.motion.acceleration, np.zeros(3))
    assert np.array_equal(prescribed.motion.angular_acceleration, np.zeros(3))
    a, m = linearize(fixed, sparse=True)
    pa, pm = linearize(prescribed, sparse=True)
    return fixed, prescribed, a.toarray(), m.toarray(), pa.toarray(), pm.toarray()


def test_prescribed_frame_retains_identical_physical_pencil_and_one_way_coupling(pencils):
    fixed, prescribed, a, m, pa, pm = pencils
    n = fixed.size
    assert prescribed.size == n+12
    np.testing.assert_allclose(pa[:n, :n], a, rtol=2e-10, atol=2e-11)
    np.testing.assert_allclose(pm[:n, :n], m, rtol=2e-10, atol=2e-11)
    np.testing.assert_array_equal(pa[n:, :n], 0.)
    np.testing.assert_array_equal(pm[n:, :n], 0.)
    np.testing.assert_array_equal(pm[:n, n:], 0.)
    # Actual aerodynamic/mechanical coupling is present in the upper block;
    # the test is not appending unrelated synthetic states to a saved matrix.
    assert np.linalg.norm(pa[:n, n:]) > 1e-3


def test_prescribed_frame_matches_inertial_cartesian_integrators(pencils):
    fixed, s, _, _, a, m = pencils
    f = solve(m[fixed.size:, fixed.size:], a[fixed.size:, fixed.size:])
    rotation = body_to_earth(s.attitude)
    # Independent axes of the bank/elevation/heading rotations in Earth
    # coordinates, obtained from their geometric rotation axes.
    heading = body_to_earth((0., 0., s.attitude[2]))
    elevation = body_to_earth((0., s.attitude[1], 0.))
    axes = np.column_stack((-heading@elevation@np.array([1., 0., 0.]),
                             heading@np.array([0., 1., 0.]),
                            -np.array([0., 0., 1.])))
    # Map scaled body-chart increments to physical inertial increments.
    t = np.zeros((12, 12))
    t[:3, :3] = s.V*rotation
    t[:3, 9:] = -skew(rotation@s.U0)@axes
    t[3:6, 3:6] = s.W*rotation
    t[6:9, 6:9] = s.L*np.eye(3)
    t[9:, 9:] = axes
    expected = np.zeros((12, 12))
    expected[6:9, :3] = np.eye(3)
    expected[9:, 3:6] = np.eye(3)
    actual = solve(t.T, (t@f).T).T
    np.testing.assert_allclose(actual, expected, rtol=3e-10, atol=3e-10)
    assert np.linalg.matrix_rank(actual, tol=1e-9) == 6
    np.testing.assert_allclose(actual@actual, 0., atol=1e-9, rtol=0.)


def test_fixed_frame_finite_modes_lift_to_original_prescribed_pencil(pencils):
    fixed, _, a, m, pa, pm = pencils
    ab, v = eig(a, m, homogeneous_eigvals=True)
    # Preserve infinite homogeneous pairs; test finite nonzero modes only.
    finite = (ab[1] != 0) & (ab[0] != 0)
    assert np.count_nonzero(finite) >= 6
    poles = ab[0, finite]/ab[1, finite]
    lifted = np.vstack((v[:, finite], np.zeros((12, np.count_nonzero(finite)))))
    residual = pa@lifted-(pm@lifted)*poles[None, :]
    denominator = (np.linalg.norm(pa)+abs(poles)*np.linalg.norm(pm))*np.linalg.norm(lifted, axis=0)
    assert np.max(np.linalg.norm(residual, axis=0)/denominator) < 1e-10
