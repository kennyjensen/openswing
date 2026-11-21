"""Directed-filament invariants, independent of native ASWING output.

An affine quarter-chord line with constant circulation is the same vortex
after subdivision. This does not prescribe endpoints for a curved ASWING
interval, nor assert that a force receiver may include its own bound field.
"""
import numpy as np
import pytest
from scipy.integrate import quad_vec

from openswing.aero import horseshoe_velocity, semi_infinite_vortex
from openswing.asw import parse_asw
from openswing.factored_influence import FactoredInfluence
from openswing.frozen_influence import lifting_geometry
from openswing.geometry import mesh_beam


def integral_segment(point, start, vector, upper):
    """Independent directed Biot--Savart quadrature in transformed space."""
    def integrand(t):
        r = point-start-t*vector
        return np.cross(vector, r)/np.linalg.norm(r)**3
    result, error = quad_vec(integrand, 0., upper, epsabs=2e-12, epsrel=2e-12)
    assert error < 2e-10
    return result/(4*np.pi)


def straight_beam(taper):
    # Nonzero sweep and dihedral; t is an arbitrary beam parameter, not arc.
    return parse_asw(f"""Name
Affine quarter-chord filament
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.80665 1.225 340.294
End
Reference
5 1 5
0 0 0
End
Beam 1
Straight tapered beam
t x y z chord Xax
-2 -.4 -2 -.2 {1-2*taper:.16g} .1
3 .6 3 .3 {1+3*taper:.16g} .1
End
""").beams[0]


@pytest.mark.parametrize('taper', [0., .15])
@pytest.mark.parametrize('wind', [(1., 0., 0.), (1., .17, -.11)])
@pytest.mark.parametrize('mach', [0., .57])
def test_straight_quarter_chord_subdivision_preserves_external_field(taper, wind, mach):
    e = np.array(wind); e /= np.linalg.norm(e)
    pg = np.eye(3)+(1/np.sqrt(1-mach**2)-1)*np.outer(e, e)
    beam = straight_beam(taper)
    span = np.array([.2, 1., .1]); span /= np.linalg.norm(span)
    across = np.linalg.norm(np.cross(e, span))
    # Derive the physical line directly from the fixture, not lifting_geometry.
    def quarter(t):
        return np.array([.2*t, t, .1*t])+.15*(1+taper*t)/across*e
    a, b = quarter(-2.), quarter(3.)
    points = np.array([[-1., -.7, 1.3], [2.1, .4, -.9], [4., 4.1, 1.7]])
    u = pg@e; u /= np.linalg.norm(u)
    expected = []
    for point in points@pg.T:
        aa, bb = pg@a, pg@b
        bound = integral_segment(point, aa, bb-aa, 1.)
        trailing = integral_segment(point, bb, u, np.inf)-integral_segment(point, aa, u, np.inf)
        expected.append((bound+trailing)@pg)
    expected = np.array(expected)
    for count in (4, 11, 32):
        for spacing in ('uniform', 'cosine'):
            settings = dict(default=count, beams={'1':dict(count=count, spacing=spacing)})
            mesh = mesh_beam(beam, settings)
            g = lifting_geometry([mesh], e)
            # Quarter-chord geometry and its weighted sample are collinear even
            # when the Glauert sample is not the arithmetic segment midpoint.
            f = (mesh.tm-mesh.t0)/(mesh.t1-mesh.t0)
            np.testing.assert_allclose(g['hv'], (1-f[:, None])*g['a']+f[:, None]*g['b'], atol=2e-13, rtol=0.)
            np.testing.assert_allclose(g['a'], np.array([quarter(t) for t in mesh.t0]), atol=2e-13, rtol=0.)
            np.testing.assert_allclose(g['b'], np.array([quarter(t) for t in mesh.t1]), atol=2e-13, rtol=0.)
            np.testing.assert_array_equal(g['b'][:-1], g['a'][1:])
            columns = horseshoe_velocity(points[:, None], g['a'][None], g['b'][None], e, pg)
            factored = FactoredInfluence(points, g['a'], g['b'], e, pg, 0.)
            gamma = np.full(len(mesh.tm), 1.7)
            for actual in (np.einsum('ijk,j->ik', columns, gamma), factored.apply(gamma)):
                np.testing.assert_allclose(actual, 1.7*expected, atol=3e-12, rtol=3e-11)


@pytest.mark.parametrize('shift', [-1.3, .7])
@pytest.mark.parametrize('mach', [0., .57])
def test_collinear_wakes_with_different_starts_retain_finite_bridge(shift, mach):
    e = np.array([1., .17, -.11]); e /= np.linalg.norm(e)
    pg = np.eye(3)+(1/np.sqrt(1-mach**2)-1)*np.outer(e, e)
    origin = np.array([.2, -.3, .1]); moved = origin+shift*e
    points = np.array([[-1., .4, .9], [2., -.8, .6], [4., 1., -1.]])
    transformed_direction = pg@e
    # S(moved)-S(origin) = -B(origin,moved), including negative shifts.
    actual = (semi_infinite_vortex((points-moved)@pg.T, np.zeros(3), transformed_direction)
              - semi_infinite_vortex((points-origin)@pg.T, np.zeros(3), transformed_direction))@pg
    expected = np.array([-integral_segment(pg@p, pg@origin, pg@(moved-origin), 1.)@pg for p in points])
    assert np.linalg.norm(expected) > 1e-4  # These finite bridges must not cancel.
    np.testing.assert_allclose(actual, expected, atol=3e-13, rtol=3e-12)
