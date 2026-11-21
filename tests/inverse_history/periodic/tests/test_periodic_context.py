"""Local branch and real residual plumbing tests, not a physical solve proof."""
from copy import copy
from dataclasses import FrozenInstanceError, asdict, replace
import math
import numpy as np
import pytest
from openswing.aero import AnalysisError, FlightCondition
from openswing.forcing import TimeForcing
from openswing.time_history import PeriodicStencilContext, validate_history_target
from openswing.reference_flow import reference_airflow
from openswing.time_integration import attitude_angles
import openswing.time_cold_initial as cold
import openswing.time_integration as time_api
from test_inverse_history_schema import model, evaluator, forcing, rotate
from cold_history_fixture import model as cold_model, setup as cold_setup

PERIODIC = [('A','reference.alpha'),('Ex','attitude.bank'),('Ez','attitude.heading')]


def context(q,actual,target,variable='control.1',time=0.,source='test frozen polynomial'):
    return PeriodicStencilContext.from_report(time,'right',source,[dict(variable=variable,
        quantity=q,actual=actual,specified_target=target)])


def data(c,m):
    return {'reference_flow':reference_airflow(m,c),'earth_state':c.earth_state(m)}


@pytest.mark.parametrize('label,q',PERIODIC)
@pytest.mark.parametrize('direction',[-1,1])
def test_representation_wrap_is_continuous_with_unwrapped_stencil_target(label,q,direction):
    a=direction*180.; ctx=context(q,a,a)
    for h in [1e-2,1e-3,1e-4]:
        # Independent real angle path: theta=a+2t+.3t^2. Its principal display
        # changes sign at the representation cut; target remains a polynomial.
        values=[]
        for t in [-h,0,h]:
            target=a+direction*(2*t+.3*t*t)
            real_actual=target+3*t+5*t*t
            principal=math.degrees(math.atan2(math.sin(math.radians(real_actual)),math.cos(math.radians(real_actual))))
            values.append(ctx.error('control.1',q,principal,target))
        assert (values[2]-values[0])/(2*h)==pytest.approx(3.,abs=5e-9)
        assert (values[2]+values[0]-2*values[1])/h**2==pytest.approx(10.,abs=2e-5)
    # Physical policy remains separate and strict.
    with pytest.raises(ValueError,match='principal range'):
        validate_history_target(q,a+direction*.01)


@pytest.mark.parametrize('label,q',PERIODIC)
def test_antipodal_achieved_chart_target_exit_and_true_residual_exit_reject(label,q):
    c=context(q,10.,10.)
    with pytest.raises(ValueError,match='antipodal'):c.error('control.1',q,-170.,10.)
    with pytest.raises(ValueError,match='half-turn'):c.error('control.1',q,10.,190.)
    with pytest.raises(ValueError,match='shortest-error'):c.error('control.1',q,110.,-90.)
    with pytest.raises(ValueError,match='antipodal'):context(q,0.,180.)
    with pytest.raises(ValueError,match='finite'):c.error('control.1',q,10.,float('nan'))


@pytest.mark.parametrize('label,q',PERIODIC)
@pytest.mark.parametrize('direction',[-1,1])
def test_operating_context_is_explicit_and_steady_and_physical_paths_stay_unchanged(label,q,direction):
    m=model();a=direction*180.;c=FlightCondition(alpha=a,attitude=(a,0,a))
    op=evaluator(q,c,target=a,m=m);ctx=context(q,a,a)
    trial=replace(c,alpha=-direction*179.9,attitude=(-direction*179.9,0,-direction*179.9))
    target=a+direction*.1
    got,report=op.evaluate([0,0,0],[0,0,0],data(trial,m),trial,targets={q:target},history_context=ctx)
    assert got==pytest.approx([0.],abs=1e-13)
    assert report[0]['specified_target']==target
    with pytest.raises(ValueError,match='principal range'):
        op.evaluate([0,0,0],[0,0,0],data(trial,m),trial,targets={q:target})
    assert op.evaluate([0,0,0],[0,0,0],data(trial,m),trial,targets={q:-direction*179.9})[0]==pytest.approx([0.],abs=1e-13)
    with pytest.raises(ValueError,match='homotopy'):
        op.evaluate([0,0,0],[0,0,0],data(trial,m),trial,factor=.5,history_context=ctx)
    with pytest.raises(ValueError,match='ownership'):
        op.evaluate([0,0,0],[0,0,0],data(trial,m),trial,history_context=context(q,a,a,variable='power.2'))
    steady=evaluator(q,c,target=a,m=m,marked=False)
    with pytest.raises(ValueError,match='ownership'):
        steady.evaluate([0,0,0],[0,0,0],data(trial,m),trial,history_context=ctx)
    # Explicit context use never installs a lasting flag or changes target data.
    assert not hasattr(op,'history_context')
    assert op.constraints[0].target==a


def test_context_is_immutable_and_independent_when_interleaved():
    first=context('attitude.heading',180.,180.,source='first')
    second=context('attitude.heading',-180.,-180.,source='second')
    for unused in range(3):
        assert first.error('control.1','attitude.heading',-179.,181.)==0.
        assert second.error('control.1','attitude.heading',179.,-181.)==0.
    with pytest.raises(FrozenInstanceError):first.time=1.
    with pytest.raises(FrozenInstanceError):first.anchors[0].target=0.
    assert first.report()['physical_lookup'] is False


