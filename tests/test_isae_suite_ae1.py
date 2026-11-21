"""AE1 original-source and saved-result contracts; no solver or mesh evaluation."""
import builtins
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

import pytest

from scripts import isae_suite_ae1 as adapter


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def jobs():
    if not (ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original ISAE archive unavailable')
    return adapter.plan(ROOT)


def test_every_original_row_token_and_precision_is_retained_on_both_declared_meshes(jobs):
    evidence = json.loads((ROOT/adapter.READINESS).read_text())
    assert len(jobs) == 200 and sum(row['expected_outputs'] for row in jobs) == 1200
    assert sum(row['execution_route'] == 'worker' for row in jobs) == 196
    assert len({(row['table_path'], row['reference_rows'][0]['row_number']) for row in jobs}) == 100
    original = {(series['alpha'], ordinal): row for series in evidence['series']
                for ordinal, row in enumerate(series['rows'], 1)}
    source_paths = set()
    for row in jobs:
        source_paths.add(row['model_path'])
        alpha = int(Path(row['driver_path']).stem.removeprefix('alpha'))
        reference = row['reference_rows'][0]
        expected = original[alpha, reference['row_number']]
        assert reference['tokens'] == expected['raw_tokens'] and reference['raw_line'] == expected['raw_line']
        assert reference['line_number'] == expected['file_line']
        assert [obs['name'] for obs in row['observations']] == list(adapter.NAMES)
        for obs, token in zip(row['observations'], expected['raw_tokens'][2:], strict=True):
            decimal = Decimal(token)
            assert obs['expected'] == float(decimal)
            assert obs['tolerance'] == float(Decimal(5).scaleb(decimal.as_tuple().exponent-1))
        assert not row['original_file_modified'] and not row['historical_settings_recovered']
        assert row['source_node_request'] == 40 and row['nominal'] in (40, 80)
        assert row['expected_elements'] == row['nominal']+1 and row['expected_nodes'] == row['nominal']+2
        assert row['mandatory_property_break'] == .52 and 'historical NODE I40' in row['mesh_scope']
        assert not Path(row['model_path']).is_absolute() and not Path(row['table_path']).is_absolute()
    assert len(source_paths) == 1
    source = ROOT/next(iter(source_paths))
    assert hashlib.sha256(source.read_bytes()).hexdigest() == '5086107d412ebf8f43ef75173fe553914fb074dd7dca3b93f7bd56ab365c17c8'
    assert source.read_text().count('0.558') == 4  # Two original anchors and two original pylon Y positions.


def test_initial_stack_rows_remain_finite_targets_with_unknown_conditions(jobs):
    blocked = [row for row in jobs if row['execution_route'] == 'unsupported']
    assert len(blocked) == 4 and sum(row['expected_outputs'] for row in blocked) == 24
    assert len({row['table_path'] for row in blocked}) == 2
    for row in blocked:
        assert row['condition'] is None and row['reference_rows'][0]['command'] is None
        assert row['reference_rows'][0]['alpha_deg'] is None
        assert all(math.isfinite(obs['expected']) for obs in row['observations'])
        assert row['blocker_code'] == 'INITIAL_OPERATING_STATE_UNIDENTIFIED'
    assert blocked[0]['reference_rows'][0]['tokens'] == blocked[-1]['reference_rows'][0]['tokens']


def test_source_planning_and_initial_blockers_import_no_production_or_numpy(monkeypatch, jobs):
    real_import = builtins.__import__
    def guarded(name, *args, **kwargs):
        assert not name.startswith(('openswing', 'numpy', 'scipy')), 'Source-only contract imported production/numerical code'
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    monkeypatch.setattr(adapter, '_execute', lambda *args: pytest.fail('Blocked initial state started physics'))
    planned = adapter.plan(ROOT)
    assert len(planned) == 200
    for row in jobs:
        if row['execution_route'] == 'unsupported':
            result = adapter.run(ROOT, row)
            assert result['status'] == 'unsupported' and result['physical_calls'] == result['production_imports'] == 0
            assert result['operations'] == dict(cold_solves=0, fresh_residuals=0, retries=0)
            assert len(result['reference_checks']) == 6 and all(item['predicted'] is None for item in result['reference_checks'])
            assert adapter.validate_result_contract(row, result)


@pytest.mark.parametrize('fault', ['speed', 'influences', 'ground', 'gravity', 'mesh', 'nodes',
                                  'weight', 'sensor', 'precision', 'command', 'token', 'source'])
def test_source_rebuild_rejects_any_changed_setup_or_original_target(jobs, fault):
    row = deepcopy(next(row for row in jobs if row['execution_route'] == 'worker'))
    if fault == 'speed': row['condition']['speed'] += 1.
    if fault == 'influences': row['condition']['freeze_influences'] = True
    if fault == 'ground': row['condition']['ground_effect'] = 0
    if fault == 'gravity': row['gravity'] = [0., -9.81, 0.]
    if fault == 'mesh': row['panels']['beams']['1']['count'] += 1
    if fault == 'nodes': row['expected_nodes'] += 1
    if fault == 'weight': row['literal_weight_rows'].pop()
    if fault == 'sensor': row['literal_sensor_rows'][0][3] += .001
    if fault == 'precision': row['observations'][0]['tolerance'] *= 10
    if fault == 'command': row['reference_rows'][0]['command']['line'] += 1
    if fault == 'token': row['reference_rows'][0]['tokens'][2] = '0.0'
    if fault == 'source': row['literal_model_sha256'] = '0'*64
    with pytest.raises(ValueError, match='differs from original'):
        adapter.verify_reference_sources(ROOT, row)


def test_sensor_reconstruction_uses_literal_pylons_and_earth_elevation():
    angle = math.radians(17.); c, s = math.cos(angle), math.sin(angle)
    node = dict(beam=1, t=.55, position=[.02,.50,.12], jig_position=[0.,.55,0.],
                rotation=[[c,0.,s],[0.,1.,0.],[-s,0.,c]])
    sensors = adapter.reconstruct_sensors([node])
    values = adapter.sensor_values(sensors)
    assert values['sensor1_RX_earth_m'] == pytest.approx(.02-.05*c)
    assert values['sensor2_RX_earth_m'] == pytest.approx(.02+.05*c)
    assert values['sensor1_RZ_earth_m'] == pytest.approx(.12+.05*s)
    assert values['sensor2_RZ_earth_m'] == pytest.approx(.12-.05*s)
    assert values['sensor3_RZ_earth_m'] == .12
    assert values['sensor3_Theta_elevation_deg'] == pytest.approx(17.)
    assert all(sensor['axes_earth'] == node['rotation'] for sensor in sensors)
    changed = deepcopy(adapter.SENSOR_ROWS); changed[0][3] = -.04
    with pytest.raises(ValueError, match='identity changed'):
        adapter.reconstruct_sensors([node], changed)


def physical_fixture(job):
    """Synthetic complete evidence exercises checks; it is not a solved state."""
    angle = math.radians(11.); c, s = math.cos(angle), math.sin(angle)
    tip = dict(beam=1, t=.55, position=[0.,.54,.02], jig_position=[0.,.55,0.],
               rotation=[[c,0.,s],[0.,1.,0.],[-s,0.,c]])
    sensors = adapter.reconstruct_sensors([tip]); values = adapter.sensor_values(sensors)
    expectations = adapter._expectations(job)
    checks = []
    for name, spec in adapter.PHYSICAL_CHECK_SPECS.items():
        item = dict(name=name, passed=True)
        if spec['kind'] == 'exact':
            expected = expectations.get(name, {'fixture': 'same complete operator identity'})
            item.update(actual=deepcopy(expected), expected=deepcopy(expected))
        else:
            item.update(metric=0., gate=job['numerical_gates'][spec['gate']])
            if spec['kind'] == 'vector': item.update(reported=[0.,0.,0.], reconstructed=[0.,0.,0.])
            if spec['kind'] == 'balance': item.update(applied=[0.,0.,0.], support=[0.,0.,0.])
            if spec['kind'] == 'clamp':
                value = [0.,0.,0.] if name.endswith('position') else [1.,0.,0.,0.,1.,0.,0.,0.,1.]
                item.update(reported=list(value), expected=list(value))
            if spec['kind'] == 'sensors':
                item.update(reported=deepcopy(sensors), reconstructed=deepcopy(sensors), tip_nodes=[tip])
            if spec['kind'] == 'parity':
                item.update(reported=dict(values), restored=dict(values), channels={name:0. for name in adapter.NAMES})
        checks.append(item)
    return checks, values


def computed_fixture(job):
    physical, values = physical_fixture(job)
    checks = adapter._checks(job, values)
    return dict(status='computed', numerical_pass=True, reference_match=all(item['passed'] for item in checks),
        source_pins_unchanged=True, kernel_pins_unchanged=True, physical_calls=2,
        operations=dict(cold_solves=1, fresh_residuals=1, retries=0), reference_checks=checks, physical_checks=physical)


def test_complete_computed_fixture_retains_output_disagreement_and_descriptive_mesh(jobs):
    pair = [deepcopy(row) for row in jobs if row['coordinate_id'] == 'a05-row002']
    results = {row['id']:computed_fixture(row) for row in pair}
    for row in pair:
        assert len(results[row['id']]['physical_checks']) == 29
        assert adapter.validate_result_contract(row, results[row['id']])
        assert results[row['id']]['reference_match'] is False
    diagnostic, = adapter.mesh_diagnostics(pair, results)
    assert diagnostic['status'] == 'COMPARED' and diagnostic['passed'] is None and diagnostic['acceptance_gate'] is None
    assert len(diagnostic['channels']) == 6 and all(item['abs_change'] == 0 for item in diagnostic['channels'].values())
    assert all(row['status'] == 'UNAVAILABLE' for row in adapter.mesh_diagnostics(jobs, {}))


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'residual', 'gate', 'source', 'kernel', 'calls', 'retry',
                                  'prediction', 'sensor_geometry', 'cold_setup', 'restored_setup', 'restored_condition',
                                  'clamp', 'balance', 'null_weights', 'precision'])
