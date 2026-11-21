from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import json
import numpy as np
import pytest
from fixture import prepared,saved_at
from openswing.aero import AnalysisError
from openswing.forcing import TimeForcing
from openswing.operating import TimeHistoryConstraint
from openswing.position_history_lift import PositionHistoryLift
from openswing.position_history_checkpoint import unpack_sample,pack_sample,validate_checkpoint,require_smooth_continuation
from openswing.time_state import unpack_state,pack_state,context,restore_checkpoint


def test_json_sample_and_current_predecessor_are_owned_and_exact():
    model,system,state,older,saved=saved_at()
    restored=validate_checkpoint(system.network,None,state,older,saved)
    assert restored.position_lift.signature==system.position_lift.signature
    current=unpack_state(system.network,saved['state'],None)
    previous=unpack_state(system.network,saved['older'],None)
    assert current.position_history==state.position_history
    assert previous.position_history==older.position_history
    saved['state']['position_history']['value'][0]+=1
    assert current.position_history.value==state.position_history.value
    assert isinstance(current.position_history.intervals,tuple)
    assert isinstance(current.position_history.intervals[0][1],tuple)


@pytest.mark.parametrize('field,value',[
    ('time',True),('time',float('inf')),('side','future'),('signature','a'*63),
    ('value',[0,1]),('value',[False,0,0]),('rate',[0,float('nan'),0]),
    ('acceleration',[0,'1',0]),('branch','invented'),
    ('intervals',[['position_earth.x',[1,0]]]),
    ('intervals',[['velocity_earth.x',[0,1]]]),
    ('intervals',[['position_earth.x',[0,1]],['position_earth.x',[0,1]]]),
])
def test_malformed_serialized_sample_is_rejected(field,value):
    _,system,state,_,_=prepared()
    data=pack_sample(state.position_history);data[field]=value
    with pytest.raises(AnalysisError,match='[Pp]osition-history'):unpack_sample(data)


@pytest.mark.parametrize('edit',[
    lambda c:c['state'].pop('position_history'),
    lambda c:c['older'].pop('position_history'),
    lambda c:c['state']['position_history'].__setitem__('time',.041),
    lambda c:c['state']['position_history'].__setitem__('side','left'),
    lambda c:c['state']['position_history'].__setitem__('branch','zero cutoff'),
    lambda c:c['state']['position_history'].__setitem__('intervals',[['position_earth.x',[-1,0]]]),
    lambda c:c['state']['position_history']['value'].__setitem__(0,1),
    lambda c:c['state']['position_history']['rate'].__setitem__(0,1),
    lambda c:c['state']['position_history']['acceleration'].__setitem__(0,1),
    lambda c:c['state']['position_history']['value'].__setitem__(1,1e-3),
    lambda c:c['context']['method'].pop('position_history'),
    lambda c:c['context']['method']['position_history'].__setitem__('policy','body-bdf'),
    lambda c:c['context']['method']['position_history']['definition']['mask'].__setitem__(1,True),
    lambda c:c['context']['setup'].__setitem__('forcing',c['context']['setup']['forcing']+'\n'),
    lambda c:c['context']['forcing_offsets'].clear(),
])
def test_cached_provenance_tampering_is_rejected_before_residual(edit):
    _,system,_,_,saved=saved_at();edit(saved)
    state=unpack_state(system.network,saved['state'],None)
    older=unpack_state(system.network,saved['older'],None)
    with pytest.raises(AnalysisError,match='[Pp]osition-history|forcing side'):
        validate_checkpoint(system.network,None,state,older,saved)


@pytest.mark.parametrize('field', ['position','U'])
def test_hidden_value_and_slope_require_physical_origin_compatibility(field):
    _,system,state,older,saved=saved_at()
    getattr(state,field)[0]+=.001
    with pytest.raises(AnalysisError,match='retained physical origin position or Earth velocity'):
        validate_checkpoint(system.network,None,state,older,saved)


def test_in_memory_parsed_and_compiled_table_mutations_are_detected():
    for kind in ('parsed','compiled'):
        _,system,state,_,_=prepared()
        distribution=system.forcing.channels[0]['distribution']
        if kind=='parsed':distribution.values[0]+=.01
        else:distribution._segments[0][2].c[0,0]+=.01
        with pytest.raises(AnalysisError,match='definition changed'):
            system.position_lift.history(state,system.forcing)


def test_effective_relative_offset_is_definition_owned():
    model,system,_,_,setup=prepared()
    rows=[TimeHistoryConstraint('power.1','position_earth.x',2.)]
    forcing=TimeForcing('time +RX\n0 0\n1 1',model,system.network.condition,system.network.motion,1,'free',
        actuator_constraints=[dict(variable='power.1',quantity='position_earth.x',target=2.)])
    lift=PositionHistoryLift(rows,forcing,length_scale=2.,velocity_scale=10.)
    before=lift.sample(.2,forcing)
    assert abs(before.value[0]-2.2)<1e-14 and abs(before.rate[0]-1)<1e-14
    forcing.channels[0]['initial']=3.
    with pytest.raises(AnalysisError,match='definition changed'):lift.sample(.2,forcing)


def test_original_table_rejects_coordinated_physical_and_cached_target_edit():
    model,_,_,_,saved=saved_at()
    saved['state']['position_earth'][0]+=.001
    saved['options']['condition']['position_earth'][0]+=.001
    saved['options']['operating_targets']['position_earth.x']+=.001
    with pytest.raises(AnalysisError,match='retained physical origin position'):
        restore_checkpoint(model,saved)


def test_replacement_break_and_radau_planning_preserves_original_sample():
    _,system,state,_,setup=prepared()
    original=state.position_history
    require_smooth_continuation(system,setup['forcing']+'\n',setup['forcing'],state,2)
    assert state.position_history is original
    require_smooth_continuation(system,setup['forcing'],setup['forcing'],state,5)
    assert state.position_history is original
    require_smooth_continuation(system,setup['forcing'],setup['forcing'],state,2,end_time=1.01)
    assert state.position_history is original


def test_method_change_cannot_relabel_the_recorded_derivative_policy():
    _,system,state,older,saved=saved_at()
    saved['context']['method']['order']=5
    with pytest.raises(AnalysisError,match='derivative policy'):
        validate_checkpoint(system.network,None,state,older,saved)


def test_future_break_is_owned_by_explicit_transition_dispatch():
    _,system,state,_,setup=prepared()
    original=state.position_history
    require_smooth_continuation(system,setup['forcing'],setup['forcing'],state,2,end_time=1.01)
    assert state.position_history is original


def test_physical_compatibility_does_not_scale_with_large_origin_or_epoch():
    rows=[TimeHistoryConstraint('power.1','position_earth.x',1e8)]
    lift=PositionHistoryLift(rows,None,length_scale=1.,velocity_scale=10.)
    state=SimpleNamespace(time=1e12,position=np.array([1e8,0,0]),orientation=np.eye(3),U=np.zeros(3))
    state.position_history=lift.sample(state.time,None)
    lift.validate_sample(state,None)
    state.position[0]+=.001
    with pytest.raises(AnalysisError,match='retained physical origin position'):lift.validate_sample(state,None)
