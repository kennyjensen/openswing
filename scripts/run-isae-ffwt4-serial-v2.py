"""Run up to four bounded FFWT-4 segments serially, stopping on any failure."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from isae_ffwt4_evidence import pin, read, write

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume-from', type=Path, required=True)
    parser.add_argument('--segments', type=int, default=4, choices=range(1, 5))
    parser.add_argument('--steps', type=int, default=20, choices=range(1, 21))
    parser.add_argument('--limit-seconds', type=int, choices=(60, 90), default=90)
    args = parser.parse_args()
    parent = args.resume_from.resolve()
    root = parent.parent
    journal = root/'serial-terminal.json'
    receipt = read(journal) if journal.exists() else dict(jobs=[])
    environment = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
                       MKL_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
    helper = ROOT/'scripts/verify-isae-ffwt4-time-refinement-v3.py'
    helper_pin, runner_pin = pin(helper), pin(__file__)
    for _ in range(args.segments):
        plan = read(parent/'plan.json')
        start = plan['end_step']
        stop = min(start+args.steps, 199*plan['divisor'])
        if start == stop:
            break
        destination = root/f'd{plan["divisor"]}-s{stop:03d}'
        if destination.exists():
            raise SystemExit('Preserve existing attempt: '+str(destination))
        command = ['nice', '-n', '10', 'timeout', '--kill-after=5s', str(args.limit_seconds)+'s',
                   'prlimit', '--as=536870912', '--', sys.executable, str(helper),
                   '--resume-from', str(parent), '--steps', str(stop-start),
                   '--output-dir', str(destination)]
        assert pin(helper) == helper_pin and pin(__file__) == runner_pin
        print(json.dumps(dict(event='START', folder=destination.name, start=start, end=stop, limit_seconds=args.limit_seconds)), flush=True)
        started = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)
        elapsed = time.monotonic()-started
        record = dict(folder=destination.name, exit_code=result.returncode,
            elapsed_seconds=elapsed, limit_seconds=args.limit_seconds,
            observed_at=datetime.now(timezone.utc).isoformat(), command=command,
            helper=helper_pin, runner=runner_pin, stdout=result.stdout, stderr=result.stderr)
        receipt['jobs'].append(record)
        write(journal, receipt)
        if result.stdout:
            print(result.stdout, end='', flush=True)
        if result.stderr:
            print(result.stderr, end='', file=sys.stderr, flush=True)
        print(json.dumps(dict(event='TERMINAL', folder=destination.name, exit_code=result.returncode)), flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
        report = read(destination/'report.json')
        assert report['status'] == 'SEGMENT_COMPUTED' and report['end_step'] == stop
        assert report['accepted_steps'] == stop-start and report['rejected_steps'] == 0
        assert pin(helper) == helper_pin and pin(__file__) == runner_pin
        parent = destination
    print(json.dumps(dict(event='BATCH_FINISHED', last_segment=str(parent))), flush=True)


if __name__ == '__main__':
    main()

