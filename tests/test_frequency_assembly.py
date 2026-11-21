"""Shared circulation derivatives and single-evaluation dynamic outputs."""
import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork, network_result
from openswing.operating import time_load_constraints
from openswing.linear_dynamics import DynamicSystem, dynamic_circulation_columns, make_system, linearize, output_perturbation
from openswing.frequency_response import HarmonicInput
from test_direct_circulation import model_for, state_for


@pytest.mark.parametrize('example,frame,extra,circulation',[
    ('rectangular','fixed',{},.08),
    ('flexible','free',{'circulation_modes':{1:3}},.3),
    ('wing-body','free',{'ground_effect':1},.08),
    ('wing-body','fixed',{'ground_effect':-1},.08),
    ('stepped-wing-body','free',{'freeze_influences':True},.08),
    ('torsion-joint','free',{},.3),
    ('rectangular','free',{},1.2),
    ('rectangular','free',{'aero_lag':False},.3),
    ('jet-0','free',{'powers':{1:50000.}},.3),
    ('jet-1','free',{'powers':{1:50000.}},.3),
    ('jet-2','free',{'powers':{1:50000.}},.3),
])
def test_direct_dynamic_columns_match_complete_refined_residual(example,frame,extra,circulation):
    model=model_for(example)
    model.reference[1]=[.7,-.2,.3];model.reference[2]=[.1,.2,-.1]
    condition=FlightCondition(speed=30,alpha=7,beta=3,mach=.2,rates=[.03,-.04,.02],
        position_earth=[0,0,30],attitude=[13,-7,21],**extra)
    net=StaticNetwork(model,4,condition,None,[],
        operating_constraints=time_load_constraints('prescribed' if frame=='fixed' else frame))
    system=DynamicSystem(net,state_for(net,circulation),frame)
    zero=np.zeros(system.size);base=system.residual(zero,zero).copy()
    direct=dynamic_circulation_columns(system)
    assert net.iteration_fields is None
    for step in [1e-5,3e-6]:
        for k,j in enumerate(range(net.gamma_start,net.operating_start)):
            h=step*max(1.,abs(system.base[j]));d=zero.copy();d[j]=h
            p,m,pp,mm=[system.residual(mult*d,zero) for mult in (1,-1,2,-2)]
            expected=(8*(p-m)-(pp-mm))/(12*h)
            error=np.max(abs(direct[:,k]-expected)/(1+abs(expected)))
            assert error<2e-8,(example,frame,step,j,error)
    np.testing.assert_array_equal(system.residual(zero,zero),base)
    # Aircraft kinematics have no direct circulation term. Global force/moment
    # balance is retained in the network rows for a moving frame.
    assert not np.any(direct[net.size:])
    if frame=='free':assert np.max(abs(direct[net.operating_start:net.size]))>0


def original_snapshot(system,z,zdot,*,forcing=None):
    """The original two-evaluation implementation, used only as an oracle."""
    _,state,options=system.residual(z,zdot,detail=True,forcing=forcing)
    result=network_result(system.network,state.x,sensor_frame=dict(body_to_earth=state.orientation,
        position_earth=state.position,velocity_origin_body=state.U),**options)
    if system.feedback is not None:result['feedback']=state.feedback_report
    return state,result


@pytest.mark.parametrize('example,frame',[
    ('wing-body','fixed'),('wing-body','free'),('powered','free'),('controlled','fixed')])
def test_single_evaluation_outputs_equal_original_including_input_and_rate_feedthrough(example,frame,monkeypatch):
    if example=='controlled':
        from test_feedback import configuration,condition,law
        system,_=make_system(configuration(),condition(),4,gravity=[0,0,0],controller=law(ki=100,ka=3))
        inputs=['power.1','command.RY[2]',dict(kind='gust',name='gust',span_mode=1)]
    else:
        model=model_for(example)
        system,_=make_system(model,FlightCondition(speed=20,alpha=3,mach=.1,
            powers={1:7} if example=='powered' else {},rates=[.003,-.002,.001]),4,
            frame=frame,structured_base=True)
        inputs=[f'control.{k}' for k in model.controls]+[dict(kind='gust',name='gust',span_mode=1)]
    system.base_report()
    rng=np.random.default_rng(712)
    vector=.001*(rng.normal(size=system.size)+1j*rng.normal(size=system.size))
    rate=7.1j*vector
    for i,spec in enumerate(inputs):
        forcing,_=HarmonicInput(system,spec,i).at_frequency(7.1)
        before=system.network.nfev
        actual=output_perturbation(system,vector,rate,forcing=forcing)
        assert system.network.nfev-before==4
        with monkeypatch.context() as patch:
            patch.setattr(system,'snapshot',lambda *args,**kwargs:original_snapshot(system,*args,**kwargs))
            before=system.network.nfev
            expected=output_perturbation(system,vector,rate,forcing=forcing)
            assert system.network.nfev-before==8
        assert actual==expected


def test_unavailable_direct_columns_fall_back_to_original_pencil(monkeypatch):
    import openswing.circulation_tangent as derivative
    system,_=make_system(model_for('rectangular'),FlightCondition(speed=20),4,structured_base=True)
    reference,rm=linearize(system)
    def unavailable(*args,**kwargs):
        raise derivative.CirculationDerivativeUnavailable('deliberate derivative budget gate')
    monkeypatch.setattr(derivative,'circulation_columns',unavailable)
    actual,am=linearize(system,sparse=True)
    np.testing.assert_allclose(actual.toarray(),reference,atol=2e-10,rtol=2e-10)
    np.testing.assert_allclose(am.toarray(),rm,atol=3e-12,rtol=3e-12)
    assert system.state_derivative_diagnostics['direct_circulation_columns']==0
    assert 'budget gate' in system.state_derivative_diagnostics['circulation_fallback']
    assert system.network.iteration_fields is None and system.network.tangent_influences is None


def test_failed_capture_restores_physical_fields(monkeypatch):
    system,_=make_system(model_for('rectangular'),FlightCondition(speed=20),4,structured_base=True)
    def fail(*args,**kwargs):raise ValueError('failed capture')
    monkeypatch.setattr(system,'residual',fail)
    with pytest.raises(ValueError,match='failed capture'):dynamic_circulation_columns(system)
    assert system.network.iteration_fields is None and system.network.aero_key is None
