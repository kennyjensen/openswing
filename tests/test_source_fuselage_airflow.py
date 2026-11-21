"""Conservative body loads, mixed charts and independent powered axial dynamics."""
import numpy as np
import pytest

from openswing.aero import FlightCondition, solve_rigid
from openswing.frequency_response import FrequencyAnalysis
from openswing.source_coupled import SourceCoupledNetwork, solve_source_coupled
from openswing.source_airflow import SourceAirflowNetwork, AIRFLOW_POLICY
from openswing.source_dynamics import SourceMovingNetwork
from openswing.linear_dynamics import make_system, linearize
from openswing.local_motion import NetworkMotion
from openswing.inertia import Motion
from test_source_fuselage import BODY_SOURCE, ENGINE, PANELS, model
from test_source_moving_system import directional
from test_body_shoulders import step_source


@pytest.mark.parametrize('closed',[False,True])
def test_source_body_shoulders_preserve_independent_global_wrench(closed):
    m=model(step_source(closed=closed))
    c=FlightCondition(speed=17.,alpha=11.,beta=-7.,mach=0.,density=1.225)
    out=solve_source_coupled(m,c,4,gravity=[0,0,0],tolerance=1e-11)
    v=c.speed*c.vectors()[0];normal=v-[v[0],0,0]
    changes=[(1.,np.pi*.2**2),(3.,-np.pi*.2**2)] if closed else [(2.,np.pi*(.3**2-.1**2))]
    force=sum(c.density*normal*v[0]*jump for x,jump in changes)
    moment=sum(np.cross([x,0,0],c.density*normal*v[0]*jump) for x,jump in changes)
    np.testing.assert_allclose(out['force'],force,rtol=1e-12,atol=2e-9)
    np.testing.assert_allclose(out['moment'],moment,rtol=1e-12,atol=2e-9)
    np.testing.assert_allclose(out['support_force'],-force,atol=2e-9)
    np.testing.assert_allclose(out['support_moment'],-moment,atol=2e-9)
    assert len(out['body_shoulders'])==len(changes)


def test_source_body_apparent_wrench_matches_cylinder_pressure_integral():
    m=model();c=FlightCondition(speed=23.,alpha=0.,density=1.2,mach=0.,stall=False)
    n=SourceAirflowNetwork(m,PANELS,c,[0,0,0],[])
    r=n.rj.copy();q=np.broadcast_to(np.eye(3),(n.nn,3,3)).copy()
    zero=np.zeros_like(r);acceleration=np.broadcast_to([.4,.7,1.2],r.shape).copy()
    angular=np.broadcast_to([.1,.2,-.3],r.shape).copy()
    acceleration+=np.cross(angular,r)
    meshes=n.deformed_meshes(r,q,n.geometry(r,q))
    motion=NetworkMotion(n,r,q,zero,zero,acceleration,angular)
    # Compare only reported fluid force/moment, independent of real-mass inertia.
    full=n.external(r,q,meshes,np.empty(0),c,Motion(),(),local_motion=motion,
                    circulation_rate=np.empty(0))
    data=full[2]
    mass_per_length=c.density*np.pi*.1**2
    # Integral of transverse acceleration a + alpha cross [x,0,0], x in [0,2].
    x,w=np.polynomial.legendre.leggauss(8);x=x+1
    forces=-mass_per_length*(np.array([0.,.7,1.2])+np.cross([.1,.2,-.3],np.c_[x,0*x,0*x]))
    expected_force=w@forces
    expected_moment=w@np.cross(np.c_[x,0*x,0*x],forces)
    np.testing.assert_allclose(data['apparent_force'],expected_force,atol=3e-12)
    np.testing.assert_allclose(data['apparent_moment'],expected_moment,atol=3e-12)
    # Verify the actual source nodal load addition, not just the aerodynamic
    # report. Subtract the separately evaluated real-inertia/gravity path.
    dry=SourceMovingNetwork.external(n,r,q,meshes,np.empty(0),None,Motion(),(),
        local_motion=motion,circulation_rate=None)
    nodal_force,nodal_moment=full[0]-dry[0],full[1]-dry[1]
    np.testing.assert_allclose(nodal_force.sum(axis=0),expected_force,atol=3e-12)
    np.testing.assert_allclose((nodal_moment+np.cross(r,nodal_force)).sum(axis=0),
                              expected_moment,atol=3e-12)


