"""Paired numerical policies at the browser/native JSON boundary."""
from copy import deepcopy
import json

import numpy as np
import pytest

from openswing import bridge
from openswing.asw import parse_asw
from openswing.geometry import geometry_summary, model_meshes
from openswing.numerical_policy import default_policy


SOURCE_POLICY = dict(beam_interpolation='drela-segspl-v1',
                     structural_operator='drela-steady-zero-offset-v1')
SOURCE = '''Name
Bridge numerical policy
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
10 1.225 340
End
Reference
2 1 2
End
Ground
1 1 0
End
Beam 1
Straight test beam
t x y z chord
1 0 0 0 .2
3 0 2 0 .2
t EA EIcc GJ EInn
1 1000 0 0 0
3 1000 0 0 0
End
'''
CURVE = SOURCE.replace('t EA EIcc GJ EInn\n1 1000 0 0 0\n3 1000 0 0 0',
                       't EA\n1 1000\n2 2000\n3 1000')
PANELS = {'default': 4, 'beams': {'1': {'nodes': [1., 1.5, 2., 2.5, 3.]}}}


def request(action='inspect', source=SOURCE, **options):
    return dict(action=action, source=source, panels=PANELS, **options)


@pytest.mark.parametrize('options', [
    {}, {'action': 'canonical_asw'},
    {'action': 'distribution', 'beam': 1, 'name': 'EA'},
    {'action': 'edit_distribution', 'beam': 1, 'name': 'EA', 'edit': {'multiplier': 2}},
])
def test_absent_and_explicit_default_preserve_complete_json_output(options):
    value = request(source=CURVE, **options)
    original = deepcopy(value)
    absent = bridge.run_json(json.dumps(value))
    explicit = bridge.run_json(json.dumps(dict(value, numerics=default_policy())))
    assert absent == explicit
    assert 'numerics' not in json.loads(absent)
    assert value == original


def test_absent_default_structural_route_matches_original_kernel_presentation():
    from openswing.network import solve_static
    value = request('solve', mode='structural', gravity=[0, 0, 0],
                    loads=[dict(beam=1, t=3, force=[0, 10, 0])])
    expected = solve_static(parse_asw(SOURCE), None, PANELS, gravity=value['gravity'],
                            loads=value['loads'], allow_signed_point_weights=True,
                            allow_signed_distributed_weights=True)
    expected.update(analysis='structural_static', structural_only=True, strips=[])
    actual = bridge.dispatch(value)
    assert actual == expected
    assert bridge.dispatch(dict(value, numerics=default_policy())) == actual
    assert 'numerics' not in actual


def test_source_inspection_uses_selected_geometry_and_labels_mass_scope():
    source = CURVE.replace('1 0 0 0 .2\n3 0 2 0 .2',
                           '1 0 0 0 .2\n2 .1 1 0 .2\n3 0 2 0 .2')
    value = request(source=source, numerics=SOURCE_POLICY)
    original = deepcopy(value)
    actual = bridge.dispatch(value)
    selected = parse_asw(source, beam_interpolation='drela-segspl-v1')
    expected = geometry_summary(selected, meshes=model_meshes(selected, PANELS))
    assert actual['beams'] == expected
    assert actual['beams'] != bridge.dispatch(request(source=source))['beams']
    assert actual['numerics'] == SOURCE_POLICY
    assert actual['mass_properties_scope']['selected_operator_mass'] is False
    assert actual['mass_properties_scope']['dynamic_inertia_validated'] is False
    assert 'midpoint' in actual['mass_properties_scope']['description']
    assert 'endpoint' in actual['mass_properties_scope']['selected_weight_rule']
    assert value == original


def test_source_distribution_edit_and_canonical_roundtrip_keep_policy():
    value = request('distribution', source=CURVE, beam=1, name='EA', numerics=SOURCE_POLICY)
    alternative = bridge.dispatch(value)
    natural = bridge.dispatch({k: v for k, v in value.items() if k != 'numerics'})
    # The three-point zero-third spline is the unique quadratic, independently
    # specified by EA=2000-1000*(t-2)^2. Natural interpolation is different.
    assert alternative['segments'][0]['t'][20] == 1.5
    assert alternative['segments'][0]['values'][20] == pytest.approx(1750.)
    assert natural['segments'][0]['values'][20] == pytest.approx(1687.5)
    edited = bridge.dispatch(request('edit_distribution', source=CURVE, beam=1,
        name='EA', edit=dict(multiplier=2), numerics=SOURCE_POLICY))
    assert edited['distribution']['segments'][0]['values'][20] == pytest.approx(3500.)
    canonical = bridge.dispatch(request('canonical_asw', source=edited['source'], numerics=edited['numerics']))
    again = bridge.dispatch(request('distribution', source=canonical['source'],
        beam=1, name='EA', numerics=canonical['numerics']))
    assert again['segments'] == edited['distribution']['segments']
    assert edited['numerics'] == canonical['numerics'] == again['numerics'] == SOURCE_POLICY


