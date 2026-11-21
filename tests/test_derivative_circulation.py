"""Accuracy, ownership, conservative fallback and checked-probe regressions."""
from copy import copy
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

import openswing
import openswing.derivative_circulation as helper
from openswing.aero import AnalysisError, FlightCondition
from openswing.derivatives import linearize_equilibrium
from openswing.network import StaticNetwork
from openswing.structured_static import StructuredTangentUnavailable
from derivative_circulation_fixtures import make_network, zero_state, displaced_state, centered_gamma_columns, collect_audit


def assert_clean(probe, report):
    assert probe.iteration_fields is None
    assert probe.tangent_influences is None
    assert probe._tangent_loads is None
    assert probe.aero_key is None and probe.aero_cached is None
    assert report['owner_restored'] and report['tangent_owner_unchanged']
    assert report['tangent_load_owner_unchanged'] and report['aero_cache_invalidated']


def unavailable(*args, **kwargs):
    raise helper.CirculationDerivativeUnavailable('deliberate centered reference')


def api_call():
    network = make_network()
    x = zero_state(network)
    # This fixture establishes the derivative baseline directly; no equilibrium
    # solver is imported or called anywhere in these tests.
    np.testing.assert_array_equal(network.residual(x), np.zeros(network.size))
    owners = {name: getattr(network, name) for name in
              ['iteration_fields', 'tangent_influences', '_tangent_loads', 'aero_key', 'aero_cached']}
    before = network.nfev
    audit, collect = collect_audit()
    result = linearize_equilibrium(network, x, parameters=['control.1', 'p'], _audit=collect)
    assert network.nfev == before
    assert all(getattr(network, name) is value for name, value in owners.items())
    np.testing.assert_array_equal(x, zero_state(network))
    return network, result, audit


@pytest.fixture(scope='module')
def centered_reference():
    with patch.object(helper, 'circulation_columns', unavailable):
        return api_call()


@pytest.mark.parametrize('modes', [None, {1: 2}])
def test_fresh_capture_matches_refined_physical_columns_and_restores_parent(modes):
    condition = FlightCondition(alpha=7, beta=3, mach=.1, stall=False,
                                rates=[.02, -.03, .01], circulation_modes=modes or {})
    parent = make_network(condition=condition)
    x = displaced_state(parent)
    baseline = parent.residual(x).copy()
    # A prior, different circulation state has populated the parent's aero
    # cache. Fresh capture on a shallow trial copy must not consume that cache.
    trial = x.copy(); trial[parent.gamma_start] += .02
    parent.residual(trial)
    attributes = {name: getattr(parent, name) for name in
                  ['iteration_fields', 'tangent_influences', '_tangent_loads', 'aero_key', 'aero_cached']}
    before = parent.nfev
    probe = copy(parent); original_x = x.copy(); calls = []
    def checked(z):
        np.testing.assert_array_equal(z, original_x)
        assert probe.iteration_fields.phase == 'capture'
        assert probe.iteration_fields.capture_circulation
        assert probe.aero_key is None and probe.aero_cached is None
        calls.append(z.copy())
        return probe.residual(z)
    report = {}
    direct = helper.capture_circulation_columns(probe, x, checked, baseline,
        response='fixed_acceleration', feedback=None, step=1e-5, report=report)
    assert report['enabled'] and report['capture_evaluations'] == len(calls) == 1
    assert direct.shape == (probe.size, probe.ng)
    assert report['capture_phase'] == 'capture' and not report['lagged_geometry']
    assert report['factor'] == 1 and report['circulation_rate_factor'] == 0
    assert_clean(probe, report)
    assert parent.nfev == before
    assert all(getattr(parent, name) is value for name, value in attributes.items())
    np.testing.assert_array_equal(x, original_x)
    expected = centered_gamma_columns(probe, x, step=1e-6)
    assert np.max(abs(direct-expected)/(1+abs(expected))) < 2e-7


