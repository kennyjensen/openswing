import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const sha=b=>createHash('sha256').update(b).digest('hex');
const work=process.argv[2];
if(!work)throw Error('Provide the modal-adjoint work directory.');
const candidate=path.join(work,'candidate'),baseline=path.join(work,'baseline');
const reports={},selected=[];
for(const name of ['zero','modes']){
 const file=`docs/validation/pazy-loaded-${name}.json`,bytes=await readFile(file),report=JSON.parse(bytes);reports[file]=sha(bytes);
 selected.push(...report.runs.filter(r=>r.specification.skin===1&&((name==='zero'&&r.specification.refinement===1)||(name==='modes'&&r.specification.refinement===4))));
}
if(selected.length!==3)throw Error('Expected three native pencils.');
const {loadPyodide}=await import(process.cwd()+'/node_modules/pyodide/pyodide.mjs');
const py=await loadPyodide({indexURL:process.cwd()+'/public/runtime'});await py.loadPackage(['numpy','scipy']);
const put=(p,b)=>{py.FS.mkdirTree(p.slice(0,p.lastIndexOf('/')));py.FS.writeFile(p,b);};
const pins={baseline:{},candidate:{}};
for(const name of(await readdir(path.join(candidate,'openswing'))).filter(n=>n.endsWith('.py')).sort()){
 const old=await readFile(path.join(baseline,'openswing',name)),current=await readFile(path.join(candidate,'openswing',name));
 pins.baseline[name]=sha(old);pins.candidate[name]=sha(current);put('/home/pyodide/openswing/'+name,current);
 if(name==='linear_dynamics.py')put('/home/pyodide/openswing/_baseline_linear_dynamics.py',old);
}
if(Object.keys(pins.candidate).length!==97)throw Error('Unexpected kernel module count');
if(Object.keys(pins.candidate).filter(n=>pins.candidate[n]!==pins.baseline[n]).join()!=='linear_dynamics.py')throw Error('Unexpected source change');
const cases=[];
for(const row of selected){
 const bytes=await readFile(row.cache);if(sha(bytes)!==row.sha256)throw Error('Native cache changed');const data=JSON.parse(bytes);
 const matrix=await readFile(data.matrices.path);if(sha(matrix)!==data.matrices.sha256)throw Error('Native pencil changed');
 put('/home/pyodide/'+data.matrices.path,matrix);cases.push({specification:row.specification,matrices:data.matrices,time_scale:data.diagnostics.time_scale,finite_dimension:data.diagnostics.finite_dimension});
}
py.globals.set('cases_json',JSON.stringify(cases));
const result=JSON.parse(await py.runPythonAsync(`
import json,time,numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.linalg import block_diag
from openswing import linear_dynamics as new
from openswing import _baseline_linear_dynamics as old
rows=[]
for case in json.loads(cases_json):
 pencil=np.load('/home/pyodide/'+case['matrices']['path']);a,m=pencil['A'],pencil['M'];answers={};times={}
 for name,solver in [('baseline',old),('candidate',new)]:
  start=time.perf_counter();modes,meta=solver.eigensystem(a,m,time_scale=case['time_scale'],count=16,shift=[-.1,0.],method='dense')
  times[name]=time.perf_counter()-start;answers[name]=(modes,meta)
  assert meta['finite_dimension']==case['finite_dimension']
 x,y=answers['baseline'][0],answers['candidate'][0]
 vx=np.array([complex(*r['eigenvalue']) for r in x]);vy=np.array([complex(*r['eigenvalue']) for r in y])
 ii,jj=linear_sum_assignment(abs(vx[:,None]-vy));checks=[]
 for i,j in zip(ii,jj):
  a0,b0=x[i],y[j];r,l=a0['right'],a0['left'];s,t=b0['right'],b0['left'];factor=np.vdot(s,r)/np.vdot(s,s);s=s*factor;t=t/np.conj(factor)
  bound=float((np.linalg.norm(r-s)*np.linalg.norm(l)+np.linalg.norm(s)*np.linalg.norm(l-t))/(np.linalg.norm(r)*np.linalg.norm(l)))
  delta=float(abs(vx[i]-vy[j])/max(1.,abs(vx[i])));assert delta<2e-8 and bound<2e-8
  assert max(b0['left_backward_error'],b0['right_backward_error'])<1e-9
  checks.append(dict(relative_eigenvalue_difference=delta,relative_residue_error_bound=bound,left_backward_error=b0['left_backward_error']))
 counts=answers['candidate'][1]['left_recovery_counts'];assert counts['sparse_adjoint']==counts['conjugate_reuse']==8 and counts['schur_pencils']==0
 rows.append(dict(**case,timing_seconds=times,observed_speedup=times['baseline']/times['candidate'],comparisons=checks,recovery=counts))
 print('WASM pencil',case['specification'],'PASS',times,flush=True)
# A selected subset of a repeated spectrum must use the unchanged fallback.
a=block_diag(*([np.array([[0.,1.],[-4.,-.2]])]*32));m=np.eye(len(a))
roots,info=new.eigensystem(a,m,count=2)
assert info['finite_dimension']==64 and info['left_recovery_counts']['schur_pencils']==1 and info['left_recovery_counts']['sparse_adjoint']==0
assert max(r['left_backward_error'] for r in roots)<1e-10
json.dumps(dict(status='PASS_WASM_PENCIL_ADJOINTS_AND_REPEATED_POLE_FALLBACK',rows=rows,repeated_pole_fallback=info,full_physical_validation=False))
`));
Object.assign(result,{modules:pins,native_report_sha256:reports,test_sha256:sha(await readFile(new URL(import.meta.url))),pyodide:py.version});
await writeFile(path.join(work,'wasm.json'),JSON.stringify(result,null,2)+'\n');console.log(result.status);
