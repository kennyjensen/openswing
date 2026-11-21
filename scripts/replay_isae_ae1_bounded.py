"""Run one predeclared AE-1 adapter job with small serial-process limits.

All raw adapter files survive inside the job folder, including failed attempts.
The existing source checks, physical contract and acceptance policy are retained.
"""
import json
import importlib.util
import os
from pathlib import Path
import resource
import signal
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'scripts'))


def checked_result(job, result):
    spec = importlib.util.spec_from_file_location('isae_suite_runner', ROOT/'scripts/run-isae-suite.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner.checked_result(job, result)


def main(folder):
    from scripts import isae_suite_ae1 as adapter
    from scripts.isae_acceptance import apply_reference_acceptance
    assert all(os.environ.get(k) == '1' for k in
               ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'))
    folder = Path(folder).resolve()
    job = json.loads((folder/'job.json').read_text())
    # A new folder is required for every attempt; never overwrite an outcome.
    (folder/'raw').mkdir()
    tempfile.tempdir = str(folder/'raw')
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (15,)*2)
    signal.alarm(25)
    wall, cpu = time.monotonic(), time.process_time()
    result = adapter.run(ROOT, job)
    adapter.validate_result_contract(job, result)
    view = apply_reference_acceptance(checked_result(job, result), relative_tolerance=.05)
    for name, value in [('strict-result', result), ('accepted-result', view)]:
        with (folder/(name+'.json')).open('x') as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write('\n')
    receipt = dict(id=job['id'], status=result['status'],
        physical_checks_passed=sum(c['passed'] for c in result.get('physical_checks', [])),
        physical_checks_required=len(result.get('physical_checks', [])),
        passed=sum(c['passed'] for c in view['reference_checks']), required=job['expected_outputs'],
        wall_seconds=time.monotonic()-wall, cpu_seconds=time.process_time()-cpu,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    with (folder/'receipt.json').open('x') as stream:
        json.dump(receipt, stream, indent=2);stream.write('\n')
    print(json.dumps(receipt), flush=True)
    return 0 if result['status'] in ('computed', 'unsupported') else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1]))
