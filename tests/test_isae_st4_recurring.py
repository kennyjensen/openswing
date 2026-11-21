"""Reviewed ST4 counts, overlap rules and invalid-evidence rejection."""
from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import isae_suite_st4_mechanics as adapter
from isae_acceptance import apply_reference_acceptance


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/filename)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


runner = load('st4_runner_test', 'run-isae-suite.py')
summary = load('st4_summary_test', 'summarize-isae-suite.py')
PAPER = ROOT/'artifacts/isae/st4-mechanics-resumed-20261109'
NATIVE = ROOT/'artifacts/isae/st4-native-refinement-20261109/n192'


@pytest.fixture(scope='module')
def jobs():
    return {scope:adapter.plan(ROOT, comparison_scopes=[scope]) for scope in adapter.SCOPES}


def physical_fixture(job):
    base = adapter.read(PAPER/'plan.json'); native = adapter.read(NATIVE/'plan.json')
    states = []
    for state in adapter.state_jobs(job):
        plan, folder = (native, NATIVE) if state['panels'] == 192 else (base, PAPER)
        states.append(adapter.read(folder/f"job-{plan['jobs'].index(state):02d}"/'report.json'))
    if job['comparison_scope'] == 'st4-mechanics':
        reviewed = [r for r in adapter.read(PAPER/'analysis.json')['spectral_rows'] if r['model'] == job['configuration']]
    else:
        index = next(i for i,j in enumerate(native['jobs']) if j['model'] == job['configuration'])
        reviewed = adapter.read(NATIVE/f'verified-{index:02d}.json')['rows']
    mesh, checks = [], []
    for i,(row, evidence) in enumerate(zip(job['observations'], reviewed, strict=True)):
        pair = [s['positive_frequencies_Hz'][i] for s in states]
        predictions = [v*2*math.pi for v in pair] if row['quantity'] == 'frequency_rad_s' else pair
        mesh.append(dict(name=row['name'], predictions=predictions, relative_change=abs(pair[0]/pair[1]-1),
            shape_MAC=evidence['shape_MAC'], mutual_shape_assignment=True,
            discrete_relative=evidence.get('independent_discrete_relative', states[1]['independent_transfer_relative']),
            continuous_relative=evidence['continuous_error_percent']/100 if 'continuous_error_percent' in evidence else None))
        value = adapter.predicted(row, predictions)
        checks.append(dict(row, predicted=value, passed=adapter.strict_pass(row, value)))
    return dict(status='computed', comparison_scope=job['comparison_scope'], states=states, mesh_checks=mesh,
                reference_checks=checks, numerical_pass=adapter.numerical(job, states, mesh), solver_calls=2,
                source_pins_unchanged=True)


def test_explicit_scopes_keep_all_reference_cells(jobs):
    assert adapter.plan(ROOT) == []
    for scope,njobs,total in [('st4-mechanics',24,72), ('st4-native',5,31)]:
        selected = jobs[scope]
        assert len(selected) == njobs and sum(j['expected_outputs'] for j in selected) == total
        assert len(runner.plan_jobs(ROOT, ['st4'], comparison_scopes=[scope])) == njobs
        assert summary.declared_scope(selected)['st4_frequency_targets'] == total
        assert summary.totals(selected)['unrun_required'] == total
    assert next(j for j in jobs['st4-native'] if j['configuration'] == '7d_b48')['expected_outputs'] == 7


@pytest.mark.parametrize('scopes', [['bad'], ['st4-mechanics']*2, list(adapter.SCOPES)])
def test_scopes_cannot_be_combined(scopes):
    with pytest.raises(ValueError, match='overlap'): adapter.plan(ROOT, comparison_scopes=scopes)


def test_reviewed_physical_results_retain_both_counts(jobs):
    for scope,expected in [('st4-mechanics',66), ('st4-native',31)]:
        rows = []
        for job in jobs[scope]:
            raw = physical_fixture(job)
            assert adapter.validate_result_contract(job, raw)
            strict = runner.checked_result(job, raw)
            assert strict['status'] == 'computed', strict.get('contract_error')
            rows.append(dict(job, result=apply_reference_acceptance(strict)))
        assert summary.totals(rows)['passed'] == expected


@pytest.mark.parametrize('other', ['archive','st4-native'])
def test_importer_rejects_overlapping_counts(jobs, other):
    with pytest.raises(ValueError, match='overlapping'):
        summary.merge_runs([dict(report=dict(jobs=jobs['st4-mechanics'])),
                            dict(report=dict(jobs=[dict(case_id='ST-4', comparison_scope=other)]))])


@pytest.mark.parametrize('fault', ['target','prediction','panel','mesh','shape','assignment','matrix','missing_matrix',
                                  'missing_target','continuous','discrete','provenance','nonfinite'])
