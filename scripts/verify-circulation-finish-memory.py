"""Verify retained runtime, numerical, package and unchanged-progress evidence."""
import hashlib,json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

R=Path(__file__).resolve().parents[1];S=R/'artifacts/isae/circulation-finish-memory-20261107'
def read(p):return json.loads(Path(p).read_text())
def digest(b):return hashlib.sha256(b).hexdigest()
def pin(p):
    p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=digest(b))
summary=read(S/'summary-verified.json');assert summary['goal_status']=='active'
assert summary['native_passes_added']==0 and summary['native_fraction']=='200/8000'
assert summary['mesh_passed']==0 and summary['mesh_required']==7
assert summary['load_component_passed']==11 and summary['load_component_required']==18
assert summary['numerical_relative_gate']==.001
tests=0
for name in ['finish-load-tests.xml','residual-block-tests.xml']:
    for suite in ET.parse(S/name).getroot().iter('testsuite'):
        assert int(suite.get('errors'))==int(suite.get('failures'))==int(suite.get('skipped'))==0
        tests+=int(suite.get('tests'))
assert tests==50
modules={p.name:digest(p.read_bytes()) for p in (R/'openswing').glob('*.py')};assert len(modules)==140
manifest=read(R/'.reference/solver-snapshots/circulation-finish-memory-20261107/manifest.json')
for item in manifest['files']:
    p=Path(item['archived']);assert digest(p.read_bytes())==item['original']['sha256']==modules[p.name]
wasm=read(S/'wasm-finish.json');browser=read(S/'browser/report.json')
assert wasm['status']==browser['status']=='PASS' and len(wasm['cases'])==7
assert wasm['modules']==browser['modules']==modules
assert len(browser['checks'])==19 and all(c['passed'] for c in browser['checks'])
assert not browser['page_errors'] and not browser['external_requests']
for job in browser['jobs']:assert job['residual']<=1e-12 and job['normalized_state_difference']<=2e-8
audit=read(S/'nodes-419/assessment.json');cold=read(S/'cold-summary.json')
assert audit['complete'] and audit['final_load_fraction']==1 and audit['rejected_load_attempts']==0
assert audit['accepted_load_steps']==audit['successful_processes']==len(audit['jobs'])==19
for row in audit['jobs']:
    folder=S/'nodes-419'/row['job'];receipt=read(folder/'execution.json')
    assert receipt['exit_code']==0 and receipt['memory_bytes']==536870912 and receipt['blas_threads']==1
    assert digest((folder/'result.json').read_bytes())==row['result_sha256']
    assert row['rebuilt_residual']<=1e-12
for row in cold['jobs'][:15]:assert row['previous_kernel_coordinates_identical'] and row['previous_kernel_load_identical']
failed=R/'artifacts/isae/source-tree-production-20261107/nodes-419/job-016'
assert read(failed/'execution.json')['exit_code']==1 and 'MemoryError' in read(failed/'failure.json')['error']
coarse=read(S/'coarse-recheck.json')
assert coarse['physical_functions_unchanged'] and coarse['maximum_scaled_output_difference']==0
assert coarse['compared_numeric_values']==45775 and coarse['rebuilt_residual']<=1e-12
for folder in ['public/kernel','dist/kernel']:
    for name,sha in modules.items():assert digest((R/folder/name).read_bytes())==sha
for location in ['public/openswing-source.zip','dist/openswing-source.zip','dist/openswing-local.zip']:
    prefix='kernel/' if location.endswith('local.zip') else 'openswing/openswing/'
    with ZipFile(R/location) as archive:
        for name,sha in modules.items():assert digest(archive.read(prefix+name))==sha
        if not location.endswith('local.zip'):
            for name in ['docs/validation/ISAE_STATUS.md','docs/NUMERICS.md','docs/validation/isae-circulation-finish-memory-20261107.md']:
                assert archive.read('openswing/'+name)==(R/name).read_bytes(),(location,name)
history=read(R/'docs/validation/isae-progress/history.json')
assert len(history['events'])==5
for item in read(S/'run-receipts.json'):assert item['actual_terminal_exit_code']==0
result=dict(status='VERIFIED_MEMORY_FIX_WITH_UNCHANGED_PHYSICAL_GATES',python_checks=tests,
    wasm_checks=7,browser_checks=19,kernel_modules=len(modules),cold_steps=19,
    old_states_identical=15,mesh_passed=0,mesh_required=7,sided_load_passed=11,sided_load_required=18,
    native_passes_added=0,progress_observations=5,goal_status='active',
    evidence=[pin(p) for p in [Path(__file__),S/'summary-verified.json',S/'run-receipts.json',
        S/'wasm-finish.json',S/'browser/report.json',S/'coarse-recheck.json',
        S/'comparison-211-419.json',S/'nodal-fields-211-419.json',S/'load-fields-211-419.json',
        S/'nodes-419/assessment.json',S/'refinement-419.png',R/'docs/validation/ISAE_STATUS.md',
        R/'docs/validation/isae-circulation-finish-memory-20261107.md']])
with (S/'verification.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in result.items() if k!='evidence'}))
