"""Cold initialization owns chart edits and commits only checked states."""
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import AnalysisError
from openswing.network import StaticNetwork
from openswing.joints import HingeLaw
from openswing.hinge_history import current
import openswing.time_integration as time


@pytest.mark.parametrize('outcome', ['solver_failure', 'residual_failure', 'residual_exception', 'accepted'])
def test_cold_hinge_chart_copy_does_not_copy_runtime_and_commits_after_check(monkeypatch, outcome):
    source = Path(__file__).parent/'fixtures'/'hinge-history'/'source'/'rigid-hinge-release.asw'
    n = StaticNetwork(parse_asw(source.read_text()), 4, None, [0, 0, 0], [])
    original = current(n)
    dictionaries = list(n.constraints)
    laws = [c.get('law') for c in n.constraints]

    def no_runtime_copy(self, memo):
        raise TypeError("cannot pickle 'module' object")
    monkeypatch.setattr(HingeLaw, '__deepcopy__', no_runtime_copy, raising=False)

    def steady(net, tolerance, steps, **options):
        assert net is not n and net.constraints is not n.constraints
        for before, after, law in zip(dictionaries, net.constraints, laws):
            assert after is not before
            assert after.get('law') is law
            if after['type'] == 3:
                after['angle_chart'] = .125
        assert current(n) == original
        if outcome == 'solver_failure':
            raise AnalysisError('deliberate solver failure')
        return np.zeros(net.size), [1.]

    def original_residual(state, **options):
        assert current(n) == original
        assert options['hinge_charts'] == (.125,)
        if outcome == 'residual_exception':
            raise AnalysisError('deliberate original-residual exception')
        return np.array([1. if outcome == 'residual_failure' else 0.])

    monkeypatch.setattr(time, 'equilibrate', steady)
    monkeypatch.setattr(n, 'residual', original_residual)
    zeros = np.zeros_like(n.rj)
    options = dict(elastic_motion=(zeros, zeros, zeros, zeros),
                   circulation_rate=np.zeros(n.ng))
    if outcome == 'accepted':
        time.initial_equilibrium(n, options, 1e-8, 4)
        assert current(n) == (.125,)
    else:
        with pytest.raises(AnalysisError):
            time.initial_equilibrium(n, options, 1e-8, 4)
        assert current(n) == original
    assert all(c is old for c, old in zip(n.constraints, dictionaries))
    assert all(c.get('law') is law for c, law in zip(n.constraints, laws))
