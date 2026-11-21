"""Check current scientific sources and reports in refreshed local downloads."""
import hashlib
import argparse
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/isae/st1-st6-current-20261103/delivery.json'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=OUT)
parser.add_argument('--additional-report',action='append',default=[])
args=parser.parse_args()


def digest(stream):
    h=hashlib.sha256()
    while block:=stream.read(1024*1024):h.update(block)
    return h.hexdigest()


def file_digest(path):
    with Path(path).open('rb') as stream:return digest(stream)


modules=sorted(p.name for p in (ROOT/'openswing').glob('*.py'))
assert len(modules)==136
hashes={}
for name in modules:
    raw=(ROOT/'openswing'/name).read_bytes();hashes[name]=hashlib.sha256(raw).hexdigest()
    for directory in ('public/kernel','dist/kernel'):
        assert (ROOT/directory/name).read_bytes()==raw,(directory,name)
for directory in ('public/kernel','dist/kernel'):
    assert sorted(json.loads((ROOT/directory/'manifest.json').read_text()))==modules

source=ROOT/'public/openswing-source.zip';dist_source=ROOT/'dist/openswing-source.zip'
source_digest=file_digest(source);assert file_digest(dist_source)==source_digest
metadata=json.loads((ROOT/'public/distribution.json').read_text())
assert (ROOT/'public/distribution.json').read_bytes()==(ROOT/'dist/distribution.json').read_bytes()
assert metadata['source']['sha256']==source_digest
reports=['docs/validation/ISAE_STATUS.md','docs/STATUS.md','docs/validation/isae-suite-backlog.md',
    *['docs/validation/'+name+suffix for name in ('isae-ua2-current-assessment-20261103','isae-st1-st6-current-20261103') for suffix in ('.md','.json')]]
reports.extend(args.additional_report)
with zipfile.ZipFile(source) as archive:
    for name in modules:assert hashlib.sha256(archive.read('openswing/openswing/'+name)).hexdigest()==hashes[name]
    for name in reports:assert archive.read('openswing/'+name)==(ROOT/name).read_bytes(),name

local=ROOT/'dist/openswing-local.zip';runtime={}
with zipfile.ZipFile(local) as archive:
    assert sorted(json.loads(archive.read('kernel/manifest.json')))==modules
    for name in modules:assert hashlib.sha256(archive.read('kernel/'+name)).hexdigest()==hashes[name]
    with archive.open('openswing-source.zip') as stream:assert digest(stream)==source_digest
    embedded=json.loads(archive.read('distribution.json'))
    assert embedded['kind']=='local' and embedded['source']['sha256']==source_digest
    for p in sorted((ROOT/'dist/runtime').rglob('*')):
        if not p.is_file():continue
        name=str(p.relative_to(ROOT/'dist'));value=file_digest(p)
        with archive.open(name) as stream:assert digest(stream)==value
        runtime[name]=value
    for p in (ROOT/'dist/assets').glob('worker-*.js'):
        name=str(p.relative_to(ROOT/'dist'));assert archive.read(name)==p.read_bytes();runtime[name]=file_digest(p)
receipt=dict(passed=True,solver_modules=136,reports_checked=reports,source_archive_sha256=source_digest,
    local_archive_sha256=file_digest(local),source_bytes=source.stat().st_size,local_bytes=local.stat().st_size,
    solver_sha256=hashes,runtime_sha256=runtime,verification_script_sha256=file_digest(Path(__file__)))
args.output.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k not in ('solver_sha256','runtime_sha256','reports_checked')}))
