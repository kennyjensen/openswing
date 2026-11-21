// Verify the same dynamic requests in the shipped, offline Python/WASM kernel.
import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const directory=process.argv[2]??'artifacts/isae/source-airflow-20261030';
const pins={},sha=data=>createHash('sha256').update(data).digest('hex');
const load=async name=>{const data=await readFile(name);pins[name]=sha(data);return data;};
const started=performance.now();
try{
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});
  await py.loadPackage(['numpy','scipy']);py.FS.mkdirTree('/home/pyodide/openswing');
  const modules=JSON.parse(await load('dist/kernel/manifest.json'));
  for(const name of modules){
    const data=await load('dist/kernel/'+name);
    if(!data.equals(await readFile('openswing/'+name)))throw new Error('Stale packaged module: '+name);
    py.FS.writeFile('/home/pyodide/openswing/'+name,data);
  }
  const checks=[];
  for(const [kind,baseline] of [['frequency','frequency-native'],['time','step-0.002'],['mode','mode-result']]){
    py.globals.set('payload',(await load(`${directory}/${kind}-request.json`)).toString());
    py.globals.set('expected_json',(await load(`${directory}/${baseline}.json`)).toString());
    py.globals.set('kind',kind);
    const details=JSON.parse(await py.runPythonAsync(`
import json, numpy as np
from openswing.bridge import dispatch
result=dispatch(json.loads(payload)); expected=json.loads(expected_json)
assert result['converged'] and result['structural_operator']=='drela-moving-airflow-v1'
comparisons=[]
def check(name,actual,reference):
    a,b=np.asarray(actual),np.asarray(reference)
    np.testing.assert_allclose(a,b,rtol=2e-7,atol=2e-10,err_msg=name)
    comparisons.append(dict(quantity=name,components=a.size,maximum_absolute_error=float(np.max(abs(a-b),initial=0))))
if kind=='frequency':
    assert result['vacuum'] is False
    for row,ref in zip(result['samples'],expected['samples'],strict=True):
        assert row['omega']==ref['omega']
        for key in ('CL','Cm'):
            for part in ('real','imag'):
                check(f"{row['omega']} {key} {part}",row['responses'][0]['output']['global'][key][part],ref['responses'][0]['output']['global'][key][part])
elif kind=='time':
    assert result['temporal_policy']=='drela-euler-bdf-v1'
    for row,ref in zip(result['snapshots'],expected['snapshots'],strict=True):
        assert row['time']==ref['time']
        for key in ('CL','Cm','force','moment','circulation_rate'):
            check(f"{row['time']} {key}",row[key],ref[key])
else:
    check('mode eigenvalues',[r['eigenvalue'] for r in result['modes']],[r['eigenvalue'] for r in expected['modes']])
json.dumps(dict(kind=kind,checks=comparisons))
`));
    checks.push(details);console.log(`Passed ${kind}: ${details.checks.length} comparisons`);
  }
  for(const [file,digest] of Object.entries(pins))if(sha(await readFile(file))!==digest)throw new Error('Input changed during execution: '+file);
  await writeFile(`${directory}/wasm.json`,JSON.stringify({status:'PASS',checks,modules:modules.length,
    source_sha256:pins,elapsed_seconds:(performance.now()-started)/1000},null,2)+'\n');
}catch(error){
  await writeFile(`${directory}/wasm.json`,JSON.stringify({status:'FAIL',error:String(error),source_sha256:pins},null,2)+'\n');
  console.error(error);process.exitCode=1;
}
