// Check the shipped kernel against the retained physical brace oracles.
import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const directory=process.argv[2]??'artifacts/isae/source-struts-20261030';
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
request=json.loads(payload);result=dispatch(request);expected=json.loads(expected_json)
assert result['converged'] and result['numerics']==request['numerics']
comparisons=[]
def check(name,a,b):
    if isinstance(b,dict):
        for key,value in b.items():check(name+'/'+key,a[key],value)
    elif isinstance(b,list):
        assert len(a)==len(b),name
        for i,(actual,ref) in enumerate(zip(a,b)):check(name+'/'+str(i),actual,ref)
    elif isinstance(b,(float,int)) and not isinstance(b,bool):
        np.testing.assert_allclose(a,b,rtol=3e-7,atol=3e-10,err_msg=name)
        comparisons.append(dict(quantity=name,absolute_error=float(abs(a-b))))
    else:assert a==b,name
def snapshot(label,a,b):
    for key in ('force','moment','applied_force','applied_moment','support_force','support_moment',
                'local_velocity','local_rates','circulation_rate','struts'):
        if key in b:check(label+'/'+key,a[key],b[key])
    for i,(node,ref) in enumerate(zip(a['nodes'],b['nodes'],strict=True)):
        for key in ('position','rotation'):check(label+f'/node{i}/'+key,node[key],ref[key])
if case_name.startswith('frequency'):
    assert result['base']['strut_mode']=='wire' and not result['base']['struts'][0]['slack']
    for row,ref in zip(result['samples'],expected['samples'],strict=True):
        assert row['omega']==ref['omega']
        a,b=row['responses'][0]['output'],ref['responses'][0]['output']
        for key in ('global','nodes'):check(str(row['omega'])+'/'+key,a[key],b[key])
        value=a['nodes'][-1]['displacement'];q=complex(value['real'][1],value['imag'][1])
        k=300 if case_name.endswith('prescribed') else 750
        assert abs(q-1/(k-3*row['omega']**2))<3e-10
elif case_name in ('time','crossing'):
    for row,ref in zip(result['snapshots'],expected['snapshots'],strict=True):
        assert row['time']==ref['time'];snapshot(str(row['time']),row,ref)
    if case_name=='crossing':
        assert not result['snapshots'][0]['struts'][0]['slack']
        assert result['snapshots'][-1]['struts'][0]['slack']
elif case_name.startswith('mode'):
    check('eigenvalues',[r['eigenvalue'] for r in result['modes']],[r['eigenvalue'] for r in expected['modes']])
    omega=np.sqrt(250 if case_name=='mode' else 100/3)
    assert abs(complex(*result['modes'][0]['eigenvalue'])-1j*omega)<3e-7
else:
    assert result['strut_mode']=='wire' and result['struts'][0]['slack']
    for key in ('nodes','struts','force_balance','moment_balance'):check(key,result[key],expected[key])
    assert abs(result['nodes'][-1]['position'][1]-2.1)<1e-9
json.dumps(dict(case=case_name,checks=comparisons))
`));
    checks.push(details);console.log(`Passed ${name}: ${details.checks.length} scalar comparisons`);
  }
  for(const [name,digest] of Object.entries(pins))if(sha(await readFile(name))!==digest)throw new Error('Input changed: '+name);
  await writeFile(`${directory}/wasm.json`,JSON.stringify({status:'PASS',checks,modules:modules.length,
    source_sha256:pins,elapsed_seconds:(performance.now()-started)/1000},null,2)+'\n');
}catch(error){
  await writeFile(`${directory}/wasm.json`,JSON.stringify({status:'FAIL',error:String(error),source_sha256:pins},null,2)+'\n');
  console.error(error);process.exitCode=1;
}
