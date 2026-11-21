"""Independent rotation-product, constitutive and body-beam dynamics checks."""
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.source_fuselage import frame_from_angles, angles_from_frame, angle_matrix, angle_matrix_rate, euler_rates
from openswing.source_discrete import (angle_matrix as mixed_matrix, angles_from_frame as mixed_angles,
    solve_source_discrete, SourceSectionNetwork)
from openswing.source_dynamics import source_strain_rates, MOVING_POLICY, DYNAMIC_POLICY
from openswing.source_time import SourceTimeChart
from openswing.linear_dynamics import make_system, linearize, eigensystem
from test_source_time_angles import axis, product as surface_product
from test_source_moving_system import AXIAL_SOURCE, beam_source, directional

PANELS={'default':4,'beams':{'1':{'count':4,'spacing':'uniform'}}}
BODY_SOURCE=AXIAL_SOURCE.replace('t x y z chord\n1 0 0 0 .2\n3 0 2 0 .2',
    't x y z radius\n1 0 0 0 .1\n3 2 0 0 .1').replace(
    '1 3 0 2 0 30','1 3 2 0 0 30')
ENGINE='''Engine
1 0 1 3 2 0 0 1 0 0 1 0 -1 80 0 0 0 0 0 0 0 0 0 0 0
End
'''


def model(source=BODY_SOURCE):
    return parse_asw(source,beam_interpolation='drela-segspl-v1')


def product(q,dq):
    """Eq.10 transposed: Rz(psi) Rx(phi) Ry(theta), with product derivative."""
    rr=[];dd=[]
    for ax,k in ((2,2),(0,0),(1,1)):
        r,generator=axis(ax,q[k]);rr.append(r);dd.append(dq[k]*generator@r)
    a,b,c=rr;da,db,dc=dd
    r=a@b@c;rd=da@b@c+a@db@c+a@b@dc
    w=rd@r.T
    return r,np.array([w[2,1],w[0,2],w[1,0]])


@pytest.mark.parametrize('q',[[.3,-.4,.7],[-.5,.2,-2.2],[0.,0.,-np.pi/2],[.2,.6,np.pi/2]])
def test_body_chart_and_curvature_follow_independent_rotation_product(q):
    q=np.array(q);r,_=product(q,np.zeros(3))
    np.testing.assert_allclose(frame_from_angles(q),r,atol=4e-16)
    np.testing.assert_allclose(angles_from_frame(r),q,atol=4e-16)
    expected=np.column_stack([r.T@product(q,d)[1] for d in np.eye(3)])
    np.testing.assert_allclose(angle_matrix(q),expected,atol=4e-16)
    dq=np.array([.4,-.2,.7]);w=product(q,dq)[1]
    np.testing.assert_allclose(euler_rates(q,w),dq,atol=4e-16)
    np.testing.assert_allclose(mixed_matrix(q,True),expected,atol=4e-16)
    np.testing.assert_allclose(mixed_angles(r,True),q,atol=4e-16)
    numeric=np.imag(angle_matrix(q+1e-25j*dq))/1e-25
    np.testing.assert_allclose(angle_matrix_rate(q,dq),numeric,atol=3e-16)


def test_mixed_material_charts_and_actual_body_pole():
    q=np.array([[.2,.3,.4],[-.3,-.2,2.1],[.1,-.2,-.4],[.2,.1,-np.pi/2]])
    mask=np.array([False,True,False,True])
    r=np.array([(product if b else surface_product)(p,np.zeros(3))[0] for p,b in zip(q,mask)])
    np.testing.assert_allclose(mixed_angles(r,mask),q,atol=5e-16)
    for i,b in enumerate(mask):
        expected=np.column_stack([r[i].T@(product if b else surface_product)(q[i],d)[1] for d in np.eye(3)])
        np.testing.assert_allclose(mixed_matrix(q,mask)[i],expected,atol=4e-16)
    with pytest.raises(AnalysisError,match='vertical'):
        angles_from_frame(product([np.pi/2,0,0],np.zeros(3))[0])


