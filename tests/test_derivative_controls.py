"""Control residual partials and checked-probe integration; no root solves."""
from copy import copy
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.network import StaticNetwork
from openswing.derivatives import linearize_equilibrium
import openswing.derivative_controls as helper
from derivative_circulation_fixtures import FIXTURE, make_network, zero_state, displaced_state, collect_audit


def assert_clean(network, report):
    assert network.iteration_fields is None
    assert network.tangent_influences is None
    assert network._tangent_loads is None
    assert network.aero_key is network.aero_cached is None
    assert all(report[k] for k in ('owner_restored', 'tangent_owner_unchanged',
                                  'tangent_load_owner_unchanged', 'aero_cache_invalidated'))


def control_network(**condition_options):
    source = FIXTURE.read_text().replace(
        't dCLdF1 dCMdF1\n0 .05 -.012\n6 .05 -.012',
        't Cdp dCLdF1 dCMdF1 dCDdF1 dCLdF2 dCMdF2 dCDdF2\n'
        '0 .02 .05 -.012 .003 -.03 .007 -.001\n'
        '6 .03 .07 -.018 .004 -.02 .009 -.002')
    model = parse_asw(source)
    condition = FlightCondition(alpha=7, beta=3, mach=.1,
        rates=[.02, -.03, .01], controls={1: 2., 2: .5}, **condition_options)
    return StaticNetwork(model, 4, condition, None, [])


@pytest.mark.parametrize('options', [
    {'stall': False}, {'stall': True},
    {'stall': True, 'circulation_modes': {1: 2}},
    {'stall': True, 'freeze_influences': True},
])
def test_complete_control_block_matches_refined_full_network_partials(options):
    parent = control_network(**options)
    x = displaced_state(parent)
    baseline = parent.residual(x).copy()
    parent_before = parent.nfev
    owners = {name: getattr(parent, name) for name in (
        'iteration_fields', 'tangent_influences', '_tangent_loads', 'aero_key', 'aero_cached')}
    probe = copy(parent); report = {}; calls = []
    def checked(z):
        np.testing.assert_array_equal(z, x)
        assert probe.iteration_fields.capture_circulation
        assert probe.aero_key is probe.aero_cached is None
        calls.append(True)
        return probe.residual(z)
    direct = helper.capture_control_columns(probe, x, checked, baseline,
        controls=[2, 1], response='fixed_acceleration', feedback=None, step=1e-5, report=report)
    assert direct is not None and report['enabled']
    assert report['controls'] == [2, 1] and report['units'] == 'literal file control setting'
    assert len(calls) == report['capture_evaluations'] == 1
    assert_clean(probe, report)
    assert parent.nfev == parent_before
    assert all(getattr(parent, name) is value for name, value in owners.items())
    for width in (1e-4, 3e-5):
        expected = []
        for key in (2, 1):
            values = []
            for factor in (1., -1., 2., -2.):
                controls = dict(parent.condition.controls)
                controls[key] += factor*width
                condition = replace(parent.condition, controls=controls)
                values.append(probe.residual(x, condition_override=condition))
            expected.append((8*(values[0]-values[1])-(values[2]-values[3]))/(12*width))
        expected = np.stack(expected, axis=1)
        assert np.max(abs(direct-expected)/(1+abs(expected))) < 2e-8
    # All dCLdF/dCMdF/dCDdF effects participate, including transferred couples.
    start = 6*parent.ne
    assert np.any(direct[start:start+3*parent.nn])
    assert np.any(direct[start+3*parent.nn:start+6*parent.nn])
    assert np.any(direct[parent.gamma_start:parent.operating_start])


def api_call():
    network = make_network(); x = zero_state(network)
    np.testing.assert_array_equal(network.residual(x), np.zeros(network.size))
    owners = {name: getattr(network, name) for name in (
        'iteration_fields', 'tangent_influences', '_tangent_loads', 'aero_key', 'aero_cached')}
    before = network.nfev
    audit, collect = collect_audit()
    result = linearize_equilibrium(network, x, parameters=['p', 'control.1'], _audit=collect)
    assert network.nfev == before
    assert all(getattr(network, name) is value for name, value in owners.items())
    np.testing.assert_array_equal(x, zero_state(network))
    return result, audit


def test_only_control_inputs_replaced_and_outputs_remain_centered(monkeypatch):
    actual, audit = api_call()
    def unavailable(*args, **kwargs):
        raise helper.CirculationDerivativeUnavailable('centered control reference')
    monkeypatch.setattr(helper, 'control_columns', unavailable)
    reference, centered = api_call()
    assert actual['method'] == reference['method'] == 'implicit residual derivatives with analytic circulation columns'
    np.testing.assert_array_equal(audit['jacobian'], centered['jacobian'])
    np.testing.assert_array_equal(audit['input_partials'][:, 0], centered['input_partials'][:, 0])
    np.testing.assert_array_equal(audit['centered_control_columns'], centered['input_partials'][:, [1]])
    np.testing.assert_array_equal(audit['analytic_control_columns'], audit['input_partials'][:, [1]])
    np.testing.assert_allclose(audit['analytic_control_columns'], audit['centered_control_columns'], rtol=2e-8, atol=2e-10)
    assert actual['input_derivative_methods'] == {
        'p': 'checked centered partial', 'control.1': 'analytic fixed-geometry control partial'}
    assert reference['input_derivative_methods']['control.1'] == 'checked centered partial'
    assert actual['output_derivative_method'].startswith('centered directional')
    assert actual['control_derivative']['checked_centered_control_probes_retained']
    assert not reference['control_derivative']['enabled']
    np.testing.assert_allclose(actual['matrices']['coefficients'], reference['matrices']['coefficients'], rtol=2e-7, atol=2e-9)


