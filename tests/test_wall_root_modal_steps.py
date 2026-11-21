"""Small adjacent strips constrain differentiation, never physical clearance."""
from dataclasses import replace
import numpy as np
import pytest

from openswing.ground import GroundIntersectionError
from openswing.linear_dynamics import make_system, linearize
from openswing.source_airflow import AIRFLOW_POLICY
from openswing.wall_root import wall_root_derivatives, wall_root_coordinate_scales
from test_wall_root import configuration, flight


def clustered(first=.0002):
    model, panels = configuration(False, interpolation='drela-segspl-v1')
    panels['beams']['1']['nodes'] = [1., 1.+first, 1.4, 1.8, 2.]
    return make_system(model, replace(flight(), alpha=0.), panels,
        gravity=[0.,0.,0.], structural_operator=AIRFLOW_POLICY, tolerance=1e-10)[0]


def test_complete_clustered_wall_pencil_matches_independent_smaller_stencil():
    s = clustered(); n = s.network
    a, m = linearize(s, sparse=True)
    report = s.state_derivative_diagnostics['wall_root_coordinate_steps']
    assert report['columns']
    root = n.node(1, 1.)
    assert all(6*root <= row['column'] < 6*root+6 for row in report['columns'])
    assert all(row['actual'] < row['requested'] and row['maximum_stencil_displacement'] <=
               row['neighborhood_radius']/2*(1+1e-15) for row in report['columns'])
    h = min(row['actual'] for row in report['columns'])/2
    assert 1e-7 <= h < 1e-5
    dense_a, dense_m = linearize(s, step=h)
    np.testing.assert_allclose(a.toarray(), dense_a, rtol=3e-8, atol=3e-9)
    np.testing.assert_allclose(m.toarray(), dense_m, rtol=3e-10, atol=3e-11)
    zero = np.zeros(s.size)
    assert np.max(abs(s.residual(zero,zero))) < 1e-9
    bad = zero.copy(); bad[6*root+1] = -1e-6
    with pytest.raises(GroundIntersectionError):
        s.residual(bad,zero)


def test_geometry_bounds_reduce_only_root_coordinates_and_preserve_the_input():
    s = clustered(); n = s.network
    before = np.ones(s.size)
    # Outside the owned derivative context there is no clearance exemption.
    actual, report = wall_root_coordinate_scales(s, before, 1e-5)
    np.testing.assert_array_equal(actual,before)
    assert report['columns'] == []
    with wall_root_derivatives(n,s.base,root_motion=True):
        actual, report = wall_root_coordinate_scales(s,before,1e-5)
        changed = np.flatnonzero(actual != before)
        assert list(changed) == [row['column'] for row in report['columns']]
        assert np.all(actual[changed] < 1.)
        for row in report['columns']:
            delta=np.zeros(s.size);delta[row['column']]=2*row['actual']
            assert np.isfinite(s.residual(delta,np.zeros(s.size))).all()
            assert np.isfinite(s.residual(-delta,np.zeros(s.size))).all()
    np.testing.assert_array_equal(before,np.ones(s.size))


def test_unresolved_wall_stencil_is_rejected_without_enlarging_the_neighborhood():
    # Exercise the differentiation floor independently of static initialization,
    # which has its own geometry probes and rejects an unresolved tiny strip.
    from openswing.wall_root import _PROBE
    s=clustered()
    with wall_root_derivatives(s.network,s.base,root_motion=True):
        owned=_PROBE.get()
        tiny=replace(owned,radius=1e-9)
        token=_PROBE.set(tiny)
        try:
            with pytest.raises(GroundIntersectionError,match='supported modal minimum'):
                wall_root_coordinate_scales(s,np.ones(s.size),1e-5)
            assert _PROBE.get() is tiny
            assert tiny.radius == 1e-9
        finally:
            _PROBE.reset(token)
    assert _PROBE.get() is None


def test_nonwall_coordinate_scales_and_existing_stencil_remain_unchanged():
    model, panels = configuration(True,interpolation='drela-segspl-v1')
    s,_=make_system(model,replace(flight(True),alpha=0.),panels,
        gravity=[0.,0.,0.],structural_operator=AIRFLOW_POLICY,tolerance=1e-10)
    scales=np.linspace(1.,2.,s.size)
    with wall_root_derivatives(s.network,s.base,root_motion=True):
        actual, report=wall_root_coordinate_scales(s,scales,1e-5)
    np.testing.assert_array_equal(actual,scales)
    assert not report['columns']
