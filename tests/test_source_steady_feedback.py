"""Source steady controllers: independent mechanics, commands and reuse."""
from copy import deepcopy
import json
import os
from pathlib import Path
import numpy as np
import pytest

from openswing.bridge import dispatch
from test_source_airflow_trim import trim_request
from test_feedback import law


def request(controller):
    value = trim_request()
    value.update(controller=controller, operating_constraints=[])
    return value


def retain(name, value):
    if folder := os.environ.get('SOURCE_STEADY_FEEDBACK_EVIDENCE'):
        p = Path(folder); p.mkdir(parents=True, exist_ok=True)
        (p/(name+'.json')).write_text(json.dumps(value, allow_nan=False)+'\n')


@pytest.mark.parametrize('ki', [0., 100.])
def test_steady_controller_solves_exact_bar_extension_and_integral(ki):
    control = law(kd=0, ki=ki); control['commands'] = {'RY[2]': 2.01}
    value = request(control); before = deepcopy(value)
    result = dispatch(value)
    displacement = .01 if ki else 200*.01/(500+200)
    np.testing.assert_allclose(result['nodes'][-1]['position'], [0, 2+displacement, 0], atol=2e-10, rtol=0)
    assert result['feedback']['actuators']['E1'] == pytest.approx(500*displacement, abs=2e-8)
    assert result['operating_values']['power.1'] == pytest.approx(500*displacement, abs=2e-8)
    np.testing.assert_allclose(result['support_force'], [0, -500*displacement, 0], atol=2e-8, rtol=0)
    assert result['residual'] < 1e-9
    assert result['source_discrete_elements']
    if ki:
        assert result['feedback']['integrals']['RY[2]'] == pytest.approx(-.05, abs=2e-9)
        assert abs(result['feedback']['errors']['RY[2]']) < 2e-10
    assert result['equilibrium_state']['launch']['controller'] == control
    assert value == before
    retain('bar-'+str(ki), dict(request=value, result=result))


@pytest.mark.parametrize('variable,ki,command,integral', [
    ('command.E1', 0., 7., None), ('command.RY[2]', 0., 2.035, None),
    ('command.RY[2]', 100., 2.01, -.05)])
def test_controller_command_trim_preserves_force_and_integral_rows(variable, ki, command, integral):
    value = request(law(kd=0, ki=ki))
    value['operating_constraints'] = [dict(variable=variable, quantity='force.y', target=5.)]
    result = dispatch(value)
    assert result['nodes'][-1]['position'][1] == pytest.approx(2.01, abs=2e-10)
    assert result['feedback']['actuators']['E1'] == pytest.approx(5., abs=2e-8)
    assert result['feedback']['commands'][variable.removeprefix('command.')] == pytest.approx(command, abs=2e-8)
    assert result['controller_equilibrium']['solved_commands'][variable] == pytest.approx(command, abs=2e-8)
    assert result['operating_constraints'][0]['actual'] == pytest.approx(5., abs=2e-8)
    if integral is not None:
        assert result['feedback']['integrals']['RY[2]'] == pytest.approx(integral, abs=2e-9)
    retain('command-'+variable+'-'+str(ki), dict(request=value, result=result))


def test_accelerating_frame_controller_uses_actual_sensor_specific_force():
    control = law(kd=0, ki=100., ka=3.)
    control['commands'] = {'RY[2]': 2.01, 'Ay[2]': 0.}
    value = request(control); value['condition']['acceleration'] = [0., .4, 0.]
    result = dispatch(value)
    # P = k*delta + m*a = 5.8; P = -100*I - 3*a, hence I=-.07.
    assert result['nodes'][-1]['position'][1] == pytest.approx(2.01, abs=2e-10)
    assert result['feedback']['measurements']['Ay[2]'] == pytest.approx(.4, abs=2e-10)
    assert result['feedback']['actuators']['E1'] == pytest.approx(5.8, abs=2e-8)
    assert result['feedback']['integrals']['RY[2]'] == pytest.approx(-.07, abs=2e-9)
    assert result['support_force'][1] == pytest.approx(-5., abs=2e-8)
    retain('accelerating', dict(request=value, result=result))


@pytest.mark.parametrize('variable,ki,match', [('power.1',0.,'command.E1'), ('command.E1',100.,'singular|nonunique')])
def test_owned_actuator_and_redundant_integral_trim_are_rejected(variable, ki, match):
    value = request(law(kd=0, ki=ki))
    value['operating_constraints'] = [dict(variable=variable, quantity='force.y', target=0.)]
    with pytest.raises(ValueError, match=match):
        dispatch(value)


def test_circulation_integral_control_matches_independent_four_horseshoes():
    from test_source_airflow_feedback import STRIP, PANELS, CONDITION, strip_law, strip_coefficients
    value = request(strip_law())
    value.update(source=STRIP, panels=deepcopy(PANELS), condition=deepcopy(CONDITION))
    command = 1e-4
    value['controller']['commands'] = {'Cr[1]': command}
    result = dispatch(value)
    a, _, forcing = strip_coefficients()
    per_flap = np.linalg.solve(a, forcing)
    flap = command/per_flap[0]
    gamma = per_flap*flap
    np.testing.assert_allclose([s['circulation'] for s in result['strips']], gamma, rtol=2e-6, atol=2e-10)
    assert result['feedback']['actuators']['F1'] == pytest.approx(flap, rel=2e-6, abs=2e-10)
    assert result['feedback']['integrals']['Cr[1]'] == pytest.approx(-flap/.15, rel=2e-6, abs=2e-10)
    assert abs(result['feedback']['errors']['Cr[1]']) < 2e-10
    assert result['residual'] < 1e-9
    retain('circulation', dict(request=value, result=result, reference_circulation=gamma.tolist(), reference_flap=float(flap)))


