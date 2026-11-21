"""Nonlinear thin-strip limits, moving-frame transport and source box loads."""
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from openswing.apparent_box import (
    endpoint_acceleration_wrench, endpoint_motion_wrench,
    interval_motion_wrench, rigid_acceleration_response,
)


def test_pitch_heave_limit_contains_rate_load_and_midchord_pitch_inertia():
    chord, xax, rho, u, q, qdot, az = .8, .13, 1.17, 23., .7, -.4, 1.8
    mu = rho*np.pi*chord**2/4
    arm = (.5-xax)*chord
    lift = mu*(u*q-az+arm*qdot)
    pitch = -arm*lift-mu*(chord*u*q/4+chord**2*qdot/32)
    f, m = endpoint_motion_wrench(np.eye(3), chord, xax, rho,
        [u,0,0], [0,0,az], [0,q,0], [0,qdot,0])
    np.testing.assert_allclose(f, [0,0,lift], rtol=2e-15, atol=1e-15)
    np.testing.assert_allclose(m, [0,pitch,0], rtol=2e-15, atol=1e-15)


def test_combined_roll_yaw_has_midchord_centrifugal_force_at_zero_axis_speed():
    chord, xax, rho, wx, wz = .65, -.2, 1.2, .6, -.9
    arm = (.5-xax)*chord
    fz = -rho*np.pi*chord**2/4*arm*wx*wz
    f, m = endpoint_motion_wrench(np.eye(3), chord, xax, rho,
        np.zeros(3), np.zeros(3), [wx,0,wz], np.zeros(3))
    np.testing.assert_allclose(f, [0,0,fz], atol=1e-16)
    np.testing.assert_allclose(m, [0,-arm*fz,0], atol=1e-16)


def test_zero_rates_recover_existing_acceleration_operator_for_broadcast_fields():
    rng = np.random.default_rng(824)
    frames = Rotation.from_rotvec(rng.normal(size=(6,3))).as_matrix()
    chord, xax, rho = rng.uniform(.1,1.1,6), rng.uniform(-.2,.9,6), rng.uniform(.8,1.3,6)
    a, alpha = rng.normal(size=(2,6,3))
    old = endpoint_acceleration_wrench(frames, chord, xax, rho, a, alpha)
    new = endpoint_motion_wrench(frames, chord, xax, rho, rng.normal(size=(6,3)), a, np.zeros(3), alpha)
    np.testing.assert_allclose(new, old, rtol=3e-15, atol=2e-16)


def test_absolute_midchord_acceleration_matches_differentiated_earth_trajectory():
    # Differentiate an actual composed rigid motion. Nonparallel frame/local
    # rates exercise the Omega cross omega angular-acceleration transport.
    omega = np.array([.7,-.4,.3]); local_rate = np.array([-.2,.8,.5])
    local_alpha = np.array([.4,-.1,.2]); origin_acc = np.array([.3,.2,-.4])
    r = np.array([.6,-.9,.2]); v = np.array([-.2,.4,.3]); adot = np.array([.5,-.3,.7])
    frame = Rotation.from_rotvec([.2,-.3,.4]).as_matrix()
    chord, xax, rho = .9, -.1, 1.18
    c, s, n = frame.T
    arm = (.5-xax)*chord*c
    total_rate = omega+local_rate
    alpha = local_alpha+np.cross(omega, local_rate)
    axis_acc = origin_acc+adot+2*np.cross(omega,v)+np.cross(omega,np.cross(omega,r))

    def point(t):
        re = Rotation.from_rotvec(omega*t).as_matrix()
        rl = Rotation.from_rotvec(local_rate*t+.5*local_alpha*t*t).as_matrix()
        return .5*origin_acc*t*t+re@(r+v*t+.5*adot*t*t+rl@arm)

    def second(h):
        return (-point(2*h)+16*point(h)-30*point(0)+16*point(-h)-point(-2*h))/(12*h*h)

    numerical = (16*second(.002)-second(.004))/15
    air = np.array([17.,-2.,3.])
    mu = rho*np.pi*chord**2/4
    normal_rate = np.dot(np.cross(air,total_rate),n)
    f = mu*(normal_rate-np.dot(numerical,n))*n
    m = np.cross(arm,f)-mu*(chord*normal_rate/4+chord**2*np.dot(alpha,s)/32)*s
    actual = endpoint_motion_wrench(frame,chord,xax,rho,air,axis_acc,total_rate,alpha)
    np.testing.assert_allclose(actual,[f,m],rtol=0,atol=3e-10)
    omitted = endpoint_motion_wrench(frame,chord,xax,rho,air,axis_acc,total_rate,local_alpha)
    assert np.max(abs(np.array(omitted)-actual)) > .01


def test_nonlinear_wrench_is_covariant_and_uses_relative_fluid_velocity():
    frame = Rotation.from_rotvec([.4,-.2,.1]).as_matrix()
    args = [np.array(v) for v in ([12.,-4.,3.],[.2,-.7,.4],[.6,.1,-.3],[-.2,.5,.7])]
    actual = endpoint_motion_wrench(frame,.7,.2,1.1,*args)
    q = Rotation.from_rotvec([-.5,.3,.8]).as_matrix()
    moved = endpoint_motion_wrench(q@frame,.7,.2,1.1,*[q@v for v in args])
    np.testing.assert_allclose(moved,[q@v for v in actual],rtol=5e-15,atol=4e-16)
    # Equal inertial boosts of air and section leave their relative velocity.
    air, section, boost = args[0]+[2.,3.,4.], np.array([2.,3.,4.]), np.array([40.,-20.,60.])
    boosted = endpoint_motion_wrench(frame,.7,.2,1.1,(air+boost)-(section+boost),*args[1:])
    np.testing.assert_allclose(boosted,actual,rtol=2e-15,atol=2e-16)


