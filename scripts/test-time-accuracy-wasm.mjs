import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=x=>createHash('sha256').update(x).digest('hex');
try{
  const bytes=await readFile('docs/validation/time-accuracy.json'),study=JSON.parse(bytes);
  for(const [name,digest] of Object.entries(study.source_sha256))if(hash(await readFile(name))!==digest)throw Error('Changed study source: '+name);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  for(const folder of ['openswing','scripts','examples'])py.FS.mkdirTree('/home/pyodide/'+folder);
  const modules=JSON.parse(await readFile('dist/kernel/manifest.json'));
  for(const name of modules){const data=await readFile('dist/kernel/'+name);if(!data.equals(await readFile('openswing/'+name)))throw Error('Stale module: '+name);py.FS.writeFile('/home/pyodide/openswing/'+name,data);}
  for(const file of ['scripts/verify-time-accuracy.py','examples/instrumented-oscillator.asw','examples/actuator-lag-controller.json','examples/rectangular.asw'])py.FS.writeFile('/home/pyodide/'+file,await readFile(file));
  await py.runPythonAsync("import json,runpy,numpy as np\nh=runpy.run_path('/home/pyodide/scripts/verify-time-accuracy.py')");
  const cases=[];
  const selected=study.cases.filter(c=>(c.spec.kind==='spring'&&(c.spec.restart||c.spec.units||c.spec.atol===1e-8))||
    (c.spec.kind==='controller'&&c.spec.restart)||(c.spec.kind==='gust'&&(c.spec.restart||c.spec.amplitude)));
  for(const c of selected){
    py.globals.set('case_json',JSON.stringify(c));
    const record=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);result=h['compute'](c['spec'])
# Adaptive grids can branch differently under floating-point perturbations.
# Each runtime must pass the independent physical reference at its own times.
# Compare runtimes at their common endpoint; do not interpolate the records.
a,b=np.asarray(result['samples'][-1]['computed']),np.asarray(c['samples'][-1]['computed'])
error=float(np.max(abs(a-b)/np.asarray(c['error_scales'])))
assert error<2e-6,(c['spec'],error)
assert result['samples'][-1]['time']==c['samples'][-1]['time']
ta,tb=np.array([s['time'] for s in result['samples']]),np.array([s['time'] for s in c['samples']])
grid_difference=float(np.max(abs(ta-tb))) if len(ta)==len(tb) else None
json.dumps(dict(spec=c['spec'],result=result,endpoint_values_compared=len(a),maximum_scaled_native_endpoint_difference=error,
    native_reported_steps=c['accepted_steps'],maximum_grid_time_difference=grid_difference),allow_nan=False)
`));
    cases.push(record);console.log('Temporal accuracy WASM',JSON.stringify(record.spec),record.maximum_scaled_native_endpoint_difference);
  }
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>[name,hash(await readFile('dist/runtime/'+name))])));
  await writeFile('docs/validation/time-accuracy-wasm.json',JSON.stringify({study_sha256:hash(bytes),module_count:modules.length,runtime_sha256,
    source_sha256:{...study.source_sha256,'scripts/test-time-accuracy-wasm.mjs':hash(await readFile('scripts/test-time-accuracy-wasm.mjs'))},cases},null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('Temporal accuracy packaged replay passed.\n',resolve));process.exit(0);
}catch(error){await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