def test_saved_integral_trim_warm_target_change_and_time_launch(monkeypatch):
    value = request(law(kd=0, ki=100.))
    value['operating_constraints'] = [dict(variable='command.RY[2]', quantity='force.y', target=5.)]
    first = dispatch(value); saved = first['equilibrium_state']; before = deepcopy(saved)
    warm = deepcopy(value); warm['initial_state'] = saved
    warm['operating_constraints'][0]['target'] = 8.
    second = dispatch(warm)
    assert second['nodes'][-1]['position'][1] == pytest.approx(2.016, abs=2e-10)
    assert second['feedback']['commands']['RY[2]'] == pytest.approx(2.016, abs=2e-10)
    assert second['feedback']['actuators']['E1'] == pytest.approx(8., abs=2e-8)
    assert second['feedback']['integrals']['RY[2]'] == pytest.approx(-.08, abs=2e-9)
    def forbidden(*args, **kwargs):
        pytest.fail('Saved controller equilibrium recomputed during time launch')
    monkeypatch.setattr('openswing.network.equilibrate', forbidden)
    monkeypatch.setattr('openswing.source_discrete.equilibrate', forbidden)
    monkeypatch.setattr('openswing.time_integration.initial_equilibrium', forbidden)
    launch = dict(action='launch_time', mode='time', source=value['source'], numerics=value['numerics'],
        equilibrium_state=saved, time=dict(duration=.004, dt=.002, frame='prescribed', order=2, tolerance=1e-10))
    result = dispatch(launch)
    assert result['converged'] and not result['initialization']['equilibrium_recomputed']
    assert result['initialization']['released_constraints'] == saved['launch']['released_constraints']
    assert result['initialization']['released_constraints'][0]['variable'] == 'command.RY[2]'
    assert result['initialization']['residual'] < 1e-9
    for sample in result['snapshots']:
        assert sample['nodes'][-1]['position'][1] == pytest.approx(2.01, abs=2e-10)
        assert sample['feedback']['actuators']['E1'] == pytest.approx(5., abs=2e-8)
        assert sample['feedback']['integrals']['RY[2]'] == pytest.approx(-.05, abs=2e-9)
        assert abs(sample['feedback']['errors']['RY[2]']) < 2e-10
        assert sample['residual'] < 1e-9
    assert saved == before
    bad = deepcopy(launch); bad['equilibrium_state']['feedback']['values'][1] += .01
    with pytest.raises(ValueError, match='inconsistent with the time equations'):
        dispatch(bad)
    retain('warm', dict(request=warm, result=second))
    retain('launch', dict(request=launch, result=result, trim=first))


def test_four_controller_commands_preserve_elastic_climbing_turn():
    from dataclasses import replace
    from openswing.aero import FlightCondition
    from openswing.asw import parse_asw
    from openswing.operating import steady_turn_constraints
    from openswing.source_airflow import solve_source_airflow_steady
    model = parse_asw(Path('examples/trim-aircraft.asw').read_text(), beam_interpolation='drela-segspl-v1')
    c = FlightCondition(alpha=4., mach=0., powers={1:120.}, attitude=(0.,4.,57.))
    targets = steady_turn_constraints(np.deg2rad(3.), 2., trim_controls=[2,1,3], engine_control=1)
    reference = solve_source_airflow_steady(model, c, 4, operating_constraints=targets, tolerance=1e-11)
    retain('turn-reference', reference)
    controller = {'outputs':[dict(actuator=a, terms=[dict(input=s, gain=g)])
        for a,s,g in [('F1','A',-.7),('F2','Ex',-.3),('F3','Wz',-.1),('E1','V',.5)]]}
    commands = [replace(t, variable='command.F'+t.variable.split('.')[1]) if t.variable.startswith('control.')
        else replace(t, variable='command.E'+t.variable.split('.')[1]) if t.variable.startswith('power.') else t for t in targets]
    result = solve_source_airflow_steady(model, c, 4, controller=controller,
        operating_constraints=commands, tolerance=1e-11)
    assert len(result['operating_constraints']) == 16
    assert max(abs(t['normalized_residual']) for t in result['operating_constraints']) < 1e-8
    np.testing.assert_allclose(result['applied_force'], 0, atol=1e-5, rtol=0)
    np.testing.assert_allclose(result['applied_moment'], 0, atol=1e-5, rtol=0)
    for axis in 'xyz':
        assert result['operating_values']['rates.'+axis] == pytest.approx(reference['operating_values']['rates.'+axis], abs=1e-8)
    for a in ('F1','F2','F3','E1'):
        key = ('control.' if a[0]=='F' else 'power.')+a[1:]
        assert result['feedback']['actuators'][a] == pytest.approx(reference['operating_values'][key], abs=1e-6)
    np.testing.assert_allclose([n['position'] for n in result['nodes']],
        [n['position'] for n in reference['nodes']], atol=1e-7, rtol=0)
    assert abs(result['feedback']['commands']['F1']-result['feedback']['actuators']['F1']) > .01
    retain('turn-controlled', result)
