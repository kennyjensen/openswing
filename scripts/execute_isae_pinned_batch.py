"""Execute a small batch from an existing verified ISAE plan, without rescanning.

The original suite owns workers, numerical checks, deadlines and reports. This
coordinator reuses only terminal job receipts and never restarts incomplete work.
Numerical child limits are applied at process creation, not to catalog metadata.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))


def main(directory, count):
    assert 1 <= count <= 16
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2,)*2)
    spec = importlib.util.spec_from_file_location('original_isae_suite', ROOT/'scripts/run-isae-suite.py')
    suite = importlib.util.module_from_spec(spec); spec.loader.exec_module(suite)
    plan_path = directory/'plan.json'; plan = json.loads(plan_path.read_text())
    policy = plan['execution_policy']
    assert policy['workers'] == 1 and policy['timeout_seconds'] == 25
    assert policy['adapters'] == ['aeroelastic'] and policy['cases'] == ['AE-2']
    assert suite.stable_code(ROOT, plan['code_sha256'])
    assert not any(k == 'openswing' or k.startswith('openswing.') for k in sys.modules)
    results = {}
    for job in plan['jobs']:
        key = hashlib.sha256(job['id'].encode()).hexdigest()[:20]
        folder = directory/'jobs'/key
        result_path, request_path = folder/'result.json', folder/'request.json'
        if not folder.exists(): continue
        # An existing worker directory is never authority to restart a process.
        assert result_path.exists() and request_path.exists(), 'Incomplete job folder: '+str(folder)
        packet = json.loads(request_path.read_text()); result = json.loads(result_path.read_text())
        assert packet == dict(job=job, code_sha256=plan['code_sha256'])
        complete = (result.get('execution_completed') is True and
            (result.get('process_reaped') is True or
             (result.get('execution_kind') == 'inline_blocker_validation' and result.get('subprocess_started') is False)))
        assert complete and result.get('job_id') == job['id']
        results[job['id']] = suite.checked_result(job, result)
    pending = [j['id'] for j in plan['jobs'] if j['id'] not in results]
    assert pending, 'All planned jobs are already terminal.'
    folder = directory/'batches'/f'{len(results):04d}'
    folder.mkdir(parents=True, exist_ok=False)
    limits = dict(address_space_bytes=512*1024**2, cpu_seconds=15, worker_wall_seconds=25, blas_threads=1)
    receipt = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        script_sha256=suite.digest(__file__), plan_sha256=suite.digest(plan_path),
        prior_terminal_jobs=len(results), scheduled=pending[:count], limits=limits,
        method=__doc__, status='STARTED')
    suite.write_json(folder/'started.json', receipt)
    original_spawn = asyncio.create_subprocess_exec
    def child_limits():
        resource.setrlimit(resource.RLIMIT_AS, (limits['address_space_bytes'],)*2)
        resource.setrlimit(resource.RLIMIT_CPU, (limits['cpu_seconds'],)*2)
    async def bounded_spawn(*args, **kwargs):
        assert 'preexec_fn' not in kwargs
        kwargs['preexec_fn'] = child_limits
        kwargs['env'] = dict(kwargs['env'], NUMEXPR_NUM_THREADS='1')
        return await original_spawn(*args, **kwargs)
    asyncio.create_subprocess_exec = bounded_spawn
    before = time.monotonic()
    try:
        args = argparse.Namespace(workers=1, timeout_seconds=25, max_new_jobs=count)
        batch = asyncio.run(suite.execute(plan, directory, args, results))
    finally:
        asyncio.create_subprocess_exec = original_spawn
    assert suite.stable_code(ROOT, plan['code_sha256'])
    assert suite.digest(plan_path) == receipt['plan_sha256']
    report = suite.report(plan, results, ROOT, time.monotonic()-before)
    report['execution_batch'] = batch
    suite.write_json(directory/'report.json', report)
    (directory/'report.md').write_text(suite.markdown(report))
    receipt.update(status='COMPLETE', completed_utc=datetime.now(timezone.utc).isoformat(),
        execution_batch=batch, total_terminal_jobs=len(results),
        cpu_seconds=resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime,
        parent_physics_imports=0)
    suite.write_json(folder/'terminal.json', receipt)
    print(json.dumps({k:report[k] for k in ('jobs_planned','jobs_finished','job_status_counts')}), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--count', type=int, default=8)
    a = p.parse_args(); main(a.directory.resolve(), a.count)
