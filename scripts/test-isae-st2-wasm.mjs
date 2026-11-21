import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const sha=b=>createHash('sha256').update(b).digest('hex'),root=process.cwd();
const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
try {
 const staticBytes=await readFile('docs/validation/isae-st2-static.json'),stat=JSON.parse(staticBytes);
 const modeBytes=await readFile('docs/validation/isae-st2-modes.json'),modal=JSON.parse(modeBytes);
 if(stat.status!=='COMPARISONS_COMPLETE_NOT_PHYSICALLY_VALIDATED'||modal.status!==stat.status)throw Error('Native study incomplete');
 const audit=JSON.parse(await readFile('docs/validation/isae-st2-source-audit.json'));
 const py=await loadPyodide({indexURL:root+'/public/runtime'});await py.loadPackage(['numpy','scipy']);
 const put=(path,bytes)=>{py.FS.mkdirTree(path.slice(0,path.lastIndexOf('/')));py.FS.writeFile(path,bytes);};
 const modules={},scripts={};
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py'))){const b=await readFile('openswing/'+n);modules[n]=sha(b);put('/home/pyodide/openswing/'+n,b);}
 for(const n of ['isae_st2.py','isae_st2_modal_reference.py','verify-isae-st2-modes.py']){const b=await readFile('scripts/'+n);scripts[n]=sha(b);put('/home/pyodide/scripts/'+n,b);}
 const original=[];
 for(const row of audit.literal_models){const p='.reference/isae-validation/'+audit.upstream_revision+'/'+row.path,b=await readFile(p);if(sha(b)!==row.sha256)throw Error('Input changed');put('/home/pyodide/'+p,b);original.push({path:row.path,text:b.toString('utf8')});}
 const selected=[];
 for(const [kind,skin,mass] of [['bending',0,3],['torsion',0,2],['torsion',1,2.8]])for(const layout of ['archive_pylon','measured_tip']){
  const row=Object.values(stat.runs).find(r=>r.specification.kind===kind&&r.specification.skin===skin&&r.specification.mass_kg===mass&&r.specification.layout===layout&&r.specification.panels===32);
  const b=await readFile(row.cache);if(sha(b)!==row.sha256)throw Error('Cache changed');selected.push(JSON.parse(b));
 }
 for(const kind of ['bending','torsion']){
  const row=Object.values(stat.runs).find(r=>r.specification.kind===kind&&r.specification.skin===0&&r.specification.mass_kg===0&&r.specification.layout==='measured_tip'&&r.specification.panels===32);
  const b=await readFile(row.cache);if(sha(b)!==row.sha256)throw Error('Cache changed');selected.push(JSON.parse(b));
 }
 const selectedModes=[];
 for(const row of modal.runs.filter(r=>r.specification.panels===16)){
  const b=await readFile(row.cache);if(sha(b)!==row.sha256)throw Error('Modal cache changed');const run=JSON.parse(b);
  const a=await readFile(run.matrices.path);if(sha(a)!==run.matrices.sha256)throw Error('Matrix cache changed');put('/home/pyodide/'+run.matrices.path,a);selectedModes.push(run);
 }
 for(const [k,v] of Object.entries({modules,statModules:stat.modules,modalModules:modal.modules,selected,selectedModes,original}))py.globals.set(k+'_json',JSON.stringify(v));
 const result=JSON.parse(await py.runPythonAsync(`
import json,sys,numpy as np
sys.path.insert(0,'/home/pyodide/scripts')
from isae_st2 import compute_static
from openswing.asw import parse_asw
from openswing.network import StaticNetwork
import importlib.util
spec=importlib.util.spec_from_file_location('modal_check','/home/pyodide/scripts/verify-isae-st2-modes.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
assert json.loads(modules_json)==json.loads(statModules_json)==json.loads(modalModules_json)
rows=[]
for old in json.loads(selected_json):
 spec=old['specification'];new=compute_static(spec);differences={}
 assert new['derived_source']==old['derived_source']
 for collection,fields in [('nodes',['position','rotation']),('elements',['force','moment','strain','curvature_change'])]:
  for field in fields:
   a=np.array([r[field] for r in old['result'][collection]]);b=np.array([r[field] for r in new['result'][collection]])
   differences[collection+'.'+field]=float(np.max(abs(a-b)));assert differences[collection+'.'+field]<2e-8,(spec,field,differences)
 for field in ['applied_force','applied_moment','support_force','support_moment','force_balance','moment_balance']:
  differences[field]=float(np.max(abs(np.array(old['result'][field])-new['result'][field])));assert differences[field]<2e-8
 assert new['result']['residual']<1e-8
 rows.append(dict(specification=spec,differences=differences,residual=new['result']['residual']))
 print('WASM static',spec,'PASS',flush=True)
mode_rows=[]
for old in json.loads(selectedModes_json):
 spec=old['specification'];new,a,m=module.compute(spec);pin=np.load('/home/pyodide/'+old['matrices']['path'])
 matrix_errors={}
 for name,actual in [('A',a),('M',m)]:
  expected=pin[name];matrix_errors[name]=float(np.max(abs(actual-expected)/(1+abs(expected))))
  assert matrix_errors[name]<2e-8,(spec,name,matrix_errors)
 assert new['derived_source']==old['derived_source'] and len(new['modes'])==len(old['modes'])
 comparisons=[]
 for before,after in zip(old['modes'],new['modes']):
  df=abs(before['frequency_Hz']-after['frequency_Hz']);assert df<2e-6,(spec,df)
  x=np.array(before['shape']['real'])+1j*np.array(before['shape']['imag']);y=np.array(after['shape']['real'])+1j*np.array(after['shape']['imag'])
  mac=float(abs(np.vdot(x,y))**2/(np.vdot(x,x).real*np.vdot(y,y).real));assert mac>1-2e-8,(spec,mac)
  assert max(after['left_backward_error'],after['right_backward_error'])<1e-9
  comparisons.append(dict(frequency_difference_Hz=df,shape_assurance=mac))
 mode_rows.append(dict(specification=spec,matrix_errors=matrix_errors,modes=comparisons));print('WASM modes',spec,'PASS',flush=True)
rejections=[]
for row in json.loads(original_json):
 try:StaticNetwork(parse_asw(row['text']),8,None,[0,0,-9.81],[],allow_signed_point_weights=True)
 except ValueError as e:
  assert 'Attachment station is outside beam' in str(e);rejections.append(dict(path=row['path'],error=str(e)))
 else:raise AssertionError('Literal out-of-range attachment accepted')
assert len(rows)==8 and len(mode_rows)==4 and len(rejections)==6
json.dumps(dict(status='PASS_EXPECTED_OUTCOMES',static_rows=rows,modal_rows=mode_rows,literal_rejections=rejections,full_suite_validated=False))
`));
 Object.assign(result,{modules,scripts,static_sha256:sha(staticBytes),modal_sha256:sha(modeBytes),test_sha256:sha(await readFile(new URL(import.meta.url))),pyodide:py.version});
 await writeFile(process.env.OPENSWING_RESULTS||'docs/validation/isae-st2-wasm.json',JSON.stringify(result,null,2)+'\n');console.log(result.status);
}catch(e){console.error(String(e));process.exitCode=1;}
