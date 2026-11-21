"""A clamped wall-root must survive warm Newton probes, not physical crossings."""
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.equilibrium_state import restore
from openswing.ground import GroundIntersectionError
from openswing.source_coupled import SourceCoupledNetwork, solve_source_coupled
import openswing.seeded_corrector as seeded
from test_wall_root import configuration, flight


@pytest.mark.parametrize('frozen', [False, True])
@pytest.mark.parametrize('dense_recovery', [False, True])
def test_source_wall_continuation_matches_cold_and_preserves_clearance(frozen, dense_recovery, monkeypatch):
    original, panels = configuration(False)
    model = parse_asw(original.dumps(), beam_interpolation='drela-segspl-v1')
    previous = replace(flight(), speed=8., freeze_influences=frozen)
    target = replace(previous, speed=10.)
    first = solve_source_coupled(model, previous, panels)
    seed = first['equilibrium_state']; unchanged = deepcopy(seed)
    cold = solve_source_coupled(model, target, panels)
    attempts = []
    if dense_recovery:
        def unavailable(*args, **kwargs):
            attempts.append(True)
            raise RuntimeError('Injected beam-factor unavailability')
        monkeypatch.setattr(seeded, 'NewtonBeamFactor', unavailable)
    warm = solve_source_coupled(model, target, panels, initial_state=seed)
    assert seed == unchanged
    for key in ('positions', 'rotations', 'internal_force', 'internal_moment', 'reactions', 'circulation'):
        np.testing.assert_allclose(warm['equilibrium_state'][key], cold['equilibrium_state'][key], rtol=2e-7, atol=2e-9)
    report = warm['equilibrium_initialization']['seeded_corrector']
    assert report['enabled'] and report['builder_detached']
    assert report['factor_wrappers_alive_before_final_tangent'] == 0
    assert report['dense_tangent_builds'] >= int(dense_recovery)
    if dense_recovery:
        assert attempts == [True]
    else:
        assert report['builds'] and all(r['status'] == 'BUILT' for r in report['builds'])
    net = SourceCoupledNetwork(model, panels, target, None, [])
    state = restore(net, warm['equilibrium_state'])
    assert np.max(abs(net.residual(state))) <= 1e-8
    np.testing.assert_allclose(warm['force_balance'], 0., atol=2e-8)
    np.testing.assert_allclose(warm['moment_balance'], 0., atol=2e-8)
    # The derivative exception must not leak into an ordinary physical trial.
    root = next(c['a'] for c in net.constraints if c['kind'] == 'ground')
    crossed = state.copy(); crossed[6*root+1] -= 1e-3/net.L
    with pytest.raises(GroundIntersectionError):
        net.residual(crossed)
