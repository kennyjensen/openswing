"""A resumable load path retains its original acceleration/net-load targets."""
from copy import deepcopy
import json

import numpy as np
import pytest

from openswing.aero import AnalysisError
from openswing.source_airflow import SourceAirflowNetwork
from openswing.operating import free_flight_constraints
from openswing.structured_static import equilibrate
from openswing.steady_continuation import ContinuationPending, context, digest, restore
from test_source_coupled import model, condition


def network(*, modes=0, frozen=True, all_axes=False):
    constraints = (free_flight_constraints() if all_axes else
                   [dict(variable='angular_acceleration.x', quantity='moment.x', target=0.)])
    return SourceAirflowNetwork(model(mass=all_axes), 4,
        condition(freeze_influences=frozen, circulation_modes={1: modes}),
        [1., -2., -10.], (), operating_constraints=constraints, steady_trim=True)


def first(net):
    with pytest.raises(ContinuationPending) as caught:
        equilibrate(net, max_load_steps=2)
    return json.loads(json.dumps(caught.value.checkpoint, allow_nan=False))


@pytest.mark.parametrize('modes,frozen,all_axes', [
    (0, True, False), (2, True, False), (2, False, False), (2, True, True),
])
def test_constrained_split_path_matches_uninterrupted_solution(modes, frozen, all_axes):
    options = dict(modes=modes, frozen=frozen, all_axes=all_axes)
    full = network(**options)
    expected, expected_steps = equilibrate(full)
    split = network(**options)
    packet = first(split)
    saved = deepcopy(packet)
    assert packet['load_fraction'] == .5 and packet['accepted_load_steps'] == 2
    assert max(abs(v) for v in split.operating.initial_values) > 1e-6
    assert packet['operating_initial_values'] == split.operating.initial_values == full.operating.initial_values
    fresh = network(**options)
    actual, steps = equilibrate(fresh, checkpoint=packet, max_load_steps=2)
    assert packet == saved and steps == expected_steps == 4
    np.testing.assert_array_equal(actual, expected)
    assert fresh.operating.initial_values == full.operating.initial_values
    assert np.max(abs(fresh.residual(actual))) <= 1e-12


@pytest.fixture(scope='module')
def packet():
    return first(network(modes=2))


@pytest.mark.parametrize('fault', ['missing', 'none', 'scalar', 'short', 'long', 'boolean', 'nonfinite'])
def test_invalid_operating_origins_are_rejected_before_residual(packet, fault, monkeypatch):
    p = deepcopy(packet)
    if fault == 'missing': p.pop('operating_initial_values')
    elif fault == 'none': p['operating_initial_values'] = None
    elif fault == 'scalar': p['operating_initial_values'] = 1.
    elif fault == 'short': p['operating_initial_values'] = []
    elif fault == 'long': p['operating_initial_values'] *= 2
    elif fault == 'boolean': p['operating_initial_values'] = [True]
    else: p['operating_initial_values'] = [float('nan')]
    net = network(modes=2)
    def forbidden(*args, **kwargs):
        pytest.fail('Invalid operating origins reached the physical residual')
    monkeypatch.setattr(net, 'residual', forbidden)
    if fault != 'nonfinite':
        p['sha256'] = digest({k:v for k,v in p.items() if k != 'sha256'})
    with pytest.raises(AnalysisError):
        restore(net, p, context(net, 1e-8, 4, True, True))
    assert net.operating.initial_values is None


def test_changed_origin_fails_physics_and_restores_callers_origin(packet):
    p = deepcopy(packet)
    p['operating_initial_values'][0] += 1.
    p['sha256'] = digest({k:v for k,v in p.items() if k != 'sha256'})
    net = network(modes=2)
    net.operating.initial_values = [123.]
    with pytest.raises(AnalysisError, match='rebuilt physical residual'):
        restore(net, p, context(net, 1e-8, 4, True, True))
    assert net.operating.initial_values == [123.]


def test_successful_restore_installs_saved_origin_before_residual(packet):
    net = network(modes=2)
    net.operating.initial_values = [123.]
    actual = restore(net, packet, context(net, 1e-8, 4, True, True))
    assert net.operating.initial_values == packet['operating_initial_values']
    np.testing.assert_array_equal(actual[0], packet['coordinates'])
    assert np.max(abs(net.residual(actual[0], packet['load_fraction']))) <= 1e-12


def test_legacy_unconstrained_packet_needs_no_operating_origin():
    net = network(modes=2)
    def mounted():
        return SourceAirflowNetwork(net.model, 4, net.condition, net.gravity, (), steady_trim=True)
    saved = first(mounted())
    assert saved.pop('operating_initial_values') == []
    saved['sha256'] = digest({k:v for k,v in saved.items() if k != 'sha256'})
    fresh = mounted()
    state, factor, *_ = restore(fresh, saved, context(fresh, 1e-8, 4, True, True))
    assert fresh.operating.initial_values == []
    assert np.max(abs(fresh.residual(state, factor))) <= 1e-12
