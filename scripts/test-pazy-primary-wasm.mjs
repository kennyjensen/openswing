import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const sha=b=>createHash('sha256').update(b).digest('hex'),root=process.cwd();
try{
 const bytes=await readFile('docs/validation/pazy-primary-mapping.json'),study=JSON.parse(bytes);
 if(study.status!=='COMPARISONS_COMPLETE_NOT_PHYSICALLY_VALIDATED')throw Error('Native study incomplete');
 const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
 const py=await loadPyodide({indexURL:root+'/public/runtime'});await py.loadPackage(['numpy','scipy']);
 const put=(p,b)=>{py.FS.mkdirTree(p.slice(0,p.lastIndexOf('/')));py.FS.writeFile(p,b);},modules={},selected=[];
 for(const name of(await readdir('openswing')).filter(n=>n.endsWith('.py'))){const b=await readFile('openswing/'+name);modules[name]=sha(b);put('/home/pyodide/openswing/'+name,b);}
 for(const row of study.runs.filter(r=>r.specification.refinement===1||r.specification.refinement===4)){
  const b=await readFile(row.cache);if(sha(b)!==row.sha256)throw Error('Native cache changed');const run=JSON.parse(b);
  if(run.status!=='computed')throw Error('Native case rejected');const a=await readFile(run.matrices.path);
  if(sha(a)!==run.matrices.sha256)throw Error('Native matrix changed');put('/home/pyodide/'+run.matrices.path,a);selected.push(run);
 }
 for(const [k,v]of Object.entries({modules,expected:study.modules,selected}))py.globals.set(k+'_json',JSON.stringify(v));
 const result=JSON.parse(await py.runPythonAsync(`
import json,numpy as np
from openswing.asw import parse_asw
from openswing.linear_dynamics import make_system,linearize,eigensystem
assert json.loads(modules_json)==json.loads(expected_json)
rows=[]
for old in json.loads(selected_json):
 system,_=make_system(parse_asw(old['source']),None,panels=old['panels'],gravity=[0,0,0],structured_base=True)
 a,m=linearize(system,step=1e-6)
 saved=np.load('/home/pyodide/'+old['matrices']['path']);errors={}
 for key,actual in [('A',a),('M',m)]:
  errors[key]=float(np.max(abs(actual-saved[key])/(1+abs(saved[key]))));assert errors[key]<2e-8,(old['specification'],key,errors)
 roots,diagnostics=eigensystem(a,m,time_scale=system.W,count=16,shift=[-.1,0.],method='dense')
 roots=[r for r in roots if complex(*r['eigenvalue']).imag>1e-6]
 assert len(roots)==len(old['modes'])==8
 assert diagnostics['finite_dimension']==old['diagnostics']['finite_dimension']
 comparisons=[]
 for actual,before in zip(roots,old['modes']):
  frequency=actual['eigenvalue'][1]/(2*np.pi);difference=abs(frequency-before['frequency_Hz']);assert difference<2e-6
  q=actual['right'][:6*system.network.nn].reshape(-1,6).copy();q[:,:3]*=system.L
  expected=np.array(before['shape']['real'])+1j*np.array(before['shape']['imag'])
  score=float(abs(np.vdot(q,expected))**2/(np.vdot(q,q).real*np.vdot(expected,expected).real));assert score>1-2e-8
  assert max(actual['left_backward_error'],actual['right_backward_error'])<1e-9
  comparisons.append(dict(frequency_difference_Hz=difference,shape_assurance=score))
 assert system.base_report()['residual']<1e-8
 rows.append(dict(specification=old['specification'],matrix_errors=errors,comparisons=comparisons,finite_dimension=diagnostics['finite_dimension']))
 print('WASM',old['specification'],'PASS',flush=True)
assert len(rows)==6
json.dumps(dict(status='PASS_EXPECTED_OUTCOMES',rows=rows,full_physical_validation=False))
 `));
 Object.assign(result,{modules,native_sha256:sha(bytes),test_sha256:sha(await readFile(new URL(import.meta.url))),pyodide:py.version});
 await writeFile('docs/validation/pazy-primary-wasm.json',JSON.stringify(result,null,2)+'\n');console.log(result.status);
}catch(e){console.error(e.message,e.stack);process.exitCode=1;}
