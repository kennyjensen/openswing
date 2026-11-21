"""Guard, ownership and routing checks; no new held-state completion is solved.

The positive routing test reuses the recorded physical helper output and
intercepts integration. Independent public solved mechanics are a separate run.
"""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.aero import AnalysisError
from openswing.asw import parse_asw
from openswing.time_initialization import launch_time
import openswing.time_saved_history as branch

B=Path(__file__).resolve().parents[1]

def inputs():
    return parse_asw((B/'inputs/both-root.asw').read_text()),json.loads((B/'inputs/saved-equilibrium.json').read_text())

def arguments():
    return dict(duration=.02,dt=.02,order=5,frame='mixed',load_targets={'force.y':0.},
        actuator_constraints=[dict(variable='power.1',quantity='velocity_earth.y',target=0.)],
        forcing='time velocity_earth.y\n0 0\n1 .6')

@pytest.mark.parametrize('case,expected',[
    ('free','force-only'),('moment','force-only'),('controller','controller'),('feedback','controller'),
    ('disturbance','disturbance'),('loads','changed loads'),('rates','angular velocity'),
    ('angular_acceleration','angular velocity'),('gust','gust'),('attitude','exactly one Earth-velocity'),
    ('extra_target','exactly one Earth-velocity'),('blank','explicit inverse-target table'),
    ('extra_channel','explicit inverse-target table'),('first_after','start at or before')])
def test_unsupported_scope_rejects_before_network_construction(monkeypatch,case,expected):
    model,saved=inputs();kw=arguments()
    if case=='free':kw.update(frame='free',load_targets=None)
    elif case=='moment':kw['load_targets']['moment.z']=0.
    elif case=='controller':saved['launch']['controller']={}
    elif case=='feedback':saved['feedback']={}
    elif case=='disturbance':kw['disturbance']={}
    elif case=='loads':kw['loads']=[dict(beam=1,t=2.,force=[0.,.1,0.])]
    elif case in ('rates','angular_acceleration'):saved['launch']['motion'][case][0]=.1
    elif case=='gust':saved['launch']['condition']['gust']=dict(type='uniform',velocity=[0.,0.,1.])
    elif case=='attitude':kw['actuator_constraints'][0]['quantity']='attitude.bank'
    elif case=='extra_target':kw['actuator_constraints'].append(dict(variable='power.2',quantity='acceleration.y',target=.4))
    elif case=='blank':kw['forcing']=''
    elif case=='extra_channel':kw['forcing']='time velocity_earth.y E2\n0 0 0\n1 .6 0'
    elif case=='first_after':kw['forcing']='time velocity_earth.y\n.001 0\n1 .6'
    original=deepcopy(saved)
    def forbidden(*args,**kwargs):raise AssertionError('guard reached network construction')
    monkeypatch.setattr(branch,'StaticNetwork',forbidden)
    with pytest.raises(AnalysisError,match=expected):launch_time(model,saved,**kw)
    assert saved==original

def test_condition_motion_cannot_bypass_zero_rotation_guard(monkeypatch):
    model,saved=inputs();saved['launch']['condition']['rates'][0]=.1
    def forbidden(*args,**kwargs):raise AssertionError('guard reached completion')
    monkeypatch.setattr(branch,'complete_history_transition',forbidden)
    with pytest.raises(AnalysisError,match='restored condition'):launch_time(model,saved,**arguments())

def test_incompatible_default_rejected_before_completion(monkeypatch):
    model,saved=inputs();kw=arguments();kw['actuator_constraints'][0]['target']=.01
    def forbidden(*args,**kwargs):raise AssertionError('guard reached completion')
    monkeypatch.setattr(branch,'complete_history_transition',forbidden)
    with pytest.raises(AnalysisError,match='saved default target'):launch_time(model,saved,**kw)

def test_value_jump_rejected_by_original_helper_before_derivative_sweep(monkeypatch):
    import openswing.time_transition_initial as helper
    model,saved=inputs();old=deepcopy(saved);kw=arguments();kw['forcing']='time velocity_earth.y\n0 .01\n1 .61'
    def forbidden(*args,**kwargs):raise AssertionError('mismatch reached derivative sweep')
    monkeypatch.setattr(helper,'consistent_initial',forbidden)
    with pytest.raises(AnalysisError,match='disagrees with the retained physical state'):launch_time(model,saved,**kw)
    assert saved==old

