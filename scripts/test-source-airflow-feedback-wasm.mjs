// Compare native and WASM feedback using exactly the modules shipped by Vite.
import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const directory=process.argv[2]??'artifacts/isae/source-airflow-feedback-20261031';
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
    checks.push(JSON.parse(await py.runPythonAsync(`
import json, numpy as np
from openswing.bridge import dispatch
request=json.loads(payload);result=dispatch(request);expected=json.loads(expected_json)
assert result['converged'] and result['structural_operator']=='drela-moving-airflow-v1'
assert result['controller']['definition']==expected['controller']['definition']==request[request['action']]['controller']
comparisons=[]
def compare(label,a,b):
    if isinstance(b,dict):
        assert set(a)==set(b),label
        for k in b:compare(label+'.'+k,a[k],b[k])
    elif isinstance(b,list) and b and isinstance(b[0],dict):
        assert len(a)==len(b),label
        for i,(x,y) in enumerate(zip(a,b,strict=True)):compare(label+str(i),x,y)
    elif isinstance(b,(list,int,float)) and not isinstance(b,bool):
        x,y=np.asarray(a),np.asarray(b)
        if x.dtype.kind in 'fiu' and y.dtype.kind in 'fiu':
            np.testing.assert_allclose(x,y,rtol=3e-7,atol=3e-9,err_msg=label)
            comparisons.append(dict(quantity=label,components=x.size,maximum_absolute_error=float(np.max(abs(x-y),initial=0))))
        else:assert a==b,label
    else:assert a==b,label
if request['action']=='frequency':
    assert len(result['samples'])==len(expected['samples'])
    for row,ref in zip(result['samples'],expected['samples'],strict=True):
        assert row['omega']==ref['omega']
        for a,b in zip(row['responses'],ref['responses'],strict=True):
            for key in ('global','nodes','sensors','feedback','frame'):
                compare(str(row['omega'])+' '+key,a['output'][key],b['output'][key])
elif request['action']=='modes':
    compare('poles',[m['eigenvalue'] for m in result['modes']],[m['eigenvalue'] for m in expected['modes']])
else:
    assert result['restart_context']['setup']['controller']==request['time']['controller']
    for row,ref in zip(result['snapshots'],expected['snapshots'],strict=True):
        assert row['time']==ref['time']
        for key in ('CL','force','moment','local_velocity','circulation_rate','feedback'):
            compare(str(row['time'])+' '+key,row[key],ref[key])
json.dumps(dict(case=case_name,checks=comparisons))
`)));
    console.log(`Passed ${name}: ${checks.at(-1).checks.length} comparisons`);
  }
  for(const [name,digest] of Object.entries(pins))if(sha(await readFile(name))!==digest)throw new Error('Input changed: '+name);
  await writeFile(`${directory}/wasm.json`,JSON.stringify({status:'PASS',checks,modules:modules.length,
    source_sha256:pins,elapsed_seconds:(performance.now()-started)/1000},null,2)+'\n');
}catch(error){
  await writeFile(`${directory}/wasm.json`,JSON.stringify({status:'FAIL',error:String(error),source_sha256:pins},null,2)+'\n');
  console.error(error);process.exitCode=1;
}