def test_computed_claim_requires_complete_physics_and_bound_sensor_evidence(jobs, fault):
    row = deepcopy(next(row for row in jobs if row['execution_route'] == 'worker'))
    result = computed_fixture(row); physical = {item['name']:item for item in result['physical_checks']}
    if fault == 'missing': result['physical_checks'].pop()
    if fault == 'duplicate': result['physical_checks'][-1] = deepcopy(result['physical_checks'][0])
    if fault == 'residual': physical['fresh_full_residual']['metric'] = 1.
    if fault == 'gate': row['numerical_gates']['residual'] = 1.
    if fault == 'source': result['source_pins_unchanged'] = False
    if fault == 'kernel': result['kernel_pins_unchanged'] = False
    if fault == 'calls': result['physical_calls'] = 1
    if fault == 'retry': result['operations']['retries'] = 1
    if fault == 'prediction': result['reference_checks'][0]['predicted'] += 1.
    if fault == 'sensor_geometry':
        for key in ('reported', 'reconstructed'):
            physical['independent_sensor_geometry'][key][0]['position_earth'][0] += 1.
    if fault == 'cold_setup': physical['cold_operating_setup']['actual']['ground_flag'] = 0
    if fault == 'restored_setup': physical['restored_operating_setup']['actual']['gravity_body'] = [0.,0.,0.]
    if fault == 'restored_condition': physical['restored_condition']['actual']['freeze_influences'] = True
    if fault == 'clamp': physical['root_clamp_position']['reported'][0] = 1.
    if fault == 'balance': physical['force_balance']['applied'][0] = 1.
    if fault == 'null_weights': physical['literal_weight_rows']['actual'].pop()
    if fault == 'precision': result['reference_checks'][0]['tolerance'] *= 2
    with pytest.raises(ValueError): adapter.validate_result_contract(row, result)