def test_only_gamma_columns_change_and_every_checked_probe_remains(centered_reference, monkeypatch):
    gamma_trials = []
    residual = StaticNetwork.residual
    def observed(self, z, *args, **kwargs):
        nonzero = np.flatnonzero(z)
        if len(nonzero) == 1 and self.gamma_start <= nonzero[0] < self.operating_start:
            gamma_trials.append((int(nonzero[0]), float(z[nonzero[0]])))
        return residual(self, z, *args, **kwargs)
    monkeypatch.setattr(StaticNetwork, 'residual', observed)
    net, result, audit = api_call()
    _, reference, original = centered_reference
    assert result['step'] == reference['step'] == 1e-5
    assert result['method'] == 'implicit residual derivatives with analytic circulation columns'
    assert reference['method'] == 'implicit centered residual derivatives'
    assert audit['circulation_derivative']['enabled']
    mask = np.ones(net.size, dtype=bool)
    mask[net.gamma_start:net.operating_start] = False
    np.testing.assert_array_equal(audit['jacobian'][:, mask], original['jacobian'][:, mask])
    np.testing.assert_array_equal(audit['input_partials'], original['input_partials'])
    np.testing.assert_array_equal(audit['centered_gamma_columns'],
                                  original['jacobian'][:, net.gamma_start:net.operating_start])
    np.testing.assert_array_equal(audit['analytic_gamma_columns'],
                                  audit['jacobian'][:, net.gamma_start:net.operating_start])
    for j in range(net.gamma_start, net.operating_start):
        assert (j, 1e-5) in gamma_trials and (j, -1e-5) in gamma_trials
    assert result['base_outputs'] == reference['base_outputs']
    assert max(result['linear_residuals']) <= 1e-8
    assert result['column_scaled_reciprocal_condition'] >= 1e-10
    assert audit['derivative_cache']['owner_restored']


@pytest.mark.parametrize('fault', ['wrong-shape', 'not-array', 'complex', 'object', 'bool',
                                   'nan', 'inf', 'direct-storage', 'field-storage', 'memory'])
def test_invalid_or_unavailable_block_leaves_complete_centered_jacobian(
        fault, centered_reference, monkeypatch):
    def broken(net, fields, factor, **kwargs):
        assert factor == 1 and kwargs == {'circulation_rate_factor': 0.}
        if fault == 'direct-storage':
            raise helper.CirculationDerivativeUnavailable('direct storage limit')
        if fault == 'field-storage':
            raise StructuredTangentUnavailable('capture storage limit')
        if fault == 'memory':
            raise MemoryError('bounded allocation unavailable')
        a = np.zeros((net.size, net.ng))
        if fault == 'wrong-shape': return a[:, :-1]
        if fault == 'not-array': return a.tolist()
        if fault in ('complex', 'object', 'bool'):
            return a.astype({'complex': complex, 'object': object, 'bool': bool}[fault])
        a[0, 0] = {'nan': np.nan, 'inf': np.inf}[fault]
        return a
    monkeypatch.setattr(helper, 'circulation_columns', broken)
    _, actual, audit = api_call()
    _, expected, original = centered_reference
    assert actual['method'] == expected['method'] == 'implicit centered residual derivatives'
    np.testing.assert_array_equal(audit['jacobian'], original['jacobian'])
    np.testing.assert_array_equal(audit['input_partials'], original['input_partials'])
    np.testing.assert_array_equal(audit['state_response'], original['state_response'])
    assert actual['matrices'] == expected['matrices']
    report = audit['circulation_derivative']
    assert report['eligible'] and not report['enabled'] and report['fallback_reasons']
    assert all(report[k] for k in ['owner_restored', 'tangent_owner_unchanged',
                                  'tangent_load_owner_unchanged', 'aero_cache_invalidated'])
    assert audit['derivative_cache']['owner_restored']
    assert 'analytic_gamma_columns' not in audit


@pytest.mark.parametrize('where', ['capture', 'analytic'])
def test_physical_failure_propagates_with_owners_restored(where, monkeypatch):
    net = make_network(); x = displaced_state(net); baseline = net.residual(x).copy()
    failure = AnalysisError('sentinel physical branch is unresolved')
    def fail(*args, **kwargs): raise failure
    checked = fail if where == 'capture' else lambda z: net.residual(z)
    if where == 'analytic': monkeypatch.setattr(helper, 'circulation_columns', fail)
    report = {}
    with pytest.raises(AnalysisError) as caught:
        helper.capture_circulation_columns(net, x, checked, baseline,
            response='fixed_acceleration', feedback=None, step=1e-5, report=report)
    assert caught.value is failure
    assert_clean(net, report)


