"""Explicit test-only bootstrap from an independently recorded physical state.

The old public output retains its exact accepted jet in the display snapshot,
but its checkpoint format omits that jet. This adapter is not a production
legacy migration. It checks old identity/values before constructing new records.
"""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import numpy as np
from openswing.asw import parse_asw
from openswing.network import StaticNetwork
from openswing.inertia import Motion
from openswing.operating import time_operating_constraints
from openswing.forcing import TimeForcing
from openswing.time_integration import TimeSystem
from openswing.time_state import read_condition,unpack_state,unpack_options,context,record,portable
from openswing.position_history_lift import PositionSample

HERE=Path(__file__).resolve().parent


def physical(t):
    return -10*t+t*t/5-t*t*t/15,-10+2*t/5-t*t/5,2/5-2*t/5


def prepared(order=2,index=0):
    result=json.loads((HERE/f'inputs/prior-bdf{order}.json').read_text())
    old=result['snapshots'][index];setup=deepcopy(result['restart_context']['setup'])
    model=parse_asw((HERE/'inputs/body.asw').read_text())
    c=read_condition(setup['condition']);motion=Motion(**setup['motion'])
    n=StaticNetwork(model,setup['panels'],c,setup['gravity'],setup['mesh_loads'],None,
        time_operating_constraints(setup['frame'],setup['load_targets'],setup['actuator_constraints']),setup['strut_mode'])
    forcing=TimeForcing(setup['forcing'],model,c,motion,.08,setup['frame'],
        load_targets=setup['load_targets'],actuator_constraints=setup['actuator_constraints'])
    for channel in forcing.channels:channel['initial']=result['restart_context']['forcing_offsets'][channel['name']]
    system=TimeSystem(n,forcing,gravity_magnitude=setup.get('gravity_magnitude'))
    state=unpack_state(n,old['restart']['state'],None)
    original=old['position_history_sample'];lift=system.position_lift
    legacy=dict(policy=lift.policy,rows=[(r.variable,r.quantity,r.target) for r in lift.rows],forcing=forcing.source)
    assert hashlib.sha256(json.dumps(legacy,sort_keys=True,allow_nan=False).encode()).hexdigest()==original['signature']
    expected=lift.sample(state.time,forcing,original['side'])
    for key in ('time','side','branch'):assert original[key]==getattr(expected,key)
    for key in ('value','rate','acceleration'):
        np.testing.assert_array_equal(original[key],getattr(expected,key))
    q,v,a=physical(state.time)
    np.testing.assert_allclose([original['value'][0],original['rate'][0],original['acceleration'][0]],[q,v,a],rtol=0,atol=2e-14)
    # Retain the original accepted numerical values; do not regenerate them.
    state.position_history=PositionSample(original['time'],original['side'],lift.signature,
        *(tuple(original[key]) for key in ('value','rate','acceleration')),original['branch'],expected.intervals)
    lift.validate_sample(state,forcing)
    options=unpack_options(n,state,old['restart']['options'])
    return model,system,state,options,setup


def saved_at(order=2,index=2):
    model,system,state,options,setup=prepared(order,index)
    older=None if index==0 else prepared(order,index-1)[2]
    saved=dict(format='openswing-time-checkpoint',version=1,
        context=context(system,setup,order,.02,1e-8),
        **record(system,state,older,options,.02,'right'))
    return model,system,state,older,json.loads(json.dumps(portable(saved),allow_nan=False))
