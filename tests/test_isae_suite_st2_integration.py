"""ST2 modal suite contracts; synthetic evidence only, no physical evaluation."""
from copy import deepcopy
from decimal import Decimal
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load('st2_integration_runner', 'scripts/run-isae-suite.py')
SUMMARY = load('st2_integration_summary', 'scripts/summarize-isae-suite.py')


@lru_cache(maxsize=1)
def fixtures():
    return load('st2_modal_contract_fixtures', 'tests/test_isae_suite_st2_modal.py')


def computed_fixture(job, values=None):
    """Mock original agreement solely to exercise accounting and rejection paths."""
    if values is None:
        values = {obs['name']: obs['expected'] for obs in job['observations']}
    return fixtures().computed_fixture(job, values)


@pytest.fixture(scope='module')
def planned():
    if not (ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original ISAE archive unavailable')
    from scripts import isae_suite_st2
    return isae_suite_st2.plan(ROOT)


def catalog():
    return dict(repository='frozen-original', revision='frozen', sources=[], models=[],
                counts={}, cases=[dict(id=name, path=name, models=[], reference_candidates=[])
                                  for name in SUMMARY.FAMILIES])


def write_packet(directory, rows):
    source_catalog = catalog()
    pins = RUNNER.code_pins(ROOT, ['st2'])
    report = dict(repository=source_catalog['repository'], revision=source_catalog['revision'], runtime={},
                  current_code_unchanged=True, jobs=rows, code_sha256=pins)
    plan = dict(catalog=source_catalog, jobs=[{k:v for k,v in row.items() if k != 'result'} for row in rows],
                runtime={}, code_sha256=pins)
    for name, value in [('report', report), ('catalog', source_catalog), ('plan', plan)]:
        (directory/(name+'.json')).write_text(json.dumps(value))
    return report, plan


def test_all_original_roots_and_blocked_targets_survive_mesh_and_medium_expansion(planned):
    from scripts import isae_suite_st2
    rows = [dict(deepcopy(row), result=None if row['execution_route'] == 'worker'
                 else isae_suite_st2.validate_blocked(ROOT, row)) for row in planned]
    assert len(rows) == 17
    workers = [row for row in rows if row['execution_route'] == 'worker']
    assert len(workers) == 8
    assert {(row['nominal'], row['medium']) for row in workers} == {
        (40, 'vacuum'), (80, 'vacuum'), (40, 'still_air'), (80, 'still_air')}
    assert len({row['model_path'] for row in workers}) == 2
    assert all(row['required_components'] == ['real', 'imaginary'] and
               len(row['reference_rows']) == 7 and row['expected_outputs'] == 14 for row in workers)
    counts = SUMMARY.totals(rows)
    assert counts == dict(required=490, reported=378, finite=0, numerically_valid_finite=0,
        passed=0, absent=112, reported_unavailable=378, unrun_required=112,
        failed_job_required=0, unsupported_required=378)
    scope = SUMMARY.declared_scope(rows)
    expected = dict(original_reference_samples=70, native_reference_samples=60,
        native_scalar_targets=396, native_scalar_slots=480, modal_reference_roots=14,
        modal_distinct_scalar_targets=28, conditional_modal_jobs=8,
        conditional_modal_scalar_slots=112, blocked_scalar_slots=378,
        qualified_workbook_cells=10, literal_model_inventory_records=6)
    assert {key: scope[key] for key in expected} == expected
    assert SUMMARY.st2_mesh_diagnostics(rows)
    assert SUMMARY.st2_mesh_diagnostics([]) == []


@pytest.mark.parametrize('fault', ['gravity', 'medium', 'count', 'shift', 'step', 'mesh',
                                  'gate', 'components', 'whole_family', 'historical_identity'])
def test_unrun_worker_contract_rejects_protocol_changes(planned, fault):
    row = deepcopy(next(row for row in planned if row['execution_route'] == 'worker'))
    if fault == 'gravity': row['gravity'][2] = 0.
    elif fault == 'medium': row['medium'] = 'moving_air'
    elif fault == 'count': row['modal_protocol']['count'] = 7
    elif fault == 'shift': row['modal_protocol']['shift'][0] = 0.
    elif fault == 'step': row['modal_protocol']['step'] = 1e-4
    elif fault == 'mesh': row['panels']['default'] = 41
    elif fault == 'gate': row['numerical_gates']['base'] *= 10
    elif fault == 'components': row['required_components'] = ['imaginary']
    elif fault == 'whole_family': row['complete_family_reproduction'] = True
    else: row['historical_settings_recovered'] = True
    with pytest.raises(ValueError): SUMMARY.scalar_counts(dict(row, result=None))


@pytest.mark.parametrize('status', ['timeout', 'error', 'terminated'])
def test_worker_process_failures_retain_all_unavailable_modal_slots(planned, status):
    row = next(row for row in planned if row['execution_route'] == 'worker')
    result = dict(status=status, reference_match=False, reference_checks=[])
    counts = SUMMARY.scalar_counts(dict(row, result=result))
    assert counts == dict(required=14, reported=0, finite=0, numerically_valid_finite=0,
        passed=0, absent=14, reported_unavailable=0, unrun_required=0,
        failed_job_required=14, unsupported_required=0)


@pytest.mark.parametrize('sign', [-1, 1])
@pytest.mark.parametrize('offset', ['1', '1.000001'])
def test_native_decimal_interval_keeps_tiny_real_parts_and_endpoint_precision(planned, sign, offset):
    from scripts import isae_suite_st2
    row = next(row for row in planned if row['execution_route'] == 'worker')
    values = {obs['name']: float(Decimal(obs['exact_decimal_expected']) + sign*Decimal(offset)*
                               Decimal(obs['exact_decimal_tolerance'])) for obs in row['observations']}
    checks = isae_suite_st2._reference_checks(row, values)
    expected_pass = offset == '1'
    assert all(check['passed'] is expected_pass for check in checks)
    assert all(SUMMARY.precision_pass(check, exact_decimal=True) is expected_pass for check in checks)
    # No relative floor or snapping of the tiny archived real components.
    assert checks[0]['predicted'] != 0. and checks[0]['exact_decimal_tolerance'] == '5E-22'
    if expected_pass:
        assert any(SUMMARY.precision_pass(check) is False for check in checks)
    result = computed_fixture(row, values)
    checked = RUNNER.checked_result(row, result)
    assert checked['status'] == 'computed' and checked['reference_match'] is expected_pass
    counts = SUMMARY.scalar_counts(dict(row, result=checked))
    assert counts['numerically_valid_finite'] == 14
    assert counts['passed'] == (14 if expected_pass else 0)
    assert SUMMARY.error_stats([dict(row, result=checked)], checks[0]['name'])['precision_passed'] == int(expected_pass)


@pytest.mark.parametrize('fault', ['missing_check', 'duplicate_check', 'detached_prediction', 'source_token',
                                  'gate', 'calls', 'retry', 'partial_roots', 'history', 'spectrum_claim'])
def test_computed_modal_result_requires_complete_bound_evidence(planned, fault):
    row = next(row for row in planned if row['execution_route'] == 'worker')
    result = computed_fixture(row)
    if fault == 'missing_check': result['physical_checks'].pop()
    elif fault == 'duplicate_check': result['physical_checks'][-1] = deepcopy(result['physical_checks'][0])
    elif fault == 'detached_prediction': result['reference_checks'][0]['predicted'] = 0.
    elif fault == 'source_token': result['reference_checks'][0]['expected_token'] = '0.0'
    elif fault == 'gate':
        next(check for check in result['physical_checks'] if check['name'] == 'fresh_full_residual')['gate'] = 1.
    elif fault == 'calls': result['physical_calls'] = 1
    elif fault == 'retry': result['operations']['retries'] = 1
    elif fault == 'partial_roots': result['modal_evidence']['eigenvalues'].pop()
    elif fault == 'history': result['historical_settings_recovered'] = True
    else: result['complete_finite_spectrum'] = True
    checked = RUNNER.checked_result(row, result)
    assert checked['status'] == 'adapter_contract_failure' and checked['reference_match'] is False
    assert checked['output_accounting']['numerically_valid'] == 0
    with pytest.raises(ValueError): SUMMARY.scalar_counts(dict(row, result=result))


def test_prediction_spectrum_cannot_detach_from_physically_checked_spectrum(planned):
    row = next(row for row in planned if row['execution_route'] == 'worker')
    original = computed_fixture(row)
    values = {obs['name']: obs['expected'] for obs in row['observations']}
    values['row0001:imaginary'] += .1
    changed = computed_fixture(row, values)
    changed['physical_checks'] = original['physical_checks']
    checked = RUNNER.checked_result(row, changed)
    assert checked['status'] == 'adapter_contract_failure'
    with pytest.raises(ValueError): SUMMARY.scalar_counts(dict(row, result=changed))


def test_zero_real_parts_do_not_pass_original_tiny_nonzero_targets(planned):
    row = next(row for row in planned if row['execution_route'] == 'worker')
    values = {obs['name']: (0. if obs['name'].endswith(':real') else obs['expected']) for obs in row['observations']}
    result = RUNNER.checked_result(row, computed_fixture(row, values))
    assert result['status'] == 'computed' and result['reference_match'] is False
    assert result['output_accounting']['required'] == result['output_accounting']['finite'] == 14
    assert SUMMARY.scalar_counts(dict(row, result=result))['passed'] == 7


def test_selected_matching_modal_scope_cannot_claim_full_family_or_spectrum(planned):
    rows = [dict(deepcopy(row), result=computed_fixture(row))
            for row in planned if row['execution_route'] == 'worker']
    cases = RUNNER.summarize(catalog(), rows, {row['id']: row['result'] for row in rows})
    assert all(case['complete_family_reproduction'] is False for case in cases)
    merged = dict(catalog=catalog(), jobs=rows, runtime={}, kernel_pins={}, helper_pins={}, source_provenance={})
    summary = SUMMARY.summarize(merged)
    assert summary['full_suite_validated'] is False and len(summary['missing_adapters']) == 40
    st2 = next(case for case in summary['families'] if case['id'] == 'ST-2')
    assert st2['status'] == 'SELECTED_SCOPE_MATCHES' and st2['complete_family_reproduction'] is False
    assert st2['scalar_counts']['passed'] == st2['scalar_counts']['required'] == 112
    assert st2['declared_scope']['numerically_valid_modal_reference_roots'] == 14
    assert st2['declared_scope']['numerically_valid_native_distinct_scalars'] == 28
    assert len(summary['st2_mesh_diagnostics']) == 4
    assert all(check['status'] == 'COMPARED' and check['passed'] is None and check['acceptance_gate'] is None
               for check in summary['st2_mesh_diagnostics'])


def test_runner_worker_dispatches_existing_run_api_with_modal_contract(tmp_path, monkeypatch, planned):
    from scripts import isae_suite_st2
    row = next(row for row in planned if row['execution_route'] == 'worker')
    calls = []
    def synthetic_run(root, job):
        calls.append((root, job['id']))
        return computed_fixture(job)
    monkeypatch.setattr(isae_suite_st2, 'run', synthetic_run)
    monkeypatch.setattr(RUNNER.importlib, 'import_module', lambda name: isae_suite_st2)
    source, output = tmp_path/'job.json', tmp_path/'result.json'
    source.write_text(json.dumps(dict(job=row, code_sha256={})))
    RUNNER.worker(source, output)
    result = json.loads(output.read_text())
    assert calls == [(ROOT, row['id'])]
    assert result['status'] == 'computed' and result['reference_match'] is True
    assert result['output_accounting']['required'] == result['output_accounting']['passed'] == 14


def test_summary_rebuilds_st2_context_once_without_importing_physics(tmp_path, monkeypatch, planned):
    import builtins
    from scripts import isae_suite_st2
    rows = [dict(deepcopy(row), result=None) for row in planned if row['execution_route'] == 'worker']
    write_packet(tmp_path, rows)
    actual_plan = isae_suite_st2.plan
    calls = []
    def counted(root):
        calls.append(root)
        return actual_plan(root)
    monkeypatch.setattr(isae_suite_st2, 'plan', counted)
    monkeypatch.setattr(isae_suite_st2, 'verify_reference_sources',
                        lambda *args: pytest.fail('Repeated per-job source reconstruction'))
    actual_import = builtins.__import__
    def guarded(name, *args, **kwargs):
        assert not name.startswith(('openswing', 'numpy', 'scipy'))
        return actual_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    merged = SUMMARY.load_runs([tmp_path], ROOT)
    assert calls == [ROOT] and len(merged['jobs']) == 8
    SUMMARY.verify_summary_sources(merged)
    # The original report bytes remain part of the publication ledger.
    with (tmp_path/'report.json').open('a') as stream:
        stream.write('\n')
    with pytest.raises(ValueError, match='Verified file changed'):
        SUMMARY.verify_summary_sources(merged)


@pytest.mark.parametrize('fault', ['source_line', 'request_gravity', 'historical_identity'])
def test_consistent_plan_and_report_edits_do_not_override_original_context(tmp_path, planned, fault):
    rows = [dict(deepcopy(next(row for row in planned if row['execution_route'] == 'worker')), result=None)]
    report, plan = write_packet(tmp_path, rows)
    for packet in (report, plan):
        row = packet['jobs'][0]
        if fault == 'source_line':
            row['reference_rows'][0]['line_number'] = 99
            for obs in row['observations'][:2]: obs['source_line'] = 99
        elif fault == 'request_gravity': row['request']['gravity'] = [0., 0., 0.]
        else: row['historical_settings_recovered'] = True
    for name, value in [('report', report), ('plan', plan)]:
        (tmp_path/(name+'.json')).write_text(json.dumps(value))
    expected_message = {'source_line': 'original sources',
                        'request_gravity': 'literal modal bridge request changed',
                        'historical_identity': 'prospective modal protocol, physical gate or claim changed'}[fault]
    with pytest.raises(ValueError, match=expected_message):
        SUMMARY.load_runs([tmp_path], ROOT)
