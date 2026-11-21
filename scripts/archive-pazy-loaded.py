"""Archive the CONM2 correction and loaded Pazy comparison, preserving history."""
from pathlib import Path
import argparse
import json
from distribution import package,checksum

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'docs/validation'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);args=parser.parse_args();files={}
    def add(path,digest=None):
        path=Path(path)
        if digest is not None:assert checksum(path)==digest,path
        files['openswing/'+path.relative_to(ROOT).as_posix()]=path
    comparison=json.loads((D/'pazy-loaded-comparison.json').read_text())
    assert comparison['status']=='COMPARISONS_COMPLETE_NOT_PHYSICALLY_VALIDATED'
    manifest_path=ROOT/'.reference/pazy-primary/manifest.json';manifest=json.loads(manifest_path.read_text());add(manifest_path)
    for name,pin in manifest['files'].items():add(manifest_path.parent/manifest['revision']/name,pin['sha256'])
    for name,pin in comparison['modules'].items():add(ROOT/'openswing'/name,pin)
    for path in (ROOT/'examples').glob('pazy-primary*'):add(path)
    reports=[D/f'pazy-loaded-{name}.json' for name in ['zero','modes','static','reference']]
    reports.extend((ROOT/'.reference/pazy-loaded-historical').glob('pazy-loaded-*.json'))
    # Both superseded and corrected caches are retained with their own exact
    # helper/module identities. A stopped superseded run is not a passing run.
    for report in reports:
        for row in json.loads(report.read_text())['runs']:
            path=ROOT/row['cache'];add(path,row['sha256']);run=json.loads(path.read_text())
            if 'matrices' in run:add(ROOT/run['matrices']['path'],run['matrices']['sha256'])
    for path in (ROOT/'.reference/pazy-loaded-historical').iterdir():
        if path.is_file():add(path)
    for path in D.glob('pazy-loaded-*'):
        if path.suffix!='.zip':add(path)
    for name in ['isae-st2-source-audit.json','pazy-primary-mapping.json','pazy-primary-comparison.md','pazy-primary-comparison.json','pazy-primary-checks.json']:
        add(D/name)
    for pattern in ['*pazy-loaded*','pazy_loaded*.py','pazy_primary*.py']:
        for path in (ROOT/'scripts').glob(pattern):add(path)
    for name in ['scripts/distribution.py','tests/browser/pazy-loaded.spec.js','web/plot-colors.js']:add(ROOT/name)
    for path in args.work.glob('*.log'):files['execution/'+path.name]=path
    for folder in ['browser','browser-harness-initial']:
        for path in (args.work/folder).rglob('*'):
            if path.is_file():files['execution/'+path.relative_to(args.work).as_posix()]=path
    pins={name:dict(bytes=p.stat().st_size,sha256=checksum(p)) for name,p in files.items()}
    notes='''Corrected primary Pazy inputs and loaded comparisons

Numerical comparisons, not full experimental validation. The historical primary
inertia conversion used the wrong interpretation of spreadsheet off-diagonals.
The original Nastran rigid-body MO matrices prove the corrected CONM2 product
signs. Use pazy-primary-conm2-*.asw, not the superseded pazy-primary-skin*.asw.
The previous pazy-primary-evidence.zip is preserved separately, unchanged.

This archive includes 105 pinned primary files, 97 unchanged production modules,
225 corrected static states, 10 zero-gravity and 16 gravity-loaded modal states,
28 independent nonlinear rod references, 77 measured rows, and 10 WASM/browser
checks each. Full native A/M matrices and static fields are retained. The
historical helper versions, 225 superseded statics, and stopped 13/16 modal run
are explicitly stored under .reference/pazy-loaded-historical. Stopping that
run followed discovery of the input error, not a timeout or failed convergence.
An initial browser harness was stopped before its first solve because it used
the aerodynamic gravity controls hidden in structural mode. Its exact test,
log and reason are retained; the corrected harness uses static gravity fields.

From extracted openswing/, run scripts/summarize-pazy-loaded.py with NumPy,
SciPy and Matplotlib. It verifies the source pins, complete caches and runtime
records and regenerates JSON/Markdown/PNG/SVG without repeating the solves.
Native, independent reference, WASM and browser scripts reproduce the solves.

The intrinsic extension-torsion term remains explicitly projected; both full
and projected independent references are provided. Exact fixture geometry,
literal out-of-range attachments, experimental discrepancies and uncertainty
remain unresolved. No flutter or time-response claim. Coverage stays at 16
partial families and 25 pending, no fully validated family. The broad ASWING
goal remains active and incomplete, with all 40 requirements Partial.
'''
    destination=D/'pazy-loaded-evidence.zip'
    package(destination,list(files.items()),{'README.txt':notes.encode(),
        'MANIFEST.json':(json.dumps(dict(files=pins,comparison_sha256=checksum(D/'pazy-loaded-comparison.json')),indent=2)+'\n').encode()})
    out=dict(status='PACKAGED_CORRECTED_PAZY_LOADED_EVIDENCE',path=destination.relative_to(ROOT).as_posix(),
        bytes=destination.stat().st_size,sha256=checksum(destination),files=len(files))
    (args.work/'archive-result.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))


if __name__=='__main__':main()