def test_invalid_native_evidence_rejected(jobs, fault):
    job = jobs['st4-native'][0]; result = physical_fixture(job)
    if fault == 'target': result['reference_checks'][0]['expected'] += 1
    elif fault == 'prediction': result['reference_checks'][0]['predicted'] += 1
    elif fault == 'panel': result['states'][0]['job']['panels'] = 32
    elif fault == 'mesh': result['mesh_checks'][0]['relative_change'] = 0.
    elif fault == 'shape': result['mesh_checks'][0]['shape_MAC'] = .5
    elif fault == 'assignment': result['mesh_checks'][0]['mutual_shape_assignment'] = False
    elif fault == 'matrix': result['states'][0]['pencil_audits'][0]['left'] = .1
    elif fault == 'missing_matrix': result['states'][0]['pencil_audits'].pop()
    elif fault == 'missing_target': result['reference_checks'].pop()
    elif fault == 'continuous': result['mesh_checks'][0]['continuous_relative'] = .01
    elif fault == 'discrete': result['mesh_checks'][0]['discrete_relative'] = .01
    elif fault == 'provenance': result['source_pins_unchanged'] = False
    else: result['states'][0]['checks']['zero_force'] = float('nan')
    with pytest.raises(ValueError): adapter.validate_result_contract(job, result)


def test_failed_job_keeps_required_frequencies(jobs):
    job = next(j for j in jobs['st4-native'] if j['configuration'] == '7d_b48')
    raw = runner.checked_result(job, dict(status='timeout'))
    counts = summary.scalar_counts(dict(job, result=apply_reference_acceptance(raw)))
    assert counts['required'] == counts['failed_job_required'] == 7 and counts['passed'] == 0


def test_new_scope_replaces_old_jobs_without_hiding_other_families(jobs, monkeypatch):
    import isae_suite_modes
    monkeypatch.setattr(isae_suite_modes, 'plan', lambda root:[dict(id='old',case_id='ST-4'),dict(id='keep',case_id='ST-5')])
    planned = runner.plan_jobs(ROOT, ['modes','st4'], comparison_scopes=['st4-native'])
    assert len(planned) == 6 and planned[0]['id'] == 'keep'


def test_helpers_and_original_inputs_pinned(jobs):
    pins = runner.code_pins(ROOT, ['st4'])
    assert all('scripts/'+p in pins for p in (*adapter.EXECUTION_HELPERS,'isae_suite_st4_mechanics.py','summarize-isae-suite.py'))
    changed = deepcopy(jobs['st4-mechanics'][0]); changed['model']['properties']['mgcc'] /= 2
    with pytest.raises(ValueError, match='canonical'): adapter.verify_reference_sources(ROOT, changed)


@pytest.fixture(scope='module')
def prepared(jobs):
    plan = adapter.read(ROOT/'artifacts/isae/st2-mechanics-summary-20261109/full-run/plan.json')
    plan['jobs'] = jobs['st4-mechanics']; plan['code_sha256'] = runner.code_pins(ROOT, ['st4'])
    plan['execution_policy'].update(adapters=['st4'], cases=['ST-4'], comparison_scopes=['st4-mechanics'], timeout_seconds=100.)
    plan['selection_scope'].pop('st2_scope_note')
    plan['selection_scope']['families_without_selected_jobs'] = [c['id'] for c in plan['catalog']['cases'] if c['id'] != 'ST-4']
    return plan, runner.report(plan, {}, ROOT, 0.)


def write_run(folder, plan, report):
    for name,data in [('plan',plan), ('report',report), ('catalog',plan['catalog'])]:
        adapter.save(folder/(name+'.json'), data)


def test_unrun_full_scope_imports_without_physics(prepared, tmp_path):
    write_run(tmp_path, *prepared)
    before = {k for k in sys.modules if k.startswith('openswing')}
    imported = summary.load_runs([tmp_path]); summary.verify_summary_sources(imported)
    assert summary.totals(imported['jobs'])['unrun_required'] == 72
    assert {k for k in sys.modules if k.startswith('openswing')} == before


@pytest.mark.parametrize('fault', ['no_opt_in','missing_helper','changed_source'])
def test_import_rejects_missing_provenance(prepared, tmp_path, fault):
    plan,report = deepcopy(prepared)
    if fault == 'no_opt_in':
        plan['execution_policy']['comparison_scopes'] = []; report['execution_policy'] = deepcopy(plan['execution_policy'])
    elif fault == 'missing_helper':
        plan['code_sha256'].pop('scripts/isae_st4_worker.py'); report['code_sha256'] = deepcopy(plan['code_sha256'])
    else:
        plan['jobs'][0]['source_pins'][0]['bytes'] += 1
        report['jobs'][0]['source_pins'] = deepcopy(plan['jobs'][0]['source_pins'])
    write_run(tmp_path, plan, report)
    with pytest.raises(ValueError): summary.load_runs([tmp_path])
