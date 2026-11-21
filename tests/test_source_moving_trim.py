"""Moving source trim against centrifugal/accelerating-frame mechanics."""
from copy import deepcopy
from dataclasses import replace
import numpy as np
import pytest

from openswing.bridge import dispatch
from openswing.equilibrium_state import restore
from openswing.source_airflow import SourceAirflowNetwork, solve_source_airflow_steady
from test_source_airflow_trim import trim_request, retain


MASS, LENGTH, STIFFNESS = 2., 2., 500.
RATES = [0., 0., .7]
ACCELERATION = [.3, -.4, .5]
ANGULAR = [.1, .2, -.15]
THRUST = 7.2204


def moving_request():
    request = trim_request()
    request['operating_constraints'] = []
    request['condition'].update(rates=RATES.copy(), acceleration=ACCELERATION.copy(),
        angular_acceleration=ANGULAR.copy(), powers={1: THRUST})
    return request


def exact_state():
    # k delta = P - m a_y + m Omega_z^2 (L + delta).
    delta = (THRUST-MASS*ACCELERATION[1]+MASS*RATES[2]**2*LENGTH)/(STIFFNESS-MASS*RATES[2]**2)
    tip = np.array([0., LENGTH+delta, 0.])
    acceleration = (np.array(ACCELERATION)+np.cross(ANGULAR, tip)
                    +np.cross(RATES, np.cross(RATES, tip)))
    force = np.array([0., THRUST, 0.])-MASS*acceleration
    return tip, force, np.cross(tip, force)


@pytest.mark.parametrize('variable', [None, 'power.1', 'rates.z', 'acceleration.y', 'angular_acceleration.z'])
def test_moving_trim_recovers_exact_point_mass_balance(variable):
    request = moving_request()
    tip, force, moment = exact_state()
    expected = {'power.1': THRUST, 'rates.z': RATES[2],
        'acceleration.y': ACCELERATION[1], 'angular_acceleration.z': ANGULAR[2]}
    if variable is not None:
        quantity, target = ('force.x', force[0]) if variable.startswith('angular_') else ('force.y', force[1])
        request['operating_constraints'] = [dict(variable=variable, quantity=quantity, target=float(target))]
        if variable == 'power.1':
            request['condition']['powers'][1] = 3.
        else:
            group, axis = variable.split('.')
            request['condition'][group]['xyz'.index(axis)] = .4 if group == 'rates' else 0.
    before = deepcopy(request)
    result = dispatch(request)
    assert request == before
    np.testing.assert_allclose(result['nodes'][-1]['position'], tip, rtol=0, atol=2e-9)
    np.testing.assert_allclose(result['applied_force'], force, rtol=0, atol=2e-8)
    np.testing.assert_allclose(result['applied_moment'], moment, rtol=0, atol=2e-8)
    np.testing.assert_allclose(result['support_force'], -force, rtol=0, atol=2e-8)
    np.testing.assert_allclose(result['support_moment'], -moment, rtol=0, atol=2e-8)
    if variable is not None:
        assert result['operating_values'][variable] == pytest.approx(expected[variable], abs=2e-8)
    saved = result['equilibrium_state']
    for group, values in [('rates', RATES), ('acceleration', ACCELERATION), ('angular_acceleration', ANGULAR)]:
        np.testing.assert_allclose(saved['launch']['motion'][group], values, rtol=0, atol=2e-8)
        np.testing.assert_allclose(saved['launch']['condition'][group], values, rtol=0, atol=2e-8)
    retain('moving-'+str(variable), dict(request=request, result=result, exact_tip=tip.tolist(),
        exact_force=force.tolist(), exact_moment=moment.tolist()))


