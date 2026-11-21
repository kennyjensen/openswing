import {readFile,readdir,writeFile} from 'node:fs/promises';
import {cases,sha} from './pazy-loaded-runtime-cases.mjs';
try{
 const selected=await cases(),root=process.cwd(),{loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
 const py=await loadPyodide({indexURL:root+'/public/runtime'});await py.loadPackage(['numpy','scipy']);
 const put=(p,b)=>{py.FS.mkdirTree(p.slice(0,p.lastIndexOf('/')));py.FS.writeFile(p,b);},modules={};
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py'))){const bytes=await readFile('openswing/'+n);modules[n]=sha(bytes);put('/home/pyodide/openswing/'+n,bytes);}
 for(const run of selected.runs)if(run.matrices){const bytes=await readFile(run.matrices.path);if(sha(bytes)!==run.matrices.sha256)throw Error('Native pencil changed');put('/home/pyodide/'+run.matrices.path,bytes);}
 py.globals.set('selected_json',JSON.stringify(selected));py.globals.set('modules_json',JSON.stringify(modules));
 const result=JSON.parse(await py.runPythonAsync(`
import json,time,numpy as np
from openswing.asw import parse_asw
from openswing.network import StaticNetwork,network_result
from openswing.structured_static import equilibrate
from openswing.linear_dynamics import make_system,linearize,eigensystem
selected=json.loads(selected_json);assert selected['modules']==json.loads(modules_json)
statics=[];modal=[]
for old in selected['runs']:
 start=time.perf_counter();spec=old['specification'];gravity=[0.,0.,-spec['gravity']];parsed=parse_asw(old['source'])
 if spec['analysis']=='static':
  net=StaticNetwork(parsed,old['panels'],None,gravity,[]);state,_=equilibrate(net);new=network_result(net,state);differences={}
  assert new['residual']<1e-8
  for group,fields in [('nodes',['position','rotation']),('elements',['force','moment','strain','curvature_change'])]:
   for field in fields:
    a=np.array([r[field] for r in old['result'][group]]);b=np.array([r[field] for r in new[group]])
    error=float(np.max(abs(a-b)));assert error<2e-8,(spec,group,field,error);differences[group+'.'+field]=error
  for field in ['applied_force','applied_moment','support_force','support_moment','force_balance','moment_balance']:
   error=float(np.max(abs(np.array(new[field])-old['result'][field])));assert error<2e-8;differences[field]=error
  statics.append(dict(specification=spec,differences=differences,seconds=time.perf_counter()-start))
 else:
  system,_=make_system(parsed,None,panels=old['panels'],gravity=gravity,structured_base=True)
  a,m=linearize(system,step=1e-6);saved=np.load('/home/pyodide/'+old['matrices']['path']);errors={}
  for key,actual in [('A',a),('M',m)]:
   errors[key]=float(np.max(abs(actual-saved[key])/(1+abs(saved[key]))));assert errors[key]<2e-8
  roots,diagnostics=eigensystem(a,m,time_scale=system.W,count=16,shift=[-.1,0.],method='dense')
  roots=[r for r in roots if complex(*r['eigenvalue']).imag>1e-6];assert len(roots)==len(old['modes'])==8
  assert diagnostics['finite_dimension']==old['diagnostics']['finite_dimension']
  matches=[]
  for actual,before in zip(roots,old['modes']):
   difference=abs(actual['eigenvalue'][1]/(2*np.pi)-before['frequency_Hz']);assert difference<2e-6
   q=actual['right'][:6*system.network.nn].reshape(-1,6).copy();q[:,:3]*=system.L
   p=np.array(before['shape']['real'])+1j*np.array(before['shape']['imag'])
   score=float(abs(np.vdot(q,p))**2/(np.vdot(q,q).real*np.vdot(p,p).real));assert score>1-2e-8
   assert max(actual['left_backward_error'],actual['right_backward_error'])<1e-9
   matches.append(dict(frequency_difference_Hz=difference,shape_assurance=score))
  assert system.base_report()['residual']<1e-8
  modal.append(dict(specification=spec,matrix_errors=errors,matches=matches,seconds=time.perf_counter()-start))
 print('WASM',spec,'PASS',flush=True)
assert len(statics)==4 and len(modal)==6
json.dumps(dict(status='PASS_EXPECTED_OUTCOMES',statics=statics,modes=modal,full_family_validated=False))
 `));
 Object.assign(result,{modules,native_report_sha256:selected.reports,selector_sha256:selected.selector_sha256,
  test_sha256:sha(await readFile(new URL(import.meta.url))),pyodide:py.version});
 await writeFile('docs/validation/pazy-loaded-wasm.json',JSON.stringify(result,null,2)+'\n');console.log(result.status);
}catch(e){console.error(e.message,e.stack);process.exitCode=1;}