def test_body_and_surface_material_charts_share_a_conservative_jointed_aircraft():
    text=BODY_SOURCE+'''Beam 2
Rigid wing attached to body tip
t x y z chord
1 2 0 0 .3
3 2 2 0 .3
End
Joint
1 2 3 1 0
End
'''
    m=model(text);c=FlightCondition(speed=17.,alpha=6.,mach=0.,stall=False)
    panels={'default':4,'beams':{'1':{'count':4,'spacing':'uniform'},'2':{'count':4,'spacing':'uniform'}}}
    # Rigid body controls the geometry so only the load/chart coupling is tested.
    m=model(text.replace('200 0 0 0 0 0','0 0 0 0 0 0'))
    n=SourceCoupledNetwork(m,panels,c,[0,0,0],[])
    assert np.array_equal(n.source_fuselage,[True]*4+[False]*4)
    rigid=solve_rigid(m,c,panels)
    coupled=solve_source_coupled(m,c,panels,gravity=[0,0,0],tolerance=1e-11)
    np.testing.assert_allclose(coupled['force'],rigid['force'],rtol=2e-9,atol=2e-8)
    np.testing.assert_allclose(coupled['moment'],rigid['moment'],rtol=2e-9,atol=2e-8)
    np.testing.assert_allclose(coupled['force_balance'],0,atol=2e-8)
    np.testing.assert_allclose(coupled['moment_balance'],0,atol=2e-8)


@pytest.mark.parametrize('frame',['prescribed','free'])
def test_body_engine_power_frequency_matches_exact_axial_oscillator(frame):
    c=FlightCondition(speed=23.,alpha=0.,density=1.2,mach=0.,stall=False,powers={1:0.})
    analysis=FrequencyAnalysis(model(BODY_SOURCE+ENGINE),c,PANELS,frame=frame,
        gravity=[0,0,0],structural_operator=AIRFLOW_POLICY,inputs=['power.1'])
    out=analysis.solve([1.,4.,8.,15.]);assert out['converged']
    for row in out['samples']:
        disp=row['responses'][0]['output']['nodes'][-1]['displacement']
        actual=np.array(disp['real'])+1j*np.array(disp['imag'])
        k=100. if frame=='prescribed' else 250.
        np.testing.assert_allclose(actual,[1/(k-3*row['omega']**2),0,0],rtol=3e-8,atol=3e-10)
    a,m=analysis.a,analysis.m
    assert analysis.solve([2.])['converged'] and analysis.a is a and analysis.m is m


def test_body_airflow_sparse_pencil_matches_complete_fluid_residual():
    c=FlightCondition(speed=23.,alpha=3.,beta=2.,density=1.2,mach=0.,stall=False,
        rates=(.017,-.013,.011),acceleration=(.025,-.018,.012),angular_acceleration=(.004,-.003,.002))
    text=BODY_SOURCE.replace('200 0 0 0 0 0','5000 800 650 900 4000 4500')
    system,_=make_system(model(text),c,4,frame='prescribed',gravity=[0,0,0],
        structural_operator=AIRFLOW_POLICY,tolerance=1e-10)
    a,m=linearize(system,step=1e-5)
    sa,sm=(v.toarray() for v in linearize(system,step=1e-5,sparse=True))
    np.testing.assert_allclose(sa,a,rtol=3e-8,atol=3e-9)
    np.testing.assert_allclose(sm,m,rtol=3e-10,atol=3e-11)
    zero=np.zeros(system.size);rng=np.random.default_rng(81817)
    for _ in range(2):
        q=rng.normal(size=system.size);q/=np.linalg.norm(q)
        rate=zero.copy();rate[system.dynamic_indices]=rng.normal(size=len(system.dynamic_indices));rate/=np.linalg.norm(rate)
        np.testing.assert_allclose(a@q,directional(lambda x:system.residual(x,zero),q),rtol=4e-8,atol=4e-9)
        np.testing.assert_allclose(m@rate,-directional(lambda x:system.residual(zero,x),rate,h=.1),rtol=4e-10,atol=4e-11)
