"""General-section policy boundary and structural-only checks."""
from copy import deepcopy

import pytest

from openswing import bridge
from openswing.numerical_policy import (
    SOURCE_DISCRETE, SOURCE_SECTION, default_policy, request_policy,
)
from test_bridge_numerics import CURVE, PANELS, SOURCE, request


ZERO = dict(beam_interpolation='drela-segspl-v1', structural_operator=SOURCE_DISCRETE)
SECTION = dict(beam_interpolation='drela-segspl-v1', structural_operator=SOURCE_SECTION)
POLICIES = [default_policy(), ZERO, SECTION]
SECTION_SOURCE = SOURCE.replace('t EA EIcc GJ EInn', '''t Cea Nea Cta Nta Ccg Ncg DCcg DNcg GKc GKn
1 .02 .01 -.01 .03 .04 -.02 -.03 .01 4000 5000
3 .02 .01 -.01 .03 .04 -.02 -.03 .01 4000 5000
t EA EIcc GJ EInn''')


def test_structural_only_keeps_engine_geometry_without_applying_thrust():
    engine = '\nEngine\n1 0 1 2 0 1 0 -1 0 0 1 0 0 0 0\nEnd\n'
    result = bridge.dispatch(request('solve', SOURCE + engine, mode='structural', numerics=SECTION))
    assert result['converged']
    assert any(item['kind'] == 'engine' for item in result['attachments'])
    assert all(component == 0 for component in result['applied_force'])


@pytest.mark.parametrize('policy', POLICIES)
def test_complete_policy_pairs_remain_distinct_and_unchanged(policy):
    original = deepcopy(policy)
    assert request_policy({'numerics': policy}) == original
    assert policy == original


@pytest.mark.parametrize('policy', [dict(SECTION, beam_interpolation='natural-v1'),
                                  dict(SECTION, structural_operator='drela-steady-section-v2')])
def test_unknown_or_conflicting_section_pair_rejects_before_parse(monkeypatch, policy):
    monkeypatch.setattr(bridge, 'parse_asw', lambda *a, **k: pytest.fail('Reached parser'))
    with pytest.raises(ValueError, match='numerics|policy'):
        bridge.dispatch(request(numerics=policy))


def test_inspection_retains_all_section_properties_without_claiming_dynamic_mass():
    value = request(source=SECTION_SOURCE, numerics=SECTION)
    original = deepcopy(value)
    result = bridge.dispatch(value)
    assert result['numerics'] == SECTION
    properties = result['distributions'][0]['properties']
    assert all(name in properties for name in (
        'Cea', 'Nea', 'Cta', 'Nta', 'Ccg', 'Ncg', 'DCcg', 'DNcg', 'GKc', 'GKn'))
    scope = result['mass_properties_scope']
    assert not scope['selected_operator_mass'] and not scope['dynamic_inertia_validated']
    assert 'midpoint' in scope['description']
    assert 'endpoint-CG gravity couples' in scope['selected_weight_rule']
    assert value == original


def test_section_distribution_edit_and_canonical_keep_exact_pair():
    report = bridge.dispatch(request('distribution', source=CURVE,
        beam=1, name='EA', numerics=SECTION))
    assert report['segments'][0]['values'][20] == pytest.approx(1750.)
    edited = bridge.dispatch(request('edit_distribution', source=CURVE,
        beam=1, name='EA', edit=dict(multiplier=2), numerics=SECTION))
    canonical = bridge.dispatch(request('canonical_asw', source=edited['source'], numerics=SECTION))
    again = bridge.dispatch(request('distribution', source=canonical['source'],
        beam=1, name='EA', numerics=canonical['numerics']))
    assert report['numerics'] == edited['numerics'] == canonical['numerics'] == again['numerics'] == SECTION
    assert edited['distribution']['segments'] == again['segments']
    assert again['segments'][0]['values'][20] == pytest.approx(3500.)


