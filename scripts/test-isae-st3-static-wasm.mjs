import {readFile, readdir, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=process.cwd(), sha=b=>createHash('sha256').update(b).digest('hex');
const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
try {
  const bytes=await readFile('docs/validation/isae-st3-static.json'), study=JSON.parse(bytes);
  const py=await loadPyodide({indexURL:root+'/public/runtime'});
  await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing'); py.FS.mkdirTree('/home/pyodide/scripts');
  const modules={}, scripts={}, inputs={};
  for(const n of (await readdir('openswing')).filter(n=>n.endsWith('.py'))) {
    const b=await readFile('openswing/'+n); modules[n]=sha(b); py.FS.writeFile('/home/pyodide/openswing/'+n,b);
  }
  for(const n of ['verify-isae-st3-static.py','isae_st3_static_reference.py']) {
    const b=await readFile('scripts/'+n); scripts[n]=sha(b); py.FS.writeFile('/home/pyodide/scripts/'+n,b);
  }
  for(const name of ['0_3_90','p15_0','m15_0']) {
    const p=`3 - Structure/CASE - ST3 Low aspect ratio/Static_Deflection_analysis/[${name}].asw`;
    const b=await readFile(`.reference/isae-validation/${study.revision}/${p}`);
    if(sha(b)!==study.sources[p].sha256) throw Error('Input changed'); inputs[name]=b.toString('utf8');
  }
  py.globals.set('study_json',bytes.toString('utf8'));
  py.globals.set('modules_json',JSON.stringify(modules)); py.globals.set('scripts_json',JSON.stringify(scripts));
  py.globals.set('inputs_json',JSON.stringify(inputs));
  const result=JSON.parse(await py.runPythonAsync(`
import json, sys, runpy, numpy as np
sys.path.insert(0,'/home/pyodide/scripts')
ns=runpy.run_path('/home/pyodide/scripts/verify-isae-st3-static.py')
study=json.loads(study_json); inputs=json.loads(inputs_json)
assert study['modules']==json.loads(modules_json) and study['scripts']==json.loads(scripts_json)
selected=[]
for name in ['0_3_90','p15_0','m15_0']:
    f=4.905 if name=='0_3_90' else 3.924
    selected.append(next(r for r in study['runs'] if r['identity']['specification']==dict(name=name,force_N=f,couple_Nm=0.,panels=32)))
    key=next(r['native_key'] for r in study['archived_final_weights'] if r['name']==name)
    selected.append(next(r for r in study['runs'] if r['key']==key))
for spec in [dict(name='p15_0',force_N=-3.924,couple_Nm=0.,panels=32),dict(name='m15_0',force_N=0.,couple_Nm=.55,panels=64)]:
    selected.append(next(r for r in study['runs'] if r['identity']['specification']==spec))
rows=[]
for row in selected:
    spec=row['identity']['specification']; old=row['result']; new=ns['compute'](inputs[spec['name']],spec)
    differences={}
    for field in ['position','rotation']:
        a=np.array([n[field] for n in old['result']['nodes']]);b=np.array([n[field] for n in new['result']['nodes']])
        differences[field]=float(np.max(abs(a-b)));assert differences[field]<2e-9,(spec,field,differences[field])
    for field in ['applied_force','applied_moment','support_force','support_moment','force_balance','moment_balance']:
        differences[field]=float(np.max(abs(np.array(old['result'][field])-new['result'][field])))
        assert differences[field]<2e-8,(spec,field,differences[field])
    assert new['result']['residual']<1e-8 and new['derived_source']==old['derived_source']
    rows.append(dict(specification=spec,maximum_differences=differences,residual=new['result']['residual'],seconds=new['seconds']))
    print('WASM',spec,'PASS',flush=True)
literal=[]
for name,text in inputs.items():
    try:ns['StaticNetwork'](ns['inspect'](text,name),8,None,[0,0,-9.81],[])
    except ValueError as exc:
        assert str(exc)=='Point weights must be nonnegative.'
        literal.append(dict(name=name,error=str(exc)))
    else:raise AssertionError('Literal signed weight unexpectedly accepted')
assert len(rows)==8 and len(literal)==3
json.dumps(dict(status='PASS',cases=rows,literal_rejections=literal,scope='Direct production Python API in actual Pyodide; not a browser UI vacuum-static workflow.',full_suite_validated=False))
`));
  Object.assign(result,{modules,scripts,study_sha256:sha(bytes),script_sha256:sha(await readFile(new URL(import.meta.url))),pyodide:py.version});
  await writeFile(process.env.OPENSWING_RESULTS||'docs/validation/isae-st3-static-wasm.json',JSON.stringify(result,null,2)+'\n');
  console.log(result.status,result.cases.length);
} catch(e) {console.error(String(e));process.exitCode=1;}
