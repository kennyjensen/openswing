"""Cheap gate/routing/replay checks; no cold initialization or Newton solve."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import numpy as np
import pytest
from openswing.aero import AnalysisError
from openswing.operating import OperatingConstraint,TimeHistoryConstraint
from openswing.time_integration import bdf_coefficients,bdf_nonlinear_gate

B=Path(__file__).resolve().parents[1]
def dummy(rows,W=5.):return SimpleNamespace(W=W,network=SimpleNamespace(operating=SimpleNamespace(constraints=rows)))
def row(quantity,typed=True):return (TimeHistoryConstraint if typed else OperatingConstraint)('power.1',quantity,0.)

@pytest.mark.parametrize('quantity',['velocity_earth.x','rates.x','rates_earth.z','reference.equivalent_airspeed','reference.alpha','reference.beta','flight_path','position_earth.x','attitude.heading'])
def test_all_typed_kinematic_orders_use_conservative_squared_gain(quantity):
    value,policy=bdf_nonlinear_gate(dummy([row(quantity)]),[50.,-50.,0.],1e-8)
    assert value==2.5e-11 and policy['derivative_gain']==20.
    assert policy['kinematic_targets'][0]['quantity']==quantity

@pytest.mark.parametrize('rows',[[],[row('velocity_earth.x',False)],[row('acceleration_earth.x')],[row('angular_acceleration_earth.y')],[OperatingConstraint('acceleration.y','force.y')]])
def test_other_rows_preserve_requested_tolerance_exactly(rows):
    value,policy=bdf_nonlinear_gate(dummy(rows),[50.,-50.,0.],1e-20)
    assert value==1e-20 and policy==dict(name='requested-bdf-tolerance-v1')

@pytest.mark.parametrize('step,old,gain',[ (.02,None,20.),(.02,.02,40.),(.01,.02,60.) ])
def test_actual_variable_step_stencil_gain(step,old,gain):
    value,policy=bdf_nonlinear_gate(dummy([row('velocity_earth.x')]),bdf_coefficients(step,old),1e-8)
    assert policy['derivative_gain']==pytest.approx(gain,rel=2e-16)
    assert value==pytest.approx((1e-8/gain)/gain,rel=4e-16)

def test_no_absolute_floor_and_large_step_never_relaxes_request():
    system=dummy([row('velocity_earth.x')])
    tiny,_=bdf_nonlinear_gate(system,[50.,-50.,0.],1e-20)
    assert tiny==pytest.approx(2.5e-23,rel=2e-16)
    same,policy=bdf_nonlinear_gate(system,[.1,-.1,0.],1e-20)
    assert same==1e-20 and policy['derivative_gain']==1.

@pytest.mark.parametrize('coefficients,W,tolerance,message',[
    ([1e308,-1e308,0.],5.,1e-8,'overflows'),
    ([1e308,0.,0.],1e-308,1e-8,'overflows'),
    ([1e150,-1e150,0.],1.,1e-100,'underflows'),
    ([np.inf,-1.,0.],5.,1e-8,'finite derivative coefficients'),
    ([1.,-1.,0.],0.,1e-8,'positive rate scale'),
])
def test_unrepresentable_gate_refuses_without_a_looser_floor(coefficients,W,tolerance,message):
    with pytest.raises(AnalysisError,match=message):bdf_nonlinear_gate(dummy([row('velocity_earth.x')],W),coefficients,tolerance)

def physical_fixture(index):
    from openswing.asw import parse_asw
    from openswing.time_state import checkpoint
    model=parse_asw((B/'inputs/both-root.asw').read_text())
    result=json.loads((B/'inputs/bdf-v1-result.json').read_text())
    return model,checkpoint(result,index)

def synthetic_v2(saved,requested=None):
    """Metadata-only replay fixture; never claimed as a newly solved point."""
    saved=deepcopy(saved);data=saved['accepted_method']
    if requested is not None:
        data['tolerance']=requested;data['accepted_inputs']['method']['tolerance']=requested
    gate,policy=bdf_nonlinear_gate(dummy([row('velocity_earth.y')]),data['coefficients'],data['tolerance'])
    data.update(scheme='openswing-so3-bdf-v2',nonlinear_tolerance=gate,nonlinear_policy=policy)
    return saved

def test_historical_v1_replays_its_original_gate_not_the_new_one():
    from openswing.time_acceptance_validation import validate_accepted_method
    model,saved=physical_fixture(-1)
    result=validate_accepted_method(model,saved,require_discrete=True)
    assert result['scheme']=='openswing-so3-bdf-v1' and result['tolerance']==1e-8
    newer=synthetic_v2(saved)
    assert result['residual']>newer['accepted_method']['nonlinear_tolerance']
    with pytest.raises(AnalysisError,match='original discrete residual fails'):
        validate_accepted_method(model,newer,require_discrete=True)

def test_fixed_real_first_step_replays_under_v2_gate_without_resolving():
    from openswing.time_acceptance_validation import validate_accepted_method
    model,saved=physical_fixture(1);saved=synthetic_v2(saved)
    report=validate_accepted_method(model,saved,require_discrete=True)
    assert report['scheme']=='openswing-so3-bdf-v2'
    assert report['residual']<=report['tolerance']==saved['accepted_method']['nonlinear_tolerance']

@pytest.mark.parametrize('mutation',['gate','policy','missing','relaxed','mixed_v1'])
def test_policy_tampering_is_rejected(mutation):
    from openswing.time_acceptance_validation import validate_accepted_method
    model,saved=physical_fixture(1);saved=synthetic_v2(saved);data=saved['accepted_method']
    if mutation=='gate':data['nonlinear_tolerance']*=2
    elif mutation=='policy':data['nonlinear_policy']['derivative_gain']*=2
    elif mutation=='missing':del data['nonlinear_policy']
    elif mutation=='relaxed':data['nonlinear_tolerance']=2*data['tolerance']
    else:data['scheme']='openswing-so3-bdf-v1'
    with pytest.raises(AnalysisError):validate_accepted_method(model,saved,require_discrete=True)

@pytest.mark.parametrize('expected',[1e-16,1e-40,1e-200])
def test_tiny_policy_gates_have_no_absolute_comparison_allowance(expected):
    from openswing.time_acceptance_validation import _relative_policy
    _relative_policy(expected,expected,'test gate')
    with pytest.raises(AnalysisError,match='disagrees'):_relative_policy(2*expected,expected,'test gate')

@pytest.mark.parametrize('route',['ordinary','accuracy_take_step'])
def test_newton_diagnostic_and_capture_receive_the_same_actual_gate(monkeypatch,route):
    from openswing.forcing import TimeForcing
    from openswing.time_state import restore_checkpoint,checkpoint
    from openswing.time_integration import TimeSystem
    import openswing.time_integration as integration
    from openswing.time_accuracy import take_step
    from openswing.time_acceptance_validation import validate_accepted_method
    model,seed=physical_fixture(0);_,known=physical_fixture(1)
    n,f,previous,older,options,_,error,restored=restore_checkpoint(model,seed)
    setup=restored['context']['setup']
    histories=TimeForcing(setup['forcing'],model,n.condition,n.motion,.01,setup['frame'],f,
        start_time=0.,load_targets=setup.get('load_targets'),actuator_constraints=setup.get('actuator_constraints'))
    for channel in histories.channels:channel['initial']=restored['context']['forcing_offsets'][channel['name']]
    system=TimeSystem(n,histories,f,gravity_magnitude=setup.get('gravity_magnitude'))
    expected,expected_policy=bdf_nonlinear_gate(system,[100.,-100.,0.],1e-8)
    values=np.asarray(known['accepted_method']['values']);calls=[];diagnostic=[]
    def root_diagnostic(rows,tolerance):diagnostic.append(tolerance);return object()
    monkeypatch.setattr(f,'root_diagnostic',root_diagnostic)
    def fake_newton(function,guess,tolerance,factorization=None,*,check_rank=False):
        # Routing-only: use the exact retained accepted vector, already within
        # this stricter residual gate. No Newton or initialization is executed.
        assert np.max(abs(function(values)))<=tolerance
        assert hasattr(function,'accepted_root_diagnostic') and check_rank
        calls.append(tolerance);return values.copy(),None,1,0
    monkeypatch.setattr(integration,'newton',fake_newton)
    if route=='ordinary':
        result=integration.integrate(system,previous,older,options,setup,duration=.01,dt=.01,order=1,
            tolerance=1e-8,max_steps=2,continuation=0,initial_error=error,
            initial_phase='checkpoint_before_next_inputs',initial_acceptance=restored.get('accepted_method'))
        record=checkpoint(result)['accepted_method']
        assert validate_accepted_method(model,checkpoint(result),require_discrete=True)['tolerance']==expected
    else:
        _,_,stats=take_step(system,previous,older,.01,1,setup['frame'],'right',1e-8,acceptance_setup=setup)
        record=stats['accepted_method']
    assert calls==diagnostic==[expected]
    assert record['tolerance']==1e-8 and record['accepted_inputs']['method']['tolerance']==1e-8
    assert record['scheme']=='openswing-so3-bdf-v2' and record['version']==1
    assert record['nonlinear_tolerance']==expected and record['nonlinear_policy']==expected_policy
    expected_policy['kinematic_targets'].clear()
    assert record['nonlinear_policy']['kinematic_targets']
