"""Straight-axis arc lengths must not depend on quadrature batch reduction."""
import numpy as np
import pytest

from openswing.arc_length import material_arc
from test_arc_length import polynomial_beam


@pytest.mark.parametrize('speed',[.125,1.,8.])
@pytest.mark.parametrize('count',[1,4,257])
def test_constant_speed_integral_is_exact_for_each_batched_interval(speed,count):
    beam=polynomial_beam(([0],[0,speed],[0]),knots=(-100000.,100000.))
    arc=material_arc(beam)
    # These widths include the four intervals of the large-span UA-1 limit.
    nodes=np.array([-100000.,-70710.67811865476,0.,70710.67811865473,100000.])
    indices=np.arange(count)%4
    left,right=nodes[indices],nodes[indices+1]
    expected=(right-left)*speed
    np.testing.assert_array_equal(arc.between(left,right),expected)
    assert arc.total==200000.*speed
    # One interval and a batch describe precisely the same straight segment.
    individual=np.array([float(arc.between(a,b)) for a,b in zip(left,right)])
    np.testing.assert_array_equal(individual,expected)


def test_constant_preservation_retains_zero_width_queries():
    arc=material_arc(polynomial_beam(([0],[0,1],[0]),knots=(-1e5,1e5)))
    positions=np.array([-1e5,-.125,0.,.125,1e5])
    np.testing.assert_array_equal(arc.between(positions,positions),np.zeros(5))
