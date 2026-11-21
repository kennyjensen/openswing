"""Checkpoint endpoints retain forcing events after duration roundoff."""
import numpy as np
import pytest

from openswing.time_integration import solve_time
from openswing.time_state import checkpoint, resume_time
from test_time_integration import rigid_body
from test_time_state import same


START = 0.016534698176788383
KNOT = 0.08267349088394192
FINISH = .12


@pytest.mark.parametrize('kind', ['smooth', 'jump', 'cutoff'])
def test_segment_endpoint_roundoff_keeps_exact_event_and_resumes(kind):
    # These are the actual UA-2 checkpoint times, not a perturbed state.
    assert START + (KNOT-START) == np.nextafter(KNOT, -np.inf)
    tail = {'smooth': f'{KNOT:.17g} .3\n{FINISH} .4\n',
            'jump': f'{KNOT:.17g} .3\n{KNOT:.17g} .7\n{FINISH} .7\n',
            'cutoff': f'{KNOT:.17g} .3\n'}[kind]
    forcing = f'time Ax\n0 .2\n{START:.17g} .25\n'+tail
    model = rigid_body()
    settings = dict(panels=4, dt=.01, gravity=[0,0,0], forcing=forcing)
    whole = solve_time(model, duration=FINISH, **settings)
    first = solve_time(model, duration=START, **settings)
    middle = resume_time(model, checkpoint(first), duration=KNOT-START)
    assert middle['snapshots'][-1]['time'] == KNOT
    assert middle['snapshots'][-1]['forcing_values']['Ax'] == pytest.approx(.3)
    if kind != 'smooth':
        assert middle['snapshots'][-1]['forcing_side'] == 'left'
    last = resume_time(model, checkpoint(middle), duration=FINISH-KNOT)
    joined = first['snapshots']+middle['snapshots'][1:]+last['snapshots'][1:]
    assert len(joined) == len(whole['snapshots'])
    for actual, expected in zip(joined, whole['snapshots']):
        assert actual['time'] == expected['time']
        assert actual['order'] == expected['order']
        same(actual, expected, tol=2e-9)
    assert sum(r['rejected_steps'] for r in (first,middle,last)) == 0
    assert min(s['step'] for s in joined[1:]) > 1e-5


def test_accuracy_control_lands_on_event_just_above_rounded_endpoint():
    model=rigid_body()
    first=solve_time(model,panels=4,duration=START,dt=.01,gravity=[0,0,0],
        forcing=f'time Ax\n0 .2\n{START:.17g} .2\n{KNOT:.17g} .2\n{FINISH} .2\n')
    middle=resume_time(model,checkpoint(first),duration=KNOT-START,
                       accuracy=dict(rtol=1e-3,atol=1e-6))
    assert middle['snapshots'][-1]['time']==KNOT
    assert middle['rejected_steps']==0
