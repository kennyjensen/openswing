import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=process.cwd(),sha=data=>createHash('sha256').update(data).digest('hex');
const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
try{
 const py=await loadPyodide({indexURL:root+'/public/runtime'});await py.loadPackage(['numpy','scipy']);
 py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
 const modules={};
 for(const name of(await readdir('openswing')).filter(n=>n.endsWith('.py'))){const bytes=await readFile('openswing/'+name);modules[name]=sha(bytes);py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);}
 const studyBytes=await readFile('docs/validation/isae-st3.json'),study=JSON.parse(studyBytes);
 for(const [name,key] of [['verify-isae-st3.py','script_sha256'],['isae_st3_reference.py','reference_script_sha256']]){
  const bytes=await readFile('scripts/'+name);if(sha(bytes)!==study.provenance[key])throw Error('Changed study script '+name);py.FS.writeFile('/home/pyodide/scripts/'+name,bytes);
 }
 const inputs={};
 for(const [name,record] of Object.entries(study.provenance.sources)){
  const bytes=await readFile(`.reference/isae-validation/${study.provenance.revision}/${name}`);
  if(sha(bytes)!==record.sha256)throw Error('Changed input '+name);inputs[name]=bytes.toString('utf8');
 }
 py.globals.set('study_json',studyBytes.toString('utf8'));py.globals.set('inputs_json',JSON.stringify(inputs));py.globals.set('modules_json',JSON.stringify(modules));
 const result=JSON.parse(await py.runPythonAsync(`
import sys,json,runpy,numpy as np
sys.path.insert(0,'/home/pyodide/scripts')
ns=runpy.run_path('/home/pyodide/scripts/verify-isae-st3.py')
study=json.loads(study_json);inputs=json.loads(inputs_json);assert study['provenance']['modules']==json.loads(modules_json)
selected=[]
for row in study['runs']:
 s=row['identity']['specification']
 if ((s['method']=='full_shift_invert' and s['panels']==16 and s['gravity']==9.81 and s['step']==1e-5 and (s['speed']==0 or (s['name']=='0_3_90' and s['speed']==.01)))
     or (s['method']=='dense' and s['rank_tolerance']==1e-9)):
  selected.append(row)
rows=[];maximum=0.;minimum=1.;physical_values=0
for expected in selected:
 s=expected['identity']['specification']
 try:actual=ns['compute'](inputs[ns['source_path'](s['name'])],s)
 except (ValueError,AssertionError) as exc:
  error=type(exc).__name__+': '+str(exc)
  assert expected['status']=='rejected' and error==expected['error'],(s,error)
  rows.append(dict(specification=s,status='rejected',error=error))
 else:
  assert expected['status']=='computed'
  ref=study['references'][s['name']][str(s['gravity'])][-1];matched=ns['match'](actual,ref)
  before=expected['result'];error=0.;mac=1.
  for old_search,new_search,old_matches,new_matches in zip(before['searches'],actual['searches'],before['matches'],matched):
   for a,b in zip(old_matches['modes'],new_matches['modes']):
    error=max(error,abs(a['frequency_Hz']-b['frequency_Hz']))
    old=ns['physical_shapes']([old_search['roots'][a['root_index']]],s['name'])
    new=ns['physical_shapes']([new_search['roots'][b['root_index']]],s['name'])
    mac=min(mac,float(ns['assurance'](old.reshape(1,-1),new.reshape(1,-1))[0,0]));physical_values+=old.size
  assert error<2e-6 and mac>1-2e-8,(s,error,mac)
  assert actual['base']['residual']<1e-8
  assert len(actual['base']['nodes'])==len(before['base']['nodes'])
  for a,b in zip(actual['base']['nodes'],before['base']['nodes']):
   for key in ['position','displacement','rotation']:
    if key in a:np.testing.assert_allclose(a[key],b[key],rtol=2e-7,atol=2e-9)
  maximum=max(maximum,error);minimum=min(minimum,mac)
  rows.append(dict(specification=s,status='computed',maximum_frequency_difference_Hz=error,minimum_shape_assurance=mac))
 print('WASM',s,rows[-1]['status'],flush=True)
json.dumps(dict(status='PASS_PORTABILITY_WITH_RETAINED_SOLVER_FAILURES',cases=rows,maximum_frequency_difference_Hz=maximum,minimum_shape_assurance=minimum,physical_shape_values=physical_values,full_suite_validated=False))
`));
 Object.assign(result,{modules,pyodide:py.version,study_sha256:sha(studyBytes),script_sha256:sha(await readFile(new URL(import.meta.url))),
  runtime_sha256:Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async n=>[n,sha(await readFile('public/runtime/'+n))])))});
 await writeFile(process.env.OPENSWING_RESULTS||'docs/validation/isae-st3-wasm.json',JSON.stringify(result,null,2)+'\n');console.log(result.status,result.cases.length);
}catch(error){console.error(String(error));process.exitCode=1;}