def test_full_endpoint_curvature_rate_matches_differentiated_rotation_products():
    qa=np.array([[.2,-.3,-1.5],[-.3,.2,1.4]])
    qb=qa+[[.12,.18,.2],[.1,-.1,.3]]
    dqa=np.array([[.4,-.2,.3],[-.2,.5,.7]]);dqb=dqa+[[.2,.3,-.2],[.1,-.4,.2]]
    pa=np.array([[0.,0.,0.],[.1,-.2,.3]]);pb=pa+[[1.,.3,.2],[.8,.2,-.1]]
    va=np.array([[.2,.3,.1],[-.1,.2,-.2]]);vb=va+[[.4,.2,-.3],[.1,.5,.3]]
    ra,wa=map(np.array,zip(*(product(q,dq) for q,dq in zip(qa,dqa))))
    rb,wb=map(np.array,zip(*(product(q,dq) for q,dq in zip(qb,dqb))))
    length=np.array([1.2,.9])
    actual=source_strain_rates(pa,pb,ra,rb,va,vb,wa,wb,length,True)
    def curvature(t):
        out=[]
        for a,b in zip(qa+t*dqa,qb+t*dqb):
            rr_a=product(a,np.zeros(3))[0];rr_b=product(b,np.zeros(3))[0]
            ka=np.column_stack([rr_a.T@product(a,e)[1] for e in np.eye(3)])
            kb=np.column_stack([rr_b.T@product(b,e)[1] for e in np.eye(3)])
            out.append((ka+kb)@(b-a)/2)
        return np.array(out)/length[:,None]
    np.testing.assert_allclose(actual[:,3:],np.imag(curvature(1e-25j))/1e-25,rtol=2e-14,atol=2e-15)
    expected=np.einsum('nij,nj->ni',(ra+rb).transpose(0,2,1)/2,
        vb-va-np.cross((wa+wb)/2,pb-pa))/length[:,None]
    np.testing.assert_allclose(actual[:,:3],expected,atol=2e-15)


@pytest.mark.parametrize('body_only',[False,True])
def test_mixed_euler_bdf_and_periodic_body_yaw_history(body_only):
    flags=np.array([True,True]) if body_only else np.array([False,True])
    jig=np.array([(product if b else surface_product)([.1,.2,.3],np.zeros(3))[0] for b in flags])
    chart=SourceTimeChart(SimpleNamespace(nn=4,a=np.array([0,2]),b=np.array([1,3]),
        R0a=jig,R0b=jig,source_fuselage=flags))
    previous=None
    for t in np.arange(0.,7.1,.2):
        q=np.array([[.2,-.3,2.9+t] if b else [2.9+t,-.3,.2] for b in np.repeat(flags,2)])
        dq=np.array([[0,0,1] if b else [1,0,0] for b in np.repeat(flags,2)])
        values=[(product if b else surface_product)(p,d) for p,d,b in zip(q,dq,np.repeat(flags,2))]
        state=SimpleNamespace(Q=np.array([x[0] for x in values])@chart.jig_frames.transpose(0,2,1),
            w=np.array([x[1] for x in values]),orientation=np.eye(3),Omega=np.zeros(3))
        chart.bind(state,previous)
        np.testing.assert_allclose(state.source_angles,q,atol=6e-15)
        if previous is not None:
            local,frame=chart.rates(state,previous,None,[5.,-5.,0.])
            np.testing.assert_allclose(local,0.,atol=2e-14);np.testing.assert_allclose(frame,0.,atol=1e-15)
            restored=deepcopy(state);restored.source_angles=None;restored.source_attitude=None
            chart.unpack(restored,chart.pack(state))
            np.testing.assert_array_equal(restored.source_angles,state.source_angles)
        previous=state


