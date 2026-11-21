"""A checkpoint must describe one physical frame, not two independent copies."""
from pathlib import Path
from copy import deepcopy
import json
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import AnalysisError,FlightCondition
from openswing.local_motion import rotation_matrix
from openswing.time_integration import solve_time
from openswing.time_state import checkpoint,restore_checkpoint,checkpoint_frame_options

@pytest.fixture(scope='module')
def saved_frame():
    model=parse_asw((Path(__file__).resolve().parents[1]/'examples'/'guided-body.asw').read_text())
    model.reference[3][:]=[.3,-.2,.1]
    condition=FlightCondition(speed=10,alpha=8,beta=-4,mach=0,
        attitude=[20,-10,30],position_earth=[3,-2,1],rates=[.13,-.21,.17],
        acceleration=[.2,-.1,.3],angular_acceleration=[.02,-.03,.01])
    out=solve_time(model,condition,4,duration=.02,dt=.02,order=1,gravity=[0,0,0])
    saved=json.loads(json.dumps(checkpoint(out)))
    return model,saved

def test_unchanged_frame_restores_without_mutating_input(saved_frame):
    model,saved=saved_frame;before=deepcopy(saved)
    restored=restore_checkpoint(model,saved)
    state=restored[2]
    np.testing.assert_allclose(state.U,saved['state']['velocity_origin_body'],atol=0,rtol=0)
    np.testing.assert_allclose(state.orientation,saved['state']['body_to_earth'],atol=0,rtol=0)
    assert saved==before

def corrupt(saved,name):
    s=saved['state'];c=saved['options']['condition']
    if name=='physical_velocity':s['velocity_origin_body'][0]+=.25
    elif name=='physical_rate':s['rates_body'][1]+=.03
    elif name=='physical_position':s['position_earth'][0]+=.5
    elif name=='physical_orientation':s['body_to_earth']=(np.asarray(s['body_to_earth'])@rotation_matrix([.02,-.03,.01])).tolist()
    elif name=='physical_time':s['time']+=.01
    elif name=='cached_speed':c['speed']+=.3
    elif name=='cached_alpha':c['alpha']+=2
    elif name=='cached_beta':c['beta']+=2
    elif name=='cached_rate':c['rates'][1]+=.03
    elif name=='cached_position':c['position_earth'][0]+=.5
    elif name=='cached_orientation':c['attitude'][0]+=2
    elif name=='cached_time':c['time']+=.01
    elif name=='cached_motion_rate':saved['options']['motion']['rates'][1]+=.03
    elif name=='cached_gravity':saved['options']['gravity'][0]+=.1
    else:raise AssertionError(name)

@pytest.mark.parametrize('name',[
    'physical_velocity','physical_rate','physical_position','physical_orientation','physical_time',
    'cached_speed','cached_alpha','cached_beta','cached_rate','cached_position','cached_orientation','cached_time',
    'cached_motion_rate','cached_gravity'])
def test_inconsistent_physical_and_cached_frame_is_rejected(saved_frame,name):
    model,original=saved_frame;saved=deepcopy(original);corrupt(saved,name)
    with pytest.raises(AnalysisError,match='[Cc]heckpoint frame'):
        restore_checkpoint(model,saved)

def test_equivalent_periodic_angles_describe_the_same_frame(saved_frame):
    model,original=saved_frame;saved=deepcopy(original)
    saved['options']['condition']['attitude'][2]+=360
    saved['options']['condition']['alpha']+=360
    restored=restore_checkpoint(model,saved)
    assert restored[6]<1e-8


def test_large_absolute_time_does_not_relax_frame_phase_consistency(saved_frame):
    model,original=saved_frame
    n,_,state,_,options,_,_,_=restore_checkpoint(model,original)
    # Check the frame consistency layer at a large absolute clock value.
    # A complete accepted-step record also binds its original times and cannot
    # be backdated by changing only these two physical/cache fields.
    state.time+=1e9
    options['condition_override'].time+=1e9
    gravity=original['context']['setup'].get('gravity_magnitude')
    checkpoint_frame_options(n,state,options,gravity)
    options['condition_override'].time+=.25
    with pytest.raises(AnalysisError,match='[Cc]heckpoint frame'):
        checkpoint_frame_options(n,state,options,gravity)


def test_complete_checkpoint_cannot_backdate_only_its_physical_frame(saved_frame):
    model,original=saved_frame;saved=deepcopy(original)
    saved['state']['time']+=1e9
    saved['options']['condition']['time']+=1e9
    if saved['older'] is not None:saved['older']['time']+=1e9
    with pytest.raises(AnalysisError,match='accepted method endpoint time'):
        restore_checkpoint(model,saved)

def test_equivalent_vector_does_not_sanitize_negative_cached_speed(saved_frame):
    model,original=saved_frame;saved=deepcopy(original);c=saved['options']['condition']
    c['speed']=-c['speed'];c['alpha']+=180;c['beta']=-c['beta']
    with pytest.raises(AnalysisError,match='[Cc]heckpoint frame'):
        restore_checkpoint(model,saved)

@pytest.mark.parametrize('name',['rates','position_earth','attitude'])
def test_cached_frame_vectors_cannot_use_broadcast_shapes(saved_frame,name):
    model,original=saved_frame;saved=deepcopy(original);c=saved['options']['condition']
    c[name]=[c[name]]
    with pytest.raises(AnalysisError,match='[Cc]heckpoint frame'):
        restore_checkpoint(model,saved)
