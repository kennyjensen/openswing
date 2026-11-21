from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, evaluate_aerodynamics, AnalysisError
from openswing.network import StaticNetwork
from openswing.inertia import Motion, inertial_wrench, parallel_axis, surface_apparent_loads
from openswing.local_motion import LocalMotion, NetworkMotion, rotation_matrix as exp


def network(example='rectangular',condition=None):
    model=parse_asw(Path(f'examples/{example}.asw').read_text())
    c=FlightCondition(mach=0) if condition is None else condition
    return StaticNetwork(model,4,c,[0,0,0],[])


def evaluation(net,c,field=None,**kwargs):
    r,q=net.rj,np.broadcast_to(np.eye(3),(net.nn,3,3))
    meshes=net.deformed_meshes(r,q,net.geometry(r,q))
    return evaluate_aerodynamics(net.model,c,meshes,point_positions=net.point_positions(r,q),
                                local_motion=field,**kwargs)


@pytest.mark.parametrize('example',['rectangular','wing-body','powered'])
def test_zero_elastic_motion_and_zero_circulation_rate_recover_steady_loads(example):
    c=FlightCondition(mach=0,powers={1:2500} if example=='powered' else {},rates=[.03,.04,.02],acceleration=[.1,.2,.3],angular_acceleration=[-.02,.03,.01])
    net=network(example,c);z=np.zeros_like(net.rj);q=np.broadcast_to(np.eye(3),(net.nn,3,3))
    field=NetworkMotion(net,net.rj,q,z,z,z,z)
    a=evaluation(net,c);b=evaluation(net,c,field,circulation_rate=np.zeros(net.ng))
    for key in ('force','moment','apparent_force','apparent_moment','point_forces','CL','CD','CDi','CDp'):
        np.testing.assert_allclose(a[key],b[key],atol=1e-12)
    assert b['analysis']=='instantaneous_unsteady'
    assert b['CDrate']==0


@pytest.mark.parametrize('example',['rectangular','wing-body','powered'])
def test_repartitioning_rigid_motion_between_body_and_nodes_preserves_aero(example):
    # Independent descriptions of exactly the same instantaneous physical motion.
    c=FlightCondition(mach=0,powers={1:2500} if example=='powered' else {},rates=[.04,-.03,.02],acceleration=[.1,.2,-.3],angular_acceleration=[.02,-.01,.04])
    net=network(example,c);r=net.rj;q=np.broadcast_to(np.eye(3),(net.nn,3,3))
    net.model.reference[2]=[.4,-.2,.1]
    net.model.reference[3]=[-.3,.2,-.1]
    w=np.array([-.025,.017,.031]);wd=np.array([.03,.04,-.01])
    d=r-net.model.reference[3]
    field=NetworkMotion(net,r,q,np.cross(w,d),np.broadcast_to(w,r.shape),
                        np.cross(wd,d)+np.cross(w,np.cross(w,d)),np.broadcast_to(wd,r.shape))
    origin=LocalMotion(net.model.reference[3],np.zeros(3),w,np.zeros(3),wd)
    combined=replace(c,rates=np.asarray(c.rates)+w,
        acceleration=origin.absolute_acceleration(net.model.reference[2],c.motion(),net.model.reference[2]),
        angular_acceleration=origin.absolute_angular_acceleration(c.motion()))
    a=evaluation(net,c,field);b=evaluation(net,combined)
    for key in ('force','moment','apparent_force','apparent_moment','point_forces','CL','CD','CDi','CDp'):
        np.testing.assert_allclose(a[key],b[key],rtol=1e-12,atol=1e-11)
    for x,y in zip(a['engines'],b['engines']):
        np.testing.assert_allclose(x['force'],y['force'],atol=1e-12)
        np.testing.assert_allclose(x['moment'],y['moment'],atol=1e-12)