def test_box_averages_completed_velocity_rate_products_before_force_moment():
    rho, h, q = 1.2, 2.4, .6
    chord = np.array([.2,.8]); u = np.array([20.,40.])
    positions = np.array([[0.,-1.,0.],[0.,1.,0.]])
    frames = np.broadcast_to(np.eye(3),(2,3,3))
    velocities = np.column_stack((u,np.zeros((2,2))))
    rates = np.array([[0.,q,0.],[0.,q,0.]])
    f,m = interval_motion_wrench(positions,frames,chord,[.5,.5],h,rho,
        velocities,np.zeros((2,3)),rates,np.zeros((2,3)),np.zeros(3))
    mu = rho*np.pi*chord**2/4
    expected_lift = h/2*np.sum(mu*u*q)
    expected_pitch = -h/2*np.sum(mu*chord*u*q/4)
    np.testing.assert_allclose(f,[0,0,expected_lift],rtol=2e-15,atol=1e-15)
    np.testing.assert_allclose(m,[0,expected_pitch,0],rtol=2e-15,atol=1e-15)
    # Endpoint r cross f would create a spurious roll couple in this source rule.
    assert m[0] == 0


@pytest.mark.parametrize('column',range(6))
def test_finite_motion_acceleration_increment_has_existing_source_response(column):
    r = np.array([[.2,-.8,.4],[.6,1.3,-.2]])
    frames = Rotation.from_rotvec([[.2,-.3,.1],[-.1,.4,.2]]).as_matrix()
    chords, axes = np.array([.37,.81]), np.array([-.2,.73])
    h,rho,reference = 2.7,1.17,np.array([-.4,.3,.6])
    matrix = rigid_acceleration_response(*r,*frames,*chords,*axes,h,rho,reference)
    velocity = np.array([[20.,-2.,3.],[17.,1.,4.]])
    rates = np.array([[.3,-.2,.7],[-.4,.6,.2]])
    acceleration = np.array([[.1,.5,-.3],[.7,-.1,.2]])
    alpha = np.array([[.2,.1,-.3],[-.4,.2,.6]])
    delta = np.eye(6)[column]
    da = delta[:3]+np.cross(delta[3:],r-reference)
    first = np.concatenate(interval_motion_wrench(r,frames,chords,axes,h,rho,velocity,
        acceleration-da,rates,alpha-delta[3:],reference))
    second = np.concatenate(interval_motion_wrench(r,frames,chords,axes,h,rho,velocity,
        acceleration+da,rates,alpha+delta[3:],reference))
    np.testing.assert_allclose((second-first)/2,-matrix[:,column],rtol=2e-13,atol=2e-15)


def test_box_broadcasts_batches_and_preserves_reference_translation():
    positions = np.array([[[0.,-1.,0.],[0.,1.,0.]],[[.2,-.6,.4],[.3,1.2,.1]]])
    frames = np.broadcast_to(np.eye(3),(2,3,3))
    chord,xax,length,rho = [.4,.7],[.2,.6],np.array([2.,2.7]),np.array([1.1,1.3])
    vectors = [np.array(x) for x in ([[20.,0.,0.],[21.,0.,0.]],[[.2,.1,.3],[.1,.4,.8]],
                                    [[.3,.2,.4],[.1,.7,-.2]],[[.1,.2,.3],[.4,.5,.6]])]
    f,m = interval_motion_wrench(positions,frames,chord,xax,length,rho,*vectors,np.zeros(3))
    shift = np.array([.7,-.4,.9])
    shifted = interval_motion_wrench(positions,frames,chord,xax,length,rho,*vectors,shift)
    np.testing.assert_allclose(shifted[0],f,atol=0,rtol=0)
    np.testing.assert_allclose(shifted[1],m-np.cross(shift,f),rtol=3e-15,atol=5e-16)
    for i in range(2):
        individual = interval_motion_wrench(positions[i],frames,chord,xax,length[i],rho[i],*vectors,np.zeros(3))
        np.testing.assert_allclose([f[i],m[i]],individual,atol=1e-15,rtol=2e-15)


@pytest.mark.parametrize('measure', ['chord','density'])
def test_zero_physical_measure_has_zero_full_motion_load_without_speed_division(measure):
    chord,rho = (0.,1.2) if measure=='chord' else (.7,0.)
    actual = endpoint_motion_wrench(np.eye(3),chord,.2,rho,[0,0,0],[1,2,3],[4,5,6],[7,8,9])
    np.testing.assert_array_equal(actual,np.zeros((2,3)))


@pytest.mark.parametrize('field', range(4))
def test_nonfinite_motion_fields_are_rejected(field):
    vectors = [np.zeros(3) for _ in range(4)]
    vectors[field][1] = np.nan
    with pytest.raises(ValueError,match='finite'):
        endpoint_motion_wrench(np.eye(3),.7,.2,1.2,*vectors)
