import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=process.cwd(),sha=b=>createHash('sha256').update(b).digest('hex');
const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
try{
 const py=await loadPyodide({indexURL:root+'/public/runtime'});await py.loadPackage(['numpy','scipy']);
 py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
 const modules={};for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py'))){const b=await readFile('openswing/'+n);modules[n]=sha(b);py.FS.writeFile('/home/pyodide/openswing/'+n,b);}
 const bytes=await readFile('docs/validation/dense-staircase.json'),study=JSON.parse(bytes);
 const baseline=JSON.parse(await readFile('docs/validation/isae-st3.json'));const scripts={};
 for(const n of ['verify-dense-staircase.py','verify-isae-st3.py','isae_st3_reference.py']){const b=await readFile('scripts/'+n);scripts[n]=sha(b);py.FS.writeFile('/home/pyodide/scripts/'+n,b);}
 if(scripts['verify-dense-staircase.py']!==study.script_sha256)throw Error('Native script changed');
 const inputs={};for(const [p,v] of Object.entries(baseline.provenance.sources)){
  const b=await readFile(`.reference/isae-validation/${baseline.provenance.revision}/${p}`);if(sha(b)!==v.sha256)throw Error('Input changed');inputs[p]=b.toString('utf8');
 }
 py.globals.set('study_json',bytes.toString('utf8'));py.globals.set('modules_json',JSON.stringify(modules));py.globals.set('inputs_json',JSON.stringify(inputs));
 const result=JSON.parse(await py.runPythonAsync(`
import sys,json,runpy,numpy as np
from scipy.optimize import linear_sum_assignment
sys.path.insert(0,'/home/pyodide/scripts')
ns=runpy.run_path('/home/pyodide/scripts/verify-dense-staircase.py')
study=json.loads(study_json);assert study['modules']==json.loads(modules_json)
inputs=json.loads(inputs_json);rows=[];maximum=0.;minimum=1.;spectrum_error=0.
for row in study['runs']:
 s=row['identity']['specification']
 if not ((s['speed']==0 and ((s['panels']==8 and s['gravity']==0) or (s['panels']==16 and s['gravity']==9.81) or (s['name']=='0_3_90' and s['panels']==32 and s['gravity']==0))) or (s['name']=='p15_0' and s['speed']==.01)):continue
 actual=ns['compute'](inputs[ns['ns']['source_path'](s['name'])],s);before=row['result'];errors=[];macs=[];complete=[]
 for old,new,os,nspec in zip(before['searches'],actual['searches'],before['spectra'],actual['spectra']):
  assert old['diagnostics']['finite_dimension']==new['diagnostics']['finite_dimension']
  assert len(old['roots'])==len(new['roots'])
  for a,b in zip(old['roots'],new['roots']):
   errors.append(abs(a['frequency_Hz']-b['frequency_Hz']))
   av=ns['ns']['physical_shapes']([a],s['name']).reshape(1,-1);bv=ns['ns']['physical_shapes']([b],s['name']).reshape(1,-1)
   macs.append(float(ns['ns']['assurance'](av,bv)[0,0]))
  x,y=[np.array([complex(*v) for v in r['eigenvalues']]) for r in [os,nspec]]
  assert len(x)==len(y);cost=abs(x[:,None]-y)/np.maximum(1.,abs(y));i,j=linear_sum_assignment(cost);complete.append(float(max(cost[i,j])))
 assert max(errors)<2e-6 and min(macs)>1-2e-8 and max(complete)<2e-6,(s,max(errors),min(macs),max(complete))
 maximum=max(maximum,max(errors));minimum=min(minimum,min(macs));spectrum_error=max(spectrum_error,max(complete))
 rows.append(dict(specification=s,finite_dimension=actual['searches'][0]['diagnostics']['finite_dimension'],maximum_low_frequency_difference_Hz=max(errors),minimum_shape_assurance=min(macs),maximum_complete_spectrum_relative_difference=max(complete)))
 print('WASM',s,'PASS',flush=True)
assert len(rows)==8
json.dumps(dict(status='PASS',cases=rows,maximum_low_frequency_difference_Hz=maximum,minimum_shape_assurance=minimum,maximum_complete_spectrum_relative_difference=spectrum_error,full_suite_validated=False))
`));
 Object.assign(result,{modules,study_sha256:sha(bytes),scripts,script_sha256:sha(await readFile(new URL(import.meta.url))),pyodide:py.version});
 await writeFile(process.env.OPENSWING_RESULTS||'docs/validation/dense-staircase-wasm.json',JSON.stringify(result,null,2)+'\n');console.log(result.status,result.cases.length);
}catch(e){console.error(String(e));process.exitCode=1;}