@pytest.mark.parametrize('order',[1,2,5])
@pytest.mark.parametrize('relative',[False,True])
@pytest.mark.parametrize('smooth_knot',[False,True])
def test_recorded_right_state_routing_ownership_and_capture(monkeypatch,order,relative,smooth_knot):
    from openswing.time_state import unpack_state,unpack_options,pack_state
    from openswing.time_acceptance import capture_initial
    model,saved=inputs();original=deepcopy(saved);kw=arguments();kw.update(order=order,initial_difference_step=.012,initial_rank_tolerance=2e-7)
    if relative:kw['forcing']='time +velocity_earth.y\n0 0\n1 .6'
    if smooth_knot:kw['forcing']=kw['forcing'].replace('\n1 .6','\n.5 .3\n1 .6')
    made=[];old_system=branch.TimeSystem;observed={}
    def system(*args,**kwargs):
        result=old_system(*args,**kwargs);made.append(result);return result
    monkeypatch.setattr(branch,'TimeSystem',system)
    def complete(system,seed,frame,**controls):
        assert len(made)==2 and made[0].forcing is None and made[1] is system
        assert system.forcing.channels[0]['initial']==0.
        assert system.forcing.channels[0]['relative']==relative
        assert controls['difference_step']==.012 and controls['rank_tolerance']==2e-7
        observed['seed']=pack_state(system.network,seed)
        state=unpack_state(system.network,json.loads((B/'inputs/right-state.json').read_text()),None)
        options=unpack_options(system.network,state,json.loads((B/'inputs/right-options.json').read_text()))
        report=json.loads((B/'inputs/initialization.json').read_text())
        assert np.max(abs(system.network.residual(state.x,**options)))<1e-8
        observed['right']=pack_state(system.network,state)
        return state,options,report
    def integrate(system,state,older,options,setup,**controls):
        assert older is None and controls['order']==order and controls['side']=='right'
        assert controls['initial_phase']=='history_transition_right_limit'
        assert controls['initial_error']<=1e-8 and controls['accuracy'] is None
        record=capture_initial(system,state,options,setup,phase=controls['initial_phase'],side='right',tolerance=1e-8)
        assert record['validation_level']=='physical_only' and record['continuous_certificate'] is False
        assert record['accepted_inputs']['input_policy']=='physical_time_forcing'
        assert record['accepted_inputs']['setup']['forcing']==kw['forcing']
        assert record['endpoint']['state']==observed['right']
        observed['record']=record
        return dict(snapshots=[{'marker':'captured handoff, not a solved step',
            'operating_values':observed['right']['network']['operating_values']}])
    monkeypatch.setattr(branch,'complete_history_transition',complete)
    monkeypatch.setattr(branch,'integrate',integrate)
    result=launch_time(model,saved,**kw);transition=result['launch_transition'];before=transition['before_input']
    assert transition['right_limit_snapshot_index']==0 and len(result['snapshots'])==1
    assert before['saved_equilibrium']==original and saved==original
    assert before['snapshot']['forcing_values']=={}
    assert before['snapshot']['frame']['acceleration_reference_body'][1]==pytest.approx(.4,abs=1e-12)
    assert before['snapshot']['local_acceleration'][-1]==[0.,0.,0.]
    assert before['input_context']['state']==observed['seed']
    assert before['restart_scope']=='saved_equilibrium_source_only'
    assert transition['completion']['seed_state']==observed['seed']
    assert max(transition['held_state_max_error'].values())<1e-13
    assert result['initialization']['equilibrium_recomputed'] is False
    assert result['initialization']['operating_values']['acceleration.y']==pytest.approx(.6,abs=1e-7)
    assert result['initialization']['before_operating_values']['acceleration.y']==pytest.approx(.4,abs=1e-12)
    assert result['initialization']['residual']==result['initialization']['right_limit_residual']
    result['launch_transition']['before_input']['saved_equilibrium']['launch']['panels']=-1
    transition['completion']['seed_state']['commands']['mutated']=1
    assert saved==original and 'mutated' not in before['input_context']['state']['commands']


