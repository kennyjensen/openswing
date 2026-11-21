"""Check that unchanged tested assets and the new Pazy evidence ship together."""
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
    parser=argparse.ArgumentParser()
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--url',default='http://127.0.0.1:8000')
    args=parser.parse_args();w=args.work
    pins=json.loads((w/'baseline-modules.json').read_text())
    assert len(pins)==97
    for name,h in pins.items():
        for folder in ['openswing','public/kernel','dist/kernel']:assert sha(ROOT/folder/name)==h,(folder,name)
    comparison=json.loads((D/'isae-st2-comparison.json').read_text())
    checks=json.loads((D/'isae-st2-checks.json').read_text())
    assert comparison['modules']==checks['modules']==pins
    assert checks['status']=='PASS_ST2_COVERAGE_AUDIT_NOT_PHYSICAL_VALIDATION'
    assert checks['snapshot_sha256']==sha(D/'isae-st2-comparison.json')
    assert checks['script_sha256']==sha(ROOT/'scripts/summarize-isae-st2.py')
    for name,h in comparison['report_sha256'].items():assert sha(D/name)==h,name
    browser=json.loads((D/'isae-st2-browser.json').read_text())
    assert browser['status']=='PASS_EXPECTED_OUTCOMES' and browser['offline'] and browser['served_build']
    assert browser['modules']==pins and len(browser['statics'])==6 and len(browser['modes'])==4
    assert browser['test_sha256']==sha(ROOT/'tests/browser/isae-st2.spec.js')
    for row in browser['statics']+browser['modes']:assert row['result']['software_provenance']['modules']==pins
    coverage=json.loads((D/'isae-coverage.json').read_text())
    assert coverage['modules']==pins and len(coverage['cases'])==41 and not coverage['full_suite_validated']
    assert sum(bool(c['evidence']) for c in coverage['cases'])==16 and not any(c['fully_validated'] for c in coverage['cases'])
    for name,h in coverage['study_sha256'].items():assert sha(D/name)==h,name
    assert coverage['source_continuity']['studies']['isae-st2-comparison']['status']=='run_on_current_source'
    reproduction=json.loads((w/'reproduction-result.json').read_text())
    assert reproduction['status']=='PASS_ARCHIVE_REEXTRACTION_AND_IDENTICAL_POSTPROCESSING'
    assert reproduction['archive_sha256']==sha(D/'isae-st2-evidence.zip')
    meta=json.loads((ROOT/'public/distribution.json').read_text())
    previous=json.loads((w/'baseline-archive-index.json').read_text());archives=list(D.rglob('*.zip'))
    with ZipFile(ROOT/'public/openswing-source.zip') as source,ZipFile(ROOT/'public/openswing-validation.zip') as raw,ZipFile(ROOT/'dist/openswing-local.zip') as local:
        catalog=json.loads(source.read('openswing/docs/validation/archive-index.json'))
        assert meta['validation']['archives']==len(archives)==128 and len(previous['archives'])==127
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
    def served(item):
        name,h=item;assert sha(ROOT/'dist'/name)==h
        with urllib.request.urlopen(args.url+'/'+name,timeout=30) as stream:assert digest(stream)==h,name
        return name
    with ThreadPoolExecutor(max_workers=4) as pool:assets=list(pool.map(served,tested.items()))
    assert sum('| Partial |' in line for line in(ROOT/'docs/REQUIREMENTS.md').read_text().splitlines())==40
    out=dict(status='PASS_ST2_EVIDENCE_AND_UNCHANGED_BROWSER_DISTRIBUTIONS',modules=pins,
        changed_solver_modules=0,static_conditions=246,modal_conditions=16,wasm_solutions=12,offline_browser_solutions=10,
        partial_families=16,pending_families=25,fully_validated_families=0,
        raw_archives=128,prior_archives_unchanged=127,served_assets=len(assets),metadata=meta,
        evidence_sha256=sha(D/'isae-st2-evidence.zip'),reproduction_sha256=sha(w/'reproduction-result.json'),
        local_bytes=(ROOT/'dist/openswing-local.zip').stat().st_size,local_sha256=sha(ROOT/'dist/openswing-local.zip'),
        audit_script_sha256=sha(__file__),
        limitations=['No full physical-validation or ASWING parity claim. All40 broad requirements remain Partial.',
            'The original six Pazy inputs retain their attachment rejection. All solved static/modal cases use explicit derived inputs.',
            'The two static reconstructions retain simplified material properties and load/setup differences from the experiment.',
            'No application code changed; previously tested167 served assets remain byte-identical. Downloads add the current reports and raw evidence.'])
    (w/'audit-release.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k!='modules'},indent=2),flush=True)


if __name__=='__main__':main()
