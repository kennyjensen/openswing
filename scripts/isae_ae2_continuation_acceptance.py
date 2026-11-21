"""Accept audited, unchanged cold continuations in their original AE-2 slots."""
import math
from pathlib import Path

from scripts import isae_suite_aeroelastic as adapter
from scripts.isae_acceptance import apply_reference_acceptance
from scripts.recover_isae_ae2_saved import CHECK_NAMES, expected_request, pin, read


def validate(job, case, record, checked, terminal, saved, request):
    original = job['result']
    assert original['status'] in ('timeout', 'process_error')
    assert original['process_reaped'] is True and original['execution_completed'] is True
    assert original['process_exit_code'] != 0
    assert case['original_process_result'] == original
    assert case['job'] == {k:v for k,v in job.items() if k not in ('result','_summary_reference_contract')}
    assert record['job'] == job['id'] and record['case'] == case['name']
    assert record['status'] == checked['status'] == 'computed'
    assert terminal['returncode'] == 0 and terminal['process_reaped'] is True
    assert terminal['supervisor_timeout'] is False
    assert saved['continuation_status'] == 'complete' and saved['converged'] is True
    for value in (saved['residual'], checked['fresh_residual'], record['fresh_residual']):
        assert type(value) in (int,float) and math.isfinite(value) and 0 <= value <= 1e-12
    assert tuple(c['name'] for c in checked['checks']) == CHECK_NAMES
    assert all(c['passed'] is True for c in checked['checks'])
    assert request == expected_request(job) and not request.get('initial_state') and 'continuation' not in request
    sensor = saved['sensors'][0]
    values = dict(RY_m=sensor['position_earth'][1], Psi_deg=sensor['heading'],
                  sensor_V_m_s=sensor['speed'], sensor_beta_deg=sensor['beta'])
    assert values == record['values'] == checked['values']
    assert all(math.isfinite(v) for v in values.values())
    return values


def load_continuations(paths, jobs, policy):
    lookup = {j['id']:j for j in jobs}; replacements = {}; evidence = []; pins = {}
    def remember(path):
        key = str(Path(path).resolve())
        if key not in pins:
            pins[key] = pin(key)
        return pins[key]
    remember(__file__)
    for path in paths:
        out = Path(path).resolve(); plan = read(out/'plan.json'); audit = read(out/'assessment.json')
        remember(out/'plan.json'); remember(out/'assessment.json')
        if audit['status'] == 'COLD_LOAD_STEP_RECOVERY_AUDIT_PASS':
            from scripts.isae_ae2_load_step_acceptance import collect
            assert audit['production_changes'] is False and audit['physical_calls'] == 0
            completed, records = collect(out, lookup, policy, remember)
            assert audit['comparisons'] == {name:r['reference_checks'] for name,r in completed.items()}
            assert audit['evidence'] == records
            assert audit['original_slots_completed'] == 4*len(completed)
            assert audit['new_independent_targets'] == 0
            for item in audit['source_pins']:
                assert remember(item['path']) == item
            assert not (replacements.keys() & completed.keys()), 'Duplicate native slots.'
            replacements.update(completed)
            evidence.extend(dict(record, chain_audit=remember(out/'assessment.json')) for record in records)
            continue
        assert audit['status'] == 'COLD_ATTEMPT_DIAGNOSTIC_AUDIT_PASS'
        assert audit['production_changes'] is False and audit['physical_calls'] == 0
        source_paths = set()
        for item in audit['source_pins']:
            assert remember(item['path']) == item
            source_paths.add(item['path'])
        auditor = Path(__file__).with_name('assess_isae_ae2_attempt_boundaries.py')
        assert str(auditor.resolve()) in source_paths
        assert str((out/'plan.json').resolve()) in source_paths
        assert len(audit['controls']) == 4
        assert all(c['maximum_coordinate_difference'] <= 1e-11 for c in audit['controls'])
        assert all(t['process_reaped'] for t in audit['terminals'])
        for record in audit['candidates']:
            if record['status'] != 'computed':
                continue
            name = record['job']; assert name not in replacements
            case = next(c for c in plan['cases'] if c['name'] == record['case'])
            assert 'expected_boundary' not in case
            folder = Path(record['report']).parent
            assert folder.parent == out/'cases'/case['name']
            for item in ('report.json','result.json','terminal.json','request.json','sources-verified.json'):
                assert str((folder/item).resolve()) in source_paths
            checked = read(folder/'report.json'); terminal = read(folder/'terminal.json')
            saved = read(folder/'result.json'); request = read(case['request'])
            assert checked['result'] == remember(folder/'result.json')
            assert checked['original_request'] == remember(case['request'])
            job = lookup[name]
            values = validate(job,case,record,checked,terminal,saved,request)
            checks = adapter._checks(job,values)
            strict = dict(status='computed',numerical_pass=True,reference_match=all(c['passed'] for c in checks),
                reference_checks=checks,physical_checks=checked['checks'],
                completion_route='verified_original_cold_continuation',
                original_process_outcome=job['result'],verification_process=terminal,
                worker_report=dict(operations=dict(cold_solves=1,fresh_residuals=1),
                                   fresh_residual=checked['fresh_residual'],solve_seconds=None),
                output_accounting=dict(required=4,reported=4,finite=4,unavailable=0,numerically_valid=4,
                                       passed=sum(c['passed'] for c in checks),missing=0))
            replacements[name] = apply_reference_acceptance(strict,
                relative_tolerance=policy['relative_tolerance'],tiny_reference=policy['tiny_reference'])
            assert replacements[name]['reference_checks'] == record['comparisons']
            evidence.append(dict(job_id=name,chain_audit=remember(out/'assessment.json'),
                verification=remember(folder/'report.json'),original_process_outcome=job['result'],
                fresh_residual=checked['fresh_residual'],newly_completed_existing_slots=4,new_independent_targets=0))
    return replacements,evidence,list(pins.values())
