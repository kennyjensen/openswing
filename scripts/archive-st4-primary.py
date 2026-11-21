"""Package pinned ST-4 study evidence, then verify an independent extraction.

Run only after the final transition audit has completed. Archive construction
does not change historical archives; the sole release destination is
docs/validation/st4-primary-evidence.zip.
"""
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile

from distribution import checksum, package


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'docs/validation/st4-primary-evidence.zip'
CACHE_DIRECTORIES = {
    'node_modules', '.venv', '.git', '__pycache__', '.pytest_cache',
    '.mypy_cache', '.ruff_cache', '.vite', '.vite-cache', '.cache',
    'Cache', 'Code Cache', 'GPUCache', 'DawnCache', 'Crashpad', 'BrowserMetrics',
}
WORK_OUTPUTS = {
    'reproduction', 'archive-reproduction', 'archive-reextraction',
    'archive-check', 'archive-result.json', 'archive-reproduction.log',
    'archive-check.json', 'check.json', 'integrated-preview/dist',
}
RAW_DIRECTORIES = (
    'isae-st4-experiment-inputs', 'isae-st4-primary',
    'isae-st4-primary-native', 'isae-st4-primary-reference',
    'isae-st4-primary-air', 'isae-st4-primary-refinement',
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_member(name):
    path = PurePosixPath(name)
    require(not path.is_absolute() and '..' not in path.parts
            and '\\' not in name and path.parts and path.as_posix() == name,
            f'Unsafe archive member: {name!r}')
    return name


def read_json(path):
    return json.loads(Path(path).read_text())


def root_relative(path):
    path = Path(path)
    path = path if path.is_absolute() else ROOT / path
    require(not path.is_symlink(), f'Expected a regular root file: {path}')
    path = path.resolve(strict=True)
    require(path.is_file() and path.is_relative_to(ROOT),
            f'File must be inside the repository: {path}')
    return path, path.relative_to(ROOT).as_posix()


def collect(work, target, audit_script, audit_report, extra_exclusions):
    files, excluded = {}, []
    work_exclusions = WORK_OUTPUTS | set(extra_exclusions)
    for name in work_exclusions:
        safe_member(name)

    def add(path, name=None, pin=None):
        path = Path(path)
        require(path.is_file() and not path.is_symlink(),
                f'Missing regular evidence file: {path}')
        name = safe_member(name or 'openswing/' + path.relative_to(ROOT).as_posix())
        if pin is not None:
            require(checksum(path) == pin, f'Source checksum mismatch: {path}')
        require(name not in files or files[name] == path,
                f'Conflicting archive member: {name}')
        files[name] = path

    def walk(directory, prefix, is_work=False):
        require(directory.is_dir() and not directory.is_symlink(),
                f'Missing regular evidence directory: {directory}')
        for base, directories, names in os.walk(directory, followlinks=False):
            base = Path(base)
            for name in sorted(directories + names):
                path = base / name
                relative = path.relative_to(directory)
                member = prefix + relative.as_posix()
                reason = None
                if path.is_symlink():
                    reason = 'symlink (not dereferenced)'
                elif name in CACHE_DIRECTORIES:
                    reason = 'transient dependency/browser/Python cache'
                elif path.suffix in {'.pyc', '.pyo'}:
                    reason = 'Python bytecode cache'
                elif (is_work and path.is_dir()
                      and (path / 'MANIFEST.json').is_file()
                      and (path / 'openswing').is_dir() and (path / 'work').is_dir()):
                    reason = 'previous independent evidence extraction'
                elif is_work and any(relative == Path(item) or
                                     relative.is_relative_to(Path(item))
                                     for item in work_exclusions):
                    reason = 'reserved extraction/archive/check output'
                elif path == target or path.is_relative_to(target):
                    reason = 'requested independent extraction target'
                if reason:
                    excluded.append({'path': member, 'reason': reason})
                    if name in directories:
                        directories.remove(name)
                elif path.is_file():
                    add(path, member)
            directories.sort()

    # The complete study tree retains successful, failed and superseded work.
    # In particular, the original forward reference is not replaced by the
    # reciprocal revision and the 97-module baseline remains a separate tree.
    walk(work, 'work/', True)
    baseline = work / 'primary-baseline-source'
    baseline_manifest = read_json(baseline / 'source-manifest.json')
    integration = read_json(work / 'root-integration.json')
    baseline_modules = integration['baseline_modules']
    current_modules = integration['candidate_modules']
    require(len(baseline_modules) == 97, 'Expected the frozen 97-module baseline.')
    require(len(current_modules) == 98, 'Expected the reviewed 98-module current source.')
    require({p.name for p in (baseline / 'openswing').glob('*.py')} == set(baseline_modules),
            'Baseline module inventory changed.')
    require({p.name for p in (ROOT / 'openswing').glob('*.py')} == set(current_modules),
            'Current module inventory differs from root-integration.json.')
    for name, pin in baseline_manifest.items():
        add(baseline / name, 'work/primary-baseline-source/' + name, pin)
    for name, pin in baseline_modules.items():
        require(baseline_manifest['openswing/' + name] == pin,
                f'Baseline source manifests disagree for {name}.')
    for name, pin in current_modules.items():
        add(ROOT / 'openswing' / name, pin=pin)
    for row in integration['web_changes']:
        add(ROOT / row['path'], pin=row['candidate_sha256'])

    # Complete source/support trees include dependencies of the focused
    # reproducers. Their presence does not claim that every test was rerun.
    for directory in ['scripts', 'tests', 'web', 'examples']:
        walk(ROOT / directory, 'openswing/' + directory + '/')
    for name in ['pyproject.toml', 'package.json', 'package-lock.json',
                 'playwright.config.js', 'vite.config.js', 'index.html',
                 'README.md', 'LICENSE', 'THIRD_PARTY.md']:
        path = ROOT / name
        if path.is_file():
            add(path)
    for folder in RAW_DIRECTORIES:
        walk(ROOT / '.reference' / folder, 'openswing/.reference/' + folder + '/')
    for name in ['manifest.json', 'asw_theory.pdf', 'asw_uns_theory.pdf', 'aswing_doc.txt']:
        add(ROOT / '.reference' / name)

    upstream = ROOT / '.reference/isae-validation'
    manifest = read_json(upstream / 'manifest.json')
    add(upstream / 'manifest.json')
    add(upstream / 'upstream-tree.json')
    asw = [name for name in manifest['files'] if name.endswith('.asw')]
    require(len(asw) == 279, f'Expected 279 pinned upstream ASW files, found {len(asw)}.')
    for name, pin in manifest['files'].items():
        if name.endswith('.asw') or name.startswith('3 - Structure/CASE - ST4 Concentrated weight/'):
            path = upstream / manifest['revision'] / name
            require(path.stat().st_size == pin['bytes'], f'Upstream byte count mismatch: {name}')
            add(path, pin=pin['sha256'])
    # Only new/relevant uncompressed reports are included; never recursively
    # embed historical evidence archives or rewrite their documentation.
    for path in (ROOT / 'docs/validation').iterdir():
        if path.is_file() and 'st4' in path.name.lower() and path.suffix != '.zip':
            add(path)
    add(audit_script)
    add(audit_report)
    return files, excluded, baseline_modules, current_modules, manifest['revision']


def reproduction_text(script_name, report_name):
    return f'''ST-4 evidence reproduction

Archive layout:
  openswing/  Current reviewed source, raw primary caches/inputs/PDF,
              original upstream ASW files and relevant reproducers/reports.
  work/       Original study work tree, including the frozen 97-module
              baseline, original and reciprocal references, failures and UI.
  MANIFEST.json  SHA256 and byte count of every other archive member.

The 98-module current source and 97-module frozen baseline have distinct
identities. Do not rerun the vacuum baseline with the current source and call
the result the archived baseline. Symlinks, dependency/browser caches and
prior extraction/check outputs were not archived. The original upstream
manifest covers the entire upstream repository; included original data are
all 279 ASW files plus the complete ST-4 folder, not all other case assets.

After extraction, create the explicit local baseline reference link:
  ln -s ../../openswing/.reference work/primary-baseline-source/.reference

From extracted openswing/, with Python >=3.12 and the project's NumPy/SciPy
dependencies installed, run the final read-only transition audit:
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 {script_name} --work ../work --output check.json
The resulting check.json must be byte-identical to {report_name}.
The archiver performs this audit automatically with an independent extraction
at --target and records its hashes in the external archive-result.json.

The study's numerical/modal/cache recomputation scripts and their original
commands remain in scripts/ and work/. Some original exploratory scripts
record absolute paths. Use the extraction-aware final transition audit above
for the portable hash/replay check; do not silently rewrite pinned evidence.
Native reruns require their recorded 97- or 98-module source as appropriate.
Browser reruns additionally require the pinned JavaScript dependencies,
Pyodide runtime assets and a supported Chromium/software-GL environment.
Those external dependency caches are not supplied as evidence source files.

Exact-zero still-air inertia is a conditional thin-strip model at an explicit
density. Numerical verification, source continuity, runtime replay and
experimental discrepancy are separate conclusions. This archive does not
assert full experimental validation or stock-ASWING executable parity.
No coverage count is increased merely by creating an evidence archive.
'''


def extract_and_check(archive_path, target, pins, manifest_bytes):
    require(not target.exists(), f'Extraction target already exists: {target}')
    target.mkdir(parents=True, exist_ok=False)
    with ZipFile(archive_path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'Duplicate archive members.')
        require(set(names) == set(pins) | {'MANIFEST.json'}, 'Archive membership mismatch.')
        for name in names:
            safe_member(name)
        require(archive.read('MANIFEST.json') == manifest_bytes, 'Manifest serialization mismatch.')
        archive.extractall(target)
    for name, pin in pins.items():
        path = target / name
        require(path.is_file() and not path.is_symlink()
                and path.stat().st_size == pin['bytes'] and checksum(path) == pin['sha256'],
                f'Extracted member mismatch: {name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True,
                        help='New independent extraction directory; must not exist.')
    parser.add_argument('--audit-script', type=Path, required=True,
                        help='Final transition audit script, relative to the repository root.')
    parser.add_argument('--audit-report', type=Path, required=True,
                        help='Pinned expected audit JSON, relative to the repository root.')
    parser.add_argument('--exclude-work', action='append', default=[], metavar='RELATIVE_PATH',
                        help='Additional exact work-tree output path to omit (recorded in manifest).')
    args = parser.parse_args()
    work, target = args.work.resolve(strict=True), args.target.resolve()
    require(work.is_dir() and work != ROOT, 'Expected a separate study work directory.')
    require(not target.exists() and not target.is_relative_to(ROOT)
            and target != work and not ROOT.is_relative_to(target)
            and not work.is_relative_to(target), 'Target must be new and independent of source roots.')
    script, script_name = root_relative(args.audit_script)
    report, report_name = root_relative(args.audit_report)
    audit = read_json(report)
    require(audit.get('status') == 'PASS_ST4_PRIMARY_SOURCE_AND_NUMERICAL_EVIDENCE_WITH_PHYSICAL_LIMITATIONS'
            and audit.get('script_sha256') == checksum(script),
            'A completed final transition audit from this exact script is required.')
    files, excluded, baseline, current, revision = collect(
        work, target, script, report, args.exclude_work)
    extras = {
        'README.txt': b'ST-4 primary-source evidence. See REPRODUCE.txt and the pinned study reports.\n'
                      b'This package does not establish full experimental validation.\n',
        'REPRODUCE.txt': reproduction_text(script_name, report_name).encode(),
    }
    pins = {name: {'bytes': path.stat().st_size, 'sha256': checksum(path)}
            for name, path in sorted(files.items())}
    pins.update({name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                 for name, data in extras.items()})
    expected = pins['openswing/' + report_name]['sha256']
    manifest = {
        'format': 'openswing-st4-primary-evidence', 'version': 1, 'files': pins,
        'baseline_modules': baseline, 'current_modules': current,
        'upstream_revision': revision, 'upstream_asw_count': 279,
        'omitted_paths': sorted(excluded, key=lambda item: item['path']),
        'additional_work_exclusions': args.exclude_work,
        'audit': {'script': script_name, 'report': report_name, 'sha256': expected},
        'original_locations': {'repository': str(ROOT), 'work': str(work)},
        'scope': 'Pinned evidence and reproducibility; no full physical validation claim.',
    }
    manifest_bytes = (json.dumps(manifest, indent=2) + '\n').encode()
    extras['MANIFEST.json'] = manifest_bytes
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    # Publish the final archive only after extracted bytes and the independent
    # audit pass. Failure leaves its extraction/log for diagnosis.
    with tempfile.TemporaryDirectory(prefix='st4-primary-package-', dir=DESTINATION.parent) as temporary:
        staged = Path(temporary) / DESTINATION.name
        package(staged, list(files.items()), extras)
        extract_and_check(staged, target, pins, manifest_bytes)
        link = target / 'work/primary-baseline-source/.reference'
        require(not link.exists() and not link.is_symlink(), 'Unexpected extracted baseline reference path.')
        link.symlink_to('../../openswing/.reference', target_is_directory=True)
        environment = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
                           PYTHONNOUSERSITE='1', PYTHONPATH=str(target / 'openswing'))
        with (work / 'archive-reproduction.log').open('w') as output:
            subprocess.run([sys.executable, script_name, '--work', '../work', '--output', 'check.json'],
                           cwd=target / 'openswing', env=environment, stdout=output,
                           stderr=subprocess.STDOUT, check=True)
        require(checksum(target / 'openswing/check.json') == expected,
                'Extracted transition audit differs from the pinned report.')
        os.replace(staged, DESTINATION)
    result = {
        'status': 'PASS_ST4_PRIMARY_ARCHIVE_REEXTRACTION_AND_IDENTICAL_AUDIT',
        'path': DESTINATION.relative_to(ROOT).as_posix(),
        'bytes': DESTINATION.stat().st_size, 'sha256': checksum(DESTINATION),
        'verified_members': len(pins), 'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
        'target': str(target), 'reproduced_audit_sha256': expected,
        'baseline_module_count': len(baseline), 'current_module_count': len(current),
        'upstream_asw_count': 279, 'script_sha256': checksum(__file__),
    }
    (work / 'archive-result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
