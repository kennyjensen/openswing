import {loadPyodide} from 'pyodide';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
try {
const study=JSON.parse(await readFile('docs/validation/integrators.json','utf8'));
for(const [file,hash] of Object.entries(study.source_sha256))if(createHash('sha256').update(await readFile(file)).digest('hex')!==hash)throw new Error('Study source changed: '+file);
const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);py.FS.mkdirTree('/home/pyodide/openswing');
for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8'))){const data=await readFile(`dist/kernel/${name}`);if(!data.equals(await readFile(`openswing/${name}`)))throw new Error('Stale packaged module: '+name);py.FS.writeFile(`/home/pyodide/openswing/${name}`,data);}
for(const [name,c] of Object.entries(study.cases)){
 py.globals.set('case_json',JSON.stringify(c));
 await py.runPythonAsync(`
import json,numpy as np
from scipy.optimize import linear_sum_assignment
from openswing.bridge import run_json
from openswing.linear_dynamics import eigensystem,complex_data
from openswing.reduced_model import real_projection
c=json.loads(case_json);request=c['request'];expected=c['result']
def z(v):return np.asarray(v['real'])+1j*np.asarray(v['imag'])
if c['kind']=='model':actual=json.loads(run_json(json.dumps(request)))
else:
    a,m=np.array(request['A']),np.array(request['M'])
    modes,meta=eigensystem(a,m,time_scale=request['time_scale'],count=20)
    if c['comparison']['exact_zero_count']==len(modes):
        ar,lift,dual,_=real_projection(a,m,modes)
        np.testing.assert_allclose(ar,0,atol=0)
        np.testing.assert_allclose(dual@m@lift,np.eye(len(modes)),atol=1e-12)
    for mode in modes:
        for key in ['right','left']:mode[key]=complex_data(mode[key])
    actual=dict(modes=modes,diagnostics=meta,matrices=dict(A=a.tolist(),M=m.tolist()))
values=np.array([complex(*mode['eigenvalue']) for mode in actual['modes']])
wanted=np.array([complex(*v) for v in c['comparison']['expected_roots']])
assert len(values)==actual['diagnostics']['finite_dimension']==len(wanted)
zeros=c['comparison']['exact_zero_count']
assert actual['diagnostics']['integrator_deflation']['count']==zeros
assert sum(mode['exact_integrator'] for mode in actual['modes'])==zeros
assert sum(values==0)==zeros
for mode in actual['modes']:
    if mode['exact_integrator']:assert mode['eigenvalue']==[0.,0.]
rows,columns=linear_sum_assignment(abs(values[:,None]-wanted[None,:]))
assert max(abs(values[rows]-wanted[columns]))<3e-7
for value in wanted:
    if 0<abs(value)<1e-6:assert min(abs(values-value))<1e-10*abs(value)
for key in ['A','M']:np.testing.assert_allclose(actual['matrices'][key],expected['matrices'][key],atol=3e-9,rtol=3e-8)
a,m=(np.array(actual['matrices'][key]) for key in ['A','M'])
maximum=0.
for mode in actual['modes']:
    value=complex(*mode['eigenvalue']);v,w=z(mode['right']),z(mode['left'])
    scale=np.linalg.norm(a)+abs(value)*np.linalg.norm(m)
    right=np.linalg.norm(a@v-value*m@v)/max(scale*np.linalg.norm(v),np.finfo(float).tiny)
    left=np.linalg.norm(w.conj()@a-value*w.conj()@m)/max(scale*np.linalg.norm(w),np.finfo(float).tiny)
    maximum=max(maximum,right,left)
    assert max(mode['right_backward_error'],mode['left_backward_error'],right,left)<1e-9
print('exact zeros =',zeros,'; maximum original-pencil backward error =',maximum)
`);
 console.log('Packaged WASM integrator check passed: '+name);
}
await new Promise(resolve=>process.stdout.write('All nine WASM integrator cases passed.\n',resolve));process.exit(0);
} catch(error) {await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
