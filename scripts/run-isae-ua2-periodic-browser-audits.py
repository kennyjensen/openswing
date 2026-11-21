"""Run browser history audits one at a time with a 45-second worker cap."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/isae/ua2-incidence-periodic-browser-20261101'


def digest(path):
    result = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-new-jobs', type=int)
    args = parser.parse_args()
    if args.max_new_jobs is not None and args.max_new_jobs < 1:
        parser.error('Positive job limit required')
    plan = json.loads((BASE / 'plan.json').read_text())
    assert json.loads((BASE / 'production-complete.json').read_text())['computed_jobs'] == 330
    assert plan['audit_jobs_per_chunk'] == 8
    assert all(digest(ROOT / name) == value for name, value in plan['source_sha256'].items())
    jobs = [(f'audit-chunk{i:03d}', ['chunk', '--index', str(i)]) for i in range(42)]
    jobs.append(('audit', ['combine']))
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
    completed = 0
    for name, arguments in jobs:
        output, receipt, log = (BASE / (name + suffix) for suffix in ('.json', '-execution.json', '.log'))
        if receipt.exists():
            saved = json.loads(receipt.read_text())
            assert saved['exit_code'] == 0 and saved['report_sha256'] == digest(output)
            continue
        assert not output.exists() and not log.exists(), 'Inspect retained live or interrupted audit: ' + name
        command = ['timeout', '45s', sys.executable, str(ROOT / 'scripts/audit-isae-ua2-periodic-browser.py'), *arguments]
        started = time.monotonic()
        print(json.dumps(dict(starting=name)), flush=True)
        with log.open('x') as stream:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
            state = dict(status='running', job=name, runner_pid=os.getpid(), child_pid=process.pid,
                         command=command, start_time_unix=time.time())
            (BASE / 'live-audit.json').write_text(json.dumps(state, indent=2)+'\n')
            code = process.wait()
        state.update(status='terminal', exit_code=code, wall_seconds=time.monotonic()-started)
        if output.exists():
            state['report_sha256'] = digest(output)
        with receipt.open('x') as stream:
            json.dump(state, stream, indent=2)
            stream.write('\n')
        (BASE / 'live-audit.json').write_text(json.dumps(state, indent=2)+'\n')
        print(json.dumps(dict(completed=name, exit_code=code, wall_seconds=state['wall_seconds'])), flush=True)
        if code:
            raise SystemExit(code if code > 0 else 1)
        completed += 1
        if args.max_new_jobs is not None and completed >= args.max_new_jobs:
            return


if __name__ == '__main__':
    main()
