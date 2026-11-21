// Execute the packaged body-beam paths and compare their physical outputs.
import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const directory=process.argv[2]??'artifacts/isae/source-fuselage-20261030';
const pins={},sha=data=>createHash('sha256').update(data).digest('hex');
const load=async name=>{const data=await readFile(name);pins[name]=sha(data);return data;};
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
  const detail=JSON.parse(await py.runPythonAsync(`
import json,numpy as np
from openswing.bridge import dispatch
request=json.loads(payload);expected=json.loads(expected_json);result=dispatch(request)
assert result['converged'] and result['numerics']==request['numerics']
errors=[]
def check(a,b):
    if isinstance(b,dict):
        for key,value in b.items():check(a[key],value)
    elif isinstance(b,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):check(x,y)
    elif isinstance(b,(int,float)) and not isinstance(b,bool):
        np.testing.assert_allclose(a,b,rtol=3e-7,atol=3e-10)
        errors.append(float(abs(a-b)))
    else:assert a==b
if case_name.startswith('frequency'):
    for row,ref in zip(result['samples'],expected['samples'],strict=True):
        assert row['omega']==ref['omega']
        a,b=row['responses'][0]['output'],ref['responses'][0]['output']
        for key in ('global','nodes'):check(a[key],b[key])
        v=a['nodes'][-1]['displacement'];k=100 if case_name.endswith('prescribed') else 250
        assert abs(complex(v['real'][0],v['imag'][0])-1/(k-3*row['omega']**2))<3e-10
elif case_name.startswith('mode'):
    check([r['eigenvalue'] for r in result['modes']],[r['eigenvalue'] for r in expected['modes']])
    omega=np.sqrt(250/3 if case_name=='mode' else 100/3)
    assert abs(complex(*result['modes'][0]['eigenvalue'])-1j*omega)<3e-7
elif case_name=='time':
    for row,ref in zip(result['snapshots'],expected['snapshots'],strict=True):
        assert row['time']==ref['time']
        for key in ('force','moment','applied_force','applied_moment','support_force','support_moment','local_velocity','local_rates'):
            if key in ref:check(row[key],ref[key])
        for node,old in zip(row['nodes'],ref['nodes'],strict=True):
            for key in ('position','rotation'):check(node[key],old[key])
        t=max(0.,row['time']-.01)
        assert abs(row['nodes'][-1]['position'][0]-2-(1-np.cos(np.sqrt(250/3)*t))/250)<3e-6
else:
    for key in ('nodes','force_balance','moment_balance','force','moment','support_force','support_moment'):
        if key in expected:check(result[key],expected[key])
    if case_name=='static':assert abs(result['nodes'][-1]['position'][0]-2.1)<1e-9
    else:
        v=17*np.array([np.cos(np.deg2rad(11)),0,np.sin(np.deg2rad(11))])
        np.testing.assert_allclose(result['moment'],[0,1.225*np.pi*.2**2*2*v[0]*v[2],0],atol=2e-9)
json.dumps(dict(case=case_name,comparisons=len(errors),max_absolute_error=max(errors,default=0.)))
`));
  checks.push(detail);console.log(JSON.stringify(detail));
}
await writeFile(`${directory}/wasm.json`,JSON.stringify({status:'PASS',modules:modules.length,checks,pins},null,2)+'\n');
