"""Stationary spatial arcs retain geometry and independently batched zero rates."""
import numpy as np
import pytest
from openswing.local_motion import rotation_interpolation


def about_z(angle):
    angle = np.asarray(angle)
    out = np.zeros(angle.shape + (3,3))
    out[...,0,0] = out[...,1,1] = np.cos(angle)
    out[...,1,0] = np.sin(angle)
    out[...,0,1] = -np.sin(angle)
    out[...,2,2] = 1.
    return out


@pytest.mark.parametrize('case', ['scalar','quadrature','rates_batch','acceleration_batch'])
def test_stationary_arc_keeps_rotation_and_all_existing_broadcast_shapes(case):
    # A fixed noncommuting initial frame and a fixed local z-axis twist.
    ra = np.array([[1.,0.,0.], [0.,0.,-1.], [0.,1.,0.]])
    angle, fraction = .7, .37
    wa = wb = aa = ab = np.zeros(3)
    rotation_shape, w_shape, a_shape, kd_shape = (3,3), (3,), (3,), (3,)
    if case == 'quadrature':
        ra = np.broadcast_to(ra, (2,1,3,3))
        angle = np.array([[.7],[-.4]])
        fraction = np.array([[0.,.2,.8,1.]])
        wa = wb = np.zeros((2,1,3))
        aa = ab = np.zeros((1,4,3))
        rotation_shape, w_shape, a_shape, kd_shape = (2,4,3,3), (2,4,3), (2,4,3), (2,1,3)
    elif case == 'rates_batch':
        wa = wb = np.zeros((2,3))
        w_shape = a_shape = kd_shape = (2,3)
    elif case == 'acceleration_batch':
        aa = ab = np.zeros((4,3))
        a_shape = (4,3)
    rb = ra @ about_z(angle)
    rotation, w, a, kd = rotation_interpolation(ra,rb,wa,wb,aa,ab,fraction)
    assert (rotation.shape,w.shape,a.shape,kd.shape) == (rotation_shape,w_shape,a_shape,kd_shape)
    np.testing.assert_allclose(rotation, ra @ about_z(np.asarray(fraction)*angle), atol=4e-16, rtol=0)
    assert np.count_nonzero(w) == np.count_nonzero(a) == np.count_nonzero(kd) == 0


def test_stationary_pi_arc_still_refuses_an_ambiguous_tangent():
    zero = np.zeros(3)
    with pytest.raises(ValueError, match='approaches pi'):
        rotation_interpolation(np.eye(3), about_z(np.pi), zero,zero,zero,zero,.5)
