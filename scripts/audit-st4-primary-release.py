"""Audit the built and served ST-4 release against its pinned final evidence.

Run only after the final distribution build and production-server handoff.
This writes its result to the work directory, not into the published docs.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'docs/validation'
TRANSITION = 'st4-primary-transition.json'
EVIDENCE = 'st4-primary-evidence.zip'
REQUIRED_DOCUMENTS = {
    'st4-primary-study.md', 'st4-primary-air.json', 'st4-primary-vacuum.json',
    'st4-primary-vacuum-experiment.json', 'st4-primary-wasm.json', 'st4-primary-browser.json',
}
WEB_FILES = {
    'web/main.js', 'web/case-settings.js', 'web/mode-results.js',
    'web/quiescent-settings.js', 'web/equilibrium-state.js',
    'web/flow-results.js', 'web/rom-results.js', 'web/stability-results.js',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(stream):
    value = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        value.update(block)
    return value.hexdigest()


def sha(path):
    with Path(path).open('rb') as stream:
        return digest(stream)


def read(path):
    return json.loads(Path(path).read_text())


def relative_file(folder, name):
    path = PurePosixPath(name)
    require(path.parts and not path.is_absolute() and '..' not in path.parts
            and '\\' not in name and path.as_posix() == name, f'Invalid relative path: {name}')
    return folder / name


def member(archive, name):
    with archive.open(name) as stream:
        return digest(stream)


def unique_members(archive):
    names = archive.namelist()
    require(len(names) == len(set(names)), f'Duplicate ZIP members: {archive.filename}')
    return set(names)


def check_sources(work, audit):
    require(audit['status'] == 'PASS_ST4_PRIMARY_SOURCE_AND_NUMERICAL_EVIDENCE_WITH_PHYSICAL_LIMITATIONS',
            'Final ST-4 transition audit is not complete.')
    require(not audit['full_physical_validation'] and not audit['accuracy_acceptance_established'],
            'The release must retain its physical limitations.')
    pins, baseline = audit['candidate_modules'], audit['baseline_modules']
    require(len(pins) == 98 and len(baseline) == 97, 'Unexpected source transition inventory.')
    for folder in ['openswing', 'public/kernel', 'dist/kernel']:
        directory = ROOT / folder
        require({p.name for p in directory.glob('*.py')} == set(pins), f'Kernel inventory mismatch: {folder}')
        for name, value in pins.items():
            require(sha(directory / name) == value, f'Kernel bytes mismatch: {folder}/{name}')
    for folder in ['public/kernel', 'dist/kernel']:
        names = read(ROOT / folder / 'manifest.json')
        require(len(names) == 98 and set(names) == set(pins), f'Kernel manifest mismatch: {folder}')
    for name, value in baseline.items():
        require(sha(work / 'primary-baseline-source/openswing' / name) == value,
                f'Frozen baseline changed: {name}')
    require({row['path'] for row in audit['web_changes']} == WEB_FILES
            and len(audit['web_changes']) == 8, 'Expected the exact eight reviewed UI files.')
    for row in audit['web_changes']:
        require(sha(ROOT / row['path']) == row['candidate_sha256'], f'UI bytes mismatch: {row["path"]}')
    for name, value in audit['test_source_sha256'].items():
        require(sha(relative_file(ROOT, name)) == value, f'Test source mismatch: {name}')
    require(audit['script_sha256'] == sha(ROOT / 'scripts/verify-st4-primary-transition.py'),
            'Transition audit script changed.')
    for name, value in audit['evidence_sha256'].items():
        require(sha(relative_file(work, name)) == value, f'Work evidence mismatch: {name}')

    documents = audit['documentation_evidence_sha256']
    require(documents == read(work / 'documentation-evidence.json'), 'Documentation registries differ.')
    require(REQUIRED_DOCUMENTS <= set(documents), 'Required final ST-4 documents are missing.')
    published = {p.name for p in D.glob('st4-primary*')
                 if p.is_file() and p.suffix != '.zip' and p.name != TRANSITION}
    require(published == set(documents), 'New ST-4 docs are missing from the final hash registry.')
    for name, value in documents.items():
        require(sha(relative_file(D, name)) == value, f'Published evidence mismatch: {name}')
    air, vacuum = read(D / 'st4-primary-air.json'), read(D / 'st4-primary-vacuum.json')
    experiment = read(D / 'st4-primary-vacuum-experiment.json')
    require(air['modules'] == pins and vacuum['modules'] == experiment['modules'] == baseline,
            'Current air and historical vacuum source identities were conflated.')
    require(air['native_states'] == vacuum['native_states'] == 252
            and not any(report['full_physical_validation'] for report in [air, vacuum, experiment]),
            'Published comparison scope differs from the audited study.')
    wasm = read(D / 'st4-primary-wasm.json')
    require(wasm['status'] == 'PASS_ST4_QUIESCENT_WASM' and wasm['modules'] == pins
            and len(wasm['rows']) == 3, 'WASM report mismatch.')
    require(wasm['script_sha256'] == sha(ROOT / 'scripts/test-st4-quiescent-wasm.mjs'),
            'WASM reproducer changed.')
    browser = read(D / 'st4-primary-browser.json')
    require(browser['status'] == 'PASS_PRIMARY_ST4_QUIESCENT_FRESH_OFFLINE_BROWSER'
            and browser['offline'] and browser['served_build'] and browser['modules'] == pins
            and len(browser['runs']) == 3, 'Fresh offline browser report mismatch.')
    require(browser['test_sha256'] == sha(ROOT / 'tests/browser/st4-quiescent.spec.js'),
            'Browser test source changed.')
    for row in browser['runs']:
        result = row['result']
        require(result['software_provenance']['modules'] == pins and not result['vacuum']
                and result['fluid']['kind'] == 'quiescent', 'Browser result has the wrong source/medium.')
    return pins, documents


def check_coverage(work, pins):
    coverage, old = read(D / 'isae-coverage.json'), read(work / 'baseline-isae-coverage.json')
    require(coverage['modules'] == pins and not coverage['full_suite_validated'], 'Coverage source/scope mismatch.')
    cases = coverage['cases']
    require(len(cases) == 41 and len({case['id'] for case in cases}) == 41, 'Family inventory mismatch.')
    partial = sum(bool(case['evidence']) for case in cases)
    require(partial == 17 and len(cases) - partial == 24
            and not any(case['fully_validated'] for case in cases), 'Expected 17 partial, 24 pending, zero full families.')
    require(dict(Counter(case['status'] for case in cases)) == coverage['case_status_counts'],
            'Coverage status totals differ from the rows.')
    old_cases = {case['id']: case for case in old['cases']}
    newly_studied = [case['id'] for case in cases if case['evidence'] and not old_cases[case['id']]['evidence']]
    require(newly_studied == ['ST-4'], 'Unexpected change in studied-family membership.')
    require(all(bool(case['evidence']) or not old_cases[case['id']]['evidence'] for case in cases),
            'A prior study disappeared from coverage.')
    for name, value in coverage['study_sha256'].items():
        require(sha(relative_file(D, name)) == value, f'Study bytes mismatch: {name}')
    for name, value in old['study_sha256'].items():
        require(coverage['study_sha256'].get(name) == value, f'Historical study hash changed: {name}')
    for name, previous in old['source_continuity']['studies'].items():
        current = coverage['source_continuity']['studies'][name]
        require(current.get('rerun_on_current_source') is not True
                and current.get('status') != 'run_on_current_source',
                f'Historical study incorrectly advertised as a current rerun: {name}')
        if previous.get('rerun_on_current_source') is False:
            require(current.get('rerun_on_current_source') is False, f'Historical qualifier lost: {name}')
    transition = coverage['source_continuity']['st4_primary_transition']
    require(transition['report'] == TRANSITION and transition['sha256'] == sha(D / TRANSITION),
            'Coverage does not identify this transition report.')
    inventory, before = read(D / 'isae-suite-inventory.json'), read(work / 'baseline-isae-suite-inventory.json')
    require(inventory['kernel_modules'] == pins and inventory['model_files'] == 279
            and inventory['parse_counts'] == {'parsed': 177, 'rejected': 102}, 'Literal parser coverage mismatch.')
    require({key: value for key, value in inventory.items() if key != 'kernel_modules'}
            == {key: value for key, value in before.items() if key != 'kernel_modules'},
            'The 279 literal rows or their inventory metadata changed.')
    require(len(inventory['models']) == 279, 'Literal model row count mismatch.')
    return {'partial_families': partial, 'pending_families': 24, 'fully_validated_families': 0,
            'literal_models': 279, 'parse_counts': inventory['parse_counts'],
            'preserved_historical_studies': len(old['study_sha256'])}


def check_archives(work):
    archive_result = read(work / 'archive-result.json')
    require(archive_result['status'] == 'PASS_ST4_PRIMARY_ARCHIVE_REEXTRACTION_AND_IDENTICAL_AUDIT'
            and archive_result['sha256'] == sha(D / EVIDENCE)
            and archive_result['reproduced_audit_sha256'] == sha(D / TRANSITION),
            'Evidence archive/re-extraction result mismatch.')
    require(archive_result['script_sha256'] == sha(ROOT / 'scripts/archive-st4-primary.py'),
            'Archiver changed after extraction verification.')
    previous = read(work / 'baseline-archive-index.json')
    archives = sorted(p for p in D.rglob('*.zip') if p.is_file())
    require(len(archives) == 133 and len(previous['archives']) == 132, 'Raw archive inventory mismatch.')
    metadata = read(ROOT / 'public/distribution.json')
    require(metadata['format'] == 'openswing-distribution' and metadata['version'] == 1
            and metadata['kind'] == 'hosted'
            and metadata['validation']['archives'] == metadata['validation']['catalog_archives'] == 133,
            'Hosted distribution metadata mismatch.')
    require(sha(ROOT / 'public/distribution.json') == sha(ROOT / 'dist/distribution.json'),
            'Built distribution metadata differs from public metadata.')
    with ZipFile(ROOT / 'public/openswing-source.zip') as source, \
            ZipFile(ROOT / 'public/openswing-validation.zip') as raw, \
            ZipFile(ROOT / 'dist/openswing-local.zip') as local:
        source_names, raw_names, local_names = map(unique_members, [source, raw, local])
        catalog_path = 'openswing/docs/validation/archive-index.json'
        catalog = json.loads(source.read(catalog_path))
        require(catalog == read(D / 'archive-index.json') == json.loads(raw.read(catalog_path)),
                'Source/raw/root archive catalogs differ.')
        require(set(catalog['archives']) == {p.relative_to(ROOT).as_posix() for p in archives},
                'Catalog contains missing or unexpected archives.')
        require(set(catalog['archives']) - set(previous['archives']) == {'docs/validation/' + EVIDENCE},
                'The release must add only the ST-4 primary evidence archive.')
        for name, pin in previous['archives'].items():
            require(catalog['archives'][name] == pin, f'Historical archive pin changed: {name}')
        for path in archives:
            name = path.relative_to(ROOT).as_posix()
            pin = catalog['archives'][name]
            require(path.stat().st_size == pin['bytes']
                    and sha(path) == pin['sha256'] == member(raw, 'openswing/' + name),
                    f'Raw archive bytes mismatch: {name}')
            require('openswing/' + name not in source_names, f'Raw archive embedded in source: {name}')
        require(raw_names == {'openswing/' + p.relative_to(ROOT).as_posix() for p in archives}
                | {catalog_path, 'openswing/VALIDATION-ARCHIVES.txt'}, 'Unexpected raw bundle members.')
        source_files = []
        for folder in ['openswing', 'web', 'tests', 'examples', 'scripts', 'docs', 'public/licenses', 'public/fonts']:
            source_files.extend(path for path in (ROOT / folder).rglob('*') if path.is_file()
                                and '__pycache__' not in path.parts and '.pytest_cache' not in path.parts
                                and path not in archives)
        source_files.extend(ROOT / name for name in ['README.md', 'LICENSE', 'THIRD_PARTY.md',
                            'package.json', 'package-lock.json', 'pyproject.toml', 'index.html',
                            'playwright.config.js', '.gitignore'] if (ROOT / name).is_file())
        require(source_names == {'openswing/' + path.relative_to(ROOT).as_posix() for path in source_files}
                | {'openswing/VALIDATION-ARCHIVES.txt'}, 'Source bundle membership mismatch.')
        for path in source_files:
            require(member(source, 'openswing/' + path.relative_to(ROOT).as_posix()) == sha(path),
                    f'Source archive bytes mismatch: {path}')
        local_excluded = {ROOT / 'dist' / name for name in
                          ['openswing-local.zip', 'openswing-validation.zip', 'distribution.json']}
        built = [path for path in (ROOT / 'dist').rglob('*') if path.is_file()
                 and path not in local_excluded
                 and '.openai' not in path.parts]
        require(local_names == {path.relative_to(ROOT / 'dist').as_posix() for path in built}
                | {'README-local.txt', 'distribution.json'}, 'Local bundle membership mismatch.')
        for path in built:
            require(member(local, path.relative_to(ROOT / 'dist').as_posix()) == sha(path),
                    f'Local archive bytes mismatch: {path}')
        require('openswing-validation.zip' not in local_names
                and json.loads(local.read('distribution.json')) == dict(metadata, kind='local', validation=None),
                'Local distribution metadata/raw-download scope mismatch.')
        require(source.read('openswing/VALIDATION-ARCHIVES.txt') == raw.read('openswing/VALIDATION-ARCHIVES.txt'),
                'Source/raw download instructions differ.')
    for key, filename in [('source', 'openswing-source.zip'), ('validation', 'openswing-validation.zip')]:
        path = ROOT / 'public' / filename
        require(metadata[key]['file'] == filename and path.stat().st_size == metadata[key]['bytes']
                and sha(path) == metadata[key]['sha256'] == sha(ROOT / 'dist' / filename),
                f'Download metadata/hash mismatch: {key}')
    return metadata


def check_assets(work, pins, audit, url):
    tested, before = read(work / 'tested-browser-assets.json'), read(work / 'baseline-served-assets.json')
    unlisted = read(work / 'previously-served-unlisted-examples.json')
    integration = read(work / 'root-integration.json')
    require(sha(work / 'tested-browser-assets.json') == integration['tested_browser_assets_sha256'],
            'Tested browser asset map differs from the integrated browser record.')
    require(len(tested) == 180 and len(before) == 167 and len(unlisted) == 12, 'Browser asset inventory mismatch.')
    require(all(name.startswith('examples/pazy-primary-') for name in unlisted),
            'Unexpected previously served example category.')
    added, removed = set(tested) - set(before), set(before) - set(tested)
    added_bundles = {name for name in added if re.fullmatch(r'assets/index-[\w-]+\.js', name)}
    removed_bundles = {name for name in removed if re.fullmatch(r'assets/index-[\w-]+\.js', name)}
    require(len(added_bundles) == len(removed_bundles) == 1
            and added == set(unlisted) | {'kernel/quiescent.py'} | added_bundles
            and removed == removed_bundles, 'Unexplained browser asset additions/removals.')
    changed = {name for name in set(tested) & set(before) if tested[name] != before[name]}
    expected_changes = {'index.html', 'kernel/manifest.json'} | {
        'kernel/' + name for name in audit['changed_solver_modules'] if name != 'quiescent.py'}
    require(changed == expected_changes, 'Unexplained changes among previously tested browser assets.')
    for name, value in unlisted.items():
        require(tested[name] == value == sha(relative_file(ROOT, name))
                == sha(relative_file(work / 'primary-baseline-source', name)),
                f'Previously served unlisted example changed: {name}')
    require(all(tested.get('kernel/' + name) == value for name, value in pins.items()),
            'The tested browser map does not contain all 98 reviewed modules.')

    def served(item):
        name, value = item
        path = relative_file(ROOT / 'dist', name)
        require(sha(path) == value, f'Final build differs from tested browser asset: {name}')
        with urllib.request.urlopen(url + '/' + urllib.parse.quote(name, safe='/'), timeout=60) as response:
            require(response.status == 200 and digest(response) == value, f'Served asset differs: {name}')
        return name

    with ThreadPoolExecutor(max_workers=4) as pool:
        served_names = list(pool.map(served, sorted(tested.items())))
    return {'tested_assets': len(served_names), 'previous_assets': len(before),
            'added_keys': sorted(added), 'removed_keys': sorted(removed),
            'changed_common_keys': sorted(changed), 'unchanged_common_assets': len(set(tested) & set(before)) - len(changed),
            'previously_served_unlisted_examples': unlisted,
            'explanation': 'The 12 Pazy examples were already served and are unchanged; the old 167-key test map omitted them. '
                           'The new quiescent module and replaced UI bundle account for the remaining key changes. '
                           'Common changes are the reviewed existing solver modules, kernel manifest and HTML bundle reference.'}


def check_downloads(url, metadata):
    with urllib.request.urlopen(url + '/distribution.json', timeout=30) as response:
        require(response.status == 200 and json.load(response) == metadata, 'Served distribution metadata mismatch.')
    checks = {}
    for name in ['openswing-source.zip', 'openswing-validation.zip', 'openswing-local.zip']:
        request = urllib.request.Request(url + '/' + name, headers={'Range': 'bytes=0-63'})
        with urllib.request.urlopen(request, timeout=30) as response:
            require(response.status == 206, f'Download does not support byte ranges: {name}')
            data = response.read(65)
            path = ROOT / 'dist' / name
            require(len(data) == 64 and response.headers['Content-Range'] == f'bytes 0-63/{path.stat().st_size}',
                    f'Download range metadata mismatch: {name}')
            with path.open('rb') as stream:
                require(data == stream.read(64), f'Served download prefix differs: {name}')
            checks[name] = {'status': response.status, 'content_range': response.headers['Content-Range']}
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    work, url = args.work.resolve(), args.url.rstrip('/')
    audit = read(D / TRANSITION)
    pins, documents = check_sources(work, audit)
    coverage = check_coverage(work, pins)
    metadata = check_archives(work)
    assets = check_assets(work, pins, audit, url)
    downloads = check_downloads(url, metadata)
    require(sum('| Partial |' in line for line in (ROOT / 'docs/REQUIREMENTS.md').read_text().splitlines()) == 40,
            'The 40 broad Partial requirements were changed.')
    result = {
        'status': 'PASS_ST4_PRIMARY_RELEASE_AND_PRESERVED_VALIDATION_HISTORY',
        'modules': pins, 'changed_solver_modules': audit['changed_solver_modules'],
        'changed_web_files': sorted(WEB_FILES), 'selected_python_tests': audit['selected_python_tests'],
        'selected_js_tests': audit['selected_js_tests'], **coverage,
        'native_vacuum_states': 252, 'native_still_air_states': 252, 'independent_reference_states': 672,
        'wasm_cases': 3, 'offline_browser_cases': 3,
        'raw_archives': 133, 'prior_archives_unchanged': 132,
        'served_assets': assets['tested_assets'], 'asset_inventory_audit': assets,
        'metadata': metadata, 'documentation_evidence_sha256': documents,
        'evidence_sha256': sha(D / EVIDENCE), 'transition_sha256': sha(D / TRANSITION),
        'local_bytes': (ROOT / 'dist/openswing-local.zip').stat().st_size,
        'local_sha256': sha(ROOT / 'dist/openswing-local.zip'),
        'audit_script_sha256': sha(__file__), 'download_checks': downloads,
        'full_suite_rerun': False, 'full_physical_validation': False,
        'limitations': [
            'The added ST-4 family has a completed quantitative partial study; no family is fully validated.',
            'Prior studies retain their original bytes/source identities and are not current numerical reruns.',
            'Experimental density, fixture/pylon/section properties and measured mode identity remain uncertain.',
            'Thin-strip still-air approximation, higher-mode mixing and numerical diagnostic flags remain explicit.',
            'No full regression or stock-ASWING executable parity claim; all 40 broad requirements remain Partial.',
        ],
    }
    (work / 'audit-release.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'modules'}, indent=2), flush=True)


if __name__ == '__main__':
    main()
