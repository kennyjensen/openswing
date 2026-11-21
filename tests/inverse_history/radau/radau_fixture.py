"""Owned samples from an actual cold solve, with independent cubic mechanics."""
from pathlib import Path
import json
import numpy as np
from openswing.asw import parse_asw
from openswing.forcing import TimeForcing
from openswing.time_integration import TimeSystem
from openswing.time_state import restore_checkpoint, checkpoint

INPUTS = Path(__file__).parent / 'inputs'


def saved(name='step'):
    return json.loads((INPUTS / (name+'-checkpoint.json')).read_text())


def prepared():
    model = parse_asw((INPUTS/'rigid.asw').read_text())
    cp = saved('initial')
    n, feedback, state, _, options, _, _, _ = restore_checkpoint(model, cp)
    setup = cp['context']['setup']
    forcing = TimeForcing(setup['forcing'], model, n.condition, n.motion, 1., setup['frame'],
        feedback, load_targets=setup['load_targets'], actuator_constraints=setup['actuator_constraints'])
    for channel in forcing.channels:
        channel['initial'] = cp['context']['forcing_offsets'][channel['name']]
    system = TimeSystem(n, forcing, feedback)
    return model, system, state, options, setup


def check(result, model, *, replacement=None):
    for i, snapshot in enumerate(result['snapshots']):
        t = snapshot['time']
        if replacement is not None and i:
            anchor, p0, v0, a0 = replacement
            tau = t-anchor
            p = p0+v0*tau+.5*a0*tau*tau-a0*tau**3/6
            v = v0+a0*tau-.5*a0*tau*tau
            a = a0*(1-tau)
        else:
            p, v, a = -10*t+.2*t*t-t**3/15, -10+.4*t-.2*t*t, .4*(1-t)
        frame = snapshot['frame']
        np.testing.assert_allclose([frame['position_earth'][0], frame['velocity_origin_body'][0],
            frame['acceleration_reference_body'][0], snapshot['operating_values']['power.1']],
            [p, v, a, a], rtol=0, atol=1e-7)
        validation = restore_checkpoint(model, checkpoint(result, i))[-1]['acceptance_validation']
        if snapshot['step'] > 0:
            assert validation['discrete_replayed']