@pytest.mark.parametrize('q', ['attitude.bank','attitude.heading'])
def test_euler_pole_rejection_survives_context(q):
    c=FlightCondition(attitude=(0.,90.,0.));op=evaluator(q,c)
    with pytest.raises(ValueError,match='Euler-angle chart'):
        op.evaluate([0,0,0],[0,0,0],{},c,history_context=context(q,0.,0.))


def test_alpha_lateral_singularity_survives_context():
    c=FlightCondition(speed=10.,beta=90.);m=model();op=evaluator('reference.alpha',c)
    with pytest.raises(ValueError,match='singular|undefined'):
        op.evaluate([0,0,0],[0,0,0],data(c,m),c,history_context=context('reference.alpha',0.,0.))


@pytest.mark.parametrize('direction',[-1,1])
def test_noncommuting_euler_kinematics_follow_independent_matrix_across_wrap(direction):
    # ASW theory eq.205, independently expanded in rotate. All three Euler
    # coordinates vary, so this does not mistake their rates for body Omega.
    anchor=np.array([direction*180.,23.,-direction*180.])
    slope=np.array([7.,-3.,11.]);curvature=np.array([2.,4.,-6.])
    ctx=[context(q,anchor[i],anchor[i]) for i,q in [(0,'attitude.bank'),(2,'attitude.heading')]]
    for t in [-.02,-.01,0,.01,.02]:
        theta=anchor+slope*t+.5*curvature*t*t
        R=rotate(theta);angles=attitude_angles(R)
        for c,i,q in zip(ctx,[0,2],['attitude.bank','attitude.heading']):
            assert c.error('control.1',q,angles[i],theta[i])==pytest.approx(0.,abs=1e-12)
        assert angles[1]==pytest.approx(theta[1],abs=1e-12)
        # Reconstructed physical orientation is identical through display cuts.
        np.testing.assert_allclose(rotate(angles),R,atol=8e-16)
    h=1e-5;R=rotate(anchor);Rp=(rotate(anchor+slope*h+.5*curvature*h*h)-rotate(anchor-slope*h+.5*curvature*h*h))/(2*h)
    spin=R.T@Rp;omega=np.array([spin[2,1],spin[0,2],spin[1,0]])
    p,e,_=np.deg2rad(anchor);pd,ed,hd=np.deg2rad(slope)
    expected=np.array([-pd+hd*np.sin(e),ed*np.cos(p)+hd*np.cos(e)*np.sin(p),ed*np.sin(p)-hd*np.cos(e)*np.cos(p)])
    np.testing.assert_allclose(omega,expected,rtol=1e-9,atol=1e-10)
    assert not np.allclose(omega,np.deg2rad(slope))


@pytest.mark.parametrize('label,q',PERIODIC)
@pytest.mark.parametrize('direction',[-1,1])
def test_real_cold_caller_installs_owned_context_and_retains_physical_forcing(monkeypatch,label,q,direction):
    # Intercept only the expensive derivative-array solve. This verifies actual
    # solve_time -> cold -> InitialSystem -> network -> operating plumbing,
    # not a solved physical initial state or any time trajectory.
    a=direction*180.;args=cold_setup();args.update(
        condition=FlightCondition(speed=10.,alpha=a if label=='A' else 0.,mach=0.,
            attitude=(a if label=='Ex' else 0.,0.,a if label=='Ez' else 0.)),
        actuator_constraints=[dict(variable='power.1',quantity=q,target=a)],
        forcing=f'time {label}\n0 {a}\n1 {a-direction}')
    original=asdict(args['condition']);captured={}
    class StopAfterPlumbing(Exception):pass
    def inspect(residual,requested,dynamic,rate,**kwargs):
        chart=residual.__self__;ctx=chart.history_context;live=chart.system
        assert isinstance(ctx,PeriodicStencilContext)
        assert ctx.time==0 and ctx.side=='right'
        assert ctx.anchors[0].quantity==q
        assert not isinstance(live.forcing,TimeForcing)
        assert np.array_equal(kwargs['fixed_state_indices'],np.arange(chart.velocity_start,chart.feedback_start))
        for t in [-.01,.01]:
            values,state,options=residual(requested,np.zeros_like(requested),t,detail=True)
            assert np.isfinite(values).all()
            assert options['history_context'] is ctx
            assert options['operating_targets'][q]==pytest.approx(a-direction*t)
            np.testing.assert_allclose(state.orientation,rotate(args['condition'].attitude),atol=1e-15)
        captured['source']=live.forcing.jet.source
        raise StopAfterPlumbing
    monkeypatch.setattr(cold,'consistent_initial',inspect)
    monkeypatch.setattr(time_api,'integrate',lambda *a,**k:pytest.fail('Plumbing sentinel reached integration.'))
    with pytest.raises(StopAfterPlumbing):time_api.solve_time(cold_model(),**args)
    assert captured['source']==args['forcing']
    assert asdict(args['condition'])==original
