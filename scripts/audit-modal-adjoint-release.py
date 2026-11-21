"""Verify the released kernel, evidence, archives and served app against tests."""
from pathlib import Path
from zipfile import ZipFile
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'docs/validation'


def digest(stream):
    h=hashlib.sha256()
    for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def sha(path):
    with Path(path).open('rb') as stream:return digest(stream)


def member(archive,name):
    with archive.open(name) as stream:return digest(stream)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--url',default='http://127.0.0.1:8000');args=parser.parse_args();w=args.work
    audit=json.loads((D/'modal-adjoint-transition.json').read_text())
    assert audit['status']=='PASS_SPARSE_ADJOINT_SOURCE_AND_NUMERICAL_CONTINUITY'
    pins=audit['candidate_modules'];assert len(pins)==97
    for name,h in pins.items():
        for folder in ['openswing','public/kernel','dist/kernel']:
            assert sha(ROOT/folder/name)==h,(folder,name)
    for name,h in audit['test_source_sha256'].items():assert sha(ROOT/name)==h,name
    for name,h in audit['evidence_sha256'].items():assert sha(D/name)==h,name
    assert audit['script_sha256']==sha(ROOT/'scripts/verify-modal-adjoint-transition.py')
    browser=json.loads((D/'modal-adjoint-browser.json').read_text())
    assert browser['status']=='PASS_FRESH_BROWSER_MODAL_ADJOINTS' and browser['offline'] and browser['served_build']
    assert browser['modules']==pins and len(browser['modes'])==3
    assert browser['test_sha256']==sha(ROOT/'tests/browser/modal-adjoint.spec.js')
    for row in browser['modes']:assert row['result']['software_provenance']['modules']==pins
    coverage=json.loads((D/'isae-coverage.json').read_text())
    assert coverage['modules']==pins and len(coverage['cases'])==41 and not coverage['full_suite_validated']
    assert sum(bool(c['evidence']) for c in coverage['cases'])==16 and not any(c['fully_validated'] for c in coverage['cases'])
    for name,h in coverage['study_sha256'].items():assert sha(D/name)==h,name
    assert coverage['source_continuity']['studies']['pazy-loaded-comparison']['status']=='original_run_preserved_before_sparse_adjoint_recovery'
    assert coverage['source_continuity']['adjoint_transition']['sha256']==sha(D/'modal-adjoint-transition.json')
    inventory=json.loads((D/'isae-suite-inventory.json').read_text())
    previous_inventory=json.loads((w/'baseline-isae-suite-inventory.json').read_text())
    assert inventory['kernel_modules']==pins
    for name in inventory:
        if name!='kernel_modules':assert inventory[name]==previous_inventory[name],name
    archive_check=json.loads((w/'archive-result.json').read_text())
    assert archive_check['status']=='PASS_ARCHIVE_REEXTRACTION_AND_IDENTICAL_TRANSITION_AUDIT'
    assert archive_check['sha256']==sha(D/'modal-adjoint-evidence.zip')
    meta=json.loads((ROOT/'public/distribution.json').read_text())
    previous=json.loads((w/'baseline-archive-index.json').read_text());archives=list(D.rglob('*.zip'))
    with ZipFile(ROOT/'public/openswing-source.zip') as source,ZipFile(ROOT/'public/openswing-validation.zip') as raw,ZipFile(ROOT/'dist/openswing-local.zip') as local:
        catalog=json.loads(source.read('openswing/docs/validation/archive-index.json'))
        assert meta['validation']['archives']==len(archives)==131 and len(previous['archives'])==130
        for name,pin in previous['archives'].items():assert catalog['archives'][name]==pin,name
        for p in archives:
            name=p.relative_to(ROOT).as_posix();pin=catalog['archives'][name]
            assert p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256']==member(raw,'openswing/'+name)
            assert 'openswing/'+name not in source.namelist()
        for folder in ['openswing','web','tests','examples','scripts','docs','public/licenses','public/fonts']:
            for p in(ROOT/folder).rglob('*'):
                if not p.is_file() or '__pycache__' in p.parts or '.pytest_cache' in p.parts or p in archives:continue
                assert member(source,'openswing/'+p.relative_to(ROOT).as_posix())==sha(p),str(p)
        for name in ['README.md','LICENSE','THIRD_PARTY.md','package.json','package-lock.json','pyproject.toml','index.html','playwright.config.js','.gitignore']:
            assert member(source,'openswing/'+name)==sha(ROOT/name)
        for p in(ROOT/'dist').rglob('*'):
            if not p.is_file() or p.name in ['openswing-local.zip','openswing-validation.zip','distribution.json'] or '.openai' in p.parts:continue
            assert member(local,p.relative_to(ROOT/'dist').as_posix())==sha(p),str(p)
        assert 'openswing-validation.zip' not in local.namelist()
        assert json.loads(local.read('distribution.json'))==dict(meta,kind='local',validation=None)
    for key in ['source','validation']:
        p=ROOT/'public'/meta[key]['file']
        assert p.stat().st_size==meta[key]['bytes'] and sha(p)==meta[key]['sha256']==sha(ROOT/'dist'/p.name)
    tested=json.loads((w/'tested-browser-assets.json').read_text())
    previous_assets=json.loads((w/'baseline-served-assets.json').read_text())
    assert tested.keys()==previous_assets.keys() and len(tested)==167
    assert [n for n in tested if tested[n]!=previous_assets[n]]==['kernel/linear_dynamics.py']
    def served(item):
        name,h=item;assert sha(ROOT/'dist'/name)==h
        with urllib.request.urlopen(args.url+'/'+name,timeout=30) as stream:assert digest(stream)==h,name
        return name
    with ThreadPoolExecutor(max_workers=4) as pool:assets=list(pool.map(served,tested.items()))
    downloads={}
    for name in ['openswing-source.zip','openswing-validation.zip','openswing-local.zip']:
        req=urllib.request.Request(args.url+'/'+name,headers={'Range':'bytes=0-63'})
        with urllib.request.urlopen(req,timeout=30) as response:
            data=response.read();assert response.status==206 and len(data)==64
            with (ROOT/'dist'/name).open('rb') as stream:assert data==stream.read(64)
            downloads[name]=dict(status=response.status,content_range=response.headers['Content-Range'])
    assert sum('| Partial |' in line for line in(ROOT/'docs/REQUIREMENTS.md').read_text().splitlines())==40
    out=dict(status='PASS_SPARSE_MODAL_ADJOINT_RELEASE_AND_PRESERVED_VALIDATION_HISTORY',modules=pins,
        changed_solver_modules=1,selected_tests=sum(r['passed'] for r in audit['tests'].values()),
        native_pencils=26,native_eigenpairs=416,wasm_pencils=3,offline_browser_cases=3,
        partial_families=16,pending_families=25,fully_validated_families=0,
        raw_archives=131,prior_archives_unchanged=130,served_assets=len(assets),metadata=meta,
        evidence_sha256=sha(D/'modal-adjoint-evidence.zip'),transition_sha256=sha(D/'modal-adjoint-transition.json'),
        local_bytes=(ROOT/'dist/openswing-local.zip').stat().st_size,local_sha256=sha(ROOT/'dist/openswing-local.zip'),
        audit_script_sha256=sha(__file__),download_checks=downloads,
        limitations=['No fresh full-repository regression, full physical-validation or ASWING-parity claim.',
            'Previous studies retain their original source pins. The source transition checks saved matrices and three fresh browser solves.',
            'The observed eigensolver speedup is not an end-to-end browser timing guarantee.',
            'ISAE coverage and all 40 Partial requirements remain unchanged.'])
    (w/'audit-release.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k!='modules'},indent=2),flush=True)


if __name__=='__main__':main()
