"""Preserve source, original matrices, vector comparisons and runtime evidence."""
from pathlib import Path
from zipfile import ZipFile
import argparse
import json
import os
import subprocess
import sys
from distribution import checksum, package

ROOT = Path(__file__).resolve().parents[1]
D = ROOT/'docs/validation'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    w = args.work.resolve()
    report = json.loads((D/'modal-adjoint-transition.json').read_text())
    assert report['status'] == 'PASS_SPARSE_ADJOINT_SOURCE_AND_NUMERICAL_CONTINUITY'
    files = {}
    def add(path, name=None, pin=None):
        path = Path(path)
        if pin is not None:
            assert checksum(path) == pin
        files[name or 'openswing/'+path.relative_to(ROOT).as_posix()] = path
    for side in ['baseline', 'candidate']:
        for name, pin in report[side+'_modules'].items():
            add(w/side/'openswing'/name, 'work/'+side+'/openswing/'+name, pin)
    for name, pin in report['candidate_modules'].items():
        add(ROOT/'openswing'/name, pin=pin)
    for name, pin in report['test_source_sha256'].items():
        add(ROOT/name, pin=pin)
        add(w/'candidate'/name, 'work/candidate/'+name, pin)
    for browser_test in ['tests/browser/modal-adjoint.spec.js','tests/browser/modal-adjoint-display.spec.js']:
        add(ROOT/browser_test)
        add(w/'candidate'/browser_test, 'work/candidate/'+browser_test)
    for name in ['verify-modal-adjoint.py', 'test-modal-adjoint-wasm.mjs',
                 'verify-modal-adjoint-transition.py', 'archive-modal-adjoint.py',
                 'audit-modal-adjoint-release.py', 'pazy-loaded-runtime-cases.mjs',
                 'verify-frozen-influences.py', 'verify-wake-core.py', 'distribution.py']:
        add(ROOT/'scripts'/name)
    for pattern in ['modal-adjoint-*.json', 'modal-adjoint.md']:
        for path in D.glob(pattern):
            add(path)
    for name in ['zero', 'modes', 'static']:
        path = D/f'pazy-loaded-{name}.json'
        add(path)
        for row in json.loads(path.read_text())['runs']:
            # The runtime selector loads four static controls before filtering
            # to the three modal cases. Preserve their inputs too.
            if name == 'static' and row['specification']['refinement'] != 4:
                continue
            cache = ROOT/row['cache']
            add(cache, pin=row['sha256'])
            data = json.loads(cache.read_text())
            if 'matrices' in data:
                add(ROOT/data['matrices']['path'], pin=data['matrices']['sha256'])
    for path in w.iterdir():
        if path.is_file() and (path.suffix in ['.log', '.xml', '.txt', '.json', '.prof', '.npz']):
            # Release/build records describe the archive and are necessarily
            # outside it. Avoid archive self-reference on a later reproduction.
            if path.stem not in ['archive-result', 'audit-release', 'final-closeout']:
                add(path, 'work/'+path.name)
    for folder in ['pencils', 'browser', 'display', 'display-invalid-icd']:
        for path in (w/folder).rglob('*'):
            if path.is_file():
                add(path, 'work/'+path.relative_to(w).as_posix())
    notes = '''Sparse modal adjoint verification

This is a numerical algorithm change, not additional experimental validation.
The original full A/M equations, finite-subspace classification, physical right
vectors and eigenpair acceptance checks are preserved. Sparse bordered solves
recover simple-pole adjoints; generalized-Schur/null-space recovery remains for
repeated, weakly paired or rejected poles. Exact integrators retain their kernel.

All 26 original corrected Pazy modal matrices, before/after left and right
vectors, native timings, three WASM replays and three fresh offline browser
solves are retained. Runtime and targeted regression source hashes are checked.
The initial test-design failure and missing-helper collection error are retained
with explanations; neither is reported as a passing test. Earlier physical
studies keep their original solver hashes and raw archives unchanged.
The numerical browser run's blank SwiftShader screenshots are preserved. A
separate saved-result Vulkan check verifies rendering without another solve.
Its invalid-ICD launch was stopped for that documented setup error and retained.

From extracted openswing/, run:
  python3 scripts/verify-modal-adjoint-transition.py --work ../work --output check.json
This verifies the archived source boundary, input and result pins, and passing
selected regressions. The native replay can be repeated with NumPy/SciPy:
  python3 scripts/verify-modal-adjoint.py --work ../work --candidate ../work/candidate --baseline ../work/baseline
Its output includes fresh timings and will change saved comparison hashes.
WASM/browser reruns additionally need the ordinary app runtime and build tools.

No full-suite, experimental-agreement, flutter or ASWING-parity claim. ISAE
coverage remains 16 partial families, 25 pending, zero fully validated families.
All 40 broad requirements remain Partial.
'''
    pins = {name:dict(bytes=p.stat().st_size, sha256=checksum(p)) for name,p in files.items()}
    destination = D/'modal-adjoint-evidence.zip'
    package(destination, list(files.items()), {'README.txt':notes.encode(),
        'MANIFEST.json':(json.dumps(dict(files=pins),indent=2)+'\n').encode()})
    target = w/'reproduction'
    target.mkdir(exist_ok=False)
    with ZipFile(destination) as archive:
        archive.extractall(target)
    for name, pin in pins.items():
        assert (target/name).stat().st_size == pin['bytes'] and checksum(target/name) == pin['sha256']
    with (w/'reproduction.log').open('w') as output:
        subprocess.run([sys.executable, 'scripts/verify-modal-adjoint-transition.py',
                        '--work', '../work', '--output', 'check.json'],
                       cwd=target/'openswing', env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),
                       stdout=output,stderr=subprocess.STDOUT,check=True)
    assert checksum(target/'openswing/check.json') == checksum(D/'modal-adjoint-transition.json')
    result = dict(status='PASS_ARCHIVE_REEXTRACTION_AND_IDENTICAL_TRANSITION_AUDIT',
        path=destination.relative_to(ROOT).as_posix(),bytes=destination.stat().st_size,
        sha256=checksum(destination),verified_members=len(pins),
        reproduced_audit_sha256=checksum(target/'openswing/check.json'),script_sha256=checksum(__file__))
    (w/'archive-result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
