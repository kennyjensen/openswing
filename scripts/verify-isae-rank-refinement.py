"""Verify the shipped rank refinement and its bounded literal/browser evidence."""
import ast
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/'artifacts/isae/ffwt4-rank-refinement-20261106'


def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def pin(path):return dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path.read_bytes()))
def stream_sha(stream):
    digest=hashlib.sha256()
    while chunk:=stream.read(1024*1024):digest.update(chunk)
    return digest.hexdigest()


def main():
    current={p.name:sha(p.read_bytes()) for p in sorted((ROOT/'openswing').glob('*.py'))}
    before={}
    for name in ('ffwt4-continuation-json-20261106','ffwt4-rank-refined-20261106'):
        folder=ROOT/'.reference/solver-snapshots'/name;archived={}
        for record in read(folder/'manifest.json')['files']:
            p=Path(record['archived']);assert p.stat().st_size==record['original']['bytes']
            archived[p.name]=sha(p.read_bytes());assert archived[p.name]==record['original']['sha256']
        assert set(archived)==set(current)
        if name=='ffwt4-rank-refined-20261106':assert archived==current
        else:before=archived
    assert [n for n in current if current[n]!=before[n]]==['structured_static.py']
    def physical_functions(path):
        tree=ast.parse(path.read_text());tree.body=[node for node in tree.body if not
            (isinstance(node,ast.FunctionDef) and node.name in ('check_initial_rank','refine_mechanical_rank_certificate'))]
        return ast.dump(tree)
    assert physical_functions(ROOT/'openswing/structured_static.py')==physical_functions(
        ROOT/'.reference/solver-snapshots/ffwt4-continuation-json-20261106/openswing/structured_static.py')
    for location in ('public/kernel','dist/kernel'):
        assert {p.name:sha(p.read_bytes()) for p in (ROOT/location).glob('*.py')}==current
    for location in ('public/openswing-source.zip','dist/openswing-source.zip','dist/openswing-local.zip'):
        prefix='kernel/' if location.endswith('local.zip') else 'openswing/openswing/'
        with ZipFile(ROOT/location) as archive:
            for name,value in current.items():assert sha(archive.read(prefix+name))==value
    shipped_sources=('docs/validation/ISAE_STATUS.md','docs/STATUS.md','docs/REQUIREMENTS.md',
        'docs/NUMERICS.md','docs/validation/isae-suite-backlog.md',
        'docs/validation/isae-suite-backlog.json',
        'docs/validation/isae-ffwt4-rank-refinement-20261106.md',
        'scripts/test-refined-rank-browser.mjs','scripts/verify-isae-rank-refinement.py',
        'tests/test_refined_rank_scaling.py','tests/test_structured_rank.py',
        'tests/fixtures/hinge-history/rank/flare20-pm2-211-mechanical.npz',
        'tests/fixtures/hinge-history/rank/flare20-pm2-211-mechanical.json')
    with ZipFile(ROOT/'dist/openswing-source.zip') as archive:
        for name in shipped_sources:assert archive.read('openswing/'+name)==(ROOT/name).read_bytes(),name
    with (ROOT/'dist/openswing-source.zip').open('rb') as stream:source_sha=stream_sha(stream)
    with (ROOT/'public/openswing-source.zip').open('rb') as stream:assert stream_sha(stream)==source_sha
    with ZipFile(ROOT/'dist/openswing-local.zip') as archive:
        with archive.open('openswing-source.zip') as stream:assert stream_sha(stream)==source_sha
    tests={}
    for name in ('rank-tests.xml','continuation-tests.xml'):
        suite=ET.parse(STUDY/name).getroot().find('testsuite')
        assert int(suite.attrib['tests'])==33
        assert all(int(suite.attrib[k])==0 for k in ('failures','errors','skipped'))
        tests[name]=33
    assessment=read(STUDY/'native/assessment.json')
    assert assessment['status']=='VERIFIED_PARTIAL_CONTINUATION' and not assessment['complete']
    assert assessment['accepted_load_steps']==2 and assessment['rejected_load_attempts']==0
    assert len(assessment['jobs'])==2
    baseline=read(ROOT/'artifacts/isae/ffwt4-pm2-mesh-20261106/level-2/job-001/request.json')
    for i,row in enumerate(assessment['jobs'],1):
        folder=STUDY/'native'/row['job'];result=read(folder/'result.json');request=read(folder/'request.json')
        assert sha((folder/'result.json').read_bytes())==row['result_sha256']
        assert read(folder/'execution.json')['exit_code']==0
        assert {k:v for k,v in request.items() if k!='continuation'}=={k:v for k,v in baseline.items() if k!='continuation'}
        assert row['nodes']==211 and row['unknowns']==2740 and row['rebuilt_residual']<=1e-12
        assert result['accepted_load_steps']==i and not result['converged'] and 'equilibrium_state' not in result
        rank=result['rank_check'];assert rank['method']=='block-triangular SVD certificate'
        assert rank['mechanical_svd']['threshold']==1e-10 and rank['mechanical_svd']['singular_ratio']>=1e-10
        assert rank['mechanical_svd']['dense_input_bytes']<=64*1024**2 and rank['rank_scaling']['iterations']<=300
    browser=read(STUDY/'browser/report.json')
    assert browser['status']=='PASS' and browser['modules']==current
    assert len(browser['jobs'])==2 and len(browser['checks'])>=29 and all(r['passed'] for r in browser['checks'])
    assert not browser['page_errors'] and not browser['external_requests']
    assert (STUDY/'browser/runner-at-execution.mjs').read_bytes()==(ROOT/'scripts/test-refined-rank-browser.mjs').read_bytes()
    receipts=read(STUDY/'terminal-receipts.json')
    for action in ('rank tests','continuation regression tests','native physical audit','app build','built browser rank and restart'):
        assert any(r['action']==action and r.get('exit_code')==0 for r in receipts),action
    evidence=[STUDY/n for n in ('study-plan.json','rank-tests.xml','continuation-tests.xml',
        'native/assessment.json','browser/report.json','terminal-receipts.json','build.log')]
    evidence += [ROOT/p for p in ('tests/test_refined_rank_scaling.py','tests/test_structured_rank.py',
        'tests/test_hinge_rank_equilibration.py','tests/test_mechanical_svd_certificate.py',
        'tests/test_steady_continuation.py','scripts/test-refined-rank-browser.mjs','scripts/verify-isae-rank-refinement.py')]
    result=dict(status='VERIFIED_BOUNDED_RANK_REFINEMENT_WITH_PARTIAL_211_NODE_CONTINUATION',
        native_tests=tests,browser_checks=len(browser['checks']),modules=current,
        unchanged_physical_functions=True,rank_threshold=1e-10,accepted_211_node_steps=2,
        full_211_node_equilibrium=False,new_native_passes=0,evidence=[pin(p) for p in evidence])
    result['shipped_sources']=list(shipped_sources)
    result['source_zip_sha256']=source_sha
    target=STUDY/'verification.json';assert not target.exists(),'Preserve prior verification.'
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('modules','evidence')}))


if __name__=='__main__':main()