def test_checked_control_branch_failure_cannot_be_bypassed(monkeypatch):
    network = make_network(); x = zero_state(network); audit, collect = collect_audit()
    residual = StaticNetwork.residual
    def changed_branch(self, z, *args, **kwargs):
        value = residual(self, z, *args, **kwargs)
        if self.operating.condition.controls.get(1, 0.) > 0:
            self.aero_cached['engines'] = [{'power_clipped': True}]
        return value
    monkeypatch.setattr(StaticNetwork, 'residual', changed_branch)
    with pytest.raises(AnalysisError, match='power-clipping transition'):
        linearize_equilibrium(network, x, parameters=['control.1'], _audit=collect)
    assert audit['control_derivative']['enabled']
    assert audit['control_derivative']['owner_restored']
    assert audit['derivative_cache']['owner_restored']
    assert network.iteration_fields is network.tangent_influences is network._tangent_loads is None


@pytest.mark.parametrize('fault', ['shape', 'list', 'complex', 'bool', 'nan', 'storage', 'memory'])
def test_unavailable_or_invalid_block_preserves_complete_centered_inputs(fault, monkeypatch):
    network = make_network(); x = displaced_state(network); baseline = network.residual(x).copy()
    def bad(net, fields, controls):
        if fault == 'storage': raise helper.StructuredTangentUnavailable('bounded storage')
        if fault == 'memory': raise MemoryError('bounded allocation')
        result = np.zeros((net.size, len(controls)))
        if fault == 'shape': return result[:-1]
        if fault == 'list': return result.tolist()
        if fault == 'complex': return result.astype(complex)
        if fault == 'bool': return result.astype(bool)
        result[0, 0] = np.nan
        return result
    monkeypatch.setattr(helper, 'control_columns', bad)
    report = {}
    assert helper.capture_control_columns(network, x, network.residual, baseline,
        controls=[1], response='fixed_acceleration', feedback=None, step=1e-5, report=report) is None
    assert report['eligible'] and not report['enabled'] and report['fallback_reasons']
    assert_clean(network, report)


@pytest.mark.parametrize('where', ['capture', 'analytic'])
def test_physical_errors_propagate_after_restoring_owners(where, monkeypatch):
    network = make_network(); x = displaced_state(network); baseline = network.residual(x).copy()
    failure = AnalysisError('unresolved physical branch')
    def fail(*args, **kwargs): raise failure
    if where == 'analytic': monkeypatch.setattr(helper, 'control_columns', fail)
    report = {}
    with pytest.raises(AnalysisError) as caught:
        helper.capture_control_columns(network, x, fail if where == 'capture' else network.residual,
            baseline, controls=[1], response='fixed_acceleration', feedback=None, step=1e-5, report=report)
    assert caught.value is failure
    assert_clean(network, report)


@pytest.mark.parametrize('fault', ['baseline', 'capture'])
def test_missing_or_stale_capture_declines_before_analytic_work(fault, monkeypatch):
    network = make_network(); x = displaced_state(network); baseline = network.residual(x).copy()
    def checked(z):
        value = network.residual(z)
        if fault == 'capture': network.iteration_fields.circulation_mechanics = None
        return value+1 if fault == 'baseline' else value
    def forbidden(*args, **kwargs): pytest.fail('Invalid capture must not build derivatives')
    monkeypatch.setattr(helper, 'control_columns', forbidden)
    report = {}
    assert helper.capture_control_columns(network, x, checked, baseline,
        controls=[1], response='fixed_acceleration', feedback=None, step=1e-5, report=report) is None
    assert_clean(network, report)


@pytest.mark.parametrize('exclusion', ['free-flight', 'feedback', 'no-gamma', 'engine', 'type3',
    'iteration_fields', 'tangent_influences', '_tangent_loads', 'empty', 'duplicate', 'unknown', 'bool'])
def test_ineligible_context_does_not_capture_or_mutate(exclusion):
    network = SimpleNamespace(ng=1, size=3, model=SimpleNamespace(controls=[1], records={}),
        constraints=[], iteration_fields=None, tangent_influences=None, _tangent_loads=None,
        aero_key=object(), aero_cached=object(), nfev=0)
    response = 'fixed_acceleration'; feedback = None; controls = [1]
    if exclusion == 'free-flight': response = 'free_flight'
    elif exclusion == 'feedback': feedback = object()
    elif exclusion == 'no-gamma': network.ng = 0
    elif exclusion == 'engine': network.model.records['engine'] = [object()]
    elif exclusion == 'type3': network.constraints = [{'type': 3}]
    elif exclusion == 'empty': controls = []
    elif exclusion == 'duplicate': controls = [1, 1]
    elif exclusion == 'unknown': controls = [2]
    elif exclusion == 'bool': controls = [True]
    else: setattr(network, exclusion, object())
    before = vars(network).copy(); report = {}
    def forbidden(*args): pytest.fail('Ineligible contexts must not evaluate a residual')
    assert helper.capture_control_columns(network, np.zeros(3), forbidden, np.zeros(3),
        controls=controls, response=response, feedback=feedback, step=1e-5, report=report) is None
    assert vars(network) == before
    assert not report['eligible'] and not report['enabled'] and report['fallback_reasons']
