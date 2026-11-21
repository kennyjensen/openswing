"""Differentiate independent physical trajectories to verify moving-frame terms."""
import numpy as np
import pytest
from openswing.local_motion import (LocalMotion, NetworkMotion, left_jacobian,
    rotation_interpolation, rotation_matrix as exp, rotation_vector as log, mv)
from openswing.inertia import Motion
from openswing.network import StaticNetwork
from test_network import model


def unskew(matrix):
    return np.stack([matrix[...,2,1]-matrix[...,1,2], matrix[...,0,2]-matrix[...,2,0],
                     matrix[...,1,0]-matrix[...,0,1]],axis=-1)/2


@pytest.mark.parametrize('scale',[0.,1e-7,.0099,.0101,.7,2.9])
def test_rotation_jacobian_and_derivative_against_matrix_trajectory(scale):
    k=np.array([.3,-.4,.5]);k*=scale/np.linalg.norm(k)
    d=np.array([-.7,.2,.4]);h=1e-5
    r=exp(k);rp=exp(k+h*d);rm=exp(k-h*d)
    np.testing.assert_allclose(mv(left_jacobian(k),d),unskew((rp-rm)@r.T/(2*h)),atol=3e-11)
    numeric=(left_jacobian(k+h*d)-left_jacobian(k-h*d))/(2*h)
    np.testing.assert_allclose(left_jacobian(k,d),numeric,atol=1e-9)


@pytest.mark.parametrize('fraction',[0.,.13,.5,1.])
def test_interpolated_rates_and_acceleration_differentiate_actual_so3_arc(fraction):
    ra,rb=exp([[.4,-.3,.2],[-.2,.5,.7]])
    wa,wb=np.array([[.3,-.7,.2],[-.5,.1,.6]])
    aa,ab=np.array([[-.4,.2,.6],[.8,-.1,.3]])
    r,w,a,_=rotation_interpolation(ra,rb,wa,wb,aa,ab,fraction)
    def trajectory(t):
        x=exp(t*wa+.5*t*t*aa)@ra;y=exp(t*wb+.5*t*t*ab)@rb
        return x@exp(fraction*log(x.T@y))
    h=2e-4;plus,minus=trajectory(h),trajectory(-h)
    np.testing.assert_allclose(r,trajectory(0),atol=1e-15)
    np.testing.assert_allclose(w,unskew((plus-minus)@r.T/(2*h)),atol=2e-8)
    np.testing.assert_allclose(a,unskew((plus-2*r+minus)@r.T/h**2),atol=2e-8)


def test_pylon_absolute_acceleration_and_angular_transport_match_earth_trajectory():
    r,u,ud=np.array([[.7,-.4,.2],[.3,.2,-.6],[-.4,.1,.3]])
    w,wd,d=np.array([[.8,-.3,.2],[-.2,.5,.3],[.2,-.5,.4]])
    omega,alpha,origin_acc=np.array([[-.3,.6,.4],[.3,-.2,.1],[.8,.5,-.7]])
    field=LocalMotion(r,u,w,ud,wd)
    motion=Motion(omega,origin_acc,alpha)
    def trajectory(t):
        earth=exp(t*omega+.5*t*t*alpha);local=exp(t*w+.5*t*t*wd)
        return .5*t*t*origin_acc+earth@(r+t*u+.5*t*t*ud+local@d),earth@local
    h=2e-4;p0,r0=trajectory(0);pp,rp=trajectory(h);pm,rm=trajectory(-h)
    np.testing.assert_allclose(field.absolute_acceleration(p0,motion,np.zeros(3)),(pp-2*p0+pm)/h**2,atol=4e-8)
    np.testing.assert_allclose(field.absolute_angular_acceleration(motion),unskew((rp-2*r0+rm)@r0.T/h**2),atol=3e-8)
    # The transport term cannot be omitted when both frames rotate.
    assert np.linalg.norm(np.cross(omega,w))>.4