def test_checked_gamma_branch_failure_is_not_bypassed_by_analytic_replacement(monkeypatch):
    net = make_network(); x = zero_state(net); audit, collect = collect_audit()
    residual = StaticNetwork.residual
    def changed_branch(self, z, *args, **kwargs):
        value = residual(self, z, *args, **kwargs)
        nonzero = np.flatnonzero(z)
        if len(nonzero) == 1 and nonzero[0] == self.gamma_start and z[nonzero[0]] > 0:
            # Simulate a newly reported physical branch after the full residual
            # probe. This exercises the API's existing checked() guard itself.
            self.aero_cached['engines'] = [{'power_clipped': True}]
        return value
    monkeypatch.setattr(StaticNetwork, 'residual', changed_branch)
    with pytest.raises(AnalysisError, match='power-clipping transition'):
        linearize_equilibrium(net, x, parameters=['control.1'], _audit=collect)
    assert audit['circulation_derivative']['enabled']
    assert audit['circulation_derivative']['owner_restored']
    assert audit['derivative_cache']['owner_restored']
    assert net.iteration_fields is net.tangent_influences is net._tangent_loads is None


def minimal_network():
    return SimpleNamespace(ng=1, size=3, gamma_start=2, operating_start=3, gamma_scale=1.,
        model=SimpleNamespace(records={}), constraints=[], iteration_fields=None,
        tangent_influences=None, _tangent_loads=None, aero_key=object(), aero_cached=object(), nfev=0)


@pytest.mark.parametrize('exclusion', ['free-flight', 'feedback', 'no-gamma', 'engine', 'type3',
                                      'iteration_fields', 'tangent_influences', '_tangent_loads'])
def test_ineligible_context_does_not_capture_or_touch_owners(exclusion):
    net = minimal_network(); response='fixed_acceleration'; feedback=None
    if exclusion == 'free-flight': response='free_flight'
    elif exclusion == 'feedback': feedback=object()
    elif exclusion == 'no-gamma': net.ng=0
    elif exclusion == 'engine': net.model.records['engine']=[object()]
    elif exclusion == 'type3': net.constraints=[{'type': 3}]
    else: setattr(net, exclusion, object())
    before=vars(net).copy(); report={}
    def forbidden(*args): pytest.fail('Ineligible context must not evaluate a residual')
    assert helper.capture_circulation_columns(net, np.zeros(3), forbidden, np.zeros(3),
        response=response, feedback=feedback, step=1e-5, report=report) is None
    assert vars(net) == before
    assert not report['eligible'] and not report['enabled'] and report['fallback_reasons']


@pytest.mark.parametrize('case', ['clear', 'floor', 'stencil-crosses-floor', 'baseline-mismatch'])
def test_fresh_capture_and_actual_gamma_stencil_clearance_are_conservative(case, monkeypatch):
    net=minimal_network(); x=np.zeros(3); baseline=np.zeros(3); report={}
    def checked(z):
        net.nfev += 1
        velocity=np.array([[1., 0., 0.]]) if case!='floor' else np.array([[0., 1., 0.]])
        gradient=1e5 if case=='stencil-crosses-floor' else 5e4
        net.iteration_fields.circulation_aero=dict(velocity=velocity,p={'s':np.array([[0.,1.,0.]])},
            condition=SimpleNamespace(speed=1.),basis=SimpleNamespace(sample=np.ones((1,1))))
        net.iteration_fields.values['vortex','hv']=SimpleNamespace(
            apply_columns=lambda _:np.array([[[gradient],[0.],[0.]]]))
        return np.ones(3) if case=='baseline-mismatch' else baseline.copy()
    calls=[]
    def direct(*args, **kwargs): calls.append(True); return np.zeros((3,1))
    monkeypatch.setattr(helper, 'circulation_columns', direct)
    result=helper.capture_circulation_columns(net,x,checked,baseline,
        response='fixed_acceleration',feedback=None,step=1e-5,report=report)
    assert (result is not None) == (case=='clear')
    assert report['enabled'] == (case=='clear')
    if case=='stencil-crosses-floor':
        assert calls and any('Gamma stencil' in reason for reason in report['fallback_reasons'])
    elif case in ('floor','baseline-mismatch'):
        assert not calls
    else:
        assert report['minimum_stencil_speed_floor_clearance'] > .49
    assert_clean(net, report)


def test_regressions_import_the_worktree_package():
    from pathlib import Path
    package=Path(__file__).resolve().parents[1]/'openswing'
    assert Path(openswing.__file__).resolve().parent == package
