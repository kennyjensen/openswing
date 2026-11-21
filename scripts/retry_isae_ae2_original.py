"""Retry declared failed AE-2 executions without changing comparison identities.

Original runs remain immutable. One predeclared retry per existing failed slot
is retained regardless of reference agreement. A derived report selects that
attempt, keeps all other slots, and records both execution receipts. The normal
AE-2 assessor still verifies every accepted physical state and reference value.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import execute_isae_ae2_staged as execution
from scripts.recover_isae_ae2_saved import CHECK_NAMES, expected_request


def read(path):
    return json.loads(Path(path).read_text())


def pin(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    assert not path.exists(), 'Preserve prior evidence: '+str(path)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def runner():
    spec = importlib.util.spec_from_file_location('retry_original_suite', ROOT/'scripts/run-isae-suite.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical(job):
    return {k: v for k, v in job.items() if k not in ('result', '_summary_reference_contract')}


def eligible(job, accepted_ids):
    assert job['id'] not in accepted_ids, 'An accepted state cannot be retried for a better reference match.'
    assert job['case_id'] == 'AE-2' and job['execution_route'] == 'worker'
    old = job['result']
    assert old['status'] in ('timeout', 'process_error')
    assert old['execution_completed'] is True and old['process_reaped'] is True
    assert old['process_exit_code'] != 0


def replacement(original, retry, accepted_ids):
    """Reject changed inputs, unfinished work, or attempts to improve a score."""
    eligible(original, accepted_ids)
    assert canonical(original) == canonical(retry), 'Retry changed the original comparison.'
    value = retry['result']
    assert value['status'] in ('computed', 'timeout', 'process_error')
    assert value['execution_completed'] is True and value['process_reaped'] is True
    assert value['execution_kind'] == 'staged_subprocess'
    assert value['reference_acceptance_policy'] == original['result']['reference_acceptance_policy']
    if value['status'] == 'computed':
        assert value['process_exit_code'] == 0 and value['numerical_pass'] is True
        worker = value['worker_report']
        assert worker['operations'] == dict(cold_solves=1, fresh_residuals=1)
        assert tuple(c['name'] for c in worker['checks']) == CHECK_NAMES
        assert all(c['passed'] is True for c in worker['checks'])
        assert value['physical_checks'] == worker['checks']
        residual = worker['fresh_residual']
        assert isinstance(residual, (int, float)) and not isinstance(residual, bool)
        assert math.isfinite(residual) and 0 <= residual <= 1e-12
    else:
        assert value['process_exit_code'] != 0
    # Reference agreement is deliberately not a condition for choosing this
    # predeclared attempt. Numerically valid mismatches must remain mismatches.
    return deepcopy(value)


def prepare(out, base, assessment, names):
    assert not out.exists() and names and len(names) == len(set(names))
    source = read(base/'report.json'); original_plan = read(base/'plan.json')
    prior = read(assessment)
    assert prior['status'] == 'CURRENT_SAVED_DATA_AUDIT_PASS'
    assert any(Path(p['path']) == (base/'report.json').resolve() and p['sha256'] == pin(base/'report.json')['sha256']
               for p in prior['source_inputs'])
    assert runner().stable_code(ROOT, original_plan['code_sha256'])
    accepted = {row['job'] for row in prior['rows']}
    jobs = {j['id']: j for j in source['jobs']}
    for name in names:
        eligible(jobs[name], accepted)
    refs = read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    references = []
    for ref in refs['files']:
        if ref['id'] in ('isae-part-4', 'drela-steady'):
            for kind, field in [('pdf', 'sha256'), ('text', 'text_sha256')]:
                p = pin(ROOT/ref['local_'+kind]); assert p['sha256'] == ref[field]
                references.append(p)
    out.mkdir()
    run = out/'run'; run.mkdir(); (run/'jobs').mkdir()
    for name in ('plan.json', 'catalog.json'):
        (run/name).write_bytes((base/name).read_bytes())
    inputs = [Path(__file__), Path(execution.__file__), base/'plan.json', base/'catalog.json',
              base/'report.json', assessment, ROOT/'docs/validation/aswing-authoritative-sources.json']
    write(out/'authorization.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        method=__doc__, previous_goal_turn='progress: forty original native passes and a common-operator branch check',
        base_snapshot=str(base), prior_assessment=str(assessment), scheduled_jobs=names,
        original_failures={name: jobs[name]['result'] for name in names},
        accepted_before=sorted(accepted), limits=execution.LIMITS, workers=1, blas_threads=1,
        new_reference_slots=0, production_changes=False,
        pins=[pin(p) for p in inputs]+references))
    (out/'progress-before.json').write_bytes((ROOT/'docs/validation/isae-progress/history.json').read_bytes())


def checked(out):
    authorization = read(out/'authorization.json')
    assert all(pin(p['path']) == p for p in authorization['pins'])
    base = Path(authorization['base_snapshot'])
    for name in ('plan.json', 'catalog.json'):
        assert (out/'run'/name).read_bytes() == (base/name).read_bytes()
    return authorization


def run(out, name):
    authorization = checked(out)
    assert name in authorization['scheduled_jobs']
    execution.run(out/'run', name)
    checked(out)


def verify_attempt(job):
    result = job['result']; stage = Path(result['artifact_directory'])
    assert read(stage/'adapter-job.json') == canonical(job)
    proof = result['staged_execution']; terminal = read(stage/'worker-terminal.json')
    assert terminal == proof['terminal']
    assert terminal['process_reaped'] and terminal['returncode'] == result['process_exit_code']
    assert terminal['limits'] == execution.LIMITS
    assert read(stage/'sources-verified.json') == proof['sources']
    assert proof['sources']['all_pins_checked_before_and_after'] is True
    assert proof['sources']['terminal'] == execution.adapter._pin(stage/'worker-terminal.json')
    assert proof['coordinator'] == execution.adapter._pin(execution.__file__)
    pins = result['artifact_files']+read(stage/'plan.json')['pins']
    assert all(execution.adapter._pin(p['path']) == p for p in pins)
    if result['status'] == 'computed':
        assert not terminal['supervisor_timeout']
        execution.verify_saved(job, result)
        request = read(stage/'cases'/job['mesh']/'request.json')
        assert request == expected_request(job) and 'initial_state' not in request
    return [pin(p['path']) for p in pins]


def reconcile(out, destination, base=None):
    authorization = checked(out)
    assert not destination.exists()
    original_base = Path(authorization['base_snapshot'])
    base = original_base if base is None else base
    original = read(base/'report.json'); retry = read(out/'run/report.json')
    plan = read(base/'plan.json')
    assert plan == read(original_base/'plan.json') == read(out/'run/plan.json')
    assert read(base/'catalog.json') == read(out/'run/catalog.json')
    assert original['code_sha256'] == retry['code_sha256'] == plan['code_sha256']
    assert original['runtime'] == retry['runtime'] == plan['runtime']
    for report in (original, retry):
        assert [canonical(j) for j in report['jobs']] == plan['jobs']
        assert report['reference_acceptance'] == plan['reference_acceptance']
    originals = {j['id']: j for j in original['jobs']}
    attempts = {j['id']: j for j in retry['jobs'] if j.get('result') is not None}
    assert set(attempts) == set(authorization['scheduled_jobs']), 'Missing or undeclared retry.'
    results = {j['id']: deepcopy(j['result']) for j in original['jobs'] if j.get('result') is not None}
    receipts, pins = [], []
    for name in authorization['scheduled_jobs']:
        assert originals[name]['result'] == authorization['original_failures'][name]
        results[name] = replacement(originals[name], attempts[name], set(authorization['accepted_before']))
        pins += verify_attempt(attempts[name])
        receipts.append(dict(job_id=name, original=originals[name]['result'], retry=attempts[name]['result'],
                             replaced_existing_slots=originals[name]['expected_outputs'], new_reference_slots=0))
    module = runner()
    assert module.stable_code(ROOT, plan['code_sha256'])
    # The source catalog, conditions, required coordinates, gates and every
    # unaffected result remain exactly the original frozen ones.
    report = module.report(plan, results, ROOT, 0.)
    source_paths = [Path(__file__), out/'authorization.json', base/'plan.json', base/'catalog.json',
                    base/'report.json', out/'run/plan.json', out/'run/catalog.json', out/'run/report.json']
    pins += [pin(p) for p in source_paths]
    pins = list({p['path']: p for p in pins}.values())
    report['execution_batch'] = dict(method=__doc__, sources=pins, retries=receipts,
        attempt_selection='One predeclared retry for an unresolved failed execution, independent of reference agreement.',
        changed_physical_inputs=False, new_reference_slots=0)
    for job in report['jobs']:
        assert canonical(job) == canonical(originals[job['id']])
        if job['id'] not in attempts:
            assert job['result'] == originals[job['id']]['result']
    assert all(pin(p['path']) == p for p in pins)
    assert not any(name == 'openswing' or name.startswith('openswing.') for name in sys.modules)
    destination.mkdir()
    for name in ('plan.json', 'catalog.json'):
        (destination/name).write_bytes((base/name).read_bytes())
    write(destination/'report.json', report)
    (destination/'report.md').write_text(module.markdown(report))
    write(destination/'reconciliation.json', dict(status='DECLARED_RETRIES_RECONCILED',
        observed_utc=datetime.now(timezone.utc).isoformat(), sources=pins,
        report=pin(destination/'report.json'), retries=receipts,
        successful_retries=sum(j['result']['status'] == 'computed' for j in attempts.values()),
        terminal_retries=len(attempts), new_reference_slots=0, original_files_unchanged=True,
        unaffected_comparisons_unchanged=True, production_changes=False))
    print(json.dumps(dict(status='DECLARED_RETRIES_RECONCILED', terminal_retries=len(attempts),
        successful_retries=sum(j['result']['status'] == 'computed' for j in attempts.values()),
        new_reference_slots=0)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'run', 'reconcile'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base', type=Path)
    parser.add_argument('--assessment', type=Path)
    parser.add_argument('--case', action='append', default=[])
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args(); out = args.output.resolve()
    if args.action == 'prepare':
        prepare(out, args.base.resolve(), args.assessment.resolve(), args.case)
    elif args.action == 'run':
        assert len(args.case) == 1
        run(out, args.case[0])
    else:
        reconcile(out, args.destination.resolve(), None if args.base is None else args.base.resolve())
