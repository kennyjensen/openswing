"""Analytic and independent-quadrature checks of the material arc coordinate."""
import numpy as np
import pytest
from pathlib import Path
from scipy.integrate import quad
from scipy.interpolate import CubicSpline

from openswing.asw import Beam, Distribution, parse_asw
from openswing.arc_length import material_arc
from openswing.discretization import CURRENT_MESH_RECIPE, CHORDAL_MESH_RECIPE
from openswing.geometry import mesh_beam, model_meshes, undeformed_mesh


def polynomial_beam(functions, *, knots=(0., .2, .7, 1.), lifting=False):
    """Exact cubic test axes; endpoint derivatives specify the known curve."""
    knots = np.asarray(knots)
    distributions = {}
    for name, polynomial in zip(('x', 'y', 'z'), functions):
        p = np.polynomial.Polynomial(polynomial)
        d = Distribution(name, knots, p(knots), 1)
        spline = CubicSpline(knots, p(knots), bc_type=((1, p.deriv()(knots[0])), (1, p.deriv()(knots[-1]))))
        d._segments = [(knots[0], knots[-1], spline)]
        distributions[name] = d
    if lifting:
        distributions['chord'] = Distribution('chord', knots[[0, -1]], [.2, .2], 1)
    return Beam(1, 1, 'Analytic axis', distributions, 1)


def arc_parabola(t):
    return .5*t*np.sqrt(1+4*t*t)+.25*np.arcsinh(2*t)


def test_parabola_arc_inverse_and_source_knots_are_not_mesh_nodes():
    beam = polynomial_beam(([0, 0, 1], [0, 1], [0]))
    arc = material_arc(beam)
    t = np.r_[0., np.linspace(.003, .999, 101), 1.]
    np.testing.assert_allclose(arc.at(t), arc_parabola(t), atol=8e-15, rtol=2e-14)
    np.testing.assert_allclose(arc.inverse(arc_parabola(t)), t, atol=8e-15, rtol=0)
    assert arc.total == pytest.approx(arc_parabola(1), abs=2e-14)
    mesh = mesh_beam(beam, 8)
    assert mesh.mesh_recipe == CURRENT_MESH_RECIPE
    assert len(mesh.tm) == 8
    assert .2 not in mesh.t0 and .7 not in mesh.t0
    assert .2 in arc.knots and .7 in arc.knots
    np.testing.assert_allclose(np.cumsum(mesh.length), arc_parabola(1)*(1-np.cos(np.arange(1, 9)*np.pi/8))/2, atol=8e-15)
    recovered = undeformed_mesh(mesh)
    for name in ('t0', 't1', 'tm', 'ts', 'r0', 'r1', 'rm', 'frames', 'length', 'theta'):
        np.testing.assert_array_equal(getattr(recovered, name), getattr(mesh, name))


@pytest.mark.parametrize('spacing', ['uniform', 'cosine', 'modified-cosine'])
def test_nonlinear_straight_parameterization_has_the_same_physical_mesh(spacing):
    # y=t+t^3 and y=2t cover the same straight line with very different t.
    linear = polynomial_beam(([0], [0, 2], [0]))
    nonlinear = polynomial_beam(([0], [0, 1, 0, 1], [0]))
    panels = {'default': 40, 'beams': {'1': {'count': 40, 'spacing': spacing}}}
    a, b = mesh_beam(linear, panels), mesh_beam(nonlinear, panels)
    assert np.max(abs(a.t0-b.t0)) > .1
    for name in ('r0', 'r1', 'rm', 'frames', 'length', 'theta'):
        np.testing.assert_allclose(getattr(a, name), getattr(b, name), atol=2e-14, rtol=2e-14)


def test_curved_affine_parameter_rescaling_preserves_physical_sampling():
    original = polynomial_beam(([0, 0, 1], [0, 1], [0]))
    # u=(t+2)/5; same parabola with a shifted, scaled arbitrary parameter.
    scaled = polynomial_beam(([.16, .16, .04], [.4, .2], [0]), knots=(-2., -1., 1.5, 3.))
    a, b = mesh_beam(original, 40), mesh_beam(scaled, 40)
    for name in ('r0', 'r1', 'rm', 'frames', 'length', 'theta'):
        np.testing.assert_allclose(getattr(a, name), getattr(b, name), atol=2e-14, rtol=2e-14)


