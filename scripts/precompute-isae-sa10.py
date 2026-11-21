"""Optional parallel cache fill using the exact pinned SA-10 compute function.

The serial driver remains the report writer. Atomic create-only publication
never replaces a cache entry that it has already consumed or computed.
"""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse, hashlib, importlib.util, json, os, sys, time

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / 'scripts'))
from isae_sa10_reference import sha
module_spec = importlib.util.spec_from_file_location('sa10', ROOT / 'scripts/verify-isae-sa10.py')
sa10 = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(sa10)


def execute(task):
    source, specification, directory, helper_hash = task
    key = hashlib.sha256(json.dumps(specification, sort_keys=True).encode()).hexdigest()
    path = Path(directory) / (key + '.json')
    if path.exists():
        row = json.loads(path.read_text()); assert row['specification'] == specification
        return dict(specification=specification, status='already_cached')
    start = time.monotonic()
    try:
        row = dict(specification=specification, status='computed', result=sa10.compute(source, specification))
    except sa10.AnalysisError as exc:
        row = dict(specification=specification, status='rejected', error=str(exc), details=getattr(exc, 'details', None))
    row.update(seconds=time.monotonic()-start, executor=dict(helper_sha256=helper_hash,
        compute_script_sha256=sha(ROOT / 'scripts/verify-isae-sa10.py'),
        meaning='Same independent compute call; parallel create-only cache publication'))
    temporary = path.with_suffix(f'.precompute-{os.getpid()}.tmp')
    temporary.write_text(json.dumps(row, indent=2) + '\n')
    try:
        # link is atomic and fails if either another helper or the main driver won.
        os.link(temporary, path)
        publication = 'published'
    except FileExistsError:
        existing = json.loads(path.read_text()); assert existing['specification'] == specification
        publication = 'existing_entry_preserved'
    finally:
        temporary.unlink()
    return dict(specification=specification, status=row['status'], publication=publication, seconds=row['seconds'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runroot', type=Path, required=True)
    parser.add_argument('--cases', nargs='+', required=True)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args(); assert 1 <= args.workers <= 4
    identity = json.loads((args.runroot / 'identity.json').read_text())
    assert identity['script_sha256'] == sha(ROOT / 'scripts/verify-isae-sa10.py')
    assert identity['reference_script_sha256'] == sha(ROOT / 'scripts/isae_sa10_reference.py')
    assert identity['source_report_sha256'] == sha(ROOT / 'docs/validation/isae-sa10-sources.json')
    assert identity['modules'] == {p.name: sha(p) for p in (ROOT / 'openswing').glob('*.py')}
    helper_hash = sha(Path(__file__)); sources = json.loads((ROOT / 'docs/validation/isae-sa10-sources.json').read_text())
    tasks = []
    cases = [c for c in sa10.case_entries(sources) if c['name'] in args.cases]
    assert len(cases) == len(set(args.cases))
    for case in cases:
        alphas = sorted(set(range(26)) | {r['xy'][0] for r in sources['experimental_lift'].get(case['name'], {}).get('values', [])})
        for panels in [25, 50, 100]:
            for frozen in [False, True]:
                for pg in ['zero', 'speed']:
                    for alpha in alphas:
                        specification = dict(case=case['case_id'], panels=panels, pg=pg, frozen=frozen, alpha=float(alpha))
                        tasks.append((case['source'], specification, str(args.runroot), helper_hash))
    print('START', len(tasks), 'requests,', args.workers, 'process workers', flush=True)
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(execute, task) for task in tasks]
        for future in as_completed(futures):
            row = future.result(); rows.append(row)
            print(json.dumps(row), flush=True)
    output = dict(status='COMPLETE', helper_sha256=helper_hash, identity=identity,
        cases=args.cases, workers=args.workers, rows=rows)
    (args.runroot / ('precompute-' + hashlib.sha256(','.join(args.cases).encode()).hexdigest()[:12] + '.json')).write_text(json.dumps(output, indent=2) + '\n')
    print('COMPLETE', len(rows), flush=True)


if __name__ == '__main__':
    main()