def moving_network():
    # Curved, twisted jig with a physical offset at the doubled station.
    b='''Beam 1
Moving beam
t x y z twist
0 0 0 0 12
1 .1 1 .3 35
1 .3 1 .5 55
2 .7 2 .6 70
End
'''
    net=StaticNetwork(model(b),6,None,[0,0,0],[])
    rng=np.random.default_rng(903)
    r=net.rj+rng.normal(0,.02,(net.nn,3));q=exp(rng.normal(0,.12,(net.nn,3)))
    values=rng.normal(0,.3,(4,net.nn,3))
    return net,r,q,values


def test_network_material_strain_rate_matches_differentiated_geometry():
    net,r,q,values=moving_network();u,w,ud,wd=values
    field=NetworkMotion(net,r,q,*values)
    def strain(t):
        p0,p1,ra,rb,_,_=net.geometry(r+t*u,exp(t*w)@q)
        k=log(ra.transpose(0,2,1)@rb);mid=ra@exp(k/2)
        return np.c_[mv(mid.transpose(0,2,1),p1-p0)-net.v0,k-net.k0]/net.ds[:,None]
    h=1e-5
    np.testing.assert_allclose(field.strain_rate(),(strain(h)-strain(-h))/(2*h),atol=2e-10)


@pytest.mark.parametrize('material',[False,True])
def test_network_quadrature_sampling_follows_geometry_with_offset_endpoints(material):
    net,r,q,values=moving_network();u,w,ud,wd=values
    fractions=np.broadcast_to([.1,.4,.9],(net.ne,3))
    field=NetworkMotion(net,r,q,*values)
    local,rotation,_=field.sample(1,fractions,material=material)
    def sampled(t):
        rt=r+t*u+.5*t*t*ud;qt=exp(t*w+.5*t*t*wd)@q
        sampled=NetworkMotion(net,rt,qt,*values).sample(1,fractions,material=material)
        return sampled[0].origin,sampled[1]
    h=2e-4;pp,rp=sampled(h);pm,rm=sampled(-h)
    np.testing.assert_allclose(local.velocity,(pp-pm)/(2*h),atol=4e-9)
    np.testing.assert_allclose(local.acceleration,(pp-2*local.origin+pm)/h**2,atol=3e-8)
    np.testing.assert_allclose(local.rates,unskew((rp-rm)@rotation.swapaxes(-1,-2)/(2*h)),atol=1e-8)
    np.testing.assert_allclose(local.rate_derivative,unskew((rp-2*rotation+rm)@rotation.swapaxes(-1,-2)/h**2),atol=4e-8)


def test_rigid_network_motion_has_zero_material_strain_rate():
    net,r,q,_=moving_network();w=np.array([.6,-.3,.4]);v=np.array([.1,.3,-.2])
    zero=np.zeros_like(r)
    field=NetworkMotion(net,r,q,v+np.cross(w,r),np.broadcast_to(w,r.shape),zero,zero)
    # Subtracting endpoint velocities and dividing by a short interval amplifies
    # floating-point roundoff. Scale the zero-identity bound with the input
    # velocity/rotation and element length, rather than a dimensional constant.
    scale = max(np.linalg.norm(field.va,axis=1).max(),
                np.linalg.norm(field.vb,axis=1).max(),
                np.linalg.norm(w)*np.linalg.norm(r,axis=1).max())
    # Curvature-rate roundoff has angular-velocity/length units, distinct
    # from the translational strain-rate bound.
    scales = np.r_[np.full(3,scale),np.full(3,np.linalg.norm(w))]
    roundoff = 32*np.finfo(float).eps*scales/net.ds[:,None]
    actual = field.strain_rate()
    assert np.all(abs(actual) <= roundoff), (actual, roundoff)


def test_pi_arc_is_rejected_instead_of_returning_ambiguous_rates():
    z=np.zeros(3)
    with pytest.raises(ValueError,match='approaches pi'):
        rotation_interpolation(np.eye(3),exp([np.pi,0,0]),z,z,z,z,.5)
