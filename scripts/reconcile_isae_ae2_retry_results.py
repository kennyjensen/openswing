"""Reconcile retries from original strict result files, applying policy once.

The first metadata-only reconciliation attempted to feed already policy-adjusted
report views back to the strict report writer. Its guard rejected that operation
before publishing. Preserve that coordinator and its execution source pins;
this wrapper supplies the original raw results after exact view-reproduction
checks. It performs no physical calculation and changes no acceptance rule.
"""
import argparse
from pathlib import Path
import hashlib
import resource
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import retry_isae_ae2_original as retry
from scripts.isae_acceptance import apply_reference_acceptance


def strict_for_view(raw, view, policy):
    assert 'reference_acceptance_policy' not in raw
    reproduced = apply_reference_acceptance(raw,
        relative_tolerance=policy['relative_tolerance'], tiny_reference=policy['tiny_reference'])
    assert reproduced == view, 'Raw result does not reproduce the frozen comparison view.'
    return raw


def reconcile(out, destination, base=None):
    authorization = retry.checked(out)
    base = Path(authorization['base_snapshot']) if base is None else base
    original_runner = retry.runner
    sources = []

    def strict_runner():
        module = original_runner()
        original_report = module.report

        def report(plan, results, root, elapsed):
            raw_results = {}
            for name, view in results.items():
                directory = out/'run' if name in authorization['scheduled_jobs'] else base.parent
                folder = directory/'jobs'/hashlib.sha256(name.encode()).hexdigest()[:20]
                path = folder/'result.json'
                raw_results[name] = strict_for_view(retry.read(path), view, plan['reference_acceptance'])
                sources.append(retry.pin(path))
            result = original_report(plan, raw_results, root, elapsed)
            result['retry_strict_source_reconstruction'] = dict(
                script=retry.pin(__file__), strict_files=sources,
                policy_views_reproduced_exactly=True, policy_applications=1,
                physical_calls=0, note=__doc__)
            return result

        module.report = report
        return module

    retry.runner = strict_runner
    try:
        retry.reconcile(out, destination, base)
    finally:
        retry.runner = original_runner
    assert all(retry.pin(p['path']) == p for p in sources)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--base', type=Path)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (15,)*2)
    signal.alarm(60)
    reconcile(args.output.resolve(), args.destination.resolve(),
              None if args.base is None else args.base.resolve())
