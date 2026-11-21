"""Audit the built/served 103-module hinge release after build completion.

This performs byte/provenance checks, not new numerical experiments. The report
goes outside the repository. Historical ST-4 evidence retains its original pins.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
import argparse
import hashlib
import json
import time
import traceback
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
COMPOSITION_SHA = 'd3d0afbe45aa86a7478d8b7b47ccb5d8d2e1af2802063d5304a4d411d12822b0'
ASSETS_SHA = '0919cdac13820d37a67ffbedfa88ada957f7af581b1fd54f7549907e473b9e8d'
RAW_SHA = 'b125fb96e84ed70405bd503d871046c47b288c6519b2819eede51c8779741585'
CATALOG_SHA = 'e33418d06817b532b85ec35cffbf352be4411ee846240a8059adcfccdc8f068b'
COVERAGE_SHA = '87224696c33a462e133bf1f30143f9996ff88ffb2c3227b72c5bff0d1a072d06'
INVENTORY_SHA = 'e50ce891611f0538d1636e0c56cdf1fabd78d0cdc1fc9f244995b2190948b91c'
OLD_AUDITOR_SHA = 'b5340126faf940c96973d0cf46b66ac811dbbe57c4d7989bd3efa3172825cdc5'
SOURCE_ROOTS = ['openswing', 'web', 'tests', 'examples', 'scripts', 'docs', 'public/licenses', 'public/fonts']
SOURCE_SINGLE = ['README.md', 'LICENSE', 'THIRD_PARTY.md', 'package.json', 'package-lock.json',
                 'pyproject.toml', 'index.html', 'playwright.config.js', '.gitignore']
_hashes = {}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(stream):
    value, count = hashlib.sha256(), 0
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        value.update(block)
        count += len(block)
    return dict(bytes=count, sha256=value.hexdigest())


def pin(path):
    path = Path(path)
    stat = path.stat()
    key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns, stat.st_ino)
    if key not in _hashes:
        with path.open('rb') as stream:
            _hashes[key] = digest(stream)
    return _hashes[key]


def sha(path):
    return pin(path)['sha256']


def read(path):
    return json.loads(Path(path).read_text())


def relative(folder, name):
    part = PurePosixPath(name)
    require(part.parts and not part.is_absolute() and '..' not in part.parts
            and '\\' not in name and part.as_posix() == name, f'Invalid relative path: {name}')
    path = folder / name
    require(path.resolve().is_relative_to(folder.resolve()), f'External path: {name}')
    return path


def members(archive):
    names = archive.namelist()
    require(len(names) == len(set(names)), f'Duplicate ZIP members: {archive.filename}')
    for name in names:
        part = PurePosixPath(name)
        require(not part.is_absolute() and '..' not in part.parts and '\\' not in name
                and '/tmp/' not in name, f'Unsafe ZIP member: {name}')
    return set(names)


def member_pin(archive, name):
    with archive.open(name) as stream:
        return digest(stream)


def fetch(base, name, head=False):
    url = base.rstrip('/') + name
    request = urllib.request.Request(url, method='HEAD' if head else 'GET',
                                     headers={'Accept-Encoding': 'identity', 'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(request, timeout=120) as stream:
        require(stream.status == 200 and stream.geturl() == url, f'Unexpected HTTP response: {name}')
        if head:
            return dict(bytes=int(stream.headers['Content-Length']), status=stream.status)
        return digest(stream)


def phase(report, name):
    report['phase'] = name
    print(json.dumps(dict(phase=name)), flush=True)


def check_kernel_and_evidence(root, work):
    folder = root / 'docs/validation/hinge-solver-evidence'
    manifest = read(folder / 'manifest.json')
    require(manifest['format'] == 'openswing-hinge-solver-evidence' and manifest['version'] == 1,
            'Unexpected evidence manifest format.')
    require(set(manifest['files']) == {p.name for p in folder.iterdir() if p.is_file()} - {'manifest.json'},
            'Unlisted or missing evidence file.')
    evidence = {}
    for name, row in manifest['files'].items():
        actual = pin(relative(folder, name))
        require(actual == {k: row[k] for k in ('bytes', 'sha256')}, f'Evidence pin mismatch: {name}')
        require(pin(relative(work, row['original_artifact'])) == actual, f'Original evidence mismatch: {name}')
        evidence[name] = actual
    composition = read(folder / 'composition.json')
    require(sha(folder / 'composition.json') == COMPOSITION_SHA
            == sha(work / 'integrated-06/composition.json'), 'Frozen composition mismatch.')
    pins = composition['modules']
    require(len(pins) == 103 and not composition['experimental_validation'], 'Invalid composition scope.')
    for directory in [root / 'openswing', root / 'public/kernel', root / 'dist/kernel', work / 'integrated-06/openswing']:
        require({p.name for p in directory.glob('*.py')} == set(pins), f'Kernel membership mismatch: {directory}')
        for name, value in pins.items():
            require(sha(directory / name) == value, f'Kernel bytes mismatch: {directory}/{name}')
    for directory in [root / 'web', work / 'integrated-06/web']:
        require({p.name for p in directory.iterdir() if p.is_file()} == set(composition['web']),
                f'Web source membership mismatch: {directory}')
        for name, value in composition['web'].items():
            require(sha(directory / name) == value, f'Web source mismatch: {name}')
    for directory in ['public/kernel', 'dist/kernel']:
        names = read(root / directory / 'manifest.json')
        require(len(names) == len(set(names)) == 103 and set(names) == set(pins), 'Kernel manifest mismatch.')
    tests = dict(composition['test_files'])
    tests.update({name: row['sha256'] for name, row in read(work/'release-tests/release-files.json')['install_root_relative_files'].items()})
    for name, value in tests.items():
        require(sha(relative(root, name)) == value, f'Portable test/fixture mismatch: {name}')
    review = read(folder / 'cold-copy-review.json')
    require(sha(root/'tests/test_hinge_initial_state_ownership.py') == review['test_sha256'], 'Lifecycle test changed.')
    require((root/'tests/test_dense_newton_factor.py').is_file(), 'Missing dense-factor regression.')
    suites = {}
    for filename, expected in [('hinge-tests.xml',132),('combined-tests.xml',47),('dense-tests.xml',25)]:
        xml = ET.parse(folder / filename).getroot()
        count = sum(int(s.get('tests',0)) for s in xml.iter('testsuite'))
        failure = sum(int(s.get('failures',0))+int(s.get('errors',0)) for s in xml.iter('testsuite'))
        require(count == expected and failure == 0, f'Native check record mismatch: {filename}')
        suites[filename] = dict(tests=count, failures=failure)
    browser, summary, wasm = [read(folder/n) for n in ['browser-controls.json','browser-summary.json','wasm-controls.json']]
    require(browser['status'] == summary['status'] == 'PASS_ISOLATED_FULL_APP_OFFLINE_HINGE_RESTART'
            and browser['offline'] and not browser['page_errors'] and not browser['blocked_requests']
            and browser['complete_checkpoint_export_equal'], 'Offline browser control did not pass.')
    require(browser['modules'] == summary['modules'] == wasm['modules'] == pins, 'Runtime kernel pins differ.')
    require(wasm['status'] == 'PASS_WASM_COLD_MODAL_AND_WARM_HARMONIC'
            and not any(r['experimental_validation'] for r in [browser,summary,wasm]), 'Runtime scope mismatch.')
    require(summary['tested_assets_sha256'] == ASSETS_SHA == sha(folder/'tested-assets.json')
            == sha(work/'full-app-06/tested-assets.json') and summary['tested_asset_count'] == 123,
            'Tested browser asset registry changed.')
    require(summary['composition_sha256'] == COMPOSITION_SHA and summary['browser_report_sha256'] == sha(folder/'browser-controls.json'),
            'Browser evidence crosspin mismatch.')
    for name, value in summary['screenshots'].items():
        require(sha(folder/name) == value, f'Screenshot mismatch: {name}')
    return pins, dict(manifest=pin(folder/'manifest.json'), files=evidence, native_runs=suites,
                      runtime_status=wasm['status'], browser_status=browser['status'])


def check_coverage(root):
    d = root/'docs/validation'
    require(sha(d/'isae-coverage.json') == COVERAGE_SHA and sha(d/'isae-suite-inventory.json') == INVENTORY_SHA,
            'Historical coverage/inventory bytes changed.')
    require(sha(root/'scripts/audit-st4-primary-release.py') == OLD_AUDITOR_SHA, 'Historical ST4 auditor changed.')
    coverage, inventory = read(d/'isae-coverage.json'), read(d/'isae-suite-inventory.json')
    require(len(coverage['modules']) == len(inventory['kernel_modules']) == 98
            and coverage['modules'] == inventory['kernel_modules'], 'Historical module pins were retagged.')
    cases = coverage['cases']
    require(len(cases) == len({c['id'] for c in cases}) == 41 and sum(bool(c['evidence']) for c in cases) == 17
            and not any(c['fully_validated'] for c in cases) and not coverage['full_suite_validated'], 'Coverage counts changed.')
    require(dict(Counter(c['status'] for c in cases)) == coverage['case_status_counts'], 'Coverage row totals differ.')
    require(len(inventory['models']) == 279 and dict(Counter(r['status'] for r in inventory['models']))
            == inventory['parse_counts'] == {'parsed':177,'rejected':102}, 'Literal inventory changed.')
    ffwt = next(c for c in cases if c['id']=='FFWT-1')
    require(ffwt['status'] == 'blocked_at_literal_import' and not ffwt['evidence'], 'FFWT1 coverage was promoted.')
    return dict(partial=17,pending=24,fully_validated=0,parser=inventory['parse_counts'],
                literal_models=279,historical_modules=98,coverage_sha256=COVERAGE_SHA,inventory_sha256=INVENTORY_SHA)


def check_assets(root, work, pins, url):
    tested = read(work/'full-app-06/tested-assets.json')['assets']
    require(len(tested) == 123, 'Expected the exact123 tested assets.')
    require({name.removeprefix('/kernel/'):row['sha256'] for name,row in tested.items() if name.endswith('.py')}
            == pins, 'Tested kernel inventory mismatch.')
    for name,row in tested.items():
        require(name.startswith('/') and not name.startswith('//') and urllib.parse.urlsplit(name).path == name,
                f'Invalid asset URL: {name}')
        expected = {k:row[k] for k in ('bytes','sha256')}
        source_root = {'work':work,'openswing':root}.get(row['root'])
        require(source_root is not None, f'Unknown tested asset root: {name}')
        require(pin(relative(source_root,row['path'])) == expected, f'Tested asset origin changed: {name}')
        require(pin(relative(root/'dist','index.html' if name=='/' else name[1:])) == expected,
                f'Final built asset differs from tested bytes: {name}')
    def compare(item):
        name,row = item
        expected = {k:row[k] for k in ('bytes','sha256')}
        actual = fetch(url,name)
        require(actual == expected, f'Served asset differs from tested bytes: {name}')
        return name,actual
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = dict(executor.map(compare,sorted(tested.items())))
    require(fetch(url,'/distribution.json') == pin(root/'dist/distribution.json'), 'Served metadata differs.')
    return results


def check_archives(root, url):
    d=root/'docs/validation'
    metadata=read(root/'public/distribution.json')
    require(metadata == read(root/'dist/distribution.json') and metadata['format']=='openswing-distribution'
            and metadata['version']==1 and metadata['kind']=='hosted', 'Distribution metadata mismatch.')
    require(sha(d/'archive-index.json') == CATALOG_SHA, 'Prior raw catalog changed.')
    catalog=read(d/'archive-index.json')
    raw_paths={p for p in d.rglob('*.zip') if p.is_file()}
    require(len(raw_paths)==len(catalog['archives'])==133 and set(catalog['archives'])
            == {p.relative_to(root).as_posix() for p in raw_paths}, 'Raw archive inventory changed.')
    for name,row in catalog['archives'].items():
        require(relative(root,name).stat().st_size == row['bytes'], f'Raw member size changed: {name}')
    require(metadata['validation']['sha256']==RAW_SHA and metadata['validation']['archives']
            == metadata['validation']['catalog_archives']==133, 'Raw bundle pin changed.')
    downloads={}
    for key,filename in [('source','openswing-source.zip'),('validation','openswing-validation.zip')]:
        expected={k:metadata[key][k] for k in ('bytes','sha256')}
        require(metadata[key]['file']==filename, f'Wrong download filename: {key}')
        for folder in ['public','dist']:
            require(pin(root/folder/filename)==expected, f'Download bytes/metadata mismatch: {folder}/{filename}')
        require(fetch(url,'/'+filename,head=True)['bytes']==expected['bytes'], f'Served download size mismatch: {key}')
        downloads[key]=expected
    source_files=[root/name for name in SOURCE_SINGLE if (root/name).is_file()]
    for folder in SOURCE_ROOTS:
        source_files.extend(p for p in (root/folder).rglob('*') if p.is_file()
                            and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts and p not in raw_paths)
    require(all(not p.is_symlink() and p.resolve().is_relative_to(root) for p in source_files), 'External/symlink source member.')
    source_map={p.relative_to(root).as_posix():p for p in source_files}
    require(len(source_map)==len(source_files), 'Duplicate source membership.')
    with ZipFile(root/'public/openswing-source.zip') as source, ZipFile(root/'public/openswing-validation.zip') as raw, ZipFile(root/'dist/openswing-local.zip') as local:
        source_names,raw_names,local_names=map(members,[source,raw,local])
        notice='openswing/VALIDATION-ARCHIVES.txt';catalog_name='openswing/docs/validation/archive-index.json'
        require(source_names=={'openswing/'+name for name in source_map}|{notice}, 'Source ZIP membership mismatch.')
        for name,path in source_map.items():
            require(member_pin(source,'openswing/'+name)==pin(path), f'Source ZIP content mismatch: {name}')
        require(raw_names=={'openswing/'+name for name in catalog['archives']}|{notice,catalog_name}, 'Raw bundle membership mismatch.')
        require(source.read(catalog_name)==raw.read(catalog_name)==(d/'archive-index.json').read_bytes(), 'Catalog copies differ.')
        require(source.read(notice)==raw.read(notice), 'Raw/source notices differ.')
        excluded={root/'dist'/n for n in ['openswing-local.zip','openswing-validation.zip','distribution.json']}
        local_files=[p for p in (root/'dist').rglob('*') if p.is_file() and p not in excluded and '.openai' not in p.parts]
        require(all(not p.is_symlink() and p.resolve().is_relative_to(root/'dist') for p in local_files), 'External local-app member.')
        require(local_names=={p.relative_to(root/'dist').as_posix() for p in local_files}|{'README-local.txt','distribution.json'},
                'Local ZIP membership mismatch.')
        for path in local_files:
            name=path.relative_to(root/'dist').as_posix()
            require(member_pin(local,name)==pin(path), f'Local ZIP content mismatch: {name}')
        require(json.loads(local.read('distribution.json'))==dict(metadata,kind='local',validation=None)
                and 'openswing-validation.zip' not in local_names, 'Local metadata/raw-download scope mismatch.')
    downloads['local']=pin(root/'dist/openswing-local.zip')
    require(fetch(url,'/openswing-local.zip',head=True)['bytes']==downloads['local']['bytes'], 'Served local ZIP size mismatch.')
    return dict(metadata=metadata,downloads=downloads,source_members=len(source_names),local_members=len(local_names),
                raw_members=len(raw_names),unchanged_raw_archives=133,raw_bundle_sha256=RAW_SHA,
                source_file_pins={name:pin(path) for name,path in sorted(source_map.items())},
                raw_check_scope='Both public/dist whole-bundle SHA256 values checked; no redundant rehash of all133 nested archives.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--url',default='http://127.0.0.1:8000')
    parser.add_argument('--output',type=Path)
    a=parser.parse_args();root=a.root.resolve();work=a.work.resolve()
    output=(a.output or work/'release/audit-hinge-solver-release.json').resolve()
    require(not output.exists(), f'Refusing to replace previous audit: {output}')
    require(not output.is_relative_to(root), 'Audit output must remain outside published source.')
    endpoint=urllib.parse.urlsplit(a.url)
    require(endpoint.scheme=='http' and endpoint.hostname in ('127.0.0.1','localhost','::1')
            and not endpoint.path and not endpoint.query and not endpoint.fragment, 'Use a local HTTP origin.')
    start=time.monotonic()
    report=dict(status='RUNNING',started_utc=datetime.now(timezone.utc).isoformat(),script_sha256=sha(Path(__file__)),
                full_repository_suite=False,experimental_validation=False,original_st4_audit_preserved=True)
    code=1
    try:
        phase(report,'source and selected evidence')
        pins,report['evidence']=check_kernel_and_evidence(root,work)
        report['modules']=pins
        phase(report,'historical coverage')
        report['coverage']=check_coverage(root)
        phase(report,'tested built and served assets')
        report['served_assets']=check_assets(root,work,pins,a.url)
        phase(report,'source local and unchanged raw downloads')
        report['archives']=check_archives(root,a.url)
        report['status']='PASS_HINGE_SOLVER_RELEASE_WITH_RETAINED_PHYSICAL_LIMITATIONS'
        report['status_document']=pin(root/'docs/STATUS.md')
        report['limitations']=['Selected numerical/runtime checks do not establish full ASWING or FFWT experimental validation.',
            'Coverage remains the pinned98-module ST4 ledger; historical physical studies were not rerun by this audit.',
            'The123 browser assets are exact byte replays of the offline tested app; this audit runs no new simulation.',
            'Source/local archives are verified member by member; HTTP downloads are checked by metadata/size while the123 runtime assets are fully hashed over HTTP.']
        code=0
    except Exception as error:
        report.update(status='FAIL_RETAINED',error=type(error).__name__+': '+str(error),traceback=traceback.format_exc())
    report['elapsed_seconds']=time.monotonic()-start
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:
        stream.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(status=report['status'],output=str(output),sha256=sha(output),elapsed_seconds=report['elapsed_seconds'],error=report.get('error'))),flush=True)
    raise SystemExit(code)


if __name__=='__main__':
    main()