def test_tiny_curved_panel_length_uses_direct_local_integration():
    beam = polynomial_beam(([0, 0, 1], [0, 1], [0]))
    arc = material_arc(beam)
    a, b = 1-2e-10, 1-1e-10
    expected = quad(lambda t: np.sqrt(1+4*t*t), a, b, epsabs=1e-25, epsrel=1e-13)[0]
    assert float(arc.between(a, b)) == pytest.approx(expected, rel=5e-15, abs=1e-25)
    mesh = mesh_beam(beam, {'default': 4, 'beams': {'1': {'nodes': [0., .2, .7, a, b, 1.]}}})
    assert mesh.length[-2] == pytest.approx(expected, rel=5e-15)
    assert np.all(mesh.tm > mesh.t0) and np.all(mesh.tm < mesh.t1)
    np.testing.assert_array_equal(undeformed_mesh(mesh).length, mesh.length)


def test_short_interval_crossing_many_knots_does_not_subtract_prefix_arcs():
    t = np.r_[0., .9+np.arange(25)*1e-13, 1.]
    beam = Beam(1, 1, 'Small intervals after long arc', {
        name: Distribution(name, t, t, 1) for name in ('x', 'y')}, 1)
    arc = material_arc(beam)
    a, b = t[2], t[-3]
    expected = (b-a)*np.sqrt(2)
    assert expected > arc.total*1e-12
    assert float(arc.between(a, b)) == pytest.approx(expected, rel=3e-15)


def test_inverse_resolves_small_arc_near_zero_endpoint_speed():
    beam = polynomial_beam(([0, 0, 0, 1], [0], [0]), knots=(0., 1.))
    arc = material_arc(beam)
    targets = np.array([0., 1e-24, 1e-18, 1e-12, 1e-6, 1.])
    np.testing.assert_allclose(arc.inverse(targets), np.cbrt(targets), rtol=2e-14, atol=1e-22)


def test_doubled_position_jumps_and_reflected_axis_have_no_extra_material():
    d = {
        'chord': Distribution('chord', [0, 1], [.2, .2], 1),
        'x': Distribution('x', [0, .3, .3, 1], [0, .3, 100.3, 101], 1),
        'y': Distribution('y', [0, .3, .3, 1], [0, .3, .3, 1], 1),
        'z': Distribution('z', [-1, -.2, 1], [0, 0, 0], 1),
    }
    beam = Beam(1, 1, 'Reflected rigid offset', d, 1)
    arc = material_arc(beam)
    assert arc.total == pytest.approx(2*np.sqrt(2), abs=2e-14)
    t = np.array([-.7, -.3, 0, .3, .7])
    np.testing.assert_allclose(arc.at(t), (t+1)*np.sqrt(2), atol=2e-14)
    np.testing.assert_allclose(arc.inverse(arc.at(t)), t, atol=2e-14)
    mesh = mesh_beam(beam, 8)
    for knot in (-.3, 0., .3):
        assert knot in mesh.t0
    assert -.2 in arc.knots and -.2 not in mesh.t0
    assert np.max(np.linalg.norm(mesh.r0[1:]-mesh.r1[:-1], axis=1)) > 99
    assert np.sum(mesh.length) == pytest.approx(2*np.sqrt(2), abs=2e-14)


def test_axis_spline_extrapolation_is_integrated_through_the_beam_domain():
    beam = polynomial_beam(([0], [0, 1], [0]), knots=(0., .2, .7, 1.), lifting=True)
    # chord controls [-2,2]; axes with t0=0 reflect and extrapolate to both tips.
    beam.distributions['chord'] = Distribution('chord', [0, 2], [.2, .2], 1)
    beam.distributions['x'] = polynomial_beam(([0, 0, 1], [0, 1], [0])).distributions['x']
    arc = material_arc(beam)
    assert arc.total == pytest.approx(2*arc_parabola(2), rel=2e-14)
    q = np.array([-2, -1.4, -.4, 0, .3, 1.3, 2])
    expected = arc_parabola(2)+np.sign(q)*arc_parabola(abs(q))
    np.testing.assert_allclose(arc.at(q), expected, atol=3e-14)
    np.testing.assert_allclose(arc.inverse(expected), q, atol=3e-14)