@pytest.mark.parametrize('claim', ['computed', 'numerical', 'alternate_numerical', 'match', 'prediction', 'calls', 'retry', 'missing'])
def test_initial_state_cannot_be_promoted_or_removed_from_required_slots(jobs, claim):
    row = next(row for row in jobs if row['execution_route'] == 'unsupported')
    result = adapter.validate_blocked(ROOT, row)
    if claim == 'computed': result['status'] = 'computed'
    if claim == 'numerical': result['numerical_pass'] = True
    if claim == 'alternate_numerical': result['numerical_passed'] = True
    if claim == 'match': result['reference_match'] = True
    if claim == 'prediction': result['reference_checks'][0]['predicted'] = 0.
    if claim == 'calls': result['physical_calls'] = 1
    if claim == 'retry': result['operations']['retries'] = 1
    if claim == 'missing': result['reference_checks'].pop()
    with pytest.raises(ValueError): adapter.validate_result_contract(row, result)


def test_worker_failure_preserves_all_six_unavailable_slots_without_retry(monkeypatch, tmp_path, jobs):
    row = next(row for row in jobs if row['execution_route'] == 'worker')
    calls = []
    def fail(root, job, stage):
        calls.append(job['id'])
        raise ValueError('Synthetic worker failure before physical execution')
    monkeypatch.setattr(adapter, '_execute', fail)
    monkeypatch.setattr(adapter.tempfile, 'mkdtemp', lambda **kwargs: str(tmp_path))
    result = adapter.run(ROOT, row)
    assert calls == [row['id']] and result['status'] == 'numerical_failure'
    assert len(result['reference_checks']) == 6 and all(item['predicted'] is None for item in result['reference_checks'])
    assert result['physical_calls'] == 0 and result['operations']['retries'] == 0
    assert (tmp_path/'exception.json').is_file() and (tmp_path/'adapter-result.json').is_file()
