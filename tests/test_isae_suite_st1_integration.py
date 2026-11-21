"""ST1 suite boundaries: complete source scope, unavailable roots and decimal gates.

All numerical records here are synthetic contract fixtures, never solved states.
"""
from copy import deepcopy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
# Match the runner's normal ``python scripts/run-isae-suite.py`` import path.
sys.path.insert(0, str(ROOT/'scripts'))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load('st1_integration_runner', 'scripts/run-isae-suite.py')
SUMMARY = load('st1_integration_summary', 'scripts/summarize-isae-suite.py')
FIXTURES = load('st1_contract_fixtures', 'tests/test_isae_suite_st1.py')


@pytest.fixture(scope='module')
def planned():
    from scripts import isae_suite_st1
    return isae_suite_st1.plan(ROOT)


def catalog():
    return dict(repository='frozen-original', revision='frozen', sources=[], models=[],
                counts={}, cases=[dict(id=name, path=name, models=[], reference_candidates=[])
                                 for name in sorted(SUMMARY.FAMILIES)])


def test_default_registration_keeps_all_st1_targets_and_models(monkeypatch, planned):
    assert RUNNER.ADAPTERS['st1'] == 'isae_suite_st1'
    loaded = []
    def module(name):
        loaded.append(name)
        return SimpleNamespace(plan=lambda root: planned if name == 'isae_suite_st1' else [])
    monkeypatch.setattr(RUNNER.importlib, 'import_module', module)
    rows = RUNNER.plan_jobs(ROOT)
    assert 'isae_suite_st1' in loaded and len(rows) == 37
    assert sum(row['expected_outputs'] for row in rows) == 200
    assert len([row for row in rows if row['execution_route'] == 'worker']) == 2
    assert len({row['model_path'] for row in rows if row['model_path']}) == 10
    assert 'scripts/isae_suite_st1.py' in RUNNER.code_pins(ROOT, ['st1'])


def test_all_native_roots_positions_and_inventory_remain_visible(planned):
    from scripts import isae_suite_st1
    rows = [dict(deepcopy(row), result=None if row['execution_route'] == 'worker'
                 else isae_suite_st1.validate_blocked(ROOT, row)) for row in planned]
    counts = SUMMARY.totals(rows)
    assert counts['required'] == 200
    assert counts['unrun_required'] == counts['absent'] == 6
    assert counts['unsupported_required'] == counts['reported_unavailable'] == 194
    assert counts['finite'] == counts['numerically_valid_finite'] == counts['passed'] == 0
    scope = SUMMARY.declared_scope(rows)
    expected = dict(original_reference_samples=197, native_reference_files=27,
        native_reference_rows=91, native_distinct_scalar_targets=197, native_scalar_slots=200,
        position_reference_rows=15, position_distinct_scalar_targets=45, position_scalar_slots=48,
        eigenvalue_reference_roots=76, eigenvalue_distinct_scalar_targets=152, real_only_reference_roots=25,
        conditional_position_reference_rows=1, conditional_position_scalar_slots=6,
        blocked_native_scalar_slots=194, literal_models_covered=10, literal_model_inventory_records=9,
        inventoried_output_candidates=61)
    assert {key: scope[key] for key in expected} == expected
    assert scope['additional_arrays_and_plots_outside_native_denominator'] is True
    assert scope['supplemental_duplicate_tree_adds_independent_targets'] is False
    assert sum(scope['candidate_files_by_classification'].values()) == 61


@pytest.mark.parametrize('kind', ['blocked_native_eigenvalues', 'blocked_native_position', 'model_inventory'])
@pytest.mark.parametrize('claim', ['computed', 'solver_call', 'match', 'numerical_alias'])
def test_unresolved_native_and_zero_target_jobs_cannot_pass(planned, kind, claim):
    from scripts import isae_suite_st1
    row = next(row for row in planned if row['target_kind'] == kind)
    result = isae_suite_st1.validate_blocked(ROOT, row)
    if claim == 'computed': result.update(status='computed', numerical_pass=True)
    elif claim == 'solver_call': result['physical_calls'] = 1
    elif claim == 'numerical_alias': result['numerical_passed'] = True
    else: result['reference_match'] = True
    checked = RUNNER.checked_result(row, result)
    assert checked['status'] == 'adapter_contract_failure'
    assert checked['reference_match'] is False
    with pytest.raises(ValueError): SUMMARY.scalar_counts(dict(row, result=result))


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'prediction', 'source_token', 'gate', 'calls', 'history'])
def test_computed_record_requires_complete_bound_physical_and_source_evidence(planned, fault):
    row = next(row for row in planned if row['execution_route'] == 'worker')
    result = FIXTURES.computed_fixture(row)
    if fault == 'missing': result['physical_checks'].pop()
    elif fault == 'duplicate': result['physical_checks'][-1] = deepcopy(result['physical_checks'][0])
    elif fault == 'prediction': result['reference_checks'][0]['predicted'] += .1
    elif fault == 'source_token': result['reference_checks'][0]['expected_token'] = '0.0'
    elif fault == 'gate':
        next(check for check in result['physical_checks'] if check['name'] == 'fresh_full_residual')['gate'] = 1.
    elif fault == 'calls': result['physical_calls'] = 1
    else: result['historical_settings_recovered'] = True
    checked = RUNNER.checked_result(row, result)
    assert checked['status'] == 'adapter_contract_failure'
    assert checked['output_accounting']['numerically_valid'] == 0
    with pytest.raises(ValueError): SUMMARY.scalar_counts(dict(row, result=result))


