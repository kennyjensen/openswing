"""Share import overhead across at most three serial SA-11 diagnostic calls."""
import argparse
import gc
import importlib.util
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('polar', ROOT/'scripts/verify-sa11-whole-beam-polar.py')
POLAR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLAR)


def main():
    assert all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--start', type=int, required=True)
    parser.add_argument('--stop', type=int, required=True)
    args = parser.parse_args()
    assert 0 <= args.start < args.stop <= 19 and args.stop-args.start <= 3
    out = args.output.resolve()
    receipt = out/f'chunk-{args.start}-{args.stop}.json'
    assert not receipt.exists(), receipt
    plan = POLAR.read(out/'plan.json')
    POLAR.STUDY.check(plan['pins'])
    for index in range(args.start, args.stop):
        assert not (out/plan['cases'][index]['id']).exists()
    record = dict(started_utc=POLAR.utc(), indices=list(range(args.start, args.stop)),
                  runner_sha256=POLAR.sha(Path(__file__)), plan_sha256=POLAR.sha(out/'plan.json'),
                  rule='At most three sequential calls, unchanged per-call15s alarm and guards; no concurrent workers. Reuse imports only.')
    start = time.monotonic()
    for index in range(args.start, args.stop):
        POLAR.run(out, index)
        gc.collect()
    record.update(completed_utc=POLAR.utc(), elapsed_seconds=time.monotonic()-start,
                  reports={plan['cases'][index]['id']:POLAR.sha(out/plan['cases'][index]['id']/'report.json') for index in range(args.start,args.stop)})
    POLAR.write(receipt, record)
    print(f'Completed serial chunk {args.start}:{args.stop} in {record["elapsed_seconds"]:.3f}s after imports.', flush=True)


if __name__ == '__main__': main()
