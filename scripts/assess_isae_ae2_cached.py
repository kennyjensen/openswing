"""Run the unchanged AE-2 assessor with transaction-scoped digest reuse.

Only file-pin metadata is cached. Every cached file is freshly read and hashed
again before publication. Equations, comparisons, canonical-input checks and
physical-state acceptance are unchanged. A failed final check leaves only a
candidate audit, never the requested published assessment.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import isae_suite_aeroelastic as adapter


class PinTransaction:
    def __init__(self, fresh):
        self.fresh = fresh
        self.aliases = {}
        self.records = {}
        self.calls = 0
        self.hits = 0

    def with_bytes(self, path):
        self.calls += 1
        key = str(path)
        if key in self.aliases:
            self.hits += 1
            return dict(self.records[self.aliases[key]])
        actual = self.fresh(path)
        canonical = actual['path']
        if canonical in self.records:
            assert self.records[canonical] == actual, 'File changed during audit: '+canonical
        self.records[canonical] = actual
        self.aliases[key] = canonical
        return dict(actual)

    def plain(self, path):
        value = self.with_bytes(path)
        return dict(path=value['path'], sha256=value['sha256'])

    def finish(self):
        for path, expected in self.records.items():
            assert self.fresh(path) == expected, 'File changed before publication: '+path
        return [dict(value) for value in self.records.values()]


def assess(runs, output, recoveries, continuations=()):
    from scripts import assess_isae_ae2_current as original
    from scripts import recover_isae_ae2_saved as recovery
    from scripts import isae_ae2_saved_acceptance as acceptance
    from scripts import isae_ae2_continuation_acceptance as continuation_acceptance
    from scripts import probe_isae_ae2_cold_trace as trace
    assert not output.exists()
    candidate = output.with_name(output.stem+'-candidate.json')
    assert not candidate.exists()
    transaction = PinTransaction(adapter._pin)
    driver = transaction.with_bytes(__file__)
    patches = [(adapter, '_pin', transaction.with_bytes),
               (recovery, 'pin', transaction.plain),
               (acceptance, 'pin', transaction.plain),
               (continuation_acceptance, 'pin', transaction.plain),
               (trace, 'pin', transaction.plain)]
    previous = [(module, name, getattr(module, name)) for module, name, value in patches]
    start = time.process_time()
    try:
        for module, name, value in patches:
            setattr(module, name, value)
        if continuations:
            original.assess(runs, candidate, recoveries, continuations)
        else:
            original.assess(runs, candidate, recoveries)
    finally:
        for module, name, value in previous:
            setattr(module, name, value)
    verified = transaction.finish()
    report = json.loads(candidate.read_text())
    assert report['status'] == 'CURRENT_SAVED_DATA_AUDIT_PASS'
    assert report['physics_calls'] == report['production_imports'] == 0
    report['digest_transaction'] = dict(driver=driver,
        candidate=transaction.fresh(candidate), observed_utc=datetime.now(timezone.utc).isoformat(),
        requested_pins=transaction.calls, cache_hits=transaction.hits,
        distinct_files_rehashed=len(verified), final_fresh_pins=verified,
        all_cached_files_rehashed_before_publication=True,
        cpu_seconds=time.process_time()-start,
        numerical_and_reference_gates_unchanged=True)
    with output.open('x') as target:
        json.dump(report, target, indent=2, allow_nan=False)
        target.write('\n')
    print(json.dumps(dict(status='PUBLISHED_AFTER_FRESH_SOURCE_CHECK',
        passed=report['full_scope']['passed'], required=report['full_scope']['required'],
        pin_calls=transaction.calls, cache_hits=transaction.hits,
        unique_files_rehashed=len(verified), cpu_seconds=time.process_time()-start)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='append', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--recovery', action='append', type=Path, default=[])
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (15,)*2)
    signal.alarm(60)
    assess(args.run, args.output, args.recovery)
