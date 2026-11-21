"""Moving source engines against blade integration and exact axial mechanics.

Engine geometry/loads follow unsteady Eqs.207--255. Rotor angular momentum is
supplied by Weight, independently of engine Omega. These are physical operator
checks, not archived ASWING aircraft validation.
"""
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest
from scipy.optimize import brentq
from scipy.spatial.transform import Rotation

from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.local_motion import NetworkMotion
from openswing.source_airflow import SourceAirflowNetwork, AIRFLOW_POLICY
from openswing.source_coupled import SourceCoupledNetwork
from test_source_airflow import UNIFORM, PANELS
from test_source_coupled_engines import powered_model
from test_source_coupled import condition, trial
from test_source_moving_system import AXIAL_SOURCE


@pytest.mark.parametrize('typ,frozen', [(0,False),(1,False),(2,False),(2,True)])
def test_powered_zero_motion_limit_matches_steady_source(typ,frozen):
    model=powered_model(typ,jet=True)
    c=condition(powers={1:3. if typ==0 else 40.},freeze_influences=frozen)
    steady=SourceCoupledNetwork(model,4,c,[1.,-2.,-10.])
    moving=SourceAirflowNetwork(model,4,c,[1.,-2.,-10.],[])
    x=trial(steady);zero=np.zeros_like(moving.rj)
    np.testing.assert_allclose(moving.residual(x,elastic_motion=(zero,zero,zero,zero),
        circulation_rate=np.zeros(moving.circulation_basis.panels)),steady.residual(x),
        rtol=3e-13,atol=3e-14)


def engine_row(typ=2,omega=80.):
    row=np.zeros(25)
    row[:15]=[1,typ,1,2,-.5,1.2,.1,-1,0,0,1,0,-.45,omega,.0004]
    row[15:17]=[.6,5.8]
    return row


def blade_data(rho,vd,radius,omega,cl,cla):
    """Integrate actual blade forces and differentiate, not Eqs.231/234/241/244."""
    x,weights=np.polynomial.legendre.leggauss(96)
    x,weights=(x+1)/2,weights/2
    r=radius*x
    chord=.04*(1+.3*x)
    blades=2
    phi=np.arctan2(vd,abs(omega)*r)
    integrals=[]
    for order in range(4):
        integrals.extend([blades*np.dot(weights,chord/radius*np.sin(phi)*x**order),
                          blades*np.dot(weights,chord/radius*np.cos(phi)*x**order)])
    psi=2*np.pi*(np.arange(128)+.5)/128
    co=np.cos(psi)[None,:]
    def blade_forces(v,w):
        tangential=abs(omega)*r[:,None]+v*co
        axial=vd-w*r[:,None]*co
        angle=np.arctan2(axial,tangential)
        lift=.5*rho*(tangential*tangential+axial*axial)*(cl-cla*(angle-phi[:,None]))*chord[:,None]
        side=lift*np.sin(angle)
        thrust=lift*np.cos(angle)
        return blades*radius*np.array([
            weights@np.mean(side*co,axis=1),
            weights@np.mean(-thrust*r[:,None]*co,axis=1)])
    derivatives=[]
    for direction in ([1.,0.],[0.,1.]):
        h=.001;direction=np.array(direction)
        vals=[blade_forces(*(k*h*direction)) for k in (1.,-1.,2.,-2.)]
        derivatives.append((8*(vals[0]-vals[1])-(vals[2]-vals[3]))/(12*h))
    return integrals,derivatives


