"""Assess the retained final browser result after the terminal-cutoff assertion."""
import gzip
import json
import math
import os
from pathlib import Path
import shutil
import time

from isae_ua2_browser_cutoff import digest, validate_checkpoint

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT/'artifacts/isae/ua2-incidence-periodic-browser-20261101'
BASE = ORIGINAL/'assessment'


def write(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    started = time.monotonic()
    assert not BASE.exists(), 'Preserve an existing assessment attempt'
    assert not (ORIGINAL/'runner.lock').exists()
    terminal = json.loads((ORIGINAL/'production-execution.json').read_text())
    assert terminal['exit_code'] == 1 and terminal['terminal_chunk_id'] == 'de0b87'
    plan = json.loads((ORIGINAL/'plan.json').read_text())
    plan_hash = digest(ORIGINAL/'plan.json')
    print('Checking frozen source and original request receipts', flush=True)
    assert all(digest(ROOT/name) == value for name, value in plan['source_sha256'].items())
    inputs = {}
    def pin(path):
        inputs[str(path.relative_to(ROOT))] = digest(path)
    pin(ORIGINAL/'plan.json')
    pin(ORIGINAL/'production-execution.json')
    for part in range(329):
        folder = ORIGINAL/'production'/f'part{part:03d}'
        receipt = json.loads((folder/'receipt.json').read_text())
        report = json.loads((folder/'report.json').read_text())
        assert receipt['outcome'] == 'success'
        assert receipt['job'] == report['job'] == plan['jobs'][part]
        assert receipt['plan_sha256'] == report['plan_sha256'] == plan_hash
        assert receipt['output_sha256']['report.json'] == digest(folder/'report.json')
        assert report['segment_passed'] and report['accepted_steps'] == 16 and report['rejected_steps'] == 0
        pin(folder/'receipt.json')
        pin(folder/'report.json')
    failed_folder = ORIGINAL/'production/part329'
    failed_path = failed_folder/'receipt.json'
    failed = json.loads(failed_path.read_text())
    assert failed['outcome'] == 'failed' and 'assert.ok(checkpoint.older)' in failed['error']
    assert failed['job'] == plan['jobs'][329] and failed['plan_sha256'] == plan_hash
    pin(failed_path)
    raw_path = failed_folder/'trajectory.json.gz'
    pin(raw_path)
    with gzip.open(raw_path, 'rt') as stream:
        raw = json.load(stream)
    previous_path = ORIGINAL/'production/part328/trajectory.json.gz'
    prior_receipt = json.loads((previous_path.parent/'receipt.json').read_text())
    assert digest(previous_path) == prior_receipt['output_sha256']['trajectory.json.gz']
    pin(previous_path)
    with gzip.open(previous_path, 'rt') as stream:
        prior = json.load(stream)
    previous = prior['snapshots'][-1]
    assert raw['software_provenance'] == prior['software_provenance']
    del prior
    target_path = ORIGINAL/plan['targets'][329]['path']
    assert digest(target_path) == plan['targets'][329]['sha256']
    pin(target_path)
    target = json.loads(target_path.read_text())
    assert target['job'] == failed['job']
    assert raw['converged'] and raw['accepted_steps'] == 16 and raw['rejected_steps'] == 0
    assert len(raw['snapshots']) == len(target['rows']) == 17
    assert len(raw['software_provenance']['modules']) == 136
    assert all(plan['source_sha256']['openswing/'+name] == value
               for name, value in raw['software_provenance']['modules'].items())
    for key in ('force', 'circulation_rate', 'frame'):
        assert raw['snapshots'][0][key] == previous[key]
    assert [r['circulation'] for r in raw['snapshots'][0]['strips']] == [r['circulation'] for r in previous['strips']]
    print('Checking the final physical samples and accepted BDF2 history', flush=True)
    angle = math.radians(9.)
    heave, wind = [-math.sin(angle), 0., math.cos(angle)], [math.cos(angle), 0., math.sin(angle)]
    dot = lambda a, b: sum(x*y for x, y in zip(a, b))
    qs = .5*1.225*100*10
    rows, maximum = [], 0.
    keys = ('CL', 'force_coefficient', 'circulation', 'circulation_rate',
            'heave_velocity', 'heave_position', 'heave_acceleration')
    for index, (sample, expected) in enumerate(zip(raw['snapshots'], target['rows'])):
        assert sample['time'] == expected['time'] == plan['times'][5264+index]
        assert len(sample['strips']) == 20
        if index:
            assert sample['order'] == 2
        assert math.isfinite(sample['residual']) and sample['residual'] < plan['gates']['normalized_residual']
        assert max(abs(v) for v in sample['frame']['attitude']+sample['frame']['rates_body']) < 1e-12
        assert abs(dot(sample['frame']['velocity_origin_body'], wind)+10) < 1e-10
        row = dict(time=sample['time'], CL=dot(sample['force'], heave)/qs,
            force_coefficient=[v/qs for v in sample['force']],
            circulation=[r['circulation'] for r in sample['strips']],
            circulation_rate=sample['circulation_rate'],
            heave_velocity=dot(sample['frame']['velocity_origin_body'], heave),
            heave_position=dot(sample['frame']['position_earth'], heave),
            heave_acceleration=dot(sample['frame']['acceleration_reference_body'], heave),
            residual=sample['residual'], order=sample['order'])
        for key in keys:
            a = row[key] if isinstance(row[key], list) else [row[key]]
            b = expected[key] if isinstance(expected[key], list) else [expected[key]]
            assert len(a) == len(b)
            for actual, reference in zip(a, b):
                assert math.isfinite(actual) and math.isfinite(reference)
                difference = abs(actual-reference)/max(1., abs(reference))
                assert difference < plan['gates']['CPython_scaled_difference']
                maximum = max(maximum, difference)
        rows.append(row)
    end = plan['times'][-1]
    cutoff = validate_checkpoint(raw, final=True, expected_end=end)
    cp_path = ROOT/'artifacts/isae/ua2-incidence-periodic-20261101-r1/recovery/n640-part51-piece02/trajectory.json.gz'
    cp_review = json.loads((ORIGINAL/'terminal-cutoff-preliminary-review.json').read_text())
    assert digest(cp_path) == next(c['sha256'] for c in cp_review['cases'] if c['label'] == 'CPython')
    pin(cp_path)
    pin(ORIGINAL/'terminal-cutoff-preliminary-review.json')
    with gzip.open(cp_path, 'rt') as stream:
        cp = json.load(stream)
    assert validate_checkpoint(cp, final=True, expected_end=end) == cutoff
    assert cp['snapshots'][-1]['restart']['accepted_method']['coefficients'] == raw['snapshots'][-1]['restart']['accepted_method']['coefficients']
    del cp
    test_receipt = ORIGINAL/'cutoff-validator-tests-execution.json'
    test = json.loads(test_receipt.read_text())
    assert test['exit_code'] == 0 and test['passed_tests'] == 10
    assert all(digest(ROOT/name) == value for name, value in test['source_sha256'].items())
    pin(test_receipt)
    sources = ['scripts/isae_ua2_browser_cutoff.py', 'scripts/assess-isae-ua2-periodic-browser-cutoff.py',
        'scripts/audit-isae-ua2-periodic-browser-cutoff.py', 'scripts/run-isae-ua2-periodic-browser-cutoff-audits.py',
        'scripts/summarize-isae-ua2-periodic-browser.py', 'tests/test_isae_ua2_browser_cutoff.py']
    source_pins = {name: digest(ROOT/name) for name in sources}
    BASE.mkdir()
    (BASE/'production').mkdir()
    for name in ('plan.json', 'periodic-reference.json', 'memory-observations.jsonl'):
        pin(ORIGINAL/name)
        shutil.copyfile(ORIGINAL/name, BASE/name)
    for name in ('targets',):
        (BASE/name).symlink_to(os.path.relpath(ORIGINAL/name, BASE), target_is_directory=True)
    for part in range(329):
        link = BASE/'production'/f'part{part:03d}'
        link.symlink_to(os.path.relpath(ORIGINAL/'production'/link.name, link.parent), target_is_directory=True)
    folder = BASE/'production/part329'
    folder.mkdir()
    shutil.copyfile(raw_path, folder/'trajectory.json.gz')
    assert digest(folder/'trajectory.json.gz') == digest(raw_path)
    record = dict(raw['snapshots'][-1]['restart'])
    version = record.pop('version', 1)
    checkpoint = dict(format='openswing-time-checkpoint', version=version,
        context=raw['snapshots'][-1].get('restart_context', raw['restart_context']), **record)
    write(folder/'checkpoint.json', checkpoint)
    write(folder/'report.json', dict(segment_passed=True, job=plan['jobs'][329], rows=rows,
        accepted_steps=16, rejected_steps=0, worker_seconds=None,
        worker_timing_note='The original assertion occurred before the producer saved this timing; retain it as unknown.',
        maximum_CPython_scaled_difference=maximum, maximum_residual=max(r['residual'] for r in rows),
        software_provenance=raw['software_provenance'], target_sha256=plan['targets'][329]['sha256'],
        plan_sha256=plan_hash, full_periodic_audit='pending', terminal_cutoff=cutoff,
        assessment_from_retained_output=True, numerical_reexecution=False))
    outputs = {name: digest(folder/name) for name in ('trajectory.json.gz', 'checkpoint.json', 'report.json')}
    write(folder/'receipt.json', dict(outcome='success', kind='retained-result-assessment',
        job=plan['jobs'][329], plan_sha256=plan_hash, output_sha256=outputs,
        wall_seconds=failed['wall_seconds'], run_id=failed['run_id'],
        original_failed_receipt=str(failed_path.relative_to(ROOT)), original_failed_receipt_sha256=digest(failed_path),
        numerical_reexecution=False))
    write(BASE/'production-complete.json', dict(kind='retained-result-assessment', computed_jobs=330,
        physical_steps=5280, original_producer_exit_code=1, original_successful_requests=329,
        reassessed_request=329, numerical_reexecution=False, audit_status='pending',
        native_ASWING_comparison=False, full_goal_complete=False))
    result = dict(passed=True, original_plan_sha256=plan_hash, original_producer_exit_code=1,
        original_successful_requests=329, reassessed_request=329, numerical_reexecution=False,
        accepted_steps=16, rejected_steps=0, maximum_CPython_scaled_difference=maximum,
        terminal_cutoff=cutoff, source_sha256=source_pins, input_sha256=inputs,
        original_raw_sha256=digest(raw_path), wall_seconds=time.monotonic()-started,
        physical_gates_unchanged=True, full_periodic_audit_passed=False,
        native_ASWING_comparison=False, full_goal_complete=False)
    write(BASE/'assessment.json', result)
    print(json.dumps({key: result[key] for key in ('passed', 'accepted_steps', 'maximum_CPython_scaled_difference', 'wall_seconds')}))


if __name__ == '__main__':
    main()
