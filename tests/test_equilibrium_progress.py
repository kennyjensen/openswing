"""Progress observes existing warm-correction work without changing its solve."""
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.equilibrium_state import capture, correct
from openswing.network import StaticNetwork, equilibrate
from openswing.operating import OperatingConstraint


def trim_network(target=10.):
    source = Path('examples/flexible.asw').read_text()
    source = source.replace('0 .008 2 -.035 0', '0 0 0 0 0').replace('8 .008 2 -.035 -2', '8 0 0 0 0')
    return StaticNetwork(parse_asw(source), 4,
        FlightCondition(speed=8, alpha=0, beta=0, mach=.03), [0, 0, 0], [],
        operating_constraints=[OperatingConstraint('alpha', 'force.z', target)])


def assert_clean(n):
    assert n.iteration_fields is None and n.tangent_influences is None and n._tangent_loads is None


def test_declined_native_progress_preserves_state_and_call_counts():
    reports = []; states = []; counts = []; events = []
    for progress in [None, lambda *event: events.append(event)]:
        n = trim_network(); initial = capture(n, np.zeros(n.size)); untouched = deepcopy(initial)
        before = n.nfev
        state, steps = equilibrate(n, tolerance=1e-9, initial_state=initial, progress=progress)
        counts.append(n.nfev-before); states.append(state.copy()); reports.append(n.equilibrium_diagnostics)
        assert steps == 1 and initial == untouched
        assert not hasattr(n, '_seeded_corrector_diagnostics')
        assert n.equilibrium_diagnostics['newton_iterations'] > 0
        assert n.equilibrium_diagnostics['tangent_builds'] > 0
        assert np.max(abs(n.residual(state))) <= 1e-8
        assert n.equilibrium_diagnostics['column_scaled_reciprocal_condition'] >= 1e-10
        assert_clean(n)
    np.testing.assert_array_equal(states[0], states[1])
    assert counts[0] == counts[1] and reports[0] == reports[1]
    iterations = [event for event in events if event[0] == 'equilibrium_iteration']
    assert iterations and iterations[0][1] == 0 and iterations[0][2] > 1e-9
    assert all(np.isfinite(event[2]) for event in iterations)
    for stage in ['equilibrium_iteration_tangent', 'equilibrium_final_tangent']:
        columns = [event for event in events if event[0] == stage]
        assert columns[0] == (stage, 0, n.size)
        assert columns[-1] == (stage, n.size, n.size)
    assert not any(event[0].startswith('time_') or event[0] == 'equilibrium_tangent' for event in events)


@pytest.mark.parametrize('stage', ['equilibrium_iteration', 'equilibrium_iteration_tangent', 'equilibrium_final_tangent'])
@pytest.mark.parametrize('kind', [RuntimeError, ValueError, KeyboardInterrupt])
def test_declined_progress_failure_propagates_and_releases_owners(stage, kind):
    n = trim_network(0. if stage == 'equilibrium_final_tangent' else 10.)
    initial = capture(n, np.zeros(n.size)); untouched = deepcopy(initial); calls = []
    failure = kind('injected warm progress failure')
    def progress(name, current, total):
        if name == stage:
            calls.append((current, total)); raise failure
    expected = AnalysisError if kind is ValueError else kind
    with pytest.raises(expected, match='injected warm progress failure') as caught:
        equilibrate(n, tolerance=1e-9, initial_state=initial, progress=progress)
    if kind is not ValueError: assert caught.value is failure
    assert len(calls) == 1 and calls[0][0] == 0 and initial == untouched
    assert not hasattr(n, '_seeded_corrector_diagnostics')
    assert_clean(n)


def test_progress_preserves_adapter_without_progress_keyword(monkeypatch):
    import openswing.equilibrium_state as equilibrium
    class Adapter:
        __slots__ = ('constraints', 'hinges', 'equilibrium_diagnostics')
        def __init__(self): self.constraints = []; self.hinges = []
        def residual(self, x, factor=1): return x-1
        def jacobian(self, x, factor=1): return np.eye(1)
    monkeypatch.setattr(equilibrium, 'restore', lambda *args: np.zeros(1))
    events = []; n = Adapter()
    state, steps = correct(n, {}, 1e-9, {}, progress=lambda *event: events.append(event))
    np.testing.assert_allclose(state, [1], atol=1e-9, rtol=0)
    assert steps == 1 and any(event[0] == 'equilibrium_iteration_tangent' for event in events)
    assert not any(event[0] == 'equilibrium_final_tangent' for event in events)
    assert not hasattr(n, 'nfev') and not hasattr(n, '_seeded_corrector_diagnostics')


def test_custom_final_tangent_keeps_original_signature(monkeypatch):
    import openswing.equilibrium_state as equilibrium
    n = trim_network(0.); initial = capture(n, np.zeros(n.size)); calls = []; events = []
    def final(values):
        calls.append(values.copy())
        return n.jacobian(values, 1.)
    state, steps = correct(n, initial, 1e-9, {}, final_tangent=final,
        progress=lambda *event: events.append(event))
    assert len(calls) == 1 and steps == 1
    np.testing.assert_array_equal(calls[0], state)
    assert not any(event[0] == 'equilibrium_final_tangent' for event in events)
    assert_clean(n)