def test_axial_body_static_extension_and_force_balance():
    result=solve_source_discrete(model(),PANELS,gravity=[0,0,0],
        loads=[dict(beam=1,t=3,force=[10,0,0])],tolerance=1e-11)
    np.testing.assert_allclose(result['nodes'][-1]['position'],[2.1,0,0],atol=3e-10)
    np.testing.assert_allclose(result['support_force'],[-10,0,0],atol=3e-9)
    np.testing.assert_allclose(result['moment_balance'],0,atol=2e-9)


@pytest.mark.parametrize('torsion',[False,True])
def test_finite_body_bending_and_torsion_match_discrete_endpoint_oracle(torsion):
    text=BODY_SOURCE.replace('200 0 0 0 0 0','200 100 80 120 0 0')
    load=np.array([12.,0,0]) if torsion else np.array([0.,-20,0])
    result=solve_source_discrete(model(text),PANELS,gravity=[0,0,0],
        loads=[dict(beam=1,t=3,moment=load.tolist())],tolerance=1e-11)
    coordinate=np.linspace(0,2,5);rate=.15 if torsion else .2
    angles=np.zeros((5,3));angles[:,2]=-np.pi/2;angles[:,1 if torsion else 0]=rate*coordinate
    frames=np.array([product(q,np.zeros(3))[0] for q in angles])
    expected=np.vstack([np.zeros(3),np.cumsum((frames[:-1,:,1]+frames[1:,:,1])*.25,axis=0)])
    np.testing.assert_allclose([n['position'] for n in result['nodes']],expected,atol=4e-9)
    np.testing.assert_allclose([n['rotation'] for n in result['nodes']],frames@frames[0].T,atol=3e-9)
    np.testing.assert_allclose(result['support_moment'],-load,atol=4e-8)


@pytest.mark.parametrize('frame,operator,omega',[('fixed',DYNAMIC_POLICY,np.sqrt(100/3)),
                                               ('free',MOVING_POLICY,np.sqrt(250/3))])
def test_body_axial_modes_match_independent_two_mass_spring(frame,operator,omega):
    system,_=make_system(model(),panels=PANELS,frame=frame,gravity_magnitude=0.,
        structural_operator=operator,tolerance=1e-11)
    modes,metadata=eigensystem(*linearize(system),time_scale=system.W,
        count=1,method='full_shift_invert',shift=(-.1,omega))
    assert len(modes)==1
    assert abs(complex(*modes[0]['eigenvalue'])-1j*omega)<2e-7


def test_body_moving_sparse_pencil_matches_full_residual_directions():
    from openswing.inertia import Motion
    # Keep local csn properties but use an x-directed fuselage with finite
    # shear, offsets, damping, distributed mass and nonzero frame motion.
    text=beam_source().replace('t x y z chord\n1 0 0 0 .2\n2 0 1 0 .2',
        't x y z radius\n1 0 0 0 .1\n2 1 0 0 .1')
    system,_=make_system(model(text),panels=PANELS,frame='prescribed',gravity_magnitude=.8,
        motion=Motion(rates=[.17,-.13,.11],acceleration=[.25,-.18,.12],angular_acceleration=[.04,-.03,.02]),
        attitude=[11,-7,16],velocity=[.7,-.4,.2],structural_operator=MOVING_POLICY,tolerance=1e-10)
    a,m=linearize(system,step=1e-5);sa,sm=(v.toarray() for v in linearize(system,step=1e-5,sparse=True))
    np.testing.assert_allclose(sa,a,rtol=2e-8,atol=2e-9)
    np.testing.assert_allclose(sm,m,rtol=2e-10,atol=2e-11)
    rng=np.random.default_rng(20261030);zero=np.zeros(system.size)
    for _ in range(2):
        q=rng.normal(size=system.size);q/=np.linalg.norm(q)
        rate=zero.copy();rate[system.dynamic_indices]=rng.normal(size=len(system.dynamic_indices));rate/=np.linalg.norm(rate)
        np.testing.assert_allclose(a@q,directional(lambda x:system.residual(x,zero),q),rtol=3e-8,atol=3e-9)
        np.testing.assert_allclose(m@rate,-directional(lambda x:system.residual(zero,x),rate,h=.1),rtol=3e-10,atol=3e-11)
