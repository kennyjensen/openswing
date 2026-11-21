"""Mounted acceleration preserves loads, detailed output and recovery on failure."""
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.aero import FlightCondition, AnalysisError
from openswing.network import StaticNetwork, equilibrate
import openswing.network as network_module


def network(example='flexible', settings=None, **options):
    model = parse_asw(Path(f'examples/{example}.asw').read_text())
    condition = FlightCondition(alpha=5, mach=0, **(settings or {}))
    return StaticNetwork(model, 4, condition, None, [], **options)


@pytest.mark.parametrize('example,settings', [
    ('rectangular', {}), ('flexible', {}), ('powered', {}), ('wing-body', {}), ('articulated', {}),
    ('wing-body', dict(freeze_influences=True)),
    ('flexible', dict(ground_effect=1, position_earth=[0, 0, 5])),
    ('rectangular', dict(circulation_modes={1: 3})),
    ('wing-body', dict(rates=[.01, -.02, .03], acceleration=[.2, -.1, .3])),
])
def test_trial_loads_and_tangent_are_exactly_the_full_evaluation(example, settings, monkeypatch):
    net = network(example, settings)
    x = np.random.default_rng(573).normal(0, .001, net.size)
    x[net.gamma_start:net.operating_start] += .04
    trial = net.residual(x, .7)
    assert 'CL' not in net.aero_cached
    actual = net.jacobian(x, .7)
    detailed, data = net.residual(x, .7, detail=True)
    np.testing.assert_array_equal(trial, detailed)
    assert 'trefftz' in data['aero'] and 'sensor_airflow' in data['aero']
    evaluate = network_module.evaluate_aerodynamics

    def full(*args, **kwargs):
        kwargs['_loads_only'] = False
        return evaluate(*args, **kwargs)

    monkeypatch.setattr(network_module, 'evaluate_aerodynamics', full)
    net.aero_key = None
    np.testing.assert_array_equal(actual, net.jacobian(x, .7))
    # Alternating trial/detailed calls must not let a compact cache entry leak
    # into exported diagnostics at the identical physical state.
    _, repeated = net.residual(x, .7, detail=True)
    assert repeated['aero'] == data['aero']


@pytest.mark.parametrize('scope', ['dynamic', 'trim'])
def test_dynamic_and_operating_residuals_preserve_physics_and_detailed_aerodynamics(scope):
    options = dict(operating_constraints=[dict(variable='alpha', quantity='CL', target=.4)]) if scope == 'trim' else {}
    net = network('rectangular', **options)
    rng = np.random.default_rng(531)
    options = dict(elastic_motion=tuple(rng.normal(0, .1, (net.nn, 3)) for _ in range(4))) if scope == 'dynamic' else {}
    x = rng.normal(0, .001, net.size)
    x[net.gamma_start:net.operating_start] += .04
    trial = net.residual(x, .7, **options)
    # Trim consumes CL during evaluation. Dynamic trial residuals can omit
    # output recovery, but must retain every equation and restore full output
    # when requested at the identical physical state.
    if scope == 'trim':
        assert 'CL' in net.aero_cached and 'trefftz' in net.aero_cached
    detailed, data = net.residual(x, .7, detail=True, **options)
    np.testing.assert_array_equal(trial, detailed)
    assert 'CL' in data['aero'] and 'trefftz' in data['aero']
    assert 'sensor_airflow' in data['aero']


@pytest.mark.parametrize('failure', ['unconverged', 'domain_error'])
def test_failed_warm_stage_retries_fresh_and_preserves_equilibrium(failure, monkeypatch):
    # These checks target the retained full-Jacobian fallback solver.
    from openswing.network import _equilibrate_full as equilibrate
    reference_net = network('rectangular')
    reference, _ = equilibrate(reference_net)
    net = network('rectangular')
    root = network_module.root
    calls, tangents = [], []
    jacobian = net.jacobian

    def record_tangent(x, factor, **options):
        tangents.append(factor)
        return jacobian(x, factor, **options)

    def fail_once(fun, x, **options):
        calls.append(options['options']['maxfev'])
        if len(calls) == 2:
            options['jac'](x)
            if failure == 'domain_error':
                raise AnalysisError('simulated rejected trial geometry')
            return SimpleNamespace(x=x.copy())
        return root(fun, x, **options)

    monkeypatch.setattr(net, 'jacobian', record_tangent)
    monkeypatch.setattr(network_module, 'root', fail_once)
    actual, steps = equilibrate(net)
    assert steps == 4
    assert np.max(np.abs(net.residual(actual))) <= 1e-8
    np.testing.assert_allclose(actual, reference, atol=1e-8, rtol=1e-8)
    assert calls[1] == 50 and calls[2] == 6*net.size+200
    assert .5 in tangents  # Same target retried freshly, before halving the load.
    assert tangents[0] == 0 and tangents[-1] == 1
    _, data = net.residual(actual, detail=True)
    np.testing.assert_allclose(data['force'].sum(axis=0) + sum(
        (np.asarray(r['force']) for r in data['reactions'] if r['other_node'] is None), start=np.zeros(3)),
        0, atol=1e-7)


def test_finite_stiffness_retains_fresh_load_stage_tangents(monkeypatch):
    # These checks target the retained full-Jacobian fallback solver.
    from openswing.network import _equilibrate_full as equilibrate
    net = network('flexible')
    factors = []
    jacobian = net.jacobian

    def record(x, factor, **options):
        factors.append(factor)
        return jacobian(x, factor, **options)

    monkeypatch.setattr(net, 'jacobian', record)
    state, steps = equilibrate(net)
    assert steps == 4
    assert all(f in factors for f in [0, .25, .5, .75, 1])
    assert np.max(np.abs(net.residual(state))) <= 1e-8
