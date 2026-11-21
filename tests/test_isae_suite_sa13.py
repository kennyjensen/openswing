"""SA13 original figure completeness and blocked-reference integrity."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import isae_suite_sa13 as adapter

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def jobs():
    return adapter.plan(ROOT)


def test_all_original_and_modified_curves_and_gaps_retained(jobs):
    assert len(jobs) == len({j['id'] for j in jobs}) == 8
    assert sum(j['expected_outputs'] for j in jobs) == 612
    assert sum(j['finite_reference_outputs'] for j in jobs) == 476
    assert sum(j['unavailable_reference_outputs'] for j in jobs) == 136
    for kind, finite in [('modified_aswing_figure', 237), ('original_discretization_figure', 239)]:
        selected = [j for j in jobs if j['target_kind'] == kind]
        assert len(selected) == 4
        assert sum(j['expected_outputs'] for j in selected) == 306
        assert sum(j['finite_reference_outputs'] for j in selected) == finite
    special = next(j for j in jobs if j['figure'] == 'r101' and j['variant'] == 'discrete')['observations'][54]
    assert special['source_row_1based'] == 55
    assert special['coordinate'] == .1651234567901235 and special['expected'] is None
    assert all(j['model_path'] is None and j['settings'] is None for j in jobs)
    assert all(len(j['source_context_series']) == 3 for j in jobs)


def test_pressure_identity_retains_unknown_mapping_and_all_reference_slots(jobs):
    job = next(j for j in jobs if j['figure'] == 'pressure' and j['variant'] == 'discrete')
    diagnostic, = job['source_diagnostics']
    assert diagnostic['code'] == 'PRESSURE_OUTPUT_MAPPING_UNRESOLVED'
    assert diagnostic['finite_values'] == 56 and diagnostic['retained_values'] == 103
    assert diagnostic['physical_pressure_match'] is False
    assert diagnostic['maximum_identity_error'] < 2e-12
    assert all(not j['source_diagnostics'] for j in jobs if j is not job)
    result = adapter.validate_blocked(ROOT, job)
    assert len(result['reference_checks']) == 103
    assert sum(c['expected'] is None for c in result['reference_checks']) == 47
    assert not any(c['passed'] or c['predicted'] is not None for c in result['reference_checks'])
    assert result['reference_checks'][1]['expected'] > 100


@pytest.mark.parametrize('change', ['drop', 'claim_pressure_match'])
def test_pressure_diagnostic_cannot_be_removed_or_promoted_to_validation(jobs, change):
    job = next(j for j in jobs if j['figure'] == 'pressure' and j['variant'] == 'discrete')
    result = adapter.validate_blocked(ROOT, job)
    if change == 'drop':
        result['source_diagnostics'] = []
    else:
        result['source_diagnostics'][0]['physical_pressure_match'] = True
    with pytest.raises(ValueError, match='source diagnostic'):
        adapter.validate_result_contract(job, result)


def test_every_target_and_curve_color_against_original_matlab_bytes(jobs):
    # Independent MAT decoding verifies the frozen JSON, including the report's
    # blue modified-ASWING / red original-discretization classification.
    import numpy as np
    from scipy.io import loadmat

    def curves(value):
        if isinstance(value, dict):
            props = value.get('properties', {})
            if 'XData' in props and 'YData' in props:
                yield props
            yield from curves(value.get('children', []))
        elif isinstance(value, (list, tuple, np.ndarray)):
            for child in value:
                yield from curves(child)

    for job in jobs:
        mat = loadmat(ROOT/job['table_path'], simplify_cells=True)
        found = [c for key, value in mat.items() if key.startswith('hgS_') for c in curves(value)
                 if c.get('DisplayName') == job['curve_label']]
        assert len(found) == 1
        curve = found[0]
        assert np.array_equal(curve['Color'], [0, 0, 1] if job['variant'] == 'continuous' else [1, 0, 0])
        xy = list(zip(np.asarray(curve['XData']).ravel(), np.asarray(curve['YData']).ravel()))
        assert len(xy) == job['expected_outputs']
        for (x, y), obs in zip(xy, job['observations'], strict=True):
            assert obs['coordinate_hex'] == (float(x).hex() if np.isfinite(x) else None)
            assert obs['expected_hex'] == (float(y).hex() if np.isfinite(y) else None)
            assert obs['tolerance'] is None and obs['expected_token'] is None


def test_planning_and_all_blockers_import_no_physics_or_numerics():
    program = '''from pathlib import Path
import sys
from scripts import isae_suite_sa13 as s
jobs=s.plan(Path.cwd())
for job in jobs:
 r=s.run(Path.cwd(),job)
 assert s.validate_result_contract(job,r)
 assert r['physical_calls']==0 and r['production_imports']==0
assert not any(n=='openswing' or n.startswith('openswing.') or n in ('numpy','scipy') for n in sys.modules)
print(len(jobs))
'''
    result = subprocess.run([sys.executable, '-c', program], cwd=ROOT,
                            capture_output=True, text=True, timeout=30, check=True)
    assert result.stdout.strip() == '8'


@pytest.mark.parametrize('change', ['value', 'precision', 'coordinate', 'kind', 'route', 'drop_row'])
def test_source_job_tampering_rejected(jobs, change):
    job = deepcopy(jobs[0])
    if change == 'value': job['observations'][0]['expected'] = 123.
    elif change == 'precision': job['observations'][0]['tolerance'] = .01
    elif change == 'coordinate': job['observations'][0]['coordinate'] = 123.
    elif change == 'kind': job['target_kind'] = 'original_discretization_figure'
    elif change == 'route': job['execution_route'] = 'worker'
    else: job['observations'].pop()
    with pytest.raises(ValueError, match='source targets'):
        adapter.validate_blocked(ROOT, job)


def test_changed_original_source_rejected(jobs, monkeypatch):
    original = adapter._pin
    def changed(root, path):
        result = original(root, path)
        if str(path).endswith('.fig'):
            result['sha256'] = '0' * 64
        return result
    monkeypatch.setattr(adapter, '_pin', changed)
    with pytest.raises(ValueError, match='source/helper'):
        adapter.validate_blocked(ROOT, jobs[0])


def test_inventory_addition_rejected_even_after_canonical_cache(jobs, monkeypatch):
    adapter.validate_blocked(ROOT, jobs[0])
    folder = (ROOT/jobs[0]['table_path']).parent
    original = Path.iterdir
    def added(path):
        yield from original(path)
        if path == folder:
            yield path/'additional.asw'
    monkeypatch.setattr(Path, 'iterdir', added)
    with pytest.raises(ValueError, match='inventory'):
        adapter.validate_blocked(ROOT, jobs[0])


@pytest.mark.parametrize('change', ['prediction', 'claim_pass', 'compute', 'physical_call', 'drop_check', 'fill_gap'])
def test_saved_blocked_evidence_cannot_turn_green(jobs, change):
    job = jobs[0]
    result = adapter.validate_blocked(ROOT, job)
    if change == 'prediction': result['reference_checks'][0]['predicted'] = 0.
    elif change == 'claim_pass': result['reference_match'] = True
    elif change == 'compute': result.update(status='computed', numerical_pass=True)
    elif change == 'physical_call': result['physical_calls'] = 1
    elif change == 'drop_check': result['reference_checks'].pop()
    else:
        next(c for c in result['reference_checks'] if c['expected'] is None)['expected'] = 0.
    with pytest.raises(ValueError):
        adapter.validate_result_contract(job, result)


def test_runner_contract_and_accounting(jobs):
    spec = importlib.util.spec_from_file_location('sa13_runner_test', ROOT/'scripts/run-isae-suite.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    sys.path.insert(0, str(ROOT/'scripts'))
    results = {j['id']: runner.checked_result(j, adapter.validate_blocked(ROOT, j)) for j in jobs}
    totals = runner.output_totals(jobs, results)
    assert totals['required'] == totals['reported'] == totals['unavailable'] == 612
    assert totals['finite'] == totals['passed'] == totals['missing'] == 0
    assert all(r['status'] == 'unsupported' and not r['reference_match'] for r in results.values())
    fabricated = deepcopy(results[jobs[0]['id']])
    fabricated.update(status='computed', numerical_pass=True)
    assert runner.checked_result(jobs[0], fabricated)['status'] == 'adapter_contract_failure'
    for status in ('error', 'timeout', 'source_mismatch'):
        fabricated = dict(status=status, numerical_pass=True, physical_calls=1,
                          production_imports=1, reference_checks=[])
        assert runner.checked_result(jobs[0], fabricated)['status'] == 'adapter_contract_failure'


def test_independent_summary_rejects_fabricated_pass_and_preserves_scope(jobs):
    spec = importlib.util.spec_from_file_location('sa13_summary_test', ROOT/'scripts/summarize-isae-suite.py')
    summary = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(summary)
    rows = [dict(j, result=adapter.validate_blocked(ROOT, j)) for j in jobs]
    counts = summary.totals(rows)
    assert counts['required'] == counts['unsupported_required'] == counts['reported_unavailable'] == 612
    assert counts['passed'] == counts['finite'] == 0
    scope = summary.declared_scope(rows)
    assert scope['aswing_figure_series'] == 8
    assert scope['finite_figure_ordinates'] == 476 and scope['unavailable_figure_ordinates'] == 136
    assert scope['original_discretization_finite_ordinates'] == 239
    assert scope['modified_aswing_finite_ordinates'] == 237
    assert scope['unique_model_count'] == 0
    job = deepcopy(rows[0])
    job['result'] = dict(status='computed', numerical_pass=True, reference_match=True,
        reference_checks=[dict(name=o['name'], expected=0., predicted=0., tolerance=0., passed=True)
                          for o in job['observations']])
    with pytest.raises(ValueError, match='SA13'):
        summary.scalar_counts(job)
