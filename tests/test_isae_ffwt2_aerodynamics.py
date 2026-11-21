"""Check the independent vortex reference against direct line quadrature."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

PATH = Path(__file__).resolve().parents[1]/'scripts/verify-isae-ffwt2-aerodynamics.py'
SPEC = importlib.util.spec_from_file_location('ffwt2_aerodynamics', PATH)
REF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REF)


def integrate_line(point, positions, tangents, weights):
    r = point-positions
    return np.sum(weights[:, None]*np.cross(tangents, r)/np.linalg.norm(r, axis=1)[:, None]**3, axis=0)/(4*np.pi)


@pytest.mark.parametrize('point', [[.3, -.4, .8], [1.4, 1.1, -.7], [-.8, -.6, .5]])
def test_finite_filament_agrees_with_direct_biot_savart_quadrature(point):
    point = np.array(point); a = np.array([-.2, -.4, .1]); b = np.array([.5, .8, -.3])
    x, w = np.polynomial.legendre.leggauss(96)
    q = (x+1)/2; weights = w/2
    expected = integrate_line(point, a+q[:, None]*(b-a), np.broadcast_to(b-a, (len(q), 3)), weights)
    actual = REF.segment_velocity(point, a, b)
    np.testing.assert_allclose(actual, expected, rtol=2e-13, atol=2e-15)
    np.testing.assert_allclose(REF.segment_velocity(point, b, a), -actual, rtol=2e-13, atol=2e-15)


@pytest.mark.parametrize('point', [[.3, -.4, .8], [1.4, 1.1, -.7], [-.8, -.6, .5]])
def test_infinite_ray_agrees_with_mapped_infinite_line_quadrature(point):
    point = np.array(point); origin = np.array([-.2, -.4, .1])
    x, w = np.polynomial.legendre.leggauss(160)
    q = (x+1)/2
    distance = q/(1-q)
    expected = integrate_line(point, origin+distance[:, None]*REF.EX,
        np.broadcast_to(REF.EX, (len(q), 3)), w/2/(1-q)**2)
    np.testing.assert_allclose(REF.ray_velocity(point, origin), expected, rtol=2e-12, atol=2e-15)


def test_unswept_horseshoe_center_has_known_downwash_and_omits_only_own_bound():
    a, b = np.array([0., -1., 0.]), np.array([0., 1., 0.])
    expected = np.array([0., 0., -1/(2*np.pi)])
    np.testing.assert_allclose(REF.induced(np.zeros(3), [a], [b], [1.], exclude=0), expected, atol=2e-15)
    downstream = np.array([.4, 0., .2])
    whole = REF.induced(downstream, [a], [b], [2.])
    rays = REF.induced(downstream, [a], [b], [2.], exclude=0)
    np.testing.assert_allclose(whole-rays, 2*REF.segment_velocity(downstream, a, b), atol=2e-15)


def test_translation_does_not_change_vortex_velocities():
    a, b, p = np.array([-.2, -.4, .1]), np.array([.5, .8, -.3]), np.array([.3, -.4, .8])
    shift = np.array([3., -7., 5.])
    np.testing.assert_allclose(REF.segment_velocity(p+shift, a+shift, b+shift), REF.segment_velocity(p, a, b), rtol=2e-14, atol=2e-15)
    np.testing.assert_allclose(REF.ray_velocity(p+shift, a+shift), REF.ray_velocity(p, a), rtol=2e-14, atol=2e-15)
