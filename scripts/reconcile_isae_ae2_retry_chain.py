"""Reconcile declared retries on an original or previously reconciled AE-2 run.

Resolve each strict result from its recorded artifact location or the prior
strict-file ledger. Never infer a new attempt from a reference value, and never
choose among multiple conflicting provenance paths. This extends report input
resolution; the original retry contract, physical verifier and policy stay fixed.
"""
import argparse
import hashlib
from pathlib import Path
import resource
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import retry_isae_ae2_original as retry
from scripts import reconcile_isae_ae2_retry_results as strict


def raw_path(name, view, base, base_report, attempt_directory=None):
    key = hashlib.sha256(name.encode()).hexdigest()[:20]
    artifact = (Path(view['artifact_root']).parent/'result.json'
                if view.get('artifact_root') else None)
    if attempt_directory is not None:
        path = attempt_directory/'jobs'/key/'result.json'
        assert artifact is not None and path.resolve() == artifact.resolve()
    else:
        ledger = base_report.get('retry_strict_source_reconstruction')
        if ledger is not None:
            matching = [p for p in ledger['strict_files']
                        if Path(p['path']).parent.name == key]
            assert len(matching) == 1, 'Missing or ambiguous strict provenance: '+name
            item = matching[0]
            assert retry.pin(item['path']) == item
            path = Path(item['path'])
            if artifact is not None:
                assert path.resolve() == artifact.resolve(), 'Artifact and strict ledger disagree.'
        else:
            path = artifact if artifact is not None else base.parent/'jobs'/key/'result.json'
    assert path.name == 'result.json' and path.parent.name == key and path.is_file()
    return path.resolve()


def reconcile(out, destination, base=None):
    authorization = retry.checked(out)
    base = Path(authorization['base_snapshot']) if base is None else base
    base_report = retry.read(base/'report.json')
    original_runner = retry.runner
    sources = []

    def strict_runner():
        module = original_runner()
        original_report = module.report

        def report(plan, results, root, elapsed):
            raw_results = {}
            for name, view in results.items():
                attempt = out/'run' if name in authorization['scheduled_jobs'] else None
                path = raw_path(name, view, base, base_report, attempt)
                raw_results[name] = strict.strict_for_view(
                    retry.read(path), view, plan['reference_acceptance'])
                sources.append(retry.pin(path))
            result = original_report(plan, raw_results, root, elapsed)
            result['retry_strict_source_reconstruction'] = dict(
                script=retry.pin(__file__), strict_validator=retry.pin(strict.__file__),
                base_report=retry.pin(base/'report.json'), strict_files=sources,
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