def test_nonuniform_tip_curvature_matches_independent_adaptive_quadrature():
    t = np.array([0., .4, .8, .99, .9999, 1.])
    beam = Beam(1, 1, 'Small curved tip cell', {
        'x': Distribution('x', t, [0., 0., 0., .002, .008, .02], 1),
        'y': Distribution('y', t, t, 1),
    }, 1)
    arc = material_arc(beam)
    expected = sum(quad(lambda s: np.linalg.norm(beam.position(s, derivative=1)), a, b,
                        epsabs=1e-13, epsrel=1e-13)[0] for a, b in zip(t[:-1], t[1:]))
    assert arc.total == pytest.approx(expected, abs=2e-12)
    mesh = mesh_beam(beam, 40)
    length = np.array([sum(quad(lambda s: np.linalg.norm(beam.position(s, derivative=1)), a, b,
                               epsabs=1e-14, epsrel=1e-13)[0]
                          for a, b in zip(bounds[:-1], bounds[1:]))
                       for lo, hi in zip(mesh.t0, mesh.t1)
                       for bounds in [np.r_[lo, t[(t > lo) & (t < hi)], hi]]])
    np.testing.assert_allclose(mesh.length, length, atol=3e-13, rtol=3e-12)
    old = mesh_beam(beam, 40, mesh_recipe=CHORDAL_MESH_RECIPE)
    assert abs(np.sum(old.length)-expected) > 1e-6


@pytest.mark.parametrize('mutation', ['coefficient', 'knot', 'segment', 'replace', 'domain', 'mirror'])
def test_cache_tracks_actual_mutable_axis_inputs(mutation):
    beam = polynomial_beam(([0, 0, 1], [0, 1], [0]))
    first = material_arc(beam)
    assert material_arc(beam) is first
    d = beam.distributions['x']
    if mutation == 'coefficient':
        d._segments[0][2].c[2, 0] += .01
    elif mutation == 'knot':
        d._segments[0][2].x[1] += .001
    elif mutation == 'segment':
        d._segments[0] = (-.01, 1., d._segments[0][2])
    elif mutation == 'replace':
        beam.distributions['x'] = Distribution('x', [0, 1], [0, 2], 1)
    elif mutation == 'domain':
        beam.distributions['x'] = Distribution('x', [-.1, 1.1], [0, 1], 1)
    else:
        beam.distributions['chord'] = Distribution('chord', [0, 1], [.2, .2], 1)
    second = material_arc(beam)
    assert second is not first
    assert material_arc(beam) is second


def test_invalid_or_zero_length_geometry_fails_and_queries_are_bounded():
    beam = polynomial_beam(([0], [0], [0]))
    with pytest.raises(ValueError, match='zero-length'):
        material_arc(beam)
    arc = material_arc(polynomial_beam(([0], [0, 1], [0])))
    for bad in (-.01, 1.01, np.nan):
        with pytest.raises(ValueError, match='outside'):
            arc.at(bad)
        with pytest.raises(ValueError, match='outside'):
            arc.inverse(bad)
    with pytest.raises(ValueError, match='reversed'):
        arc.between(.7, .3)


def test_daedalus_coarse_mesh_inversion_terminates_at_representable_parameters():
    model = parse_asw((Path(__file__).resolve().parents[1]/'examples'/'dae.asw').read_text())
    meshes = model_meshes(model, 4)
    assert len(meshes) == len(model.beams)
    for mesh in meshes:
        assert np.all(np.isfinite(mesh.tm)) and np.all(np.isfinite(mesh.ts))
        assert np.all(mesh.tm > mesh.t0) and np.all(mesh.tm < mesh.t1)
        assert np.all(mesh.ts > mesh.t0) and np.all(mesh.ts < mesh.t1)
        arc = material_arc(mesh.beam)
        np.testing.assert_allclose(arc.at(mesh.ts), (arc.at(mesh.t0)+arc.at(mesh.t1))/2, atol=2e-14, rtol=2e-14)