@pytest.fixture(scope='module')
def source_result():
    # Negative point and distributed weights exercise both explicitly enabled
    # static-load flags; they are not physical dynamic masses.
    source = SOURCE.replace(
        't EA EIcc GJ EInn', 't mg\n1 -2\n3 -2\nt EA EIcc GJ EInn')
    source += 'Weight\n1 3 0 2 0 -3\nEnd\n'
    value = request('solve', source=source, mode='structural', numerics=SOURCE_POLICY,
        condition=None, operating_constraints=[], derivatives=None, controller=None,
        strut_mode='bilateral', loads=[dict(beam=1, t=3, force=[0, 10, 0])])
    return value, bridge.dispatch(value)


def test_source_structural_solve_has_analytic_extension_and_standard_presentation(source_result):
    value, result = source_result
    assert result['analysis'] == 'structural_static' and result['structural_only']
    assert result['strips'] == [] and result['converged']
    assert result['structural_elements'] == 4 and result['structural_nodes'] == 5
    assert result['numerics'] == SOURCE_POLICY
    assert result['nodes'][-1]['position'][1] == pytest.approx(2.02, abs=2e-10)
    np.testing.assert_allclose(result['applied_force'], [0, 10, 7], atol=2e-9)
    np.testing.assert_allclose(result['support_force'], [0, -10, -7], atol=2e-9)
    assert result['residual'] < 1e-8
    assert result['equilibrium_state']['identity']['beam_interpolation'] == SOURCE_POLICY['beam_interpolation']
    assert result['equilibrium_state']['identity']['structural_operator'] == SOURCE_POLICY['structural_operator']
    assert 'launch' not in result['equilibrium_state']
    json.dumps(result, allow_nan=False)


def test_source_route_forwards_only_honored_options_without_mutating_request(monkeypatch):
    import openswing.source_discrete as kernel
    seen = {}
    def solve(model, panels, **kwargs):
        seen.update(model=model, panels=panels, options=kwargs)
        return {'converged': True}
    monkeypatch.setattr(kernel, 'solve_source_discrete', solve)
    value = request('solve', mode='structural', numerics=SOURCE_POLICY,
        tolerance=3e-9, continuation_steps=2, gravity=[0, 0, 0], loads=[])
    original = deepcopy(value)
    progress = lambda *a: None
    result = bridge.dispatch(value, progress)
    assert seen['model'].beam_interpolation == SOURCE_POLICY['beam_interpolation']
    assert seen['options'] == dict(tolerance=3e-9, continuation_steps=2, gravity=[0, 0, 0],
        loads=[], initial_state=None, progress=progress,
        structural_operator=SOURCE_POLICY['structural_operator'],
        allow_signed_point_weights=True, allow_signed_distributed_weights=True)
    assert value == original and result['numerics'] == SOURCE_POLICY


@pytest.mark.parametrize('policy', [None, {}, [], True,
    {'beam_interpolation': 'natural-v1'}, {'structural_operator': 'midpoint-v1'},
    dict(SOURCE_POLICY, extra=True), dict(SOURCE_POLICY, beam_interpolation='unknown'),
    dict(SOURCE_POLICY, structural_operator='unknown'), dict(SOURCE_POLICY, structural_operator=[]),
    dict(SOURCE_POLICY, beam_interpolation='natural-v1'),
    dict(SOURCE_POLICY, structural_operator='midpoint-v1'),
])
def test_invalid_or_conflicting_policy_rejects_before_parsing(monkeypatch, policy):
    monkeypatch.setattr(bridge, 'parse_asw', lambda *a, **k: pytest.fail('Policy was not checked first'))
    with pytest.raises(ValueError, match='numerics|policy'):
        bridge.dispatch(request(source='invalid ASW', numerics=policy))