@pytest.mark.parametrize('omega',[80.,-80.])
def test_moving_pylon_loads_match_independent_blade_integration(omega):
    rotation=Rotation.from_rotvec([.12,-.08,.05]).as_matrix()
    shift=np.array([.2,-.1,.3])
    velocity=np.array([.04,.05,-.02]);rate=np.array([.03,.02,-.01])
    frame_rate=np.array([.17,-.13,.11])
    row=engine_row(omega=omega)
    p=rotation@row[4:7]+shift
    arm=rotation@(row[4:7]-[0.,1.,0.])
    body_inflow=np.array([23.,0.,0.])-np.cross(frame_rate,p)-velocity-np.cross(rate,arm)
    local_v=rotation.T@body_inflow
    local_w=rotation.T@(frame_rate+rate)
    radius,rho,power=.45,1.2,40.
    tip=abs(omega)*radius;axial=local_v[0]
    viscous=rho/8*np.sqrt(axial*axial+tip*tip)*(axial*axial+3*tip*tip)*row[14]
    swirl=1+5*(axial/tip)**2
    dv=brentq(lambda d:rho*np.pi*radius**2*(axial+swirl*d/2)*(axial+d/2)*d+viscous-power,0.,100.,xtol=1e-14)
    row[17:],derivatives=blade_data(rho,axial+dv/2,radius,omega,*row[15:17])
    (fv,mv),(fw,mw)=derivatives
    spin=-np.sign(omega)
    expected_f=rotation@np.r_[-rho*np.pi*radius**2*(axial+dv/2)*dv,
                              fv*local_v[1:]+spin*fw*local_w[1:]]
    expected_m=rotation@np.r_[power/omega,spin*mv*local_v[1:]+mw*local_w[1:]]
    c=FlightCondition(speed=23.,alpha=0.,density=rho,mach=0.,rates=tuple(frame_rate),powers={1:power})
    outputs=[]
    for powered in (False,True):
        model=parse_asw(UNIFORM,beam_interpolation='drela-segspl-v1')
        if powered:model.records['engine']=[row.copy()]
        cc=c if powered else replace(c,powers={})
        n=SourceAirflowNetwork(model,PANELS,cc,[0.,0.,0.],[])
        r=n.rj@rotation.T+shift
        q=np.broadcast_to(rotation,(n.nn,3,3)).copy()
        v=np.broadcast_to(velocity,r.shape).copy();w=np.broadcast_to(rate,r.shape).copy()
        local=NetworkMotion(n,r,q,v,w,np.zeros_like(r),np.zeros_like(r))
        meshes=n.deformed_meshes(r,q,n.geometry(r,q))
        gamma=np.zeros(n.circulation_basis.panels)
        outputs.append(n.external(r,q,meshes,gamma,cc,cc.motion(),(),local_motion=local,
                                  circulation_rate=np.zeros_like(gamma)))
        if powered:
            engine=outputs[-1][2]['engines'][0]
            np.testing.assert_allclose(engine['position'],p,atol=2e-15)
            assert engine['axial_velocity']==pytest.approx(local_v[0],abs=2e-14)
            np.testing.assert_allclose(engine['force'],expected_f,rtol=2e-10,atol=2e-11)
            np.testing.assert_allclose(engine['moment'],expected_m,rtol=2e-10,atol=2e-11)
            for index in (0,1,3,4):np.testing.assert_array_equal(n.mass_cached[index],0.)
    off,on=outputs
    df,dm=on[0]-off[0],on[1]-off[1]
    expected_force=np.zeros_like(df);expected_couple=np.zeros_like(dm)
    j=n.node(1,2.)
    expected_force[j]=expected_f
    expected_couple[j]=expected_m+np.cross(arm,expected_f)
    np.testing.assert_allclose(df,expected_force,rtol=2e-10,atol=2e-11)
    np.testing.assert_allclose(dm,expected_couple,rtol=2e-10,atol=2e-11)
    # A disabled jet cannot introduce any distributed force or moment.
    for index in (4,5):np.testing.assert_array_equal(on[index],off[index])


def test_rotor_angular_momentum_enters_once_through_separate_weight():
    rotation=Rotation.from_rotvec([.12,-.08,.05]).as_matrix()
    omega=np.array([.17,-.13,.11]);rate=np.array([.03,.02,-.01])
    spin=np.array([.2,-.03,.07])
    c=FlightCondition(speed=23.,alpha=0.,density=1.2,mach=0.,rates=tuple(omega),powers={1:2.})
    results=[];caches=[]
    for spinning in (False,True):
        model=parse_asw(UNIFORM,beam_interpolation='drela-segspl-v1')
        model.records['engine']=[engine_row(typ=0)]
        weight=np.zeros(17);weight[:6]=[1,2,-.5,1.2,.1,5]
        weight[11:14]=[2,3,4]
        if spinning:weight[8:11]=10*spin
        model.records['weight']=[weight]
        n=SourceAirflowNetwork(model,PANELS,c,[0.,0.,0.],[])
        r=n.rj@rotation.T;q=np.broadcast_to(rotation,(n.nn,3,3)).copy()
        zero=np.zeros_like(r)
        local=NetworkMotion(n,r,q,zero,np.broadcast_to(rate,r.shape),zero,zero)
        meshes=n.deformed_meshes(r,q,n.geometry(r,q))
        gamma=np.zeros(n.circulation_basis.panels)
        results.append(n.external(r,q,meshes,gamma,c,c.motion(),(),local_motion=local,
                                  circulation_rate=np.zeros_like(gamma)))
        caches.append(deepcopy(n.mass_cached))
    def angular_momentum(t):
        earth=Rotation.from_rotvec(t*omega).as_matrix()
        local=Rotation.from_rotvec(t*rate).as_matrix()
        return earth@local@rotation@spin
    h=1e-4
    expected=-(8*(angular_momentum(h)-angular_momentum(-h))
               -(angular_momentum(2*h)-angular_momentum(-2*h)))/(12*h)
    np.testing.assert_array_equal(results[1][0],results[0][0])
    moments=results[1][1]-results[0][1]
    target=np.zeros_like(moments);target[n.node(1,2.)]=expected
    np.testing.assert_allclose(moments,target,rtol=2e-10,atol=2e-12)
    np.testing.assert_allclose(caches[1][1]-caches[0][1],target,rtol=2e-10,atol=2e-12)
    for key in ('force','moment'):
        np.testing.assert_array_equal(results[1][2]['engines'][0][key],results[0][2]['engines'][0][key])


