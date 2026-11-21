import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const directory='artifacts/isae/source-body-still-air-20261031',pins={};
const load=async name=>{const b=await readFile(name);pins[name]=createHash('sha256').update(b).digest('hex');return b;};
const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
py.FS.mkdirTree('/home/pyodide/openswing');
const modules=JSON.parse(await load('dist/kernel/manifest.json'));
for(const name of modules){const b=await load('dist/kernel/'+name);if(!b.equals(await readFile('openswing/'+name)))throw new Error('Stale module '+name);py.FS.writeFile('/home/pyodide/openswing/'+name,b);}
const references=JSON.parse(await load(`${directory}/references.json`)),checks=[];
for(const name of JSON.parse(await load(`${directory}/runtime-cases.json`))){
  py.globals.set('request_json',(await load(`${directory}/${name}-request.json`)).toString());
  py.globals.set('expected_json',(await load(`${directory}/${name}-native.json`)).toString());
  py.globals.set('ref_json',JSON.stringify(references[name]));py.globals.set('case_name',name);
  const row=JSON.parse(await py.runPythonAsync(`
import json,numpy as np
from openswing.bridge import dispatch
request=json.loads(request_json);expected=json.loads(expected_json);ref=json.loads(ref_json)
result=dispatch(request);assert result['converged'];errors=[]
def check(a,b):
    if isinstance(b,dict):
        for k,v in b.items():check(a[k],v)
    elif isinstance(b,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):check(x,y)
    elif isinstance(b,(int,float)) and not isinstance(b,bool):
        np.testing.assert_allclose(a,b,rtol=4e-7,atol=3e-10);errors.append(float(abs(a-b)))
    else:assert a==b
check(result['base']['fluid'],expected['base']['fluid'])
assert result['base']['equilibrium_state']['identity']['quiescent_body_added_mass_factor']==ref['factor']
if case_name.startswith('mode'):
    check([m['eigenvalue'] for m in result['modes']],[m['eigenvalue'] for m in expected['modes']])
    np.testing.assert_allclose(complex(*result['modes'][0]['eigenvalue']),1j*ref['omega'],rtol=2e-7,atol=2e-8)
else:
    for row,old in zip(result['samples'],expected['samples'],strict=True):
        assert row['omega']==old['omega']
        a,b=row['responses'][0]['output'],old['responses'][0]['output']
        for key in ('nodes','global'):check(a[key],b[key])
        s=.3+1j*row['omega'];target=.001*s/(s*s+ref['omega_squared'])
        d=a['nodes'][-1]['displacement'];np.testing.assert_allclose(complex(d['real'][2],d['imag'][2]),target,rtol=4e-7,atol=3e-10)
json.dumps(dict(case=case_name,comparisons=len(errors),max_absolute_error=max(errors,default=0.)))
`));checks.push(row);console.log(JSON.stringify(row));
}
await writeFile(`${directory}/wasm.json`,JSON.stringify({status:'PASS',modules:modules.length,checks,pins},null,2)+'\n');
