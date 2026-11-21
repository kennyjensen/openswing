import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=x=>createHash('sha256').update(x).digest('hex');
try{
  const bytes=await readFile('docs/validation/control-allocation.json'),study=JSON.parse(bytes);
  for(const [file,value] of Object.entries(study.source_sha256))if(hash(await readFile(file))!==value)throw new Error('Study source changed: '+file);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  const modules=JSON.parse(await readFile('dist/kernel/manifest.json','utf8'));
  for(const name of modules){const data=await readFile('dist/kernel/'+name);if(!data.equals(await readFile('openswing/'+name)))throw new Error('Stale packaged module: '+name);py.FS.writeFile('/home/pyodide/openswing/'+name,data);}
  py.FS.writeFile('/home/pyodide/scripts/verify-control-allocation.py',await readFile('scripts/verify-control-allocation.py'));
  await py.runPythonAsync("import runpy,json,numpy as np\nhelpers=runpy.run_path('/home/pyodide/scripts/verify-control-allocation.py')");
  const cases=[];
  for(const c of study.cases){py.globals.set('case_json',JSON.stringify(c));const report=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);spec=c['specification'];actual=helpers['compute'](spec);checks=helpers['verify'](spec,actual)
a,b=helpers['physical'](actual),helpers['physical'](c['result']);difference=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
assert difference<5e-6,(spec['name'],difference)
r=actual['static']['control_allocation'];assert r['equality_residual']<1e-8 and r['normalized_stationarity']<2e-6 and min(r['reduced_curvatures'])>0
json.dumps(dict(name=spec['name'],physical_values_compared=a.size,maximum_scaled_native_difference=difference,stationarity=r['normalized_stationarity'],reduced_curvatures=r['reduced_curvatures'],**checks))
`));cases.push(report);console.log('Packaged WASM allocation passed:',JSON.stringify(report));}
  if(cases.length!==7)throw new Error('Incomplete allocation study.');
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>[name,hash(await readFile('dist/runtime/'+name))])));
  await writeFile('docs/validation/control-allocation-wasm.json',JSON.stringify({study_sha256:hash(bytes),module_count:modules.length,runtime_sha256,source_sha256:{...study.source_sha256,'scripts/test-control-allocation-wasm.mjs':hash(await readFile('scripts/test-control-allocation-wasm.mjs'))},cases},null,2)+'\n');
  await new Promise(r=>process.stdout.write('All packaged WASM control-allocation checks passed.\n',r));process.exit(0);
}catch(error){await new Promise(r=>process.stderr.write(String(error)+'\n',r));process.exit(1);}
