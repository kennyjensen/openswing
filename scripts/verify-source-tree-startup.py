"""Verify source-tree startup, retained physical states and shipped browser kernel."""
import ast
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/'artifacts/isae/source-tree-production-20261107'


def read(p):return json.loads(Path(p).read_text())
def sha(data):return hashlib.sha256(data).hexdigest()
def pin(p):
    p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=sha(b))
def check(p):assert pin(p['path'])==p,p['path']


def main():
    plan=read(STUDY/'study-plan.json')
    for name in ('kernel_manifest','previous_kernel_manifest','helper','runner','mesh_211','mesh_419','source_tree_module'):check(plan[name])
    for p in plan['previous_211_jobs']:check(p)
    current={p.name:sha(p.read_bytes()) for p in (ROOT/'openswing').glob('*.py')}
    manifest=read(plan['kernel_manifest']['path'])
    assert len(current)==len(manifest['files'])==140
    for r in manifest['files']:
        assert current[Path(r['archived']).name]==r['original']['sha256']==sha(Path(r['archived']).read_bytes())
    previous=read(plan['previous_kernel_manifest']['path'])
    assert set(current)-{Path(r['archived']).name for r in previous['files']}=={'source_initial_rank.py'}
    changed=[]
    for r in previous['files']:
        p=Path(r['archived']);assert sha(p.read_bytes())==r['original']['sha256']
        if current[p.name]!=r['original']['sha256']:changed.append(p.name)
    assert changed==['structured_static.py']
    def physical(p):
        tree=ast.parse(Path(p).read_text());tree.body=[n for n in tree.body if not
            (isinstance(n,ast.FunctionDef) and n.name=='check_initial_rank')]
        return ast.dump(tree)
    old=Path(plan['previous_kernel_manifest']['path']).parent/'openswing/structured_static.py'
    assert physical(ROOT/'openswing/structured_static.py')==physical(old)
    tests={}
    for name,minimum in [('scope-tests-v2',44),('oracle-rigid-regression',83),
                         ('javascript-roundtrip',2),('continuation-controls-v2',30),
                         ('continuation-state-parity',3),('rank-regression',19)]:
        suite=ET.parse(STUDY/(name+'.xml')).getroot().find('testsuite')
        assert int(suite.attrib['tests'])>=minimum
        assert all(int(suite.attrib[k])==0 for k in ('errors','failures','skipped'))
        assert read(STUDY/(name+'-execution.json'))['exit_code']==0
        tests[name]=int(suite.attrib['tests'])
    # Preserve the rejected first test invocation and its actual exit status.
    assert read(STUDY/'scope-tests-execution.json')['exit_code']==1
    assert read(STUDY/'continuation-rank-regression-execution.json')['exit_code']==124
    assert read(STUDY/'continuation-controls-execution.json')['exit_code']==1
    node=read(STUDY/'node-address-cap-diagnostic.json')
    assert node['exit_code']==-5 and 'subspace allocation' in node['stderr']
    comparison=read(STUDY/'native-comparison.json')
    assert len(comparison['jobs'])==2
    assert all(r['normalized_state_difference']<=plan['native_state_comparison_limit'] for r in comparison['jobs'])
    audits={}
    for name,count,nodes in [('native',2,211),('nodes-419',1,419)]:
        audit=read(STUDY/name/'assessment.json');audits[name]=audit
        assert audit['status']=='VERIFIED_PARTIAL_CONTINUATION' and not audit['complete']
        assert audit['accepted_load_steps']==count and len(audit['jobs'])==count
        assert audit['rejected_load_attempts']==audit['process_timeouts']==0
        assert read(STUDY/name/'assessment-execution.json')['exit_code']==0
        for j in audit['jobs']:
            folder=STUDY/name/j['job'];result=read(folder/'result.json');receipt=read(folder/'execution.json')
            assert receipt['exit_code']==0 and receipt['memory_bytes']==536870912 and receipt['blas_threads']==1
            assert sha((folder/'result.json').read_bytes())==j['result_sha256']
            assert j['nodes']==nodes and j['rebuilt_residual']<=1e-12
            assert result['continuation_status']=='pending' and not result['converged'] and 'equilibrium_state' not in result
            rank=result['rank_check'];assert rank['method']=='source flexible-tree rank certificate'
            assert rank['physical_certificate']['certified'] and not rank['physical_certificate']['numerical_condition_bound']
            assert rank['circulation_rank']['threshold']==1e-10 and rank['circulation_rank']['singular_ratio']>=1e-10
            assert 'mechanical_svd' not in rank
    browser=read(STUDY/'browser/report.json')
    assert browser['status']=='PASS' and browser['modules']==current
    assert len(browser['jobs'])==2 and len(browser['checks'])>=29 and all(c['passed'] for c in browser['checks'])
    assert not browser['page_errors'] and not browser['external_requests']
    assert (STUDY/'browser/runner-at-execution.mjs').read_bytes()==(ROOT/'scripts/test-source-tree-browser.mjs').read_bytes()
    assert read(STUDY/'browser-execution.json')['exit_code']==0
    for location in ('public/kernel','dist/kernel'):
        assert {p.name:sha(p.read_bytes()) for p in (ROOT/location).glob('*.py')}==current
    for location in ('public/openswing-source.zip','dist/openswing-source.zip','dist/openswing-local.zip'):
        prefix='kernel/' if location.endswith('local.zip') else 'openswing/openswing/'
        with ZipFile(ROOT/location) as z:
            for name,value in current.items():assert sha(z.read(prefix+name))==value
    shipped=['docs/validation/ISAE_STATUS.md','docs/STATUS.md','docs/REQUIREMENTS.md','docs/NUMERICS.md',
        'docs/validation/isae-suite-backlog.md','docs/validation/isae-suite-backlog.json',
        'docs/validation/isae-source-tree-production-20261107.md',
        'scripts/test-source-tree-browser.mjs','scripts/verify-source-tree-startup.py',
        'tests/test_source_flexible_tree_rank.py','tests/test_source_flexible_zero_load_oracle.py']
    with ZipFile(ROOT/'dist/openswing-source.zip') as z:
        for name in shipped:assert z.read('openswing/'+name)==(ROOT/name).read_bytes(),name
    report=dict(status='VERIFIED_SOURCE_TREE_STARTUP_WITH_UNCHANGED_PHYSICAL_STATES',
        modules=current,tests=tests,browser_checks=len(browser['checks']),
        unchanged_physical_functions=True,certificate_kind='algebraic full rank; no numerical condition bound',
        circulation_rank_threshold=1e-10,physical_residual_limit=1e-12,
        accepted_211_node_steps=2,accepted_419_node_steps=1,
        full_419_node_equilibrium=False,new_native_passes=0,
        native_comparison=comparison,browser_jobs=browser['jobs'],shipped_sources=shipped,
        evidence=[pin(STUDY/n) for n in ('study-plan.json','native-comparison.json','native/assessment.json',
            'nodes-419/assessment.json','browser/report.json','scope-tests-v2.xml',
            'oracle-rigid-regression.xml','javascript-roundtrip.xml','continuation-controls-v2.xml',
            'continuation-state-parity.xml','rank-regression.xml')])
    with (STUDY/'verification.json').open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('modules','evidence','native_comparison')}))


if __name__=='__main__':main()
