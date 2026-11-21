"""Run the complete AE-2 audit with checked transaction-local path resolution.

The unchanged digest-cached assessor still performs every source, canonical
input, physical and reference check. Repeated Path.resolve calls reuse only
their pathname result. Every mapping is resolved afresh before the final report
is published; changed symlinks or working directory abort publication.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import assess_isae_ae2_cached as cached


class ResolutionTransaction:
    def __init__(self, fresh):
        self.fresh = fresh
        self.cwd = os.getcwd()
        self.records = {}
        self.calls = 0
        self.hits = 0

    def resolve(self, path, strict=False):
        self.calls += 1
        if not path.is_absolute():
            assert os.getcwd() == self.cwd, 'Audit working directory changed.'
        key = (str(path), bool(strict))
        if key in self.records:
            self.hits += 1
            return self.records[key]
        result = self.fresh(path, strict=strict)
        self.records[key] = result
        return result

    def finish(self):
        assert os.getcwd() == self.cwd, 'Audit working directory changed.'
        for (path, strict), expected in self.records.items():
            assert self.fresh(Path(path), strict=strict) == expected, (
                'Path resolution changed before publication: '+path)
        return [dict(path=path, strict=strict, resolved=str(resolved))
                for (path, strict), resolved in self.records.items()]


def assess(runs, output, recoveries, continuations=()):
    output = output.resolve()
    assert not output.exists()
    candidate = output.with_name(output.stem+'-resolved-candidate.json')
    assert not candidate.exists()
    fresh = Path.resolve
    transaction = ResolutionTransaction(fresh)
    start = time.process_time()
    try:
        Path.resolve = lambda path, strict=False: transaction.resolve(path, strict)
        if continuations:
            cached.assess(runs, candidate, recoveries, continuations)
        else:
            cached.assess(runs, candidate, recoveries)
    finally:
        Path.resolve = fresh
    mappings = transaction.finish()
    report = json.loads(candidate.read_text())
    assert report['status'] == 'CURRENT_SAVED_DATA_AUDIT_PASS'
    assert report['physics_calls'] == report['production_imports'] == 0
    report['resolution_transaction'] = dict(
        driver=cached.adapter._pin(__file__),
        candidate=cached.adapter._pin(candidate),
        observed_utc=datetime.now(timezone.utc).isoformat(),
        calls=transaction.calls, cache_hits=transaction.hits,
        unique_mappings=len(mappings), fresh_verified_mappings=mappings,
        all_mappings_resolved_afresh_before_publication=True,
        cwd_unchanged=True, cpu_seconds=time.process_time()-start,
        source_digest_and_numerical_gates_unchanged=True)
    with output.open('x') as target:
        json.dump(report, target, indent=2, allow_nan=False)
        target.write('\n')
    print(json.dumps(dict(status='PUBLISHED_AFTER_FRESH_PATH_CHECK',
        passed=report['full_scope']['passed'], required=report['full_scope']['required'],
        path_calls=transaction.calls, cache_hits=transaction.hits,
        unique_mappings_rechecked=len(mappings),
        cpu_seconds=time.process_time()-start)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='append', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--recovery', action='append', type=Path, default=[])
    parser.add_argument('--continuation', action='append', type=Path, default=[])
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (15,)*2)
    signal.alarm(60)
    assess(args.run, args.output, args.recovery, args.continuation)
