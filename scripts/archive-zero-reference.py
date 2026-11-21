"""Preserve and re-extract zero-area/ST-4 numerical evidence and failures."""
from pathlib import Path
from zipfile import ZipFile
import argparse
import json
import os
import subprocess
import sys
from distribution import checksum,package

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'docs/validation'


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();w=a.work.resolve()
    report=json.loads((D/'zero-reference-transition.json').read_text());assert report['status']=='PASS_ZERO_REFERENCE_SOURCE_AND_NUMERICAL_CONTINUITY'
    files={}
    def add(path,name=None,pin=None):
        path=Path(path)
        if pin is not None:assert checksum(path)==pin
        name=name or 'openswing/'+path.relative_to(ROOT).as_posix()
        if name in files:assert files[name]==path
        files[name]=path
    for side in ['baseline','candidate']:
        for name,pin in report[side+'_modules'].items():add(w/side/'openswing'/name,'work/'+side+'/openswing/'+name,pin)
    for name,pin in report['candidate_modules'].items():add(ROOT/'openswing'/name,pin=pin)
    for name,pin in report['test_source_sha256'].items():
        add(ROOT/name,pin=pin);add(w/'candidate'/name,'work/candidate/'+name,pin)
    browser_test='tests/browser/zero-reference.spec.js';add(ROOT/browser_test);add(w/'candidate'/browser_test,'work/candidate/'+browser_test)
    for path in (ROOT/'tests/fixtures').rglob('*'):
        if path.is_file():add(path)
    for name in ['pyproject.toml','tests/conftest.py']:
        if (ROOT/name).exists():add(ROOT/name)
    scripts=['verify-zero-reference.py','verify-isae-st4.py','verify-isae-st4-reference.py','isae_st4_reference.py',
        'verify-isae-st4-transfer.py','isae_st4_transfer.py','summarize-zero-reference-structure.py',
        'test-zero-reference-wasm.mjs','verify-zero-reference-transition.py','archive-zero-reference.py',
        'audit-zero-reference-release.py','inventory-isae-validation.py','fetch-isae-validation.py','distribution.py']
    for name in scripts:add(ROOT/'scripts'/name)
    for pattern in ['zero-reference-*.json','zero-reference.md']:
        for path in D.glob(pattern):add(path)
    for folder in ['isae-st4-native','isae-st4-independent','isae-st4-primary']:
        for path in (ROOT/'.reference'/folder).rglob('*'):
            if path.is_file():add(path)
    manifest_path=ROOT/'.reference/isae-validation/manifest.json';manifest=json.loads(manifest_path.read_text());add(manifest_path)
    add(ROOT/'.reference/isae-validation/upstream-tree.json')
    for name,pin in manifest['files'].items():
        if name.endswith('.asw') or name.startswith('3 - Structure/CASE - ST4 Concentrated weight/'):
            add(ROOT/'.reference/isae-validation'/manifest['revision']/name,pin=pin['sha256'])
    for path in (ROOT/'examples').glob('*.asw'):add(path)
    for path in w.iterdir():
        if path.is_file() and path.suffix in ['.log','.xml','.txt','.json','.py'] and path.stem not in ['archive-result','audit-release','final-closeout']:
            add(path,'work/'+path.name)
    for path in (w/'browser-results').rglob('*'):
        if path.is_file():add(path,'work/'+path.relative_to(w).as_posix())
    notes='''Zero-reference input compatibility and ST-4 numerical evidence

Literal zero-area inputs are retained for structural and vacuum analyses.
Aerodynamic normalization explicitly requires positive area. The two changed
modules contain only eligibility checks; physical equations are unchanged.

This archive retains 81 native modal states and matrices, 81 corrected energy
beam states, 27 continuous-beam calculations, three WASM and three fresh offline
browser cases, and 129 selected regressions. Failed initial energy meshes,
test expectations and pilot diagnostics are preserved. No full regression or
experimental-validation pass is claimed. Primary inertia, table/CSV, gravity,
surrounding-air and archive-provenance questions remain. Coverage stays 16
partial families and 25 pending, zero fully validated.

From extracted openswing/, run:
  python3 scripts/verify-zero-reference-transition.py --work ../work --output check.json
The resulting audit must be byte-identical to docs/validation/zero-reference-transition.json.
See docs/validation/zero-reference.md for numerical rerun scripts and scope.
The original file manifest describes the full repository; this archive includes
all original ASW files and the ST-4 source folder, not all other case data.
'''
    pins={name:dict(bytes=p.stat().st_size,sha256=checksum(p)) for name,p in files.items()}
    destination=D/'zero-reference-evidence.zip'
    package(destination,list(files.items()),{'README.txt':notes.encode(),'MANIFEST.json':(json.dumps(dict(files=pins),indent=2)+'\n').encode()})
    target=w/'reproduction';target.mkdir(exist_ok=False)
    with ZipFile(destination) as archive:archive.extractall(target)
    for name,pin in pins.items():assert (target/name).stat().st_size==pin['bytes'] and checksum(target/name)==pin['sha256']
    with (w/'reproduction.log').open('w') as output:
        subprocess.run([sys.executable,'scripts/verify-zero-reference-transition.py','--work','../work','--output','check.json'],
            cwd=target/'openswing',env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),stdout=output,stderr=subprocess.STDOUT,check=True)
    assert checksum(target/'openswing/check.json')==checksum(D/'zero-reference-transition.json')
    out=dict(status='PASS_ARCHIVE_REEXTRACTION_AND_IDENTICAL_TRANSITION_AUDIT',path=destination.relative_to(ROOT).as_posix(),
        bytes=destination.stat().st_size,sha256=checksum(destination),verified_members=len(pins),
        reproduced_audit_sha256=checksum(target/'openswing/check.json'),script_sha256=checksum(__file__))
    (w/'archive-result.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))


if __name__=='__main__':main()
