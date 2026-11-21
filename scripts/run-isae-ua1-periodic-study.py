"""Bounded serial UA-1 studies with pinned inputs and independently reread states."""
import argparse
from dataclasses import asdict
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np

from isae_ua1_periodic_study import Case, GATES, RESTART_SCALE_ULPS, request, reference_history, summarize_grid, assess, check_restart_join
from isae_ua_incidence_reference import trajectory
from isae_ua_periodic import fourier
from isae_ua_artifacts import write_trajectory
from isae_ua2_browser_cutoff import validate_checkpoint

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(ROOT))


def digest(path):
    h = sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024*1024):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False)+'\n')


def verify(pins):
    for name, value in pins.items():
        assert digest(ROOT/name) == value, name


def prepare(args, base):
    case = Case(args.alpha, args.k, args.amplitude)
    assert args.fine == 2*args.coarse
    assert all(case.cycles*n % args.segment_steps == 0 for n in (args.coarse, args.fine))
    assert args.segment_steps >= 3 and args.audit_parts >= 1
    base.mkdir(parents=True, exist_ok=True)
    names = ['isae_ua1_periodic_study.py', 'isae_ua_incidence_reference.py', 'isae_ua_incidence_periodic.py',
             'isae_ua_periodic.py', 'isae_ua_section_reference.py', 'isae_suite_unsteady.py',
             'isae_ua_artifacts.py', 'isae_ua2_browser_cutoff.py']
    paths = [*sorted((ROOT/'openswing').glob('*.py')), SCRIPT,
             *[ROOT/'scripts'/name for name in names], ROOT/'tests/test_isae_ua1_periodic_study.py',
             ROOT/'.reference/asw_theory.txt', ROOT/'.reference/asw_uns_theory.txt',
             ROOT/'docs/validation/isae-ua1-phase-sources-20261101.json',
             ROOT/'artifacts/isae/ua1-incidence-20261101/source-review.json']
    pins = {str(p.relative_to(ROOT)): digest(p) for p in paths}
    plan = dict(case=asdict(case), grids=[args.coarse, args.fine], segment_steps=args.segment_steps,
        audit_parts=args.audit_parts, gates=GATES, time_atol=1e-12, source_sha256=pins,
        restart_scale_roundtrip_max_ulps=RESTART_SCALE_ULPS,
        per_job_timeout_seconds=45, serial=True, threads=1,
        scope='Nonlinear attached-flow section limit, eight continuous cycles from production steady equilibrium',
        normalization='Cold lift/circulation: peak departure from pre-motion steady value. Periodic lift/circulation: peak departure from periodic mean. Rate: reference peak. Every strip participates.',
        full_forcing_before_startup=True, production_changed=False, native_ASWING_comparison=False,
        registered_rows=[line for line in (ROOT/'docs/validation/ISAE_STATUS.md').read_text().splitlines() if line.startswith('| [')])
    write(base/'plan.json', plan)
    shutil.copyfile(ROOT/'docs/validation/ISAE_STATUS.md', base/'status-before.md')
    for p in paths:
        target = base/'frozen-code'/p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)
    started = time.monotonic()
    reference = reference_history(case, args.fine)
    comparisons = {}
    times = [r['time'] for r in reference['cold_rows']]
    for method in ('DOP853', 'Radau'):
        direct = trajectory(times, **case.settings, boundary='steady', method=method)
        differences = {}
        for key in ('circulation', 'circulation_rate', 'CL', 'CF'):
            expected = np.array([r[key] for r in direct['rows']])
            actual = np.array([r[key] for r in reference['cold_rows']])
            differences[key] = float(np.max(abs(actual-expected))/np.max(abs(expected)))
        comparisons[method] = dict(error_fractions=differences, ode_evaluations=direct['ode_evaluations'])
    phase512 = trajectory(np.linspace(0., case.period, 513), **case.settings, boundary='periodic')
    measured = fourier([r['time'] for r in reference['periodic']['rows']],
                       [r['CL'] for r in reference['periodic']['rows']], case.period)
    other = fourier([r['time'] for r in phase512['rows']], [r['CL'] for r in phase512['rows']], case.period)
    harmonic_change = max(abs(measured['mean']-other['mean']),
        *(abs(a['amplitude']-b['amplitude']) for a, b in zip(measured['harmonics'], other['harmonics'])))
    passed = all(value < GATES['reference_agreement_fraction'] for result in comparisons.values()
                 for value in result['error_fractions'].values()) and harmonic_change < 1e-10
    write(base/'reference.json', dict(passed=passed, reference=reference, comparisons=comparisons,
        maximum_harmonic_quadrature_change=harmonic_change, seconds=time.monotonic()-started))
    for steps in plan['grids']:
        write(base/f'request-n{steps}.json', request(case, steps))
    verify(pins)
    print(json.dumps(dict(passed=passed, reference_comparisons=comparisons,
                          harmonic_change=harmonic_change, numerical_jobs_started=0)), flush=True)
    assert passed, 'Preserve failed reference; no production jobs may start'