def staged_record(version=3):
    """Capture retained helper state only; not a new solved launch certificate."""
    from openswing.inertia import Motion
    from openswing.network import StaticNetwork
    from openswing.operating import time_operating_constraints,time_constraint_data
    from openswing.forcing import TimeForcing
    from openswing.time_integration import TimeSystem
    from openswing.time_state import read_condition,condition_data,motion_data,unpack_state,unpack_options,context,record
    from openswing.time_acceptance import capture_initial
    model,saved=inputs();launch=saved['launch'];kw=arguments();c=read_condition(launch['condition'])
    rows=time_operating_constraints(kw['frame'],kw['load_targets'],kw['actuator_constraints'])
    n=StaticNetwork(model,launch['panels'],c,launch['gravity'],launch['loads'],None,rows,launch['strut_mode'])
    state=unpack_state(n,json.loads((B/'inputs/right-state.json').read_text()),None)
    options=unpack_options(n,state,json.loads((B/'inputs/right-options.json').read_text()))
    forcing=TimeForcing(kw['forcing'],model,c,n.motion,.02,'mixed',None,start_time=0.,load_targets=kw['load_targets'],actuator_constraints=kw['actuator_constraints'])
    system=TimeSystem(n,forcing,gravity_magnitude=launch['frame']['gravity_magnitude'])
    setup=dict(panels=n.panels,condition=condition_data(c),motion=motion_data(n.motion),gravity=launch['gravity'],
        gravity_magnitude=launch['frame']['gravity_magnitude'],mesh_loads=launch['loads'],loads=launch['loads'],
        strut_mode=launch['strut_mode'],frame='mixed',controller=None,forcing=kw['forcing'],**time_constraint_data(rows))
    setup[branch.SCOPE_KEY]=branch.scope_record(rows[-1],version=version)
    accepted=capture_initial(system,state,options,setup,phase='history_transition_right_limit',side='right',tolerance=1e-8)
    cp=dict(format='openswing-time-checkpoint',version=1,context=context(system,setup,5,.02,1e-8),
        **record(system,state,None,options,.02,'right',accepted_method=accepted))
    return model,cp,forcing


def test_staged_initial_record_and_same_table_interior_scope_are_valid():
    from openswing.time_acceptance_validation import validate_accepted_method
    model,cp,forcing=staged_record()
    report=validate_accepted_method(model,cp)
    assert report['level']=='initial_physical_only' and report['continuous_certificate'] is False
    branch.require_continuation(cp['context']['setup'],forcing,0.,.02)
    assert branch.validate_scope({}) is None


@pytest.mark.parametrize('mutation',['removed_outer','null_outer','extra','bool_version','both_null','both_absent','record_removed','forcing','loads','quantity'])
def test_owned_scope_cannot_be_silently_downgraded(mutation):
    from openswing.time_acceptance_validation import validate_accepted_method
    model,cp,_=staged_record();outer=cp['context']['setup'];owned=cp['accepted_method']['accepted_inputs']['setup'];key=branch.SCOPE_KEY
    if mutation=='removed_outer':del outer[key]
    elif mutation=='null_outer':outer[key]=None
    elif mutation=='extra':outer[key]['extra']=True;owned[key]['extra']=True
    elif mutation=='bool_version':outer[key]['version']=True;owned[key]['version']=True
    elif mutation=='both_null':outer[key]=owned[key]=None
    elif mutation=='both_absent':del outer[key];del owned[key]
    elif mutation=='record_removed':del cp['accepted_method']
    elif mutation=='forcing':outer['forcing']='time velocity_earth.y\n0 0\n1 .4'
    elif mutation=='loads':outer['loads']=[{'changed':True}]
    elif mutation=='quantity':outer[key]['quantity']=owned[key]['quantity']='velocity_earth.x'
    with pytest.raises(AnalysisError):validate_accepted_method(model,cp)


@pytest.mark.parametrize('change',['replacement','cutoff','beyond','repeated_knot'])
def test_continuation_recomputes_original_table_scope(change):
    from openswing.forcing import TimeForcing
    from openswing.time_state import read_condition
    from openswing.inertia import Motion
    model,cp,forcing=staged_record(version=2);setup=cp['context']['setup'];duration=.02
    if change=='replacement':forcing.source='time velocity_earth.y\n0 0\n1 .4'
    elif change=='cutoff':duration=1.
    elif change=='beyond':duration=1.1
    else:
        setup['forcing']='time velocity_earth.y\n0 0\n.5 .3\n.5 .3\n1 .6'
        forcing=TimeForcing(setup['forcing'],model,read_condition(setup['condition']),Motion(**setup['motion']),.02,'mixed',None,
            start_time=0.,load_targets=setup['load_targets'],actuator_constraints=setup['actuator_constraints'])
    with pytest.raises(AnalysisError):branch.require_continuation(setup,forcing,0.,duration)