def test_unsteady_inertial_wrench_matches_direct_earth_mass_cloud_accelerations():
    points=np.array([[.2,.3,.7],[-.4,.1,.3],[.3,-.6,-.2],[.1,.4,-.3]])
    masses=np.array([2.,3.,1.,4.]);cg=np.average(points,weights=masses,axis=0)
    inertia=parallel_axis(masses,points-cg).sum(axis=0)
    omega,alpha=np.array([.3,-.2,.4]),np.array([-.4,.1,.2])
    w,wd=np.array([-.1,.5,.2]),np.array([.2,-.3,.1])
    u,ud=np.array([.2,.4,-.1]),np.array([.3,-.1,.4])
    a0,g=np.array([-.2,.3,.1]),np.array([0,0,-9.81])
    local=LocalMotion(np.zeros(3),u,w,ud,wd);motion=Motion(omega,a0,alpha)
    force,couple=inertial_wrench(masses.sum(),cg,inertia,np.zeros(3),motion,g,np.zeros(3),local_motion=local)
    def trajectory(t):
        earth=exp(t*omega+.5*t*t*alpha);q=exp(t*w+.5*t*t*wd)
        return .5*t*t*a0+(t*u+.5*t*t*ud+points@q.T)@earth.T
    h=2e-4;acc=(trajectory(h)-2*points+trajectory(-h))/h**2
    forces=masses[:,None]*(g-acc)
    np.testing.assert_allclose(force,forces.sum(axis=0),atol=2e-7)
    np.testing.assert_allclose(couple,np.cross(points-cg,forces).sum(axis=0),atol=1e-7)


def test_local_plate_heave_and_pitch_acceleration_have_analytic_added_loads():
    rho,chord,length=1.2,2.,3.;position=np.array([[.4,.1,.2]])
    field=LocalMotion(position,np.zeros((1,3)),np.array([[0,.3,0]]),np.array([[0,0,1.7]]),np.array([[0,.4,0]]))
    f,m=surface_apparent_loads(position,np.eye(3)[None],np.array([chord]),np.array([.5]),np.array([length]),rho,
        np.array([[10,0,0]]),Motion(),np.zeros(3),local_motion=field)
    added=rho*np.pi/4*chord**2*length
    np.testing.assert_allclose(f,[[0,0,added*(10*.3-1.7)]],atol=1e-13)
    np.testing.assert_allclose(m,[[0,-added*(chord/4*10*.3+chord**2/32*.4),0]],atol=1e-13)


@pytest.mark.parametrize('frequency',[.001,.1,1.,10.,100.])
def test_empirical_lag_has_documented_two_dimensional_complex_lift_transfer(frequency):
    # AR=200,000 suppresses tip influence; differentiate the actual 3D residual
    # and force evaluation, then solve the harmonic scalar circulation equation.
    text=Path('examples/rectangular.asw').read_text()
    text=text[:text.index('t dCLdF1')]+ 'End\n'
    text=text.replace('6 0 6 0','100000 0 100000 0').replace('6 .008','100000 .008').replace('.008','0')
    c=FlightCondition(speed=30,alpha=0,mach=0,stall=False)
    net=StaticNetwork(parse_asw(text),4,c,[0,0,0],[])
    eps=1e-4;ones=np.ones(net.ng);zero=np.zeros(net.ng)
    a=evaluation(net,c,circulation=eps*ones,circulation_rate=zero)
    b=evaluation(net,c,circulation=zero,circulation_rate=eps*ones)
    ar=np.mean(a['circulation_residual'])/eps;br=np.mean(b['circulation_residual'])/eps
    lf=a['force'][2]/eps;lr=b['force'][2]/eps
    omega=2*c.speed*frequency # c=1, k=omega*c/(2V)
    computed=ar/(ar+1j*omega*br)*(lf+1j*omega*lr)/lf
    expected=(1+2j*frequency)/(1+4j*frequency)
    assert computed==pytest.approx(expected,rel=3e-5,abs=2e-6)


def test_circulation_rate_lift_quarter_chord_moment_and_pressure_drag():
    c=FlightCondition(alpha=5,mach=0,stall=False)
    text=Path('examples/rectangular.asw').read_text().replace('.008','0').replace('1 .25','1 .5')
    net=StaticNetwork(parse_asw(text),6,c,[0,0,0],[])
    rate=np.full(net.ng,2.)
    r=evaluation(net,c,circulation_rate=rate)
    assert r['residual']<1e-10
    assert r['CDp']<1e-20 # circulation lag is not artificial stall pressure drag
    for strip in r['strips']:
        # Unit chord: the rate-lift magnitude is independent of local inflow.
        assert np.linalg.norm(strip['circulation_rate_force'])==pytest.approx(1.225*2*strip['length'],rel=1e-13)
    assert r['circulation_rate_moment'][1]==pytest.approx(.25*r['circulation_rate_force'][2],rel=1e-12)
    assert r['CD']==pytest.approx(sum(r[k] for k in ('CDi_near','CDp','CDam','CDbody','CDeng','CDrate')),abs=1e-14)
    assert r['circulation_rate_force'][2]>0
    with pytest.raises(AnalysisError,match='rates must'):
        evaluation(net,c,circulation_rate=[np.nan]*net.ng)