AXIAL_ENGINE='''Engine
1 0 1 3 0 2 0 0 1 0 1 0 -1 80 0 0 0 0 0 0 0 0 0 0 0
End
'''
AXIAL_POWER_SOURCE=AXIAL_SOURCE+AXIAL_ENGINE


@pytest.mark.parametrize('frame',['prescribed','free'])
@pytest.mark.parametrize('count',[4,14])
def test_engine_power_frequency_matches_exact_two_mass_spring(frame,count):
    from openswing.frequency_response import FrequencyAnalysis
    model=parse_asw(AXIAL_POWER_SOURCE,beam_interpolation='drela-segspl-v1')
    c=FlightCondition(speed=23.,alpha=0.,density=1.2,mach=0.,stall=False,powers={1:0.})
    panels={'default':count,'beams':{'1':{'count':count,'spacing':'uniform'}}}
    analysis=FrequencyAnalysis(model,c,panels,frame=frame,gravity=[0.,0.,0.],
        structural_operator=AIRFLOW_POLICY,inputs=['power.1'],matrices=True)
    result=analysis.solve([1.,4.,15.])
    assert result['converged'] and not result['vacuum']
    z=lambda v:np.asarray(v['real'])+1j*np.asarray(v['imag'])
    a,m=(np.array(result['matrices'][key]) for key in ('A','M'))
    for sample in result['samples']:
        omega=sample['omega'];s=1j*omega
        # The physical forcing acts on the 3 kg tip, not on the 2 kg root.
        effective_k=100. if frame=='prescribed' else 250.
        q=1/(effective_k-3*omega**2)
        response=sample['responses'][0]
        np.testing.assert_allclose(z(response['output']['nodes'][-1]['displacement'])[1],q,
                                   rtol=3e-8,atol=2e-10)
        assert z(response['output']['operating']['power.1'])==pytest.approx(1.,abs=2e-12)
        np.testing.assert_allclose((s*m-a)@z(response['state']),z(sample['B'])[:,0],rtol=2e-9,atol=2e-10)
    old_a,old_m=analysis.a,analysis.m
    refined=analysis.solve([2.,8.])
    assert refined['converged'] and analysis.a is old_a and analysis.m is old_m
    assert 'engine_load_transfer' in result['base']['output_scope']
    assert not any('struts or engines' in s for s in result['base']['limitations'])


@pytest.mark.parametrize('frozen',[False,True])
def test_powered_moving_dense_sparse_pencils_match_full_residual(frozen):
    from openswing.linear_dynamics import make_system,linearize
    from test_source_moving_system import directional
    model=powered_model(2,jet=True)
    c=condition(powers={1:40.},freeze_influences=frozen,
        rates=(.017,-.013,.011),acceleration=(.025,-.018,.012),angular_acceleration=(.004,-.003,.002))
    system,_=make_system(model,c,4,frame='prescribed',gravity=[0.,0.,0.],
                          structural_operator=AIRFLOW_POLICY,tolerance=1e-10)
    dense=linearize(system,step=1e-5)
    sparse=tuple(a.toarray() for a in linearize(system,step=1e-5,sparse=True))
    for a,b in zip(dense,sparse):np.testing.assert_allclose(a,b,rtol=3e-8,atol=3e-9)
    zero=np.zeros(system.size)
    rng=np.random.default_rng(81925)
    for _ in range(2):
        q=rng.normal(size=system.size);q/=np.linalg.norm(q)
        rate=np.zeros(system.size);rate[system.dynamic_indices]=rng.normal(size=len(system.dynamic_indices))
        rate/=np.linalg.norm(rate)
        ea=directional(lambda v:system.residual(v,zero),q)
        em=-directional(lambda v:system.residual(zero,v),rate,h=.1)
        for a,m in (dense,sparse):
            np.testing.assert_allclose(a@q,ea,rtol=3e-7,atol=3e-8)
            np.testing.assert_allclose(m@rate,em,rtol=3e-9,atol=3e-10)
