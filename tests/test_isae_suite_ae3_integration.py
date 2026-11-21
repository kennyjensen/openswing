"""AE3 coverage, blocked-output accounting and source binding at suite boundaries."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load('ae3_integration_runner', 'run-isae-suite.py')
SUMMARY = load('ae3_integration_summary', 'summarize-isae-suite.py')


@pytest.fixture(scope='module')
def planned():
    from scripts import isae_suite_ae3
    return isae_suite_ae3.plan(ROOT)


def catalog():
    return dict(repository='frozen-original', revision='frozen', sources=[], models=[],
                counts={}, cases=[dict(id=name, path=name, models=[], reference_candidates=[])
                                 for name in sorted(SUMMARY.FAMILIES)])


def test_default_registry_includes_all_ae3_scopes_and_code_pins(monkeypatch, planned):
    assert RUNNER.ADAPTERS['ae3'] == 'isae_suite_ae3'
    loaded = []
    def module(name):
        loaded.append(name)
        return SimpleNamespace(plan=lambda root: planned if name == 'isae_suite_ae3' else [])
    monkeypatch.setattr(RUNNER.importlib, 'import_module', module)
    rows = RUNNER.plan_jobs(ROOT)
    assert 'isae_suite_ae3' in loaded and len(rows) == len(planned)
    assert sum(row['expected_outputs'] for row in rows) == 725
    active = [row for row in rows if row['execution_route'] == 'worker']
    assert len(active) == 30 and sum(row['expected_outputs'] for row in active) == 612
    assert {row['case_id'] for row in rows} == {'AE-3'}
    pins = RUNNER.code_pins(ROOT, ['ae3'])
    assert {'scripts/isae_suite_ae3.py', 'scripts/extract-isae-ae3-reference.py',
            'scripts/isae_suite_ap1.py', 'scripts/isae_ae3_observables.py'} <= pins.keys()


def test_enabled_native_targets_stay_unrun_until_computed_and_embedded_targets_stay_visible(planned, monkeypatch):
    from scripts import isae_suite_ae3
    # This is a full-ledger accounting test. Authenticate the original catalog
    # before and after, instead of re-reading every reference file for each row.
    # Per-job canonical reconstruction and all 725 targets remain exercised.
    real_context = isae_suite_ae3._context
    context = real_context(ROOT)
    def shared_context(root):
        assert Path(root).resolve() == ROOT
        return context
    monkeypatch.setattr(isae_suite_ae3, '_context', shared_context)
    rows = deepcopy(planned)
    for row in rows:
        row['result'] = (None if row['execution_route'] == 'worker' else
                         isae_suite_ae3.validate_blocked(ROOT, row))
    counts = SUMMARY.totals(rows)
    assert counts['required'] == 725
    assert counts['unrun_required'] == counts['absent'] == 612
    assert counts['unsupported_required'] == counts['reported_unavailable'] == 113
    assert counts['finite'] == counts['numerically_valid_finite'] == counts['passed'] == 0
    assert SUMMARY.declared_scope(rows)['native_reference_states'] == 6
    assert real_context(ROOT) == context


@pytest.mark.parametrize('claim', ['computed', 'prediction', 'solver_call', 'match'])
def test_blocked_ae3_cannot_be_promoted_to_numerical_success(planned, claim):
    from scripts import isae_suite_ae3
    row = deepcopy(next(row for row in planned if row['execution_route'] == 'unsupported'
                        and row['expected_outputs']))
    result = isae_suite_ae3.validate_blocked(ROOT, row)
    if claim == 'computed': result.update(status='computed', numerical_pass=True)
    elif claim == 'prediction':
        result['reference_checks'][0].update(predicted=result['reference_checks'][0]['expected'], passed=True)
    elif claim == 'solver_call': result['physical_calls'] = 1
    else: result['reference_match'] = True
    checked = RUNNER.checked_result(row, result)
    assert checked['status'] == 'adapter_contract_failure'
    assert checked['reference_match'] is False
    with pytest.raises(ValueError): SUMMARY.scalar_counts(dict(row, result=result))


def test_native_coefficients_require_physical_evidence_not_just_matching_numbers(planned):
    from scripts import isae_suite_ae3
    row = next(row for row in planned if row['execution_route'] == 'worker')
    result = dict(status='computed', numerical_pass=True, reference_match=True,
                  reference_checks=[dict(name=name, **reference,
                    predicted=reference['expected'], passed=True)
                    for name, reference in isae_suite_ae3.reference_contract(row).items()])
    checked = RUNNER.checked_result(row, result)
    assert checked['status'] == 'adapter_contract_failure'
    assert checked['output_accounting']['numerically_valid'] == 0
    with pytest.raises(ValueError): SUMMARY.scalar_counts(dict(row, result=result))


def test_selected_ae3_run_still_reports_all_families(planned):
    cases = RUNNER.summarize(catalog(), planned, {})
    assert len(cases) == 41
    assert sum(case['jobs_planned'] > 0 for case in cases) == 1
    ae3 = next(case for case in cases if case['id'] == 'AE-3')
    assert ae3['output_accounting']['required'] == 725
    assert ae3['complete_family_reproduction'] is False


def test_summary_rebuilds_ae3_sources_once_and_checks_all_declared_settings(tmp_path, monkeypatch, planned):
    import builtins
    from scripts import isae_suite_ae3
    rows = [dict(deepcopy(row), result=None) for row in planned if row['execution_route'] == 'worker'][:2]
    source_catalog = catalog()
    pins = RUNNER.code_pins(ROOT, ['ae3'])
    report = dict(repository=source_catalog['repository'], revision=source_catalog['revision'], runtime={},
                  current_code_unchanged=True, jobs=rows, code_sha256=pins)
    plan = dict(catalog=source_catalog, jobs=[{k:v for k,v in row.items() if k != 'result'} for row in rows],
                runtime={}, code_sha256=pins)
    for name, value in [('report', report), ('catalog', source_catalog), ('plan', plan)]:
        (tmp_path/(name+'.json')).write_text(json.dumps(value))
    actual_plan = isae_suite_ae3.plan; calls = []
    def counted(root):
        calls.append(root)
        return actual_plan(root)
    monkeypatch.setattr(isae_suite_ae3, 'plan', counted)
    monkeypatch.setattr(isae_suite_ae3, 'verify_reference_sources',
                        lambda *args: pytest.fail('Repeated per-job source reconstruction'))
    actual_import = builtins.__import__
    def guarded(name, *args, **kwargs):
        assert not name.startswith(('openswing', 'numpy', 'scipy'))
        return actual_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    merged = SUMMARY.load_runs([tmp_path], ROOT)
    assert calls == [ROOT] and len(merged['jobs']) == 2
    SUMMARY.verify_summary_sources(merged)
    # Editing both report and plan does not establish a new original source state.
    changed_speed = report['jobs'][0]['condition']['speed'] + 1.
    report['jobs'][0]['condition']['speed'] = changed_speed
    plan['jobs'][0]['condition']['speed'] = changed_speed
    for name, value in [('report', report), ('plan', plan)]:
        (tmp_path/(name+'.json')).write_text(json.dumps(value))
    with pytest.raises(ValueError, match='original sources'):
        SUMMARY.load_runs([tmp_path], ROOT)
    assert calls == [ROOT, ROOT]
