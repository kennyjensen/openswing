"""Saved-only acceptance of independently rechecked, original AE-2 states.

The failed original process receipt stays immutable. This completes the same
comparison identity, never selects a better branch or adds a second target.
"""
import math
from pathlib import Path

from scripts import isae_suite_aeroelastic as adapter
from scripts.isae_acceptance import apply_reference_acceptance
from scripts.recover_isae_ae2_saved import CHECK_NAMES, ROOT, expected_request, pin, read


def validate_case(job, original, case, checked, terminal, sources, saved, request, expected):
    """Pure contract checks, also exercised with adverse record mutations."""
    assert job['case_id'] == 'AE-2' and job['execution_route'] == 'worker'
    assert original['status'] in ('timeout','process_error')
    assert original['process_reaped'] is True and original['execution_completed'] is True
    assert original['process_exit_code'] != 0
    assert case['original_failed_result'] == original
    # load_runs attaches this independently derived comparison contract after
    # checking the frozen job. It is not part of the original execution input.
    assert case['job'] == {k:v for k,v in job.items()
                           if k not in ('result', '_summary_reference_contract')}
    assert checked['job_id'] == terminal['job_id'] == case['id'] == job['id']
    assert terminal['returncode'] == 0 and terminal['process_reaped'] is True
    assert terminal['supervisor_timeout'] is False
    assert sources['all_pins_checked_before_and_after'] is True
    assert checked['status'] == 'VERIFIED_ORIGINAL_SAVED_EQUILIBRIUM'
    assert checked['original_process_outcome'] == original
    assert checked['operations'] == dict(new_cold_solves=0, fresh_residuals=1)
    assert tuple(c['name'] for c in checked['checks']) == CHECK_NAMES
    assert all(c['passed'] is True for c in checked['checks'])
    assert saved['converged'] is True
    for value in (saved['residual'], checked['fresh_residual']):
        assert isinstance(value, (int,float)) and not isinstance(value,bool)
        assert math.isfinite(value) and 0 <= value <= 1e-12
    assert request == expected and not request.get('initial_state') and 'continuation' not in request
    sensor = saved['sensors'][0]
    values = dict(RY_m=sensor['position_earth'][1], Psi_deg=sensor['heading'],
                  sensor_V_m_s=sensor['speed'], sensor_beta_deg=sensor['beta'])
    assert checked['values'] == values and all(math.isfinite(v) for v in values.values())
    return values


def load_recoveries(paths, jobs, policy):
    lookup = {j['id']:j for j in jobs}; replacements = {}; evidence = []; pins = {}
    def remember(path):
        # Hash each file once during this audit. The assessor rehashes the
        # complete ledger before publishing, so changes still fail acceptance.
        key = str(Path(path).resolve())
        if key in pins:
            return pins[key]
        actual = pin(path)
        pins[actual['path']] = actual
        return actual
    remember(__file__)
    for path in paths:
        out = Path(path).resolve(); plan = read(out/'plan.json'); remember(out/'plan.json')
        for item in plan['pins']: assert remember(item['path']) == item
        for case in plan['cases']:
            folder = out/case['id']
            if not folder.exists(): continue
            assert (folder/'terminal.json').exists(), 'Recovery is still incomplete: '+case['id']
            terminal = read(folder/'terminal.json'); remember(folder/'terminal.json')
            assert terminal['process_reaped'] is True
            if terminal['returncode'] != 0: continue
            assert case['id'] not in replacements, 'Duplicate recovery for one original comparison.'
            job = lookup[case['id']]; original = job['result']
            checked = read(folder/'report.json'); sources = read(folder/'sources-verified.json')
            saved = read(case['result']); request = read(case['request'])
            values = validate_case(job, original, case, checked, terminal, sources,
                                   saved, request, expected_request(job))
            assert sources['plan'] == remember(out/'plan.json')
            assert sources['terminal'] == remember(folder/'terminal.json')
            assert sources['source_files'] == len(plan['pins'])
            assert checked['original_result'] == remember(case['result'])
            assert checked['original_request'] == remember(case['request'])
            result_path = Path(case['result']); stage = result_path.parents[2]
            assert read(result_path.with_name('started.json'))['cold_solve_budget'] == 1
            assert read(stage/'adapter-job.json') == case['job']
            authorization = read(stage/'authorization.json')
            assert authorization['authorized'] is True
            assert authorization['plan_sha256'] == remember(stage/'plan.json')['sha256']
            for path in (result_path.with_name('started.json'), stage/'adapter-job.json', stage/'authorization.json'):
                remember(path)
            assert checked['verifier'] == remember(ROOT/'scripts/recover_isae_ae2_saved.py')
            assert checked['verifier_helper'] == remember(ROOT/'scripts/probe_isae_ae2_cold_stages.py')
            for name in ('report.json','sources-verified.json','started.json'): remember(folder/name)
            checks = adapter._checks(job, values)
            strict = dict(status='computed', numerical_pass=True,
                reference_match=all(c['passed'] for c in checks), reference_checks=checks,
                physical_checks=checked['checks'], completion_route='verified_original_saved_equilibrium',
                original_process_outcome=original, verification_process=terminal,
                worker_report=dict(operations=checked['operations'], fresh_residual=checked['fresh_residual'],
                    solve_seconds=read(case['original_report'])['solve_seconds'] if case['original_report'] else None),
                output_accounting=dict(required=4, reported=4, finite=4, unavailable=0,
                    numerically_valid=4, passed=sum(c['passed'] for c in checks), missing=0))
            replacements[case['id']] = apply_reference_acceptance(strict,
                relative_tolerance=policy['relative_tolerance'], tiny_reference=policy['tiny_reference'])
            evidence.append(dict(job_id=case['id'], plan=str(out/'plan.json'),
                verification=remember(folder/'report.json'), terminal=terminal,
                original_process_outcome=original, fresh_residual=checked['fresh_residual'],
                newly_completed_existing_slots=4, new_independent_targets=0, new_cold_solves=0))
    return replacements, evidence, list(pins.values())
