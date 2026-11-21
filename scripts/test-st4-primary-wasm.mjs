import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const sha=b=>createHash('sha256').update(b).digest('hex');
const work=process.argv[2];if(!work)throw Error('Provide the primary ST4 work directory.');
const selections=[['unloaded',null,'lower',8],['7d',48,'upper',16],['7c',48,'lower',16]],requests=[],modules={};
for(const name of(await readdir('openswing')).filter(n=>n.endsWith('.py')).sort())modules[name]=sha(await readFile('openswing/'+name));
for(const [variant,position,endpoint,panels] of selections){
 const bytes=await readFile(path.join(work,`primary-native-${endpoint}.json`)),report=JSON.parse(bytes);
 if(JSON.stringify(report.modules)!==JSON.stringify(modules))throw Error('Mixed solver sources');
 const entry=report.runs.find(r=>r.specification.variant===variant&&r.specification.position_in===position&&r.specification.panels===panels);
 if(!entry)throw Error('Requested native calculation has not finished');
 const cache=await readFile(entry.cache);if(sha(cache)!==entry.sha256)throw Error('Native cache changed');
 const saved=JSON.parse(cache);if(saved.status!=='computed')throw Error('Native calculation rejected');
 requests.push({...saved,specification:entry.specification,cache_path:entry.cache,cache_sha256:entry.sha256});
}
const inputs={modules,requests,full_physical_validation:false};
await writeFile(path.join(work,'primary-runtime-inputs.json'),JSON.stringify(inputs,null,2)+'\n');
const {loadPyodide}=await import(process.cwd()+'/node_modules/pyodide/pyodide.mjs');
const py=await loadPyodide({indexURL:process.cwd()+'/public/runtime'});await py.loadPackage(['numpy','scipy']);
const put=(p,b)=>{py.FS.mkdirTree(p.slice(0,p.lastIndexOf('/')));py.FS.writeFile(p,b);};
for(const name of Object.keys(modules))put('/home/pyodide/openswing/'+name,await readFile('openswing/'+name));
for(const r of requests){const b=await readFile(r.matrices.path);if(sha(b)!==r.matrices.sha256)throw Error('Native matrices changed');put('/home/pyodide/'+r.matrices.path,b);}
py.globals.set('requests_json',JSON.stringify(requests));
const result=JSON.parse(await py.runPythonAsync(`
import json,time,numpy as np
from openswing.bridge import dispatch
rows=[]
for saved in json.loads(requests_json):
 spec=saved['specification'];g=saved['parameters']['gravity']
 start=time.perf_counter()
 result=dispatch(dict(action='modes',source=saved['source'],panels=spec['panels'],gravity=[0,0,g],condition=dict(speed=0.),
                     modes=dict(vacuum=True,frame='fixed',count=12,shift=[-.1,0.],method='dense',matrices=True)))
 seconds=time.perf_counter()-start;pencil=np.load('/home/pyodide/'+saved['matrices']['path']);checks={}
 for name in ['A','M']:
  x=np.array(result['matrices'][name]);y=pencil[name];assert x.shape==y.shape
  scale=np.maximum(1.,np.max(abs(y),axis=1))[:,None];delta=float(np.max(abs(x-y)/scale));assert delta<2e-8;checks[name]=delta
 x=sorted([m for m in result['modes'] if m['eigenvalue'][1]>0],key=lambda m:m['frequency'])
 y=sorted([m for m in saved['result']['modes'] if m['eigenvalue'][1]>0],key=lambda m:m['frequency'])
 assert len(x)==len(y)==6
 difference=max(abs(a['frequency']-b['frequency']) for a,b in zip(x,y));assert difference<2e-6
 assert result['vacuum'] and result['converged']
 np.testing.assert_allclose(result['base']['gravity_body'],[0,0,g],atol=1e-14,rtol=0)
 assert result['diagnostics']['finite_dimension']==saved['result']['diagnostics']['finite_dimension']
 assert max(max(m['left_backward_error'],m['right_backward_error']) for m in result['modes'])<1e-9
 result.pop('matrices');rows.append(dict(specification=spec,seconds=seconds,matrix_scaled_differences=checks,
     frequency_max_difference_Hz=difference,cache_sha256=saved['cache_sha256'],result=result))
 print('WASM',spec,seconds,'PASS',flush=True)
json.dumps(dict(status='PASS_PRIMARY_ST4_WASM_PHYSICAL_MATRICES',rows=rows,full_physical_validation=False))
`));
Object.assign(result,{modules,script_sha256:sha(await readFile(new URL(import.meta.url))),runtime_inputs_sha256:sha(await readFile(path.join(work,'primary-runtime-inputs.json'))),pyodide:py.version});
await writeFile(path.join(work,'primary-wasm.json'),JSON.stringify(result,null,2)+'\n');console.log(result.status);
