"""Knot-crossing body integrals and their field/geometry derivatives."""
import numpy as np
from numpy.polynomial import Polynomial
import pytest

from openswing.asw import parse_asw
from openswing.geometry import mesh_beam
from openswing.inertia import Motion
from openswing.volume import (VolumeField, body_loads, body_quadrature,
                              body_quadrature_count, body_quadrature_rule)


def model_for(policy='natural-v1'):
    return parse_asw('''Name
Knot-crossing body
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.81 1 340
End
Reference
1 1 1
End
Ground
1 0 0
End
Beam 1
Body
t x
0 0
1 1
t radius
0 .08
.07 .13
.22 .09
.31 .18
.63 .12
.91 .10
1 .09
t Cdf Cdp
0 0 0
1 0 0
End
''', beam_interpolation=policy)


def squared_radius_integral(beam, lo, hi):
    # Integrate squared spline polynomials exactly, without a quadrature rule.
    spline = beam.distributions['radius']._segments[0][2]
    result = 0.
    for i, (left, right) in enumerate(zip(spline.x, spline.x[1:])):
        a, b = max(lo, left), min(hi, right)
        if b > a:
            p = Polynomial(spline.c[:, i][::-1])
            primitive = (p*p).integ()
            result += primitive(b-left)-primitive(a-left)
    return result


@pytest.mark.parametrize('policy', ['natural-v1', 'drela-segspl-v1'])
def test_force_and_local_moment_match_endpoint_areas_and_exact_volume(policy):
    model = model_for(policy); beam = model.beams[0]
    mesh = mesh_beam(beam, 4)
    t, points, _, weights = body_quadrature(mesh)
    assert t.shape[1] > 8 and body_quadrature_count(mesh) == t.size
    np.testing.assert_allclose(weights.sum(axis=1), mesh.length, rtol=2e-15)
    velocity = np.array([.93, 0., .27])
    loads = body_loads(mesh, 1., np.broadcast_to(velocity, points.shape), Motion(), np.zeros(3))
    a0 = np.pi*beam.value('radius', mesh.t0, side='right')**2
    a1 = np.pi*beam.value('radius', mesh.t1, side='left')**2
    factor = velocity[0]*velocity[2]
    expected_force = factor*(a1-a0)
    volume = np.array([np.pi*squared_radius_integral(beam, a, b)
                       for a, b in zip(mesh.t0, mesh.t1)])
    expected_moment = -factor*((mesh.t1-mesh.tm)*a1-(mesh.t0-mesh.tm)*a0-volume)
    np.testing.assert_allclose(loads['lift'][:, 2], expected_force, rtol=2e-13, atol=1e-15)
    np.testing.assert_allclose(loads['moment'][:, 1], expected_moment, rtol=2e-12, atol=1e-15)


@pytest.mark.parametrize('policy', ['natural-v1', 'drela-segspl-v1'])
def test_pg_source_and_doublet_strengths_match_exact_area_and_volume(policy):
    model = model_for(policy); beam = model.beams[0]
    mesh = mesh_beam(beam, 4)
    direction = np.array([.93, 0., .27]); pg = np.diag([1.3, 1.1, .9])
    field = VolumeField(model, [mesh], direction, pg)
    xi = pg@direction
    expected_source = xi[0]*np.pi*(beam.value('radius', 1.)**2-beam.value('radius', 0.)**2)
    expected_doublet = 2*np.pi*squared_radius_integral(beam, 0., 1.)*1.3*np.array([0., 0., xi[2]])
    assert len(field.sources) == body_quadrature_count(mesh)
    assert field.sources.sum() == pytest.approx(expected_source, rel=2e-13, abs=1e-15)
    np.testing.assert_allclose(field.doublets.sum(axis=0), expected_doublet, rtol=2e-13, atol=1e-15)


def test_drag_table_knots_are_integrated_without_changing_the_mesh():
    from openswing.asw import Distribution
    model = model_for(); beam = model.beams[0]
    beam.distributions['radius'] = Distribution('radius', [0., 1.], [.1, .1], 1)
    beam.distributions['Cdf'] = Distribution('Cdf', [0., .09, .36, .81, 1.], [.01, .04, .02, .06, .03], 1)
    mesh = mesh_beam(beam, 4)
    _, points, _, _ = body_quadrature(mesh)
    assert len(mesh.t0) == 4
    velocity = np.array([1., 0., 0.])
    loads = body_loads(mesh, 1., np.broadcast_to(velocity, points.shape), Motion(), np.zeros(3))
    spline = beam.distributions['Cdf']._segments[0][2]
    expected = [.1*spline.integrate(a, b) for a, b in zip(mesh.t0, mesh.t1)]
    np.testing.assert_allclose(loads['profile'][:, 0], expected, rtol=2e-13, atol=1e-15)


def test_unsplit_rule_preserves_the_eight_point_gauss_rule():
    from openswing.asw import Distribution
    model = model_for(); beam = model.beams[0]
    beam.distributions['radius'] = Distribution('radius', [0., 1.], [.1, .1], 1)
    mesh = mesh_beam(beam, 4)
    u, w = body_quadrature_rule(mesh)
    nodes, weights = np.polynomial.legendre.leggauss(8)
    np.testing.assert_array_equal(u, np.tile((nodes+1)/2, (4, 1)))
    np.testing.assert_array_equal(w, np.tile(weights/2, (4, 1)))


def test_split_field_state_columns_include_pg_weights_and_images():
    from openswing.ground import GroundPlane
    from openswing.volume_state_tangent import VolumeStateTangent
    from test_volume_state_tangent import inputs, stencil
    model = model_for(); meshes = [mesh_beam(model.beams[0], 4)]
    e, pg, de, dp, points, dr = inputs()
    ground = GroundPlane(1, position=[0., 0., 2.], attitude=[8., -11., 4.])
    tangent = VolumeStateTangent(model, meshes, e, pg, de, dp, ground, pair_limit=17)
    actual = tangent.velocity_columns(points, dr)
    for h in (2e-5, 1e-5):
        expected = stencil(model, meshes, e, pg, de, dp, points, dr, ground, h, {})
        np.testing.assert_allclose(actual, expected, rtol=3e-7, atol=2e-10)


@pytest.mark.parametrize('chart', ['spatial', 'absolute'])
@pytest.mark.parametrize('freeze', [False, True])
def test_split_body_geometry_columns_follow_material_points(monkeypatch, chart, freeze):
    import test_geometry_partials as check
    monkeypatch.setattr(check, 'model_for', lambda name: model_for())
    net, fields, geometry, state_at = check.fixture('knotted-body', {'freeze_influences': freeze}, chart, panels=4)
    columns = [0, 7, 11]
    actual = geometry.columns(columns)
    for offset, column in enumerate(columns):
        for step in (1e-5, 3e-6):
            delta = np.zeros(6*net.nn); delta[column] = step
            samples = [fields.prepare(state_at(k*delta)) for k in (1, -1, 2, -2)]
            arrays = [list(check.leaves(actual, sample)) for sample in samples]
            for rows in zip(*arrays):
                path, derivative, _ = rows[0]
                a, b, c, d = [r[2] for r in rows]
                expected = (8*(a-b)-(c-d))/(12*step)
                if expected.size:
                    assert np.max(abs(derivative[..., offset]-expected)/(1+abs(expected))) < 2e-8, path