def segment_name(steps, part):
    return f'n{steps}-part{part:03d}'


def read_completed(base, name):
    receipt = read(base/(name+'-execution.json'))
    assert receipt['exit_code'] == 0, name
    for relative, value in receipt['output_sha256'].items():
        assert digest(base/relative) == value, relative
    verify(receipt.get('origin_sha256', {}))
    return receipt


def check_join(previous, current):
    for key in ('time', 'force', 'circulation_rate', 'frame'):
        assert previous[key] == current[key], key
    assert [s['circulation'] for s in previous['strips']] == [s['circulation'] for s in current['strips']]
    return check_restart_join(previous['restart']['state'], current['restart']['state'])


def adopt_initial(args, base, plan):
    """Reuse an already successful initial segment with complete provenance."""
    origin = args.from_base.resolve()
    old = read(origin/'plan.json')
    assert old['case'] == plan['case'] and old['gates'] == plan['gates']
    assert old['segment_steps'] == plan['segment_steps']
    assert old['grids'] == plan['grids']
    for name, value in plan['source_sha256'].items():
        if name.startswith('openswing/'):
            assert old['source_sha256'][name] == value
    origin_pins = {str((origin/'plan.json').relative_to(ROOT)): digest(origin/'plan.json')}
    for name, value in old['source_sha256'].items():
        frozen = origin/'frozen-code'/name
        assert digest(frozen) == value
        origin_pins[str(frozen.relative_to(ROOT))] = value
    steps = plan['grids'][0]
    assert read(origin/f'request-n{steps}.json') == read(base/f'request-n{steps}.json')
    name = segment_name(steps, 0)
    old_receipt = read_completed(origin, name)
    origin_pins[str((origin/(name+'-execution.json')).relative_to(ROOT))] = digest(origin/(name+'-execution.json'))
    (base/name).mkdir()
    for relative, value in old_receipt['output_sha256'].items():
        assert relative.startswith(name+'/')
        shutil.copyfile(origin/relative, base/relative)
        assert digest(base/relative) == value
        origin_pins[str((origin/relative).relative_to(ROOT))] = value
    verify({**plan['source_sha256'], **origin_pins})
    write(base/(name+'-execution.json'), dict(exit_code=0, status='terminal', kind='verified_retained_initial_segment',
        numerical_reexecution=False, origin_sha256=origin_pins, output_sha256=old_receipt['output_sha256']))
    print(json.dumps(dict(adopted=name, numerical_reexecution=False, unchanged_scientific_modules=136)), flush=True)


