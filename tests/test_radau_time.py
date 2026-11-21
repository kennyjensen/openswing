"""Independent high-index mechanics and stiff-ODE checks for Radau collocation."""
import numpy as np
from scipy.integrate import solve_ivp
from openswing.radau_time import collocate


def test_constrained_pendulum_reactions_and_velocities_converge_from_nonzero_initial_speed():
    m,L,g,theta,omega=2.,2.,9.80665,1.1,1.3
    r=np.array([L*np.sin(theta),-L*np.cos(theta)]);v=np.array([L*omega*np.cos(theta),L*omega*np.sin(theta)])
    initial=np.r_[r,v,m*(omega**2+g*np.cos(theta)/L)]
    def residual(x,d,t):return np.r_[d[:2]-x[2:4],m*d[2:4]+x[4]*x[:2]+[0,m*g],x[:2]@x[:2]-L*L]
    reference=solve_ivp(lambda t,y:[y[1],-g/L*np.sin(y[0])],(0,.12),[theta,omega],rtol=2e-13,atol=1e-14,method='DOP853',dense_output=True)
    errors=[]
    for h in (.02,.01,.005):
        x=initial.copy();time=0.;error=np.zeros(5);factor=None
        for _ in range(round(.12/h)):
            guess=np.r_[x[2:4],-x[4]*x[:2]/m-[0,g],0.]
            x,rate,factor,_,_,defect=collocate(residual,x,guess,time,h,1e-12,factorization=factor);time+=h
            assert defect<=1e-12
            th,w=reference.sol(time);exact=np.r_[L*np.sin(th),-L*np.cos(th),L*w*np.cos(th),L*w*np.sin(th),m*(w*w+g*np.cos(th)/L)]
            error=np.maximum(error,abs(x-exact))
        errors.append(error)
    # Index-three multipliers converge at order two, velocities at order three.
    assert errors[1][-1]<.27*errors[0][-1] and errors[2][-1]<.27*errors[1][-1]
    assert np.linalg.norm(errors[2][2:4])<.14*np.linalg.norm(errors[1][2:4])


def test_stiff_ode_step_matches_independently_derived_radau_stability_function():
    for z in (-.2,-10.,-10000.):
        x,_,_,_,_,error=collocate(lambda x,d,t:d-z*x,np.ones(1),np.array([z]),0.,1.,1e-11)
        exact=(1+2*z/5+z*z/20)/(1-3*z/5+3*z*z/20-z**3/60)
        np.testing.assert_allclose(x,[exact],atol=2e-12,rtol=2e-12)
        assert error<=1e-11


def test_forcing_endpoint_uses_exact_event_time_despite_subtraction_roundoff():
    start=.9090279688772233;end=1.9094528293586002;h=end-start
    assert start+h>end
    def residual(x,d,t):return d-(1. if t<=end else 0.)
    x,_,_,_,_,_=collocate(residual,np.zeros(1),np.ones(1),start,h,1e-12,end_time=end)
    np.testing.assert_allclose(x,[h],atol=1e-12,rtol=0)


def test_radau_frame_acceleration_jumps_cutoff_and_checkpoint_follow_piecewise_quadratics():
    from openswing.time_integration import solve_time
    from openswing.time_state import checkpoint,resume_time
    from test_time_integration import rigid_body
    model=rigid_body();out=solve_time(model,panels=4,gravity=[0,0,0],duration=.06,dt=.013,order=5,
        forcing='time Ay\n0 1\n.02 1\n.02 -2\n.04 -2')
    assert out['method']=='Radau IIA (3 stages)'
    for s in out['snapshots']:
        t=s['time']
        if t<=.02:position=.5*t*t;velocity=t
        elif t<=.04:u=t-.02;position=.0002+.02*u-u*u;velocity=.02-2*u
        else:position=.0002-.02*(t-.04);velocity=-.02
        np.testing.assert_allclose(s['frame']['position_earth'],[0,position,0],atol=1e-10)
        np.testing.assert_allclose(s['frame']['velocity_origin_body'],[0,velocity,0],atol=1e-10)
        assert s['restart']['older'] is None
        if t:assert s['order']==5 and s['collocation']['maximum_stage_residual']<=s['collocation']['stage_tolerance']
    i=next(i for i,s in enumerate(out['snapshots']) if s['time']==.02)
    assert out['snapshots'][i]['forcing_side']=='left' and out['snapshots'][i]['forcing_values']['Ay']==1
    assert out['snapshots'][i+1]['forcing_values']['Ay']==-2
    resumed=resume_time(model,checkpoint(out,i),duration=.04)
    for a,b in zip(resumed['snapshots'],out['snapshots'][i:]):
        np.testing.assert_allclose(a['frame']['position_earth'],b['frame']['position_earth'],atol=1e-10)
        np.testing.assert_allclose(a['frame']['velocity_origin_body'],b['frame']['velocity_origin_body'],atol=1e-10)


def test_radau_gust_lift_and_circulation_rate_match_independent_empirical_lag():
    from pathlib import Path
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.time_integration import solve_time
    original=Path('examples/rectangular.asw').read_text()
    original=original[:original.index('t dCLdF1')]+'End\n'
    errors=[]
    for span,dt in ((100000,.4),(100000,.2),(100000,.1),(200000,.1)):
        source=(original.replace('6 0 6 0',f'{span} 0 {span} 0').replace('6 .008',f'{span} .008')
            .replace('.008','0').replace('12 1 12',f'{2*span} 1 {2*span}'))
        out=solve_time(parse_asw(source),FlightCondition(speed=10,alpha=0,mach=0,stall=False,
            gust=dict(type='expression',components=['0','0','.002*t'])),4,
            duration=.4,dt=dt,order=5,tolerance=1e-10,gravity=[0,0,0])
        t=np.array([s['time'] for s in out['snapshots']])
        # Infinite-span limit, tau=2c/V=.2: total lift includes tau/2*CLdot.
        exact=2*np.pi*.002/10*(t-.1*(1-np.exp(-t/.2)))
        errors.append(np.max(abs(np.array([s['CL'] for s in out['snapshots']])-exact)))
    assert errors[1]<.12*errors[0]
    # The finer time step reaches finite-span error in the infinite-span
    # reference. Doubling span must reduce that remaining discrepancy.
    assert errors[2]<4e-9
    assert errors[3]<.6*errors[2]
