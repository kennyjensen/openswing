"""Reassess retained UA-1 histories, distinguishing resume records from steps."""
import argparse
import gzip
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np

from isae_ua1_periodic_study import Case, GATES, summarize_grid, assess
from isae_ua1_periodic_boundary import check_boundary
from isae_ua2_browser_cutoff import validate_checkpoint

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).resolve()
spec = importlib.util.spec_from_file_location('ua1_producer', ROOT/'scripts/run-isae-ua1-periodic-study.py')
producer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(producer)
read, write, digest, verify = producer.read, producer.write, producer.digest, producer.verify


def chunk(base, plan, assessment, steps, number):
    case = Case(**plan['case'])
    size = plan['segment_steps']
    parts = case.cycles*steps//size
    first = number*plan['audit_parts']
    assert steps in plan['grids'] and first < parts
    reference = read(base/'reference.json')['reference']
    rows, inputs, times, rounding, boundaries = [], {}, [], [], 0
    for part in range(first, min(first+plan['audit_parts'], parts)):
        name = producer.segment_name(steps, part)
        receipt = producer.read_completed(base, name)
        inputs.update(receipt.get('origin_sha256', {}))
        inputs.update({str((base/n).relative_to(ROOT)): value for n, value in receipt['output_sha256'].items()})
        inputs[str((base/(name+'-execution.json')).relative_to(ROOT))] = digest(base/(name+'-execution.json'))
        folder = base/name
        with gzip.open(folder/'trajectory.json.gz', 'rt') as stream:
            raw = json.load(stream)
        samples = raw['snapshots']
        assert raw['converged'] and raw['accepted_steps'] == size and raw['rejected_steps'] == 0
        assert len(samples) == size+1 and samples[-1] == read(folder/'endpoint.json')
        validate_checkpoint(raw, final=(part == parts-1), expected_end=samples[-1]['time'])
        if part:
            prior = base/producer.segment_name(steps, part-1)
            rounding.extend(producer.check_join(read(prior/'endpoint.json'), samples[0]))
            rounding.extend(check_boundary(read(prior/'checkpoint.json'), samples))
            boundaries += 1
            for path in [prior/'endpoint.json', prior/'checkpoint.json']:
                inputs[str(path.relative_to(ROOT))] = digest(path)
        report = read(folder/'report.json')
        verify(report['parent_sha256'])
        inputs.update(report['parent_sha256'])
        times.append(report['solver_seconds'])
        for local_index, sample in enumerate(samples):
            index = size*part+local_index
            target = reference['cold_rows'][index*(plan['grids'][-1]//steps)]
            assert abs(sample['time']-case.period*index/steps) < plan['time_atol']
            # The duplicate initial record has already passed the physical and
            # accepted-history join checks above. It is not a new time step.
            if local_index == 0 and part:
                continue
            if index:
                assert sample['order'] == (1 if index == 1 else 2)
            frame = sample['frame']
            assert max(abs(x) for x in frame['attitude']+frame['rates_body']) < 1e-12
            velocity = np.array(frame['velocity_origin_body'])
            acceleration = np.array(frame['acceleration_reference_body'])
            position = np.array(frame['position_earth'])
            assert abs(velocity@case.wind+case.speed) < 1e-10
            assert abs(acceleration@case.direction-target['acceleration']) < 1e-10
            rows.append(dict(time=sample['time'], CL=float(np.array(sample['force'])@case.direction/(.5*1.225*case.speed**2*200000)),
                circulation=[s['circulation'] for s in sample['strips']], circulation_rate=sample['circulation_rate'],
                heave_velocity=float(velocity@case.direction), heave_position=float(position@case.direction),
                residual=sample['residual'], order=sample['order']))
        del raw, samples
    verify({**plan['source_sha256'], **assessment['source_sha256'], **inputs})
    write(base/'audit-r1'/f'audit-n{steps}-chunk{number:03d}.json', dict(rows=rows, input_sha256=inputs,
        solver_seconds=times, restart_scale_roundoff=rounding, boundary_history_checks=boundaries,
        first_part=first, parts=min(plan['audit_parts'], parts-first)))
    print(json.dumps(dict(grid=steps, chunk=number, audited_states=len(rows), boundary_history_checks=boundaries)), flush=True)


def combine(base, plan, assessment):
    case = Case(**plan['case'])
    reference = read(base/'reference.json')
    assert reference['passed']
    directory = base/'audit-r1'
    results, inputs, times, rounding, boundaries = {}, {}, [], [], 0
    for steps in plan['grids']:
        rows = []
        parts = case.cycles*steps//plan['segment_steps']
        for number in range((parts+plan['audit_parts']-1)//plan['audit_parts']):
            name = f'audit-n{steps}-chunk{number:03d}'
            receipt = read(directory/(name+'-execution.json'))
            assert receipt['exit_code'] == 0 and digest(directory/(name+'.json')) == receipt['report_sha256']
            report = read(directory/(name+'.json'))
            rows.extend(report['rows'])
            inputs.update(report['input_sha256'])
            times.extend(report['solver_seconds'])
            rounding.extend(report['restart_scale_roundoff'])
            boundaries += report['boundary_history_checks']
            for path in [directory/(name+'.json'), directory/(name+'-execution.json')]:
                inputs[str(path.relative_to(ROOT))] = digest(path)
        results[str(steps)] = summarize_grid(case, steps, rows, reference['reference'], plan['grids'][-1])
    assert boundaries == sum(case.cycles*n//plan['segment_steps']-1 for n in plan['grids'])
    pins = {**plan['source_sha256'], **assessment['source_sha256']}
    for path in [base/'plan.json', base/'reference.json', directory/'assessment.json',
                 base/'audits-attempt01-execution.json', base/'audit-n160-chunk000.log', base/'audit-order-diagnostic.json']:
        inputs[str(path.relative_to(ROOT))] = digest(path)
    verify({**pins, **inputs})
    verdict = assess(results[str(plan['grids'][0])], results[str(plan['grids'][1])])
    output = dict(**verdict, case=plan['case'], results=results, input_sha256=inputs, source_sha256=pins,
        audited_unique_snapshots=sum(r['samples'] for r in results.values()), boundary_history_checks=boundaries,
        solver_seconds=dict(min=min(times), max=max(times), total=sum(times)), restart_scale_roundoff=rounding,
        production_changed=False, numerical_reexecution=False, native_ASWING_comparison=False, browser_validation=False)
    write(base/'audit.json', output)
    print(json.dumps({key: output[key] for key in ['passed', 'checks', 'fine_to_coarse_ratios', 'audited_unique_snapshots', 'boundary_history_checks']}), flush=True)
    if not output['passed']:
        raise SystemExit(1)


def run(base, plan, directory):
    assert read(base/'production-execution.json')['exit_code'] == 0
    assert read(base/'audits-attempt01-execution.json')['exit_code'] == 1
    paths = [SCRIPT, ROOT/'scripts/isae_ua1_periodic_boundary.py', ROOT/'tests/test_isae_ua1_periodic_boundary.py',
             ROOT/'artifacts/isae/ua1-periodic-study-preparation-20261102/boundary-tests-execution.json']
    assert read(paths[-1])['exit_code'] == 0
    directory.mkdir()
    pins = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    assessment = dict(source_sha256=pins, gates=GATES, numerical_reexecution=False,
        reason='A resumed duplicate initial display record has order zero but retains its accepted BDF2 history. Check both physical predecessors before excluding that duplicate from integrated-step order assertions.')
    write(directory/'assessment.json', assessment)
    for path in paths:
        target = directory/'frozen-code'/path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
    completed = 0
    for steps in plan['grids']:
        parts = Case(**plan['case']).cycles*steps//plan['segment_steps']
        for number in range((parts+plan['audit_parts']-1)//plan['audit_parts']):
            name = f'audit-n{steps}-chunk{number:03d}'
            command = ['timeout', '45s', sys.executable, str(SCRIPT), 'chunk', '--base', str(base), '--steps', str(steps), '--part', str(number)]
            start = time.monotonic()
            print(json.dumps(dict(starting=name)), flush=True)
            with (directory/(name+'.log')).open('x') as stream:
                child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
                live = dict(job=name, runner_pid=os.getpid(), child_pid=child.pid, status='running')
                (directory/'live-job.json').write_text(json.dumps(live)+'\n')
                code = child.wait()
            receipt = dict(**live, exit_code=code, wall_seconds=time.monotonic()-start)
            receipt['status'] = 'terminal'
            if code == 0:
                receipt['report_sha256'] = digest(directory/(name+'.json'))
            write(directory/(name+'-execution.json'), receipt)
            (directory/'live-job.json').write_text(json.dumps(receipt)+'\n')
            print(json.dumps(receipt), flush=True)
            if code != 0:
                raise SystemExit(code if code > 0 else 1)
            completed += 1
    print(json.dumps(dict(completed_audit_chunks=completed, numerical_reexecution=False)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run', 'chunk', 'combine'])
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--steps', type=int)
    parser.add_argument('--part', type=int)
    args = parser.parse_args()
    base = args.base.resolve()
    assert base.is_relative_to(ROOT/'artifacts/isae')
    plan = read(base/'plan.json')
    assert plan['gates'] == GATES
    verify(plan['source_sha256'])
    directory = base/'audit-r1'
    if args.action == 'run':
        run(base, plan, directory)
    else:
        assessment = read(directory/'assessment.json')
        verify(assessment['source_sha256'])
        if args.action == 'chunk':
            chunk(base, plan, assessment, args.steps, args.part)
        else:
            combine(base, plan, assessment)


if __name__ == '__main__':
    main()
