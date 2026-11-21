"""Resume a frozen serial ISAE plan with independently forked cold workers.

Only process launch changes. The original runner's worker, timeout supervisor,
result checker, source/physics hashes and reporting code execute unchanged.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RUNNER_PATH = ROOT/'scripts/run-isae-suite.py'
spec = importlib.util.spec_from_file_location('isae_original_runner', RUNNER_PATH)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
from scripts.isae_fork_launcher import make_launcher, make_server_launcher

PRELOAD_MODULES = ('numpy', 'scipy.linalg', 'scipy.optimize', 'scipy.interpolate',
                   'scipy.sparse.linalg', 'openswing.aero', 'openswing.bridge')


def write_streamed_json(path, value):
    """Keep atomic replacement without building two complete JSON strings."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
    temporary.replace(path)


def read(path):
    with Path(path).open() as stream:
        return json.load(stream)


def pin(path):
    # UserLAnd emulates hardlinks with changing internal symlink targets.
    # Pin the requested logical path and its bytes, not that implementation path.
    path = Path(os.path.abspath(path))
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def load_results(directory, plan):
    results = {}
    for job in plan['jobs']:
        key = hashlib.sha256(job['id'].encode()).hexdigest()[:20]
        folder = directory/'jobs'/key
        output, request = folder/'result.json', folder/'request.json'
        if not output.exists():
            continue
        if not request.exists() or read(request) != {'job': job, 'code_sha256': plan['code_sha256']}:
            raise ValueError('Saved job identity differs')
        result = read(output)
        complete = (result.get('execution_completed') is True and
                    (result.get('process_reaped') is True or
                     (result.get('execution_kind') == 'inline_blocker_validation' and
                      result.get('subprocess_started') is False)))
        if result.get('job_id') != job['id'] or not complete:
            raise ValueError('Saved result is incomplete or belongs to a different job')
        results[job['id']] = runner.checked_result(job, result)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--max-new-jobs', type=int, required=True)
    parser.add_argument('--launch-method', choices=('exec', 'fork', 'forkserver'), default='forkserver')
    parser.add_argument('--benchmark-selection', type=Path,
                        help='Predeclared job ordering for a separate comparison run; all pending targets remain in its plan')
    args = parser.parse_args()
    if args.max_new_jobs < 1:
        parser.error('--max-new-jobs must be positive')
    directory = args.run_dir.resolve()
    plan_pin = pin(directory/'plan.json')
    plan = read(plan_pin['path'])
    policy = plan['execution_policy']
    if policy['workers'] != 1:
        raise ValueError('Only serial frozen plans are supported')
    if read(directory/'catalog.json') != plan['catalog']:
        raise ValueError('Saved catalog differs from the frozen plan')
    if not runner.stable_code(ROOT, plan['code_sha256']):
        raise ValueError('Code differs from the frozen plan')
    inputs = runner.verify_registered_upstream_inputs(ROOT, plan['jobs'], plan['catalog']['revision'])
    if inputs != plan['verified_registered_upstream_inputs']:
        raise ValueError('Registered upstream inputs differ from the frozen plan')
    limits = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')
    if any(os.environ.get(key) != '1' for key in limits):
        raise ValueError('Set all three BLAS thread limits to one before starting Python')
    helpers = [pin(__file__), pin(ROOT/'scripts/isae_fork_launcher.py')]
    runner.write_json = write_streamed_json
    receipts = directory/'launches'
    receipts.mkdir(exist_ok=True)
    receipt_path = receipts/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    record = dict(started_utc=datetime.now(timezone.utc).isoformat(),
        launcher_pid=os.getpid(), launch_method=args.launch_method, helpers=helpers, plan=plan_pin,
        max_new_jobs=args.max_new_jobs, parent_physical_solver_calls=0,
        worker_entrypoint='Unmodified scripts/run-isae-suite.py:worker',
        worker_timeout_seconds=policy['timeout_seconds'], workers=1,
        qualification='Import reuse only; every physical call runs in its own process. Original numerical gates and cold-job inputs are unchanged.')
    runner.write_json(receipt_path, record)
    results = load_results(directory, plan)
    execution_plan = plan
    if args.benchmark_selection is not None:
        if results:
            raise ValueError('A benchmark must start in an empty run directory')
        selection = read(args.benchmark_selection)
        if selection['source_plan']['sha256'] != plan_pin['sha256']:
            raise ValueError('Benchmark selection belongs to a different frozen plan')
        ids = [item['id'] for item in selection['jobs']]
        indexed = {job['id']:job for job in plan['jobs']}
        if len(ids) != len(set(ids)) or not set(ids) <= set(indexed) or args.max_new_jobs != len(ids):
            raise ValueError('Invalid benchmark selection')
        execution_plan = dict(plan, jobs=[indexed[key] for key in ids] +
                              [job for job in plan['jobs'] if job['id'] not in set(ids)])
        record['benchmark_selection'] = pin(args.benchmark_selection)
    started = time.monotonic()
    if args.launch_method == 'fork':
        for module in PRELOAD_MODULES:
            importlib.import_module(module)
        record['preload_seconds'] = time.monotonic()-started
        record['preloaded_solver_modules'] = sorted(name for name in sys.modules
                                                   if name == 'openswing' or name.startswith('openswing.'))
        record['parent_threads'] = len(os.listdir('/proc/self/task'))
        record['parent_maximum_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        record['parent_memory_status'] = [line for line in Path('/proc/self/status').read_text().splitlines()
                                          if line.startswith(('VmSize:', 'VmRSS:'))]
        if record['parent_threads'] != 1:
            raise RuntimeError('Preloading created threads; refuse to fork')
        runner.asyncio.create_subprocess_exec = make_launcher(runner.worker, RUNNER_PATH)
    elif args.launch_method == 'forkserver':
        runner.asyncio.create_subprocess_exec = make_server_launcher(RUNNER_PATH, PRELOAD_MODULES)
        record['preload_seconds'] = None
        record['preload_timing_note'] = 'Clean server starts lazily; import time is included in the first worker duration.'
        record['parent_preloaded_solver_modules'] = sorted(name for name in sys.modules
            if name == 'openswing' or name.startswith('openswing.'))
        record['parent_memory_status'] = [line for line in Path('/proc/self/status').read_text().splitlines()
                                         if line.startswith(('VmSize:', 'VmRSS:'))]
    else:
        record['preload_seconds'] = 0.
    runner.write_json(receipt_path, record)
    print(json.dumps(dict(event='READY', launch_method=args.launch_method,
                          preload_seconds=record['preload_seconds'], resumed=len(results))), flush=True)
    batch_args = argparse.Namespace(workers=1, timeout_seconds=policy['timeout_seconds'],
                                    max_new_jobs=args.max_new_jobs)
    batch = None
    try:
        batch = asyncio.run(runner.execute(execution_plan, directory, batch_args, results))
    finally:
        if pin(directory/'plan.json') != plan_pin or any(pin(p['path']) != p for p in helpers):
            raise ValueError('Plan or launcher changed during execution')
        if ('benchmark_selection' in record and
                pin(record['benchmark_selection']['path']) != record['benchmark_selection']):
            raise ValueError('Benchmark selection changed during execution')
        report = runner.report(plan, results, ROOT, time.monotonic()-started)
        if batch is not None:
            report['execution_batch'] = batch
        record.update(finished_utc=datetime.now(timezone.utc).isoformat(),
                      elapsed_seconds=time.monotonic()-started, jobs_finished=len(results), batch=batch)
        runner.write_json(receipt_path, record)
        report['execution_launcher'] = pin(receipt_path)
        runner.write_json(directory/'report.json', report)
        (directory/'report.md').write_text(runner.markdown(report))
    print(json.dumps({key:report[key] for key in
                      ('status','jobs_planned','jobs_finished','job_status_counts','seconds')}), flush=True)
    raise SystemExit(0 if report['full_suite_validated'] and report['current_code_unchanged'] else 1)


if __name__ == '__main__':
    main()