@pytest.mark.parametrize('name', ['beam_interpolation', 'structural_operator'])
def test_top_level_policy_does_not_silently_override_paired_contract(name):
    with pytest.raises(ValueError, match='request.numerics'):
        bridge.dispatch(request(**{name: SOURCE_POLICY[name]}))


@pytest.mark.parametrize('action', ['time', 'modes', 'frequency', 'rom', 'stability',
    'resume_time', 'launch_time', 'flow_survey', 'extend_frequency',
    'steady_turn_constraints', 'reference_airflow_constraints',
    'gust_import', 'gust_export', 'gust_sample', 'gust_validate', 'rom_import', 'discard_frequency'])
def test_source_policy_rejects_unsupported_actions_before_parsing(monkeypatch, action):
    monkeypatch.setattr(bridge, 'parse_asw', lambda *a, **k: pytest.fail('Unsupported action reached parsing'))
    with pytest.raises(ValueError, match='static solves only'):
        bridge.dispatch(request(action, source='invalid ASW', numerics=SOURCE_POLICY))


@pytest.mark.parametrize('extra', [
    {'mode': 'mounted'}, {'mode': 'free'}, {'mode': 'rigid'},
    {'condition': {'speed': 1}}, {'controller': {}}, {'derivatives': {}},
    {'operating_constraints': [dict(variable='alpha', quantity='CL', target=0)]},
    {'strut_mode': 'wire'}, {'strut_mode': 'unknown'}, {'motion': None},
    {'time': {}}, {'frequency': {}}, {'circulation_method': 'auto'},
    {'quiescent_density': 1.2}, {'allow_signed_point_weights': False},
])
def test_source_policy_rejects_options_it_cannot_honor(monkeypatch, extra):
    monkeypatch.setattr(bridge, 'parse_asw', lambda *a, **k: pytest.fail('Unsupported option reached parsing'))
    value = request('solve', source='invalid ASW', mode='structural', numerics=SOURCE_POLICY)
    value.update(extra)
    with pytest.raises(ValueError, match='source-discrete|Source-discrete'):
        bridge.dispatch(value)


@pytest.mark.parametrize('loads', [None, {}, [None], [{'force': [0, 1, 0]}],
    [dict(beam=1, t=3, force=[0, 1, 0], frame='local')],
    [dict(beam=1, t=3, moment=[0, 1, 0], follower=True)]])
def test_source_loads_cannot_silently_ignore_nested_options(monkeypatch, loads):
    monkeypatch.setattr(bridge, 'parse_asw', lambda *a, **k: pytest.fail('Unsupported load reached parsing'))
    with pytest.raises(ValueError, match='Source-discrete loads'):
        bridge.dispatch(request('solve', mode='structural', numerics=SOURCE_POLICY, loads=loads))


@pytest.mark.parametrize('mode', ['structural', 'mounted', 'rigid'])
def test_natural_request_rejects_saved_source_state_even_on_route_which_would_ignore_it(source_result, monkeypatch, mode):
    value, result = source_result
    monkeypatch.setattr(bridge, 'parse_asw', lambda *a, **k: pytest.fail('State mismatch reached parsing'))
    with pytest.raises(ValueError, match='Saved state numerical policy'):
        bridge.dispatch(request('solve', mode=mode, initial_state=result['equilibrium_state']))


@pytest.mark.parametrize('wrapper', ['direct', 'checkpoint', 'frequency'])
def test_nested_saved_source_identity_rejects_default_policy(wrapper):
    packet = {'identity': dict(SOURCE_POLICY)}
    if wrapper == 'direct': options = dict(equilibrium_state=packet)
    elif wrapper == 'checkpoint': options = dict(checkpoint={'context': packet})
    else: options = dict(frequency={'initial_state': packet})
    with pytest.raises(ValueError, match='Saved state numerical policy'):
        bridge.dispatch(request(**options))


def test_source_request_rejects_untagged_default_state_before_parse(monkeypatch):
    monkeypatch.setattr(bridge, 'parse_asw', lambda *a, **k: pytest.fail('State mismatch reached parsing'))
    with pytest.raises(ValueError, match='Saved state numerical policy'):
        bridge.dispatch(request('solve', mode='structural', numerics=SOURCE_POLICY,
                                initial_state={'identity': {}}))
