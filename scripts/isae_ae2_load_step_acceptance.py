"""Verify original cold solves partitioned at accepted load boundaries.

Legacy diagnostics remain immutable. A new, bounded saved-state verification
and the complete original checkpoint chain are required before an original
failed slot can be completed. This module never performs an equilibrium solve.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import recover_isae_ae2_saved as recovery
from scripts import isae_suite_aeroelastic as adapter
from scripts.isae_acceptance import apply_reference_acceptance
from scripts.probe_isae_ae2_cold_trace import read, write

ROUTE = 'original_cold_load_steps_v1'
STATUS = 'COLD_LOAD_STEP_RECOVERY_AUDIT_PASS'


def finite_residual(value):
    assert type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1e-12


def validate_stage(original, request, saved, report, terminal, previous, final):
    """Require the exact preceding checkpoint, never a replacement seed."""
    assert not original.get('initial_state') and 'continuation' not in original
    expected = deepcopy(original)
    options = dict(max_load_steps=1)
    if previous is not None:
        assert previous['continuation_status'] == 'pending'
        options['checkpoint'] = previous['checkpoint']
    expected['continuation'] = options
    assert request == expected
    assert terminal['returncode'] == 0 and terminal['process_reaped'] is True
    assert terminal['supervisor_timeout'] is False
    if final:
        assert saved['continuation_status'] == 'complete' and saved['converged'] is True
        assert report['status'] == 'computed'
        finite_residual(saved['residual']); finite_residual(report['fresh_residual'])
        assert tuple(c['name'] for c in report['checks'][:18]) == recovery.CHECK_NAMES
        assert all(c['passed'] is True for c in report['checks'])
    else:
        assert saved['continuation_status'] == 'pending' and report['status'] == 'pending'
        checkpoint = saved['checkpoint']
        finite_residual(checkpoint['physical_residual'])
        assert report['accepted'] is False
        assert report['boundary_residual'] == checkpoint['physical_residual']
        assert saved['load_fraction'] == report['load_fraction'] == checkpoint['load_fraction']
        old_load = 0 if previous is None else previous['checkpoint']['load_fraction']
        assert old_load < checkpoint['load_fraction'] < 1
        assert checkpoint['accepted_load_steps'] == (1 if previous is None else previous['checkpoint']['accepted_load_steps']+1)
        solver = checkpoint['context']['solver']
        assert solver['physical_residual_target'] == 1e-12
        assert solver['continuation_steps'] == 4
        assert solver['reuse_matrices'] is True and solver['full_structure'] is True


def review_chain(base, name, job, remember):
    def load(path):
        remember(path)
        return read(path)
    legacy = load(base/'plan.json')
    for item in legacy['pins']:
        assert remember(item['path']) == item
    case = next(c for c in legacy['cases'] if c['name'] == name)
    assert case['job'] == job['id'] and case['expected_elements'] == job['expected_elements']
    original = load(case['request'])
    assert original == recovery.expected_request(job)
    folder = base/'cases'/name
    stages = sorted(p for p in folder.iterdir() if p.is_dir())
    assert stages and [p.name for p in stages] == [f'{i:02d}' for i in range(len(stages))]
    previous = None
    for i, stage in enumerate(stages):
        request = load(stage/'request.json'); saved = load(stage/'result.json')
        report = load(stage/'report.json'); terminal = load(stage/'terminal.json')
        load(stage/'started.json')
        validate_stage(original, request, saved, report, terminal, previous, i == len(stages)-1)
        previous = saved
    if 'control_result' in case:
        control = load(case['control_result'])
        assert job['result']['status'] == 'computed'
        # Compare all stored physical coordinates directly, in addition to the
        # old checker's normalized-coordinate and sensor comparisons.
        assert saved['equilibrium_state'] == control['equilibrium_state']
        assert saved['sensors'] == control['sensors']
        assert report['parity']['maximum_coordinate_difference'] == 0
        assert all(v == 0 for v in report['parity']['values'].values())
        assert tuple(c['name'] for c in report['checks'][18:]) == ('control_values', 'control_full_coordinates')
    else:
        assert len(report['checks']) == 18
    return case, stages[-1], saved, report


def prepare(out):
    assert not out.exists()
    legacy = ROOT/'artifacts/isae/ae2-cold-stages-20261110'
    original = ROOT/'artifacts/isae/ae2-beta5-sweeps-current-20261110/report.json'
    jobs = {j['id']:j for j in read(original)['jobs']}
    pins = {}
    def remember(path):
        actual = recovery.pin(path)
        prior = pins.setdefault(actual['path'], actual)
        assert prior == actual
        return actual
    remember(original)
    for path in [__file__, ROOT/'scripts/isae_ae2_continuation_acceptance.py',
                 ROOT/'scripts/recover_isae_ae2_saved.py',
                 ROOT/'scripts/probe_isae_ae2_staged_inverse.py',
                 ROOT/'scripts/probe_isae_ae2_inverse_speed.py']:
        remember(path)
    control = jobs['AE-2-m15_02-b05-ias019-m80']
    review_chain(legacy, 'control19-m80', control, remember)
    job = jobs['AE-2-m15_02-b05-ias018-m160']
    assert job['result']['status'] in ('timeout', 'process_error')
    assert job['result']['process_reaped'] is True and job['result']['execution_completed'] is True
    assert job['result']['process_exit_code'] != 0
    case, final, _, _ = review_chain(legacy, 'cold18-m160', job, remember)
    record = dict(id=job['id'], job={k:v for k,v in job.items() if k != 'result'},
                  original_failed_result=job['result'], request=case['request'],
                  result=str(final/'result.json'), original_report=str(final/'report.json'),
                  chain_name=case['name'])
    write(out/'plan.json', dict(route=ROUTE, observed_utc=datetime.now(timezone.utc).isoformat(),
        legacy_root=str(legacy), original_report=str(original), control_job=control['id'],
        control_name='control19-m80', cases=[record], pins=list(pins.values()),
        limits=dict(address_space_bytes=512*1024**2, cpu_seconds=15, supervisor_seconds=25),
        new_cold_solves=0, fresh_residuals_per_case=1, production_changes=False,
        qualification='Original staged 30-second supervisor receipts remain unchanged. New restore verification uses the current 25-second limit. No new solve or alternate branch is requested.'))
    print('Prepared independent verification of '+job['id'], flush=True)


def collect(out, lookup, policy, remember):
    """Revalidate evidence on every collection, rather than trusting a label."""
    from scripts.isae_ae2_continuation_acceptance import validate
    def load(path):
        remember(path)
        return read(path)
    remember(__file__)
    plan = load(out/'plan.json')
    assert plan['route'] == ROUTE and plan['new_cold_solves'] == 0
    assert plan['fresh_residuals_per_case'] == 1 and plan['production_changes'] is False
    assert plan['limits'] == dict(address_space_bytes=512*1024**2, cpu_seconds=15, supervisor_seconds=25)
    for item in plan['pins']:
        assert remember(item['path']) == item
    legacy = Path(plan['legacy_root'])
    review_chain(legacy, plan['control_name'], lookup[plan['control_job']], remember)
    replacements = {}; evidence = []
    for case in plan['cases']:
        job = lookup[case['id']]
        assert job['id'] not in replacements
        assert case['job'] == {k:v for k,v in job.items() if k not in ('result','_summary_reference_contract')}
        assert case['original_failed_result'] == job['result']
        old, final, saved, _ = review_chain(legacy, case['chain_name'], job, remember)
        assert case['result'] == str(final/'result.json') and case['request'] == old['request']
        folder = out/case['id']
        checked = load(folder/'report.json'); terminal = load(folder/'terminal.json')
        sources = load(folder/'sources-verified.json'); load(folder/'started.json')
        assert sources['all_pins_checked_before_and_after'] is True
        assert sources['plan'] == remember(out/'plan.json')
        assert sources['terminal'] == remember(folder/'terminal.json')
        assert checked['status'] == 'VERIFIED_ORIGINAL_SAVED_EQUILIBRIUM'
        assert checked['operations'] == dict(new_cold_solves=0, fresh_residuals=1)
        assert checked['job_id'] == job['id']
        assert checked['original_process_outcome'] == job['result']
        assert checked['original_result'] == remember(final/'result.json')
        assert checked['original_request'] == remember(case['request'])
        assert checked['verifier'] == remember(ROOT/'scripts/recover_isae_ae2_saved.py')
        assert checked['verifier_helper'] == remember(ROOT/'scripts/probe_isae_ae2_cold_stages.py')
        record = dict(job=job['id'], case=case['chain_name'], status='computed',
                      values=checked['values'], fresh_residual=checked['fresh_residual'])
        validated_case = dict(name=case['chain_name'], job=case['job'], original_process_result=job['result'])
        values = validate(job, validated_case, record, dict(checked, status='computed'),
                          terminal, saved, load(case['request']))
        checks = adapter._checks(job, values)
        strict = dict(status='computed', numerical_pass=True, reference_match=all(c['passed'] for c in checks),
            reference_checks=checks, physical_checks=checked['checks'],
            completion_route='verified_original_cold_continuation',
            original_process_outcome=job['result'], verification_process=terminal,
            worker_report=dict(operations=dict(cold_solves=1,fresh_residuals=1),
                               fresh_residual=checked['fresh_residual'], solve_seconds=None),
            output_accounting=dict(required=4,reported=4,finite=4,unavailable=0,numerically_valid=4,
                                   passed=sum(c['passed'] for c in checks),missing=0))
        replacements[job['id']] = apply_reference_acceptance(strict,
            relative_tolerance=policy['relative_tolerance'], tiny_reference=policy['tiny_reference'])
        evidence.append(dict(job_id=job['id'], route=ROUTE, original_staged_plan=remember(legacy/'plan.json'),
            verification=remember(folder/'report.json'), original_process_outcome=job['result'],
            fresh_residual=checked['fresh_residual'], newly_completed_existing_slots=4,
            new_independent_targets=0, new_equilibrium_solves=0,
            original_staged_supervisor_seconds=read(legacy/'plan.json')['limits']['supervisor_seconds']))
    return replacements, evidence


def audit(out):
    assert not (out/'assessment.json').exists()
    plan = read(out/'plan.json'); original = read(plan['original_report'])
    lookup = {j['id']:j for j in original['jobs']}; pins = {}
    def remember(path):
        item = recovery.pin(path)
        assert pins.setdefault(item['path'],item) == item
        return item
    replacements, evidence = collect(out, lookup, original['reference_acceptance'], remember)
    assert all(recovery.pin(p['path']) == p for p in pins.values())
    write(out/'assessment.json', dict(status=STATUS, observed_utc=datetime.now(timezone.utc).isoformat(),
        production_changes=False, physical_calls=0, production_imports=0,
        source_pins=list(pins.values()), evidence=evidence,
        comparisons={name:r['reference_checks'] for name,r in replacements.items()},
        original_slots_completed=4*len(replacements), new_independent_targets=0))
    print('Audited '+str(len(replacements))+' completed original cold chain(s).', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare','audit'])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    globals()[args.action](args.output.resolve())
