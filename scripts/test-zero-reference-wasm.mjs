import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const sha=b=>createHash('sha256').update(b).digest('hex');
const work=process.argv[2];if(!work)throw Error('Provide the zero-reference work directory.');
const data=JSON.parse(await readFile(path.join(work,'st4-native.json'),'utf8'));
if(data.status!=='COMPARISONS_COMPUTED_NOT_PHYSICALLY_VALIDATED')throw Error('Native study incomplete');
const requests=[];
for(const [name,panels] of [['WING.asw',8],['7a_b11.asw',16],['7b_b11.asw',16]]){
 const row=data.runs.find(r=>r.specification.panels===panels&&r.paths.some(p=>p.endsWith('/'+name)));
 const bytes=await readFile(row.cache);if(sha(bytes)!==row.sha256)throw Error('Native cache changed');
 requests.push({...JSON.parse(bytes),specification:row.specification});
}
const {loadPyodide}=await import(process.cwd()+'/node_modules/pyodide/pyodide.mjs');
const py=await loadPyodide({indexURL:process.cwd()+'/public/runtime'});await py.loadPackage(['numpy','scipy']);
const put=(p,b)=>{py.FS.mkdirTree(p.slice(0,p.lastIndexOf('/')));py.FS.writeFile(p,b);};
const modules={};
for(const n of (await readdir(path.join(work,'candidate/openswing'))).filter(n=>n.endsWith('.py')).sort()){
 const b=await readFile(path.join(work,'candidate/openswing',n));modules[n]=sha(b);put('/home/pyodide/openswing/'+n,b);
}
if(JSON.stringify(modules)!==JSON.stringify(data.modules))throw Error('Mixed solver source');
for(const r of requests){const b=await readFile(r.matrices.path);if(sha(b)!==r.matrices.sha256)throw Error('Native matrix changed');put('/home/pyodide/'+r.matrices.path,b);}
py.globals.set('requests_json',JSON.stringify(requests));
const result=JSON.parse(await py.runPythonAsync(`
import json,time,numpy as np
from openswing.bridge import dispatch
rows=[]
for saved in json.loads(requests_json):
 source=saved['source'];panels=saved['specification']['panels']
 inspected=dispatch(dict(action='inspect',source=source,panels=panels));assert inspected['reference'][0][0]==0.
 try:dispatch(dict(action='solve',mode='rigid',source=source,panels=panels,condition=dict(speed=10.)))
 except ValueError as exc:
  error=str(exc);assert 'positive Reference area for coefficient normalization' in error
 else:raise AssertionError('Undefined aerodynamic normalization was accepted')
 start=time.perf_counter()
 result=dispatch(dict(action='modes',source=source,panels=panels,gravity=[0,0,0],condition=dict(speed=10.,alpha=0.,mach=0.,gravity_magnitude=0.),
                     modes=dict(vacuum=True,frame='fixed',count=12,shift=[-.1,0.],method='dense',matrices=True)))
 seconds=time.perf_counter()-start;pencil=np.load('/home/pyodide/'+saved['matrices']['path']);checks={}
 for name in ['A','M']:
  x=np.array(result['matrices'][name]);y=pencil[name];assert x.shape==y.shape
  scale=np.maximum(1.,np.max(abs(y),axis=1))[:,None];delta=float(np.max(abs(x-y)/scale));assert delta<2e-8;checks[name]=delta
 x=sorted([m for m in result['modes'] if m['eigenvalue'][1]>0],key=lambda m:m['frequency'])
 y=sorted([m for m in saved['result']['modes'] if m['eigenvalue'][1]>0],key=lambda m:m['frequency'])
 difference=max(abs(a['frequency']-b['frequency']) for a,b in zip(x,y));assert len(x)==len(y)==6 and difference<2e-6
 assert result['diagnostics']['finite_dimension']==saved['result']['diagnostics']['finite_dimension']
 assert max(max(m['left_backward_error'],m['right_backward_error']) for m in result['modes'])<1e-9
 result.pop('matrices');rows.append(dict(paths=saved['paths'],panels=panels,seconds=seconds,reference=inspected['reference'],aerodynamic_error=error,matrix_scaled_differences=checks,frequency_max_difference_Hz=difference,result=result))
 print('WASM',saved['paths'][0].split('/')[-1],panels,seconds,'PASS',flush=True)
json.dumps(dict(status='PASS_ZERO_REFERENCE_WASM_PHYSICAL_MATRICES_AND_GUARDS',rows=rows,full_physical_validation=False))
`));
Object.assign(result,{modules,script_sha256:sha(await readFile(new URL(import.meta.url))),native_report_sha256:sha(await readFile(path.join(work,'st4-native.json'))),pyodide:py.version});
await writeFile(path.join(work,'wasm.json'),JSON.stringify(result,null,2)+'\n');console.log(result.status);
