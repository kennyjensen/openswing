// Execute powered source dynamics using the exact shipped offline WASM kernel.
import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const directory=process.argv[2]??'artifacts/isae/source-airflow-engines-20261030';
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
  for(const name of JSON.parse(await load(`${directory}/runtime-cases.json`))){
    py.globals.set('payload',(await load(`${directory}/${name}-request.json`)).toString());
    py.globals.set('expected_json',(await load(`${directory}/${name}-native.json`)).toString());
    py.globals.set('case_name',name);
    const details=JSON.parse(await py.runPythonAsync(`
import json, numpy as np
from openswing.bridge import dispatch
result=dispatch(json.loads(payload));expected=json.loads(expected_json)
assert result['converged'] and result['structural_operator']=='drela-moving-airflow-v1'
comparisons=[]
def check(name,actual,reference):
    a,b=np.asarray(actual),np.asarray(reference)
    np.testing.assert_allclose(a,b,rtol=3e-7,atol=3e-10,err_msg=name)
    comparisons.append(dict(quantity=name,components=a.size,maximum_absolute_error=float(np.max(abs(a-b),initial=0))))
if case_name.startswith('frequency'):
    assert not result['vacuum'] and len(result['base']['engines'])==1
    for row,ref in zip(result['samples'],expected['samples'],strict=True):
        assert row['omega']==ref['omega']
        a,b=row['responses'][0]['output'],ref['responses'][0]['output']
        for key in ('CL','CD','Cm','force','moment'):
            for part in ('real','imag'):check(f"{row['omega']} {key} {part}",a['global'][key][part],b['global'][key][part])
        for i,(node,other) in enumerate(zip(a['nodes'],b['nodes'],strict=True)):
            for key in ('displacement','velocity'):
                for part in ('real','imag'):check(f"{row['omega']} node {i} {key} {part}",node[key][part],other[key][part])
        if case_name!='frequency-propeller':
            q=a['nodes'][-1]['displacement'];q=complex(q['real'][1],q['imag'][1])
            k=100 if case_name.endswith('prescribed') else 250
            assert abs(q-1/(k-3*row['omega']**2))<3e-10
elif case_name=='time':
    for row,ref in zip(result['snapshots'],expected['snapshots'],strict=True):
        assert row['time']==ref['time']
        for key in ('force','moment','local_velocity','local_rates','circulation_rate'):
            check(f"{row['time']} {key}",row[key],ref[key])
        for key in ('position','axes','force','moment','axial_velocity'):
            check(f"{row['time']} engine {key}",row['engines'][0][key],ref['engines'][0][key])
else:
    check('mode eigenvalues',[r['eigenvalue'] for r in result['modes']],[r['eigenvalue'] for r in expected['modes']])
    assert abs(complex(*result['modes'][0]['eigenvalue'])-1j*np.sqrt(250/3))<3e-7
json.dumps(dict(case=case_name,checks=comparisons))
`));
    checks.push(details);console.log(`Passed ${name}: ${details.checks.length} comparisons`);
  }
  for(const [name,digest] of Object.entries(pins))if(sha(await readFile(name))!==digest)throw new Error('Input changed: '+name);
  await writeFile(`${directory}/wasm.json`,JSON.stringify({status:'PASS',checks,modules:modules.length,
    source_sha256:pins,elapsed_seconds:(performance.now()-started)/1000},null,2)+'\n');
}catch(error){
  await writeFile(`${directory}/wasm.json`,JSON.stringify({status:'FAIL',error:String(error),source_sha256:pins},null,2)+'\n');
  console.error(error);process.exitCode=1;
}
