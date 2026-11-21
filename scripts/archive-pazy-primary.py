"""Package the primary-property Pazy comparison and its reproducible evidence."""
from pathlib import Path
import argparse
import json
from distribution import package, checksum

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'docs/validation'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args();files={}
    def add(path,digest=None):
        path=Path(path)
        if digest is not None:assert checksum(path)==digest,path
        files['openswing/'+path.relative_to(ROOT).as_posix()]=path
    native=json.loads((D/'pazy-primary-mapping.json').read_text())
    comparison=json.loads((D/'pazy-primary-comparison.json').read_text())
    manifest_path=ROOT/'.reference/pazy-primary/manifest.json'
    manifest=json.loads(manifest_path.read_text());add(manifest_path)
    for name,pin in manifest['files'].items():
        add(manifest_path.parent/manifest['revision']/name,pin['sha256'])
    for name,pin in native['modules'].items():add(ROOT/'openswing'/name,pin)
    for model in native['mapping']['models'].values():add(ROOT/model['path'],model['sha256'])
    for mesh in comparison['meshes'].values():add(ROOT/mesh['path'],mesh['sha256'])
    for row in native['runs']:
        path=ROOT/row['cache'];add(path,row['sha256']);run=json.loads(path.read_text())
        add(ROOT/run['matrices']['path'],run['matrices']['sha256'])
    for name,pin in comparison['attachment_audit']['source_sha256'].items():add(ROOT/name,pin)
    add(ROOT/comparison['plot_palette']['path'],comparison['plot_palette']['sha256'])
    for path in D.glob('pazy-primary*'):
        if path.suffix!='.zip':add(path)
    for pattern in ['*pazy-primary*','pazy_primary*.py']:
        for path in (ROOT/'scripts').glob(pattern):add(path)
    for name in ['scripts/distribution.py','tests/browser/pazy-primary.spec.js']:add(ROOT/name)
    for name in ['native.log','pilot-native.log','pilot-native.json','discrete.log','wasm.log','browser.log']:
        path=args.work/name
        if path.is_file():files['execution/'+name]=path
    for path in (args.work/'browser').rglob('*'):
        if path.is_file():files['execution/'+path.relative_to(args.work).as_posix()]=path
    pins={name:dict(bytes=p.stat().st_size,sha256=checksum(p)) for name,p in files.items()}
    notes='''Primary Pazy model evidence: numerical comparison, not experimental validation

The openswing/ tree contains the pinned primary-author data, four explicit
derived .asw inputs, ten native modal solutions with complete A/M matrices,
independent references, six WASM and six offline browser comparisons, and the
exact 97 production modules used. The execution/ tree retains logs and images.
No production module was changed. Prior simplified ST-2 evidence remains in
its separate archive and is not overwritten by this study.

The primary model has a small intrinsic extension-torsion term that documented
ASWING section fields cannot express. Its explicit removal is quantified by a
strain-energy bound; both full and projected independent references are saved.
All other stiffness terms, nodal masses, CG offsets and full inertia tensors
are preserved. No property was fitted to the reported frequencies.

From the extracted openswing/ directory, run scripts/summarize-pazy-primary.py
with NumPy, SciPy and Matplotlib to verify pins and rebuild the comparison and
plots without repeating the solves. Run scripts/audit-pazy-primary-discrete.py
for the independent coarse-mesh rank/frequency check. The native/WASM/browser
scripts in this archive reproduce the calculations with their stated runtime.

The 120-interval native states are not included in the WASM/browser sample.
This gravity-free numerical comparison does not validate self-weight, loaded
modes, static measured curves or flutter. The original literal Pazy files
still have unresolved out-of-domain attachment semantics. Family coverage
remains 16 partial/25 pending, with no fully validated family. All 40 broad
ASWING requirements remain Partial; the full user goal is incomplete.
'''
    destination=D/'pazy-primary-evidence.zip'
    package(destination,list(files.items()),{'README.txt':notes.encode(),
        'MANIFEST.json':(json.dumps(dict(files=pins,comparison_sha256=checksum(D/'pazy-primary-comparison.json')),indent=2)+'\n').encode()})
    result=dict(path=destination.relative_to(ROOT).as_posix(),bytes=destination.stat().st_size,
        sha256=checksum(destination),files=len(files),status='PACKAGED_PINNED_PRIMARY_PAZY_EVIDENCE')
    (args.work/'archive-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