def test_lifting_moving_trim_recovers_prescribed_loaded_state_and_full_dynamic_residual():
    from test_source_coupled import model, condition
    m = model()
    c = condition(rates=[.02, -.03, .04], acceleration=[.1, -.2, .3],
                  angular_acceleration=[.01, .02, -.03])
    gravity = [1., -2., -10.]
    forward = solve_source_airflow_steady(m, c, 4, gravity=gravity, tolerance=1e-10)
    targets = [dict(variable='alpha', quantity='CL', target=forward['CL']),
        dict(variable='acceleration.z', quantity='force.z', target=forward['applied_force'][2])]
    guess = replace(c, alpha=2., acceleration=[.1, -.2, 0.])
    result = solve_source_airflow_steady(m, guess, 4, gravity=gravity,
        operating_constraints=targets, tolerance=1e-10)
    assert result['operating_values']['alpha'] == pytest.approx(c.alpha, abs=2e-7)
    assert result['operating_values']['acceleration.z'] == pytest.approx(.3, abs=2e-7)
    np.testing.assert_allclose([n['position'] for n in result['nodes']],
        [n['position'] for n in forward['nodes']], rtol=0, atol=2e-9)
    for field in ('CL', 'CD', 'Cm'):
        assert result[field] == pytest.approx(forward[field], abs=2e-9)
    # Reconstruct the ordinary dynamic network with the solved motion, release
    # the trim rows and evaluate its complete residual at zero local rates.
    from openswing.time_state import read_condition
    solved = read_condition(result['equilibrium_state']['launch']['condition'])
    n = SourceAirflowNetwork(m, 4, solved, gravity, [])
    x = restore(n, result['equilibrium_state'])
    zero = np.zeros((n.nn, 3))
    residual = n.residual(x, elastic_motion=(zero, zero, zero, zero),
                          circulation_rate=np.zeros(n.circulation_basis.panels))
    assert np.max(abs(residual)) < 2e-9
    retain('lifting-moving', dict(result=result, forward=forward,
                                 full_dynamic_residual=float(np.max(abs(residual)))))


def test_moving_trim_launch_keeps_loads_and_integrates_aircraft_motion(monkeypatch):
    request = moving_request()
    request['condition'].update(acceleration=[0., ACCELERATION[1], 0.], angular_acceleration=[0., 0., 0.])
    trimmed = dispatch(request)
    saved = trimmed['equilibrium_state']; before = deepcopy(saved)
    def forbidden(*args, **kwargs):
        pytest.fail('Steady equilibrium recomputed during moving launch')
    monkeypatch.setattr('openswing.network.equilibrate', forbidden)
    monkeypatch.setattr('openswing.source_discrete.equilibrate', forbidden)
    monkeypatch.setattr('openswing.time_integration.initial_equilibrium', forbidden)
    errors = []
    for dt in (.002, .001):
        value = dict(action='launch_time', mode='time', source=request['source'], numerics=request['numerics'],
            equilibrium_state=saved, time=dict(duration=.004, dt=dt, order=2, frame='prescribed', tolerance=1e-10))
        result = dispatch(value)
        assert result['converged'] and not result['initialization']['equilibrium_recomputed']
        assert result['initialization']['residual'] < 1e-9
        for sample in result['snapshots']:
            np.testing.assert_allclose(sample['nodes'][-1]['position'], [0., 2.02, 0.], rtol=0, atol=2e-9)
            np.testing.assert_allclose(sample['local_velocity'], 0., rtol=0, atol=2e-8)
            assert sample['residual'] < 1e-9
        final = result['snapshots'][-1]
        t = final['time']; omega = RATES[2]; ay = ACCELERATION[1]
        exact_velocity = np.array([-10*np.cos(omega*t)+ay*(1-np.cos(omega*t))/omega,
            (10+ay/omega)*np.sin(omega*t), 0.])
        errors.append(float(np.linalg.norm(np.array(final['frame']['velocity_origin_body'])-exact_velocity)/10.))
        assert saved == before
        retain('moving-launch-'+str(dt), dict(request=value, result=result,
            exact_velocity=exact_velocity.tolist(), velocity_error=errors[-1]))
    assert errors[1] < 1e-6 and errors[1] < .4*errors[0], errors
