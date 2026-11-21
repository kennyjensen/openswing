"""Public cold/restart/transition behavior, not just metadata acceptance."""
from copy import deepcopy
import pytest
from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.time_integration import solve_time
from openswing.time_state import checkpoint, restore_checkpoint, resume_time
from radau_fixture import INPUTS, saved, check


@pytest.mark.parametrize('order', [1, 2, 5])
def test_actual_radau_checkpoint_continues_with_each_method(order):
    model = parse_asw((INPUTS/'rigid.asw').read_text())
    cp = saved(); before = deepcopy(cp)
    result = resume_time(model, cp, duration=.02, dt=.02, order=order)
    assert cp == before
    assert result['snapshots'][0]['restart']['accepted_method'] == cp['accepted_method']
    assert result['accepted_steps'] == 1 and result['rejected_steps'] == 0
    check(result, model)


def test_public_cold_start_retains_replayable_radau_position_samples():
    model = parse_asw((INPUTS/'rigid.asw').read_text())
    result = solve_time(model, FlightCondition(speed=10, alpha=0, mach=0), 4,
        duration=.02, dt=.02, order=5, frame='free', gravity=[0, 0, 0],
        forcing=(INPUTS/'position.tbl').read_text(),
        actuator_constraints=[dict(variable='power.1', quantity='position_earth.x', target=0.)])
    assert result['accepted_steps'] == 1 and result['rejected_steps'] == 0
    assert result['initialization']['source'] == 'cold inverse-history equilibrium'
    assert all(s['restart']['state']['position_history'] is not None for s in result['snapshots'])
    check(result, model)


def test_compatible_position_replacement_holds_motion_and_retains_before_record():
    model = parse_asw((INPUTS/'rigid.asw').read_text())
    cp = saved(); before = deepcopy(cp); state = cp['state']
    t, p, v, a = state['time'], state['position_earth'][0], state['velocity_origin_body'][0], -.3
    table = f'time RX\n{t-1!r} {p-v+a/3!r}\n{t!r} {p!r}\n{t+1!r} {p+v+a/3!r}'
    result = resume_time(model, cp, duration=.02, dt=.02, order=5, forcing=table)
    assert cp == before and checkpoint(result, 0) == before
    assert result['accepted_steps'] == 1 and result['rejected_steps'] == 0
    assert [s['order'] for s in result['snapshots']] == [0, 0, 5]
    assert max(result['snapshots'][1]['input_transition']['held_physical_max_error'].values()) < 1e-12
    check(result, model, replacement=(t, p, v, a))


def test_incompatible_position_slope_refuses_before_completion(monkeypatch):
    import openswing.time_transition_initial as transition
    def forbidden(*args, **kwargs):
        raise AssertionError('Incompatible velocity entered derivative completion')
    monkeypatch.setattr(transition, 'consistent_initial', forbidden)
    model = parse_asw((INPUTS/'rigid.asw').read_text()); cp = saved(); before = deepcopy(cp)
    t, p, v = cp['state']['time'], cp['state']['position_earth'][0], cp['state']['velocity_origin_body'][0]
    table = f'time RX\n{t-1!r} {p-v-.1!r}\n{t!r} {p!r}\n{t+1!r} {p+v+.1!r}'
    with pytest.raises(AnalysisError, match='incompatible.*Earth velocity'):
        resume_time(model, cp, duration=.02, dt=.02, order=5, forcing=table)
    assert cp == before


@pytest.mark.parametrize('kind', ['missing-sample', 'sample-acceleration', 'method-policy',
    'old-stage-scheme', 'stage-position', 'stage-velocity', 'seed-position', 'stage-time', 'stage-side'])
def test_recorded_radau_inputs_and_stages_cannot_be_relabelled(kind):
    model = parse_asw((INPUTS/'rigid.asw').read_text()); cp = saved()
    record = cp['accepted_method']; j = record['layout']['frame_start']
    if kind == 'missing-sample': cp['state'].pop('position_history')
    elif kind == 'sample-acceleration': cp['state']['position_history']['acceleration'][0] = 10.
    elif kind == 'method-policy': cp['context']['method']['position_history']['policy'] = 'original-continuous-dae-v1'
    elif kind == 'old-stage-scheme': record['scheme'] = 'openswing-so3-radau-iia-3-v1'
    elif kind == 'stage-position': record['increments'][0][j+6] = .001
    elif kind == 'stage-velocity': record['increments'][1][j] = .001
    elif kind == 'seed-position': record['seed']['position_earth'][0] = .01
    elif kind == 'stage-time': record['stage_times'][0] = 0.
    elif kind == 'stage-side': record['stage_sides'][0] = 'left'
    with pytest.raises(AnalysisError):
        restore_checkpoint(model, cp)
