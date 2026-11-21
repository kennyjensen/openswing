"""Nonsingular axis derivatives of the original Biot--Savart integrals."""
import numpy as np
import pytest

from openswing.aero import finite_vortex, semi_infinite_vortex, horseshoe_velocity
from openswing.ground import GroundPlane
from openswing.vortex_tangent import finite_partials, semi_infinite_partials, VortexFieldTangent, VortexDerivativeUnavailable
from openswing.vortex_state_tangent import vortex_state_columns
from test_vortex_tangent import integrate_partials, decimal_partials
from test_vortex_state_tangent import centered


@pytest.mark.parametrize('finite,z', [(True, -2.), (True, 2.), (False, -2.)])
@pytest.mark.parametrize('core,offset', [(0., 0.), (0., 1e-16), (1e-13, 0.), (1e-16, 1e-16)])
def test_all_regular_axis_partials_match_independent_integral(finite, z, core, offset):
    p = np.array([z, offset, -.3*offset]); a = np.zeros(3); d = np.array([1., 0., 0.])
    function = finite_partials if finite else semi_infinite_partials
    expected = integrate_partials(p, a, d, core, finite)
    actual = function(p, a, d, core)
    for name in expected:
        np.testing.assert_allclose(actual[name], expected[name], rtol=3e-12, atol=2e-14)
    assert np.max(abs(actual['point'])) > .001


@pytest.mark.parametrize('finite,z', [(True, -2.), (True, 2.), (False, -2.)])
def test_exact_axis_partials_match_110_digit_physical_differences(finite, z):
    for offset in (0., 1e-16):
        p = [z, offset, -.3*offset]
        expected = decimal_partials(p, 0., finite)
        function = finite_partials if finite else semi_infinite_partials
        actual = function(p, [0., 0., 0.], [1., 0., 0.])
        for name in expected:
            np.testing.assert_allclose(actual[name], expected[name], rtol=3e-12, atol=2e-14)


@pytest.mark.parametrize('finite,z', [(True, -2.), (True, 2.), (False, -2.)])
@pytest.mark.parametrize('scale', [1e-16, 1e-8, 1e8])
def test_regular_axis_derivatives_have_no_absolute_distance_floor(finite, z, scale):
    p = np.array([z, 1e-4, -3e-5]); a = np.zeros(3); d = np.array([1., 0., 0.])
    expected = integrate_partials(p, a, d, 0., finite)
    actual = finite_partials(scale*p, a, scale*d) if finite else semi_infinite_partials(scale*p, a, d)
    for name in expected:
        power = 1 if name == 'direction' else 2
        np.testing.assert_allclose(actual[name]*scale**power, expected[name], rtol=3e-12, atol=2e-14)


@pytest.mark.parametrize('flag', [-1, 0, 1])
def test_regular_axes_retain_full_pg_image_and_independent_endpoint_chain_rules(flag):
    points = np.array([[2., 0., 0.], [-2., 0., 0.], [-.5, -2., 0.]])
    a = np.array([[-.5, 0., 0.]]); b = np.array([[.5, 0., 0.]])
    args = (points, a, b, np.array([0., 2., 0.]), np.diag([1.2, 1., 1.]), 0., np.array([.7]))
    ground = GroundPlane(flag, [0., 0., 2.], [0., 0., 0.])
    rng = np.random.default_rng(304)
    cols = [np.zeros(v.shape+(6,)) for v in args[:5]]
    for k in range(5): cols[k][..., k] = rng.normal(size=args[k].shape)*.1
    for col in cols: col[..., 5] = rng.normal(size=col.shape[:-1])*.1
    actual = vortex_state_columns(*args, *cols, ground)
    retained = VortexFieldTangent(*args, ground)
    for step in (1e-5, 3e-6):
        expected = centered(args, cols, ground, step=step)
        np.testing.assert_allclose(actual, expected, atol=2e-10, rtol=2e-7)
        for k in range(3):
            plus = retained.value(points+step*cols[0][..., k], a+step*cols[1][..., k], b+step*cols[2][..., k], 0.)
            minus = retained.value(points-step*cols[0][..., k], a-step*cols[1][..., k], b-step*cols[2][..., k], 0.)
            np.testing.assert_allclose((plus-minus)/(2*step), expected[..., k], atol=2e-10, rtol=2e-7)


def test_real_filament_guards_remain_active():
    a = np.array([[-.5, 0., 0.]]); b = np.array([[.5, 0., 0.]])
    for p in ([0., 0., 0.], [-.5, 1., 0.], [.5, 1., 0.]):
        with pytest.raises(VortexDerivativeUnavailable, match='principal-value mask'):
            VortexFieldTangent(np.array([p]), a, b, [0., 1., 0.], np.eye(3), 0., np.ones(1))