def segment(args, base, plan):
    from openswing.bridge import dispatch
    from openswing.time_state import checkpoint
    case = Case(**plan['case'])
    steps, part, size = args.steps, args.part, plan['segment_steps']
    assert steps in plan['grids'] and part in range(case.cycles*steps//size)
    full = read(base/f'request-n{steps}.json')
    assert full == request(case, steps)
    end = case.period*(size*(part+1))/steps
    job = segment_name(steps, part)
    folder = base/job
    folder.mkdir()
    calculation = {**full, 'time': {**full['time'], 'duration': end}}
    parent_pins, previous = {}, None
    if part:
        parent = segment_name(steps, part-1)
        read_completed(base, parent)
        previous = read(base/parent/'endpoint.json')
        saved = read(base/parent/'checkpoint.json')
        assert saved['older'] is not None
        calculation = {key: value for key, value in full.items() if key not in ('condition', 'time')}
        calculation.update(action='resume_time', checkpoint=saved,
            time=dict(duration=end-saved['state']['time'], max_steps=4*case.cycles*steps))
        for path in [base/parent/'checkpoint.json', base/parent/'endpoint.json', base/(parent+'-execution.json')]:
            parent_pins[str(path.relative_to(ROOT))] = digest(path)
    write(folder/'request.json', calculation)
    start = time.monotonic()
    def progress(*values):
        if len(values) == 2 and isinstance(values[0], (int, float)):
            (folder/'progress.json').write_text(json.dumps(dict(time=values[0], steps=values[1], seconds=time.monotonic()-start))+'\n')
    raw = dispatch(calculation, progress=progress)
    elapsed = time.monotonic()-start
    assert raw['converged'] and raw['accepted_steps'] == size and raw['rejected_steps'] == 0
    assert len(raw['snapshots']) == size+1
    last = raw['snapshots'][-1]
    assert abs(last['time']-end) < plan['time_atol']
    final = size*(part+1) == case.cycles*steps
    history = validate_checkpoint(raw, final=final, expected_end=last['time'])
    rounding = check_join(previous, raw['snapshots'][0]) if previous is not None else []
    write_trajectory(folder/'trajectory.json.gz', raw)
    write(folder/'endpoint.json', last)
    write(folder/'checkpoint.json', checkpoint(raw))
    verify({**plan['source_sha256'], **parent_pins})
    maximum_residual = max(s['residual'] for s in raw['snapshots'])
    assert maximum_residual < GATES['normalized_residual']
    report = dict(converged=True, accepted_steps=size, rejected_steps=0, solver_seconds=elapsed,
        maximum_residual=maximum_residual, checkpoint=history, parent_sha256=parent_pins,
        restart_scale_roundoff=rounding,
        requested_end=end, actual_end=last['time'], source_unchanged=True)
    write(folder/'report.json', report)
    print(json.dumps(dict(job=job, seconds=elapsed, maximum_residual=maximum_residual)), flush=True)


def audit_chunk(args, base, plan):
    case = Case(**plan['case'])
    steps, size = args.steps, plan['segment_steps']
    count = case.cycles*steps//size
    first = args.part*plan['audit_parts']
    assert steps in plan['grids'] and first < count
    reference = read(base/'reference.json')['reference']
    finest = plan['grids'][-1]
    rows, inputs, times, rounding = [], {}, [], []
    for part in range(first, min(first+plan['audit_parts'], count)):
        name = segment_name(steps, part)
        receipt = read_completed(base, name)
        inputs.update(receipt.get('origin_sha256', {}))
        inputs.update({str((base/n).relative_to(ROOT)): value for n, value in receipt['output_sha256'].items()})
        inputs[str((base/(name+'-execution.json')).relative_to(ROOT))] = digest(base/(name+'-execution.json'))
        folder = base/name
        with gzip.open(folder/'trajectory.json.gz', 'rt') as stream:
            raw = json.load(stream)
        samples = raw['snapshots']
        assert raw['accepted_steps'] == size and raw['rejected_steps'] == 0 and raw['converged']
        assert len(samples) == size+1 and samples[-1] == read(folder/'endpoint.json')
        validate_checkpoint(raw, final=(part == count-1), expected_end=samples[-1]['time'])
        if part:
            prior_path = base/segment_name(steps, part-1)/'endpoint.json'
            rounding.extend(check_join(read(prior_path), samples[0]))
            inputs[str(prior_path.relative_to(ROOT))] = digest(prior_path)
        report = read(folder/'report.json')
        verify(report['parent_sha256'])
        inputs.update(report['parent_sha256'])
        times.append(report['solver_seconds'])
        for local_index, sample in enumerate(samples):
            index = size*part+local_index
            target = reference['cold_rows'][index*(finest//steps)]
            assert abs(sample['time']-case.period*index/steps) < plan['time_atol']
            if index:
                assert sample['order'] == (1 if index == 1 else 2)
            frame = sample['frame']
            assert max(abs(x) for x in frame['attitude']+frame['rates_body']) < 1e-12
            velocity, acceleration = np.array(frame['velocity_origin_body']), np.array(frame['acceleration_reference_body'])
            position = np.array(frame['position_earth'])
            assert abs(velocity@case.wind+case.speed) < 1e-10
            assert abs(acceleration@case.direction-target['acceleration']) < 1e-10
            if local_index == 0 and part:
                continue
            rows.append(dict(time=sample['time'], CL=float(np.array(sample['force'])@case.direction/(.5*1.225*case.speed**2*200000)),
                circulation=[s['circulation'] for s in sample['strips']], circulation_rate=sample['circulation_rate'],
                heave_velocity=float(velocity@case.direction), heave_position=float(position@case.direction),
                residual=sample['residual'], order=sample['order']))
        del raw, samples
    verify({**plan['source_sha256'], **inputs})
    write(base/f'audit-n{steps}-chunk{args.part:03d}.json', dict(rows=rows, input_sha256=inputs,
        solver_seconds=times, restart_scale_roundoff=rounding, first_part=first, parts=min(plan['audit_parts'], count-first)))
    print(json.dumps(dict(grid=steps, chunk=args.part, audited_states=len(rows))), flush=True)


def combine(base, plan):
    case = Case(**plan['case'])
    reference = read(base/'reference.json')
    assert reference['passed']
    results, inputs, times, rounding = {}, {}, [], []
    for steps in plan['grids']:
        rows = []
        parts = case.cycles*steps//plan['segment_steps']
        for chunk in range((parts+plan['audit_parts']-1)//plan['audit_parts']):
            name = f'audit-n{steps}-chunk{chunk:03d}'
            read_completed(base, name)
            result = read(base/(name+'.json'))
            rows.extend(result['rows'])
            inputs.update(result['input_sha256'])
            inputs[str((base/(name+'.json')).relative_to(ROOT))] = digest(base/(name+'.json'))
            inputs[str((base/(name+'-execution.json')).relative_to(ROOT))] = digest(base/(name+'-execution.json'))
            times.extend(result['solver_seconds'])
            rounding.extend(result['restart_scale_roundoff'])
        results[str(steps)] = summarize_grid(case, steps, rows, reference['reference'], plan['grids'][-1])
    # Chunk readers checked every raw byte. Recheck all pinned outputs here to
    # bind the complete final assessment to the same retained physical history.
    verify({**plan['source_sha256'], **inputs})
    verdict = assess(results[str(plan['grids'][0])], results[str(plan['grids'][1])])
    for path in [base/'plan.json', base/'reference.json']:
        inputs[str(path.relative_to(ROOT))] = digest(path)
    output = dict(**verdict, case=asdict(case), results=results, input_sha256=inputs,
        source_sha256=plan['source_sha256'], audited_unique_snapshots=sum(r['samples'] for r in results.values()),
        solver_seconds=dict(min=min(times), max=max(times), total=sum(times)),
        restart_scale_roundoff=rounding,
        production_changed=False, native_ASWING_comparison=False, browser_validation=False)
    write(base/'audit.json', output)
    print(json.dumps({key: output[key] for key in ('passed', 'checks', 'fine_to_coarse_ratios', 'audited_unique_snapshots')}), flush=True)
    assert output['passed'], 'Accuracy failure retained; do not change acceptance limits'


def run(args, base, plan):
    assert read(base/'reference.json')['passed']
    assert read(base/'prepare-execution.json')['exit_code'] == 0
    jobs = []
    for steps in plan['grids']:
        parts = Case(**plan['case']).cycles*steps//plan['segment_steps']
        for part in range(parts if args.phase == 'production' else (parts+plan['audit_parts']-1)//plan['audit_parts']):
            name = segment_name(steps, part) if args.phase == 'production' else f'audit-n{steps}-chunk{part:03d}'
            jobs.append((name, steps, part))
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
    completed = 0
    for name, steps, part in jobs:
        receipt_path = base/(name+'-execution.json')
        if receipt_path.exists():
            assert args.resume, 'Explicit --resume required for retained results'
            read_completed(base, name)
            continue
        assert not (base/name).exists() and not (base/(name+'.json')).exists(), 'Unreceipted work exists; inspect actual process before recovery'
        command = ['timeout', str(plan['per_job_timeout_seconds'])+'s', sys.executable, str(SCRIPT),
            'segment' if args.phase == 'production' else 'audit-chunk', '--base', str(base), '--steps', str(steps), '--part', str(part)]
        start = time.monotonic()
        print(json.dumps(dict(starting=name)), flush=True)
        with (base/(name+'.log')).open('x') as stream:
            child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
            live = dict(job=name, runner_pid=os.getpid(), child_pid=child.pid, command=command, status='running', start_time_unix=time.time())
            (base/'live-job.json').write_text(json.dumps(live, indent=2)+'\n')
            code = child.wait()
        receipt = dict(**live, exit_code=code, wall_seconds=time.monotonic()-start)
        receipt['status'] = 'terminal'
        if code == 0:
            paths = [base/name/n for n in ['request.json', 'trajectory.json.gz', 'checkpoint.json', 'endpoint.json', 'report.json']] if args.phase == 'production' else [base/(name+'.json')]
            receipt['output_sha256'] = {str(path.relative_to(base)): digest(path) for path in paths}
        write(receipt_path, receipt)
        (base/'live-job.json').write_text(json.dumps(receipt, indent=2)+'\n')
        print(json.dumps(dict(completed=name, exit_code=code, wall_seconds=receipt['wall_seconds'])), flush=True)
        if code != 0:
            raise SystemExit(code if code > 0 else 1)
        completed += 1
        if args.max_new_jobs is not None and completed >= args.max_new_jobs:
            print(json.dumps(dict(status='requested_job_limit', new_jobs=completed)), flush=True)
            return
    write(base/(args.phase+'-complete.json'), dict(completed_jobs=len(jobs), serial=True))
    print(json.dumps(dict(status='all_jobs_terminal', phase=args.phase, completed_jobs=len(jobs))), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'adopt-initial', 'segment', 'run', 'audit-chunk', 'combine'])
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--from-base', type=Path)
    parser.add_argument('--alpha', type=float, default=5.)
    parser.add_argument('--k', type=float, default=.47)
    parser.add_argument('--amplitude', type=float, default=.5)
    parser.add_argument('--coarse', type=int, default=160)
    parser.add_argument('--fine', type=int, default=320)
    parser.add_argument('--segment-steps', type=int, default=80)
    parser.add_argument('--audit-parts', type=int, default=4)
    parser.add_argument('--steps', type=int)
    parser.add_argument('--part', type=int)
    parser.add_argument('--phase', choices=['production', 'audit'], default='production')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--max-new-jobs', type=int)
    args = parser.parse_args()
    if args.max_new_jobs is not None and args.max_new_jobs < 1:
        parser.error('Positive job limit required')
    base = args.base.resolve()
    assert base.is_relative_to(ROOT/'artifacts/isae'), 'Study artifacts belong under artifacts/isae'
    if args.action == 'prepare':
        prepare(args, base)
        return
    plan = read(base/'plan.json')
    assert plan['gates'] == GATES
    verify(plan['source_sha256'])
    if args.action == 'adopt-initial':
        assert args.from_base is not None
        adopt_initial(args, base, plan)
    elif args.action == 'run':
        run(args, base, plan)
    elif args.action == 'segment':
        segment(args, base, plan)
    elif args.action == 'audit-chunk':
        audit_chunk(args, base, plan)
    else:
        combine(base, plan)


if __name__ == '__main__':
    main()
