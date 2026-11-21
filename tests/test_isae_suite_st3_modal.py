"""ST3 registration/accounting regressions; synthetic roots are not validation."""
from copy import deepcopy
import importlib.util
import math
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts import isae_suite_st3_modal as adapter
from scripts.isae_acceptance import apply_reference_acceptance


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load('st3_modal_runner', 'scripts/run-isae-suite.py')
SUMMARY = load('st3_modal_summary', 'scripts/summarize-isae-suite.py')


@pytest.fixture(scope='module')
def jobs():
    if not (ROOT / '.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original ISAE archive unavailable')
    return RUNNER.plan_jobs(ROOT, ['st3_modal'])


def synthetic(job, first_hz=3.8):
    modes = []
    # Intentionally unrelated high roots and one inaccurate low root. Selection
    # must use frequency order, never the root nearest each workbook target.
    for hz in (220., first_hz, 24.29, 25.91, 90., 150.):
        for sign in (-1, 1):
            modes.append(dict(index=len(modes), eigenvalue=[0., sign * 2 * math.pi * hz],
                frequency=hz, left_backward_error=1e-15, right_backward_error=2e-15))
    raw = dict(converged=True, frame_mode='fixed', vacuum=False, modes=modes,
        diagnostics=dict(structural_operator='drela-fixed-still-air-v1',
                         method='full_shift_invert', requested_count=12, shift=[-.01, 0.]),
        fluid=dict(density=1.23, mean_velocity_body=[0., 0., 0.]),
        base=dict(converged=True, residual=1e-14, gravity_body=[0., 0., -9.81],
                  structural_nodes=job['nominal'] + 2, structural_elements=job['nominal'] + 1))
    return adapter.assess_bridge(job, raw, 2e-14, 0)


def test_complete_source_scope_and_unrun_accounting(jobs):
    assert len(jobs) == 6
    assert {(j['layup'], j['nominal']) for j in jobs} == {
        (layup, n) for layup in ('0_3_90', 'p15_0', 'm15_0') for n in (64, 128)}
    scope = SUMMARY.declared_scope(jobs)
    assert scope['unique_model_count'] == 3
    assert scope['original_reference_samples'] == scope['qualified_st3_workbook_cells'] == 9
    assert scope['conditional_st3_modal_scalar_slots'] == 18
    assert SUMMARY.totals(jobs)['unrun_required'] == 18
    assert [r['cell'] for r in jobs[-1]['observations']] == ['C15', 'D15', 'E15']
    assert all(j['table_path'].endswith('/Comparaison.xlsx') for j in jobs)
    assert all(r['status'] == 'INCOMPLETE' for r in adapter.mesh_diagnostics(jobs, {}))


def test_default_relative_policy_preserves_strict_precision_evidence(jobs):
    job = jobs[0]
    result = RUNNER.checked_result(job, synthetic(job))
    assert result['status'] == 'computed'
    assert result['output_accounting']['passed'] == 2
    assert [r['mode_index'] for r in result['reference_checks']] == [3, 5, 7]
    view = apply_reference_acceptance(result)
    assert view['reference_match'] is True
    assert view['strict_reference_match'] is False
    assert view['strict_output_accounting']['passed'] == 2
    assert result['output_accounting']['passed'] == 2
    assert SUMMARY.scalar_counts(dict(job, result=view))['passed'] == 3
    strict = apply_reference_acceptance(result, relative_tolerance=0)
    assert SUMMARY.scalar_counts(dict(job, result=strict))['passed'] == 2


@pytest.mark.parametrize('first_hz,default_passes', [(3.85, 3), (3.9, 2)])
def test_requested_five_percent_gate_is_configurable_and_bounded(jobs, first_hz, default_passes):
    job = jobs[0]
    result = RUNNER.checked_result(job, synthetic(job, first_hz))
    default = apply_reference_acceptance(result)
    narrower = apply_reference_acceptance(result, relative_tolerance=.03)
    assert default['reference_acceptance_policy']['relative_tolerance'] == .05
    assert SUMMARY.scalar_counts(dict(job, result=default))['passed'] == default_passes
    assert SUMMARY.scalar_counts(dict(job, result=narrower))['passed'] == 2
    assert default['reference_checks'][0]['exact_decimal_expected'] == '3.7'
    assert default['reference_checks'][0]['strict_passed'] is False


@pytest.mark.parametrize('change', [
    'partial_spectrum', 'selected_nearest_target', 'bad_backward_error', 'nonfinite_pole',
    'frequency_detached', 'vacuum', 'nonzero_flow', 'bad_restoration', 'missing_restoration',
    'wrong_mesh', 'missing_qualifications', 'claim_identity', 'changed_target', 'extra_calls'])
def test_runner_and_summary_reject_corrupted_evidence(jobs, change):
    job = deepcopy(jobs[0])
    result = synthetic(job)
    e = result['numerical_evidence']
    if change == 'partial_spectrum':
        e['modes'].pop()
    elif change == 'selected_nearest_target':
        result['reference_checks'][0]['mode_index'] = 5
    elif change == 'bad_backward_error':
        e['modes'][0]['left_backward_error'] = 1e-3
    elif change == 'nonfinite_pole':
        e['modes'][0]['eigenvalue'][0] = float('nan')
    elif change == 'frequency_detached':
        e['modes'][0]['frequency'] = 3.7
    elif change == 'vacuum':
        e['vacuum'] = True
    elif change == 'nonzero_flow':
        e['mean_velocity'] = [1e-3, 0., 0.]
    elif change == 'bad_restoration':
        e['fresh_residual'] = 1e-3
    elif change == 'missing_restoration':
        del e['fresh_residual']
    elif change == 'wrong_mesh':
        e['structural_nodes'] += 1
        e['structural_elements'] += 1
    elif change == 'missing_qualifications':
        result['qualifications'] = []
    elif change == 'claim_identity':
        result['native_modal_identity_verified'] = True
    elif change == 'changed_target':
        job['observations'][0]['expected'] = 3.8
    elif change == 'extra_calls':
        result['operations']['retries'] = 1
    checked = RUNNER.checked_result(job, result)
    assert checked['status'] == 'adapter_contract_failure'
    assert checked['output_accounting']['numerically_valid'] == 0
    with pytest.raises((ValueError, KeyError)):
        SUMMARY.scalar_counts(dict(job, result=result))


def test_incomplete_mesh_is_not_promoted_and_policy_view_is_supported(jobs):
    pair = jobs[:2]
    result = {j['id']: apply_reference_acceptance(RUNNER.checked_result(j, synthetic(j))) for j in pair}
    assert adapter.mesh_diagnostics(pair, {pair[0]['id']: result[pair[0]['id']]})[0]['status'] == 'INCOMPLETE'
    mesh = adapter.mesh_diagnostics(pair, result)[0]
    assert mesh['status'] == 'PASS' and len(mesh['checks']) == 3
    assert mesh['historical_modal_identity_verified'] is False
    assert SUMMARY.st3_modal_mesh_diagnostics([dict(j, result=result[j['id']]) for j in pair]) == [mesh]


@pytest.mark.parametrize('field', ['passed', 'strict_passed', 'effective_tolerance'])
def test_mesh_diagnostic_rejects_tampered_policy_views(jobs, field):
    pair = jobs[:2]
    results = {j['id']: apply_reference_acceptance(RUNNER.checked_result(j, synthetic(j))) for j in pair}
    check = results[pair[0]['id']]['reference_checks'][0]
    check[field] = not check[field] if isinstance(check[field], bool) else check[field]*2
    with pytest.raises(ValueError, match='relative policy view'):
        adapter.mesh_diagnostics(pair, results)
