"""Package the pinned Pazy sources, native solutions and runtime evidence."""
from pathlib import Path
import argparse
import json
from distribution import package, checksum

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'docs/validation'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--work',type=Path,required=True,help='Directory containing the retained execution logs and browser screenshots.')
    args=parser.parse_args()
    source=json.loads((D/'isae-st2-source-audit.json').read_text())
    static=json.loads((D/'isae-st2-static.json').read_text())
    modal=json.loads((D/'isae-st2-modes.json').read_text())
    comparison=json.loads((D/'isae-st2-comparison.json').read_text())
    files={}
    def add(path,digest=None):
        path=Path(path)
        if digest is not None:assert checksum(path)==digest,path
        files['openswing/'+path.relative_to(ROOT).as_posix()]=path
    for folder,revision,records in [('isae-validation',source['upstream_revision'],source['sources']),
                                    ('pazy-primary',source['primary']['revision'],source['primary']['files'])]:
        add(ROOT/'.reference'/folder/'manifest.json')
        for name,pin in records.items():add(ROOT/'.reference'/folder/revision/name,pin['sha256'])
    manifest=json.loads((ROOT/'.reference/isae-validation/manifest.json').read_text())
    for name in ['README.md','5 - Technical Reports/Experimental_validation_of_ASWING_Part_3__Structure_V5.pdf']:
        add(ROOT/'.reference/isae-validation'/source['upstream_revision']/name,manifest['files'][name]['sha256'])
    for name,digest in comparison['modules'].items():add(ROOT/'openswing'/name,digest)
    for row in static['runs'].values():add(ROOT/row['cache'],row['sha256'])
    for row in modal['runs']:
        add(ROOT/row['cache'],row['sha256'])
        run=json.loads((ROOT/row['cache']).read_text());add(ROOT/run['matrices']['path'],run['matrices']['sha256'])
    for path in D.glob('isae-st2*'):
        if path.suffix!='.zip':add(path)
    for path in (ROOT/'scripts').glob('*isae*st2*'):add(path)
    for name in ['scripts/distribution.py','tests/browser/isae-st2.spec.js']:add(ROOT/name)
    # Preserve earlier pilot/harness records without treating them as passing
    # production results. Authoritative runs are pinned by the JSON reports.
    for path in args.work.rglob('*'):
        if path.is_file() and path.suffix in ['.json','.log','.png','.npz']:
            if path.name.startswith(('archive-','audit-','reproduction-')):continue
            files['execution/'+path.relative_to(args.work).as_posix()]=path
    pins={name:dict(bytes=p.stat().st_size,sha256=checksum(p)) for name,p in files.items()}
    notes='''Pazy ST-2 evidence — partial comparison, not physical validation

Extract alongside an OpenSwing source checkout: the openswing/ tree supplies
the required .reference inputs/caches, reports and exact study/solver scripts.
The execution/ tree preserves logs, pilots and browser screenshots. The old
static harness TypeError and corrected successful run are separate records.
They do not indicate a rejected final native condition.

The source audit pins146 original ISAE files and105 primary-author files.
The original six .asw inputs retain their invalid out-of-domain attachments.
The native caches record246 solved explicit static reconstructions and16
air-free modal states, including complete states and compressed A/M matrices.
No archived field is silently edited to match measured data. The final
comparison postprocesses the primary x-z chord angle from saved rotations;
the older chord-elevation diagnostic remains in the raw static report.

Run scripts/summarize-isae-st2.py with NumPy and Matplotlib to verify all consumed
pins and rebuild the final comparison/plots without solving. Run the source,
static, modal, WASM and browser scripts described in the report to reproduce
calculations; scipy and the local Pyodide/Chromium setup are then required.
The browser report was captured offline after boot from the actual served
endpoint-repair build; solver and UI assets are unchanged by this study.

Neither reconstruction is the exact experimental setup. Skin-specific full
primary stiffness/inertia, the physical spanwise load offset, added rod and
instrument masses, remaining curves/shapes and uncertainty remain unfinished.
All40 broad ASWING requirements remain Partial. No full family/suite pass.
'''
    destination=D/'isae-st2-evidence.zip'
    package(destination,list(files.items()),{'README.txt':notes.encode(),
        'MANIFEST.json':(json.dumps(dict(files=pins,comparison_sha256=checksum(D/'isae-st2-comparison.json')),indent=2)+'\n').encode()})
    result=dict(path=destination.relative_to(ROOT).as_posix(),bytes=destination.stat().st_size,
                sha256=checksum(destination),files=len(files),status='PACKAGED_PINNED_ST2_EVIDENCE')
    (args.work/'archive-result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
