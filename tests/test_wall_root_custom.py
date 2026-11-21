"""Sensor-constrained wall-root equilibria must recover ordinary physical solves."""
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.equilibrium_state import restore
from openswing.ground import GroundIntersectionError
from openswing.network import StaticNetwork, solve_static
from openswing.source_coupled import SourceCoupledNetwork, solve_source_coupled
from test_wall_root import configuration, flight


@pytest.mark.parametrize('source', [False, True])
@pytest.mark.parametrize('frozen', [False, True])
def test_wall_root_custom_sensor_recovers_independent_speed_and_preserves_clearance(source, frozen):
    original, panels = configuration(False)
    original.records['sensor'] = [[1, 1, 2, 0, 1, 0, 1, 0, 0, 0, 0, 1]]
    model = parse_asw(original.dumps(), beam_interpolation='drela-segspl-v1')
    solver = solve_source_coupled if source else solve_static
    cls = SourceCoupledNetwork if source else StaticNetwork
    earlier = replace(flight(), speed=8., freeze_influences=frozen)
    target_condition = replace(earlier, speed=10.)
    first = solver(model, earlier, panels)
    forward = solver(model, target_condition, panels)
    target = forward['sensors'][0]['position_earth'][2]
    constraint = dict(variable='speed', quantity='user.tip',
        expression='sensor("1.position_earth.z")', target=target, unit='input L', residual_scale=1.)
    seed = first['equilibrium_state']; untouched = deepcopy(seed)
    result = solver(model, earlier, panels, initial_state=seed, operating_constraints=[constraint])
    assert seed == untouched
    assert result['operating_values']['speed'] == pytest.approx(10., abs=2e-6)
    for key in ('positions', 'rotations', 'internal_force', 'internal_moment', 'reactions', 'circulation'):
        np.testing.assert_allclose(result['equilibrium_state'][key], forward['equilibrium_state'][key], rtol=2e-6, atol=2e-8)
    assert result['custom_trim']['one_sided_tangent_ratio'] <= 1.
    assert result['custom_trim']['column_scaled_reciprocal_condition'] > 1e-10
    net = cls(model, panels, earlier, None, [], operating_constraints=[constraint])
    state = restore(net, result['equilibrium_state'])
    assert np.max(abs(net.residual(state))) <= 1e-8
    np.testing.assert_allclose(result['force_balance'], 0., atol=2e-8)
    np.testing.assert_allclose(result['moment_balance'], 0., atol=2e-8)
    root = next(c['a'] for c in net.constraints if c['kind'] == 'ground')
    crossed = state.copy(); crossed[6*root+1] -= 1e-3/net.L
    with pytest.raises(GroundIntersectionError):
        net.residual(crossed)