def position_fixture(row, position):
    """Update every independent/parity position binding in a synthetic fixture."""
    from scripts import isae_suite_st1
    result = FIXTURES.computed_fixture(row)
    values = dict(zip(isae_suite_st1.NAMES, position))
    physical = {check['name']: check for check in result['physical_checks']}
    anchor = physical['independent_sensor_anchor']
    anchor['node']['position'] = list(position)
    anchor.update(reported=values, reconstructed=values,
                  body_position=list(position), earth_position=list(position))
    physical['restored_position_parity'].update(reported=values, restored=values)
    result['reference_checks'] = isae_suite_st1._checks(row, values)
    result['reference_match'] = all(check['passed'] for check in result['reference_checks'])
    return result


@pytest.mark.parametrize('sign', [-1, 1])
@pytest.mark.parametrize('offset', ['1', '1.000001'])
def test_exact_decimal_endpoints_agree_across_adapter_runner_and_summary(planned, sign, offset):
    from scripts import isae_suite_st1
    row = next(row for row in planned if row['execution_route'] == 'worker')
    position = [float(Decimal(obs['exact_decimal_expected']) + sign*Decimal(offset)*
                      Decimal(obs['exact_decimal_tolerance'])) for obs in row['observations']]
    result = position_fixture(row, position)
    expected_pass = offset == '1'
    assert [check['passed'] for check in result['reference_checks']] == [expected_pass]*3
    assert isae_suite_st1.validate_result_contract(row, result)
    checked = RUNNER.checked_result(row, result)
    assert checked['status'] == 'computed' and checked['reference_match'] is expected_pass
    counts = SUMMARY.scalar_counts(dict(row, result=checked))
    assert counts['numerically_valid_finite'] == 3
    assert counts['passed'] == (3 if expected_pass else 0)
    if sign == 1 and expected_pass:
        check = result['reference_checks'][0]
        assert check['predicted'] == -0.1296705
        assert SUMMARY.precision_pass(check, exact_decimal=True) is True
        # Existing families keep their historical binary-float convention.
        assert SUMMARY.precision_pass(check) is False
        legacy = dict(row, adapter='synthetic_other_family')
        assert RUNNER.checked_result(legacy, result)['status'] == 'adapter_contract_failure'


def test_selected_matching_position_scope_cannot_claim_full_family_or_suite(planned):
    rows = [dict(deepcopy(row), result=position_fixture(row, [o['expected'] for o in row['observations']]))
            for row in planned if row['execution_route'] == 'worker']
    runner_cases = RUNNER.summarize(catalog(), rows, {row['id']: row['result'] for row in rows})
    assert len(runner_cases) == 41
    assert all(case['complete_family_reproduction'] is False for case in runner_cases)
    merged = dict(catalog=catalog(), jobs=rows, runtime={}, kernel_pins={}, helper_pins={}, source_provenance={})
    summary = SUMMARY.summarize(merged)
    assert summary['full_suite_validated'] is False and summary['family_count'] == 41
    assert len(summary['missing_adapters']) == 40
    st1 = next(case for case in summary['families'] if case['id'] == 'ST-1')
    assert st1['status'] == 'SELECTED_SCOPE_MATCHES' and st1['complete_family_reproduction'] is False
    assert st1['scalar_counts']['passed'] == st1['scalar_counts']['required'] == 6
    assert st1['declared_scope']['numerically_valid_native_distinct_scalars'] == 3
    assert st1['declared_scope']['numerically_valid_eigenvalue_roots'] == 0
    assert summary['st1_mesh_diagnostics'][0]['passed'] is None
    assert summary['st1_mesh_diagnostics'][0]['acceptance_gate'] is None


def test_summary_rebuilds_original_st1_context_once_and_rejects_edited_setup(tmp_path, monkeypatch, planned):
    import builtins
    from scripts import isae_suite_st1
    rows = [dict(deepcopy(row), result=None) for row in planned if row['execution_route'] == 'worker']
    source_catalog = catalog()
    pins = RUNNER.code_pins(ROOT, ['st1'])
    report = dict(repository=source_catalog['repository'], revision=source_catalog['revision'], runtime={},
                  current_code_unchanged=True, jobs=rows, code_sha256=pins)
    plan = dict(catalog=source_catalog, jobs=[{k:v for k,v in row.items() if k != 'result'} for row in rows],
                runtime={}, code_sha256=pins)
    for name, value in [('report', report), ('catalog', source_catalog), ('plan', plan)]:
        (tmp_path/(name+'.json')).write_text(json.dumps(value))
    actual_plan = isae_suite_st1.plan; calls = []
    def counted(root):
        calls.append(root)
        return actual_plan(root)
    monkeypatch.setattr(isae_suite_st1, 'plan', counted)
    monkeypatch.setattr(isae_suite_st1, 'verify_reference_sources',
                        lambda *args: pytest.fail('Repeated per-job source reconstruction'))
    actual_import = builtins.__import__
    def guarded(name, *args, **kwargs):
        assert not name.startswith(('openswing', 'numpy', 'scipy'))
        return actual_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    merged = SUMMARY.load_runs([tmp_path], ROOT)
    assert calls == [ROOT] and len(merged['jobs']) == 2
    SUMMARY.verify_summary_sources(merged)
    report['jobs'][0]['gravity'][2] = plan['jobs'][0]['gravity'][2] = -9.8
    for name, value in [('report', report), ('plan', plan)]:
        (tmp_path/(name+'.json')).write_text(json.dumps(value))
    with pytest.raises(ValueError, match='original sources'):
        SUMMARY.load_runs([tmp_path], ROOT)
    assert calls == [ROOT, ROOT]