@pytest.mark.parametrize('policy', [ZERO, SECTION])
def test_route_forwards_exact_operator_and_static_options_only(monkeypatch, policy):
    import openswing.source_discrete as source_kernel
    seen = {}
    def stub(model, panels, **options):
        seen.update(model=model, panels=panels, options=options)
        return dict(structural_operator=options['structural_operator'],
                    mass_properties=dict(mass=2., first_moment=[0., 1., 0.],
                                         cg=[0., .5, 0.], inertia_cg=None, spin=None))
    monkeypatch.setattr(source_kernel, 'solve_source_discrete', stub)
    monkeypatch.setattr(bridge, 'solve_static', lambda *a, **k: pytest.fail('Wrong solver'))
    progress = lambda *a: None
    value = request('solve', mode='structural', numerics=policy,
        gravity=[0, 0, -10], loads=[dict(beam=1, t=3, force=[0, 2, 0])],
        tolerance=2e-9, continuation_steps=3, condition=None,
        operating_constraints=[], controller=None, derivatives=None, strut_mode='bilateral')
    original = deepcopy(value)
    result = bridge.dispatch(value, progress)
    assert seen['model'].beam_interpolation == 'drela-segspl-v1'
    assert seen['panels'] == PANELS
    assert seen['options'] == dict(gravity=value['gravity'], loads=value['loads'],
        initial_state=None, progress=progress, structural_operator=policy['structural_operator'],
        tolerance=2e-9, continuation_steps=3,
        allow_signed_point_weights=True, allow_signed_distributed_weights=True)
    assert result['analysis'] == 'structural_static' and result['structural_only']
    assert result['strips'] == [] and result['numerics'] == policy
    assert result['mass_properties']['inertia_cg'] is None and result['mass_properties']['spin'] is None
    assert value == original


@pytest.mark.parametrize('requested', POLICIES)
@pytest.mark.parametrize('saved', POLICIES)
def test_saved_state_requires_exact_operator_before_any_solver(monkeypatch, requested, saved):
    def stub(request, progress, policy):
        return {'received_policy': policy}
    monkeypatch.setattr(bridge, '_dispatch', stub)
    value = request('solve', mode='structural', numerics=requested,
                    initial_state={'identity': saved})
    if requested != saved:
        with pytest.raises(ValueError, match='Saved state numerical policy'):
            bridge.dispatch(value)
    else:
        assert bridge.dispatch(value)['received_policy'] == requested


@pytest.mark.parametrize('action', [
    'time', 'modes', 'frequency', 'rom', 'stability', 'resume_time', 'launch_time',
    'flow_survey', 'extend_frequency', 'steady_turn_constraints',
    'reference_airflow_constraints', 'gust_import', 'gust_export',
    'gust_sample', 'gust_validate', 'rom_import', 'discard_frequency',
])
def test_section_policy_rejects_unsupported_action_before_parse(monkeypatch, action):
    monkeypatch.setattr(bridge, 'parse_asw', lambda *a, **k: pytest.fail('Reached parser'))
    with pytest.raises(ValueError, match='static solves only'):
        bridge.dispatch(request(action, numerics=SECTION))


@pytest.mark.parametrize('extra', [
    {'mode': 'mounted'}, {'mode': 'rigid'}, {'condition': {'speed': 0}},
    {'motion': {}}, {'controller': {}}, {'derivatives': {}},
    {'operating_constraints': [dict(variable='alpha', quantity='CL', target=0)]},
    {'strut_mode': 'wire'}, {'time': {}}, {'quiescent_density': 0},
    {'loads': [dict(beam=1, t=3, force=[0, 2, 0], follower=True)]},
])
def test_section_policy_rejects_unhonored_options_before_parse(monkeypatch, extra):
    monkeypatch.setattr(bridge, 'parse_asw', lambda *a, **k: pytest.fail('Reached parser'))
    value = request('solve', mode='structural', numerics=SECTION)
    value.update(extra)
    with pytest.raises(ValueError, match='source-discrete|Source-discrete'):
        bridge.dispatch(value)
