"""UA source provenance and actual production harmonic residual verification."""
from copy import deepcopy
import importlib.util
import math
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import isae_suite_unsteady as ua


@pytest.fixture(scope='module')
def jobs():
    return ua.plan(ROOT)


def test_source_audit_identifies_corrected_2d_ua2_figures():
    audit = ua.audit_sources(ROOT)
    assert audit['literal_models'] == audit['shell_drivers'] == []
    assert audit['native_3D_run_provenance_verified'] is False
    assert [r['circulatory_scale_in_matlab'] for r in audit['ua2']] == [.85, .9, .9]
    assert sum(len(r['observations']) for r in audit['ua2']) == 222
    assert max(r['formula_max_absolute_error']['amplitude'] for r in audit['ua2']) < 1e-14
    assert max(r['formula_max_absolute_error']['phase_deg'] for r in audit['ua2']) < 1e-12


def test_plan_separates_equation_checks_from_native_solver_claims(jobs):
    assert len(jobs) == 5
    assert sum(j['expected_outputs'] for j in jobs if j['case_id'] == 'UA-1') == 148
    assert sum(j['expected_outputs'] for j in jobs if j['case_id'] == 'UA-2') == 222
    for job in jobs[:2]:
        assert job['duplicate_plot_labels_deg'] == [0, 5, 9]
        assert len([r for r in job['observations'] if r['output'] == 'amplitude']) == 60
        assert len([r for r in job['observations'] if r['output'] == 'phase_deg']) == 14
        assert all(r['k'] > 0 for r in job['observations'] if r['output'] == 'phase_deg')
        assert 'A is peak-to-peak displacement, A=2a' in job['normalization']
    assert all(j['execution_route'] == 'unsupported' for j in jobs[2:])


def test_prepared_job_cannot_relax_equation_tolerance(jobs):
    job = deepcopy(jobs[0])
    job['observations'][1]['tolerance'] = 1
    with pytest.raises(ValueError, match='observations'):
        ua.run(ROOT, job)


def test_native_ua2_blocker_does_not_execute_a_substitute_model(jobs, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('No verified UA-2 native run to reproduce')
    monkeypatch.setattr(ua, 'harmonic_response', forbidden)
    result = ua.validate_blocked(ROOT, jobs[2])
    assert ua.validate_result_contract(jobs[2], result)
    assert result['status'] == 'unsupported'
    assert all(c['predicted'] is None and not c['passed'] for c in result['reference_checks'])
    result['status'] = 'computed'
    with pytest.raises(ValueError, match='cannot pass'):
        ua.validate_result_contract(jobs[2], result)


def test_finer_production_mesh_matches_all_ua1_harmonics(jobs):
    result = ua.run(ROOT, jobs[1])
    assert ua.validate_result_contract(jobs[1], result)
    assert result['status'] == 'computed' and result['reference_match']
    assert len(result['reference_checks']) == 74
    assert all(c['passed'] for c in result['reference_checks'])
    assert result['production']['maximum_harmonic_residual'] < 1e-12
    assert result['production']['circulation_unknowns'] == 8
    assert result['production']['matrices_reused']
    assert all(c['relative_tolerance_allowed'] is False for c in result['reference_checks'])


def test_lag_disabled_response_is_not_silently_the_reference_formula(jobs):
    # At k=1/2, C_ASW=(3-i)/5. The normalized upward-heave transfer is
    # pi*(.05-.6i), whereas no lag gives pi*(.25-1i). Apparent mass stays on.
    settings = dict(jobs[0]['settings'], aero_lag=False)
    result = ua.harmonic_response(ROOT, settings, frequencies=(.5,))
    r = result['response'][0]
    actual = complex(r['CL_real'], r['CL_imag'])
    assert actual == pytest.approx(math.pi*(.25-1j), rel=5e-5)
    assert abs(actual - math.pi*(.05-.6j)) > 1


def test_missing_added_mass_is_detected_by_ua1(jobs, monkeypatch):
    from openswing import aero
    original = aero.evaluate_aerodynamics
    def omit_apparent(model, condition, *args, **kwargs):
        result = original(model, condition, *args, **kwargs)
        qs = .5*model.constants[1]*condition.speed**2*model.reference[0][0]
        result['CL'] -= result['apparent_force'][2]/qs
        return result
    monkeypatch.setattr(aero, 'evaluate_aerodynamics', omit_apparent)
    result = ua.run(ROOT, jobs[0])
    assert result['numerical_passed'] and not result['reference_match']
    assert any(not c['passed'] for c in result['reference_checks'] if c['output'] == 'phase_deg')


def test_suite_runner_rejects_a_forged_native_ua2_success(jobs):
    spec = importlib.util.spec_from_file_location('ua_suite_runner', ROOT/'scripts/run-isae-suite.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    job = jobs[2]
    result = ua.run(ROOT, job)
    assert runner.checked_result(job, result)['status'] == 'unsupported'
    result.update(status='computed', numerical_passed=True, reference_match=True)
    for check in result['reference_checks']:
        check.update(predicted=check['expected'], passed=True)
    assessed = runner.checked_result(job, result)
    assert assessed['status'] == 'adapter_contract_failure'
    assert assessed['output_accounting']['passed'] == 0
