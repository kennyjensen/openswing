"""Full source-equation trim, checked against mechanics and prescribed states."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.bridge import dispatch
from openswing.equilibrium_state import restore
from openswing.source_coupled import SourceCoupledNetwork, solve_source_coupled
from test_source_coupled import model, condition, assert_balanced


NUMERICS = dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-steady-coupled-v1')


def engine_request(target=5.):
    return dict(action='solve', mode='mounted', numerics=NUMERICS,
        source=Path('examples/instrumented-oscillator.asw').read_text(), panels=4,
        condition=dict(speed=10., alpha=0., mach=0., gravity_magnitude=0.),
        operating_constraints=[dict(variable='power.1', quantity='force.y', target=target)],
        tolerance=1e-10)


def check_fresh(result, m, flight, constraints, gravity=None):
    n = SourceCoupledNetwork(m, 4, flight, gravity, operating_constraints=constraints)
    state = restore(n, result['equilibrium_state'])
    residual, data = n.residual(state, detail=True)
    assert np.max(abs(residual)) < 2e-9
    assert_balanced(result)
    return n, state, data


def test_engine_force_trim_has_exact_axial_extension_and_warm_target_change():
    request = engine_request(); original = deepcopy(request)
    first = dispatch(request)
    assert request == original
    m = parse_asw(request['source'], beam_interpolation='drela-segspl-v1')
    for target, result in [(5., first), (8., dispatch(dict(engine_request(8.), initial_state=first['equilibrium_state'])))]:
        # P = F, extension = FL/EA; independent of the solver's load report.
        assert result['operating_values']['power.1'] == pytest.approx(target, abs=2e-9)
        assert result['nodes'][-1]['position'][1] == pytest.approx(2.+target*2./1000., abs=2e-10)
        assert result['support_force'][1] == pytest.approx(-target, abs=2e-9)
        check_fresh(result, m, FlightCondition(**request['condition']), engine_request(target)['operating_constraints'])


def test_alpha_and_flap_trim_recovers_the_complete_loaded_prescribed_state():
    m = model(); base = condition(); gravity = [1., -2., -10.]
    forward = solve_source_coupled(m, base, 4, gravity=gravity, tolerance=1e-10)
    targets = [dict(variable='alpha', quantity='CL', target=forward['CL']),
               dict(variable='control.1', quantity='moment.y', target=forward['applied_moment'][1])]
    guess = replace(base, alpha=1., controls={1: -.1})
    result = solve_source_coupled(m, guess, 4, gravity=gravity, operating_constraints=targets, tolerance=1e-10)
    assert result['operating_values']['alpha'] == pytest.approx(base.alpha, abs=2e-7)
    assert result['operating_values']['control.1'] == pytest.approx(base.controls[1], abs=2e-7)
    for field in ('CL', 'CD', 'Cm'):
        assert result[field] == pytest.approx(forward[field], abs=2e-9)
    np.testing.assert_allclose([n['position'] for n in result['nodes']],
                               [n['position'] for n in forward['nodes']], rtol=0, atol=2e-9)
    n, state, data = check_fresh(result, m, guess, targets, gravity)
    # Every target column differentiates the full mechanics/circulation system.
    for column in range(n.operating_start, n.size):
        derivatives = []
        for h in (1e-5, 3e-6):
            delta = np.zeros(n.size); delta[column] = h
            derivatives.append((n.residual(state+delta)-n.residual(state-delta))/(2*h))
        np.testing.assert_allclose(*derivatives, rtol=2e-6, atol=2e-7)
    assert np.linalg.norm(data['r']-n.rj) > 1e-4


def test_speed_lift_trim_and_earth_pose_use_the_solved_flight_condition():
    m = model(); base = condition(); base = replace(base, attitude=[8., -4., 3.])
    forward = solve_source_coupled(m, base, 4, tolerance=1e-10)
    lift = forward['CL'] * (.5*base.density*base.speed**2*m.reference[0][0])
    targets = [dict(variable='speed', quantity='lift', target=lift),
               dict(variable='attitude.bank', quantity='attitude.bank', target=8.),
               dict(variable='attitude.elevation', quantity='attitude.elevation', target=-4.)]
    guess = replace(base, speed=6.5, attitude=[0., 0., 3.])
    result = solve_source_coupled(m, guess, 4, operating_constraints=targets, tolerance=1e-10)
    assert result['operating_values']['speed'] == pytest.approx(base.speed, abs=1e-7)
    check_fresh(result, m, guess, targets)
    np.testing.assert_allclose([n['position'] for n in result['nodes']],
                               [n['position'] for n in forward['nodes']], rtol=0, atol=2e-9)


@pytest.mark.parametrize('variable', ['rates.x', 'acceleration.z', 'angular_acceleration.y'])
def test_direct_api_cannot_release_stationary_motion(variable):
    with pytest.raises(ValueError, match='prescribed zero'):
        SourceCoupledNetwork(model(), 4, condition(), operating_constraints=[
            dict(variable=variable, quantity='force.z')])
