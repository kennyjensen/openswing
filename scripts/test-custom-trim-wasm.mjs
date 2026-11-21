import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=x=>createHash('sha256').update(x).digest('hex');
try{
  const bytes=await readFile('docs/validation/custom-trim.json'),study=JSON.parse(bytes);
  for(const [file,value] of Object.entries(study.source_sha256))if(hash(await readFile(file))!==value)throw new Error('Study source changed: '+file);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  const modules=JSON.parse(await readFile('dist/kernel/manifest.json','utf8'));
  for(const name of modules){const data=await readFile('dist/kernel/'+name);if(!data.equals(await readFile('openswing/'+name)))throw new Error('Stale packaged module: '+name);py.FS.writeFile('/home/pyodide/openswing/'+name,data);}
  py.FS.writeFile('/home/pyodide/scripts/verify-custom-trim.py',await readFile('scripts/verify-custom-trim.py'));
  await py.runPythonAsync("import runpy,json,numpy as np\nhelpers=runpy.run_path('/home/pyodide/scripts/verify-custom-trim.py')");
  const cases=[];
  for(const c of study.cases){py.globals.set('case_json',JSON.stringify(c));const report=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);spec=c['specification'];actual=helpers['compute'](spec);checks=helpers['verify'](spec,actual)
a,b=helpers['physical'](actual),helpers['physical'](c['result']);difference=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
assert difference<5e-6,(spec['name'],difference)
json.dumps(dict(name=spec['name'],physical_values_compared=a.size,maximum_scaled_native_difference=difference,tangent_ratio=actual['static']['custom_trim']['one_sided_tangent_ratio'],**checks))
`));cases.push(report);console.log('Packaged WASM custom trim passed:',JSON.stringify(report));}
  if(cases.length!==10)throw new Error('Incomplete custom-trim study.');
  const [coarse,fine]=cases.filter(c=>c.name.startsWith('curved_beam_')).map(c=>c.continuum_torque_relative_error);
  if(!(fine<.27*coarse&&fine<.003))throw new Error('Bending refinement did not converge.');
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>[name,hash(await readFile('dist/runtime/'+name))])));
  await writeFile('docs/validation/custom-trim-wasm.json',JSON.stringify({study_sha256:hash(bytes),module_count:modules.length,runtime_sha256,source_sha256:{...study.source_sha256,'scripts/test-custom-trim-wasm.mjs':hash(await readFile('scripts/test-custom-trim-wasm.mjs'))},cases},null,2)+'\n');
  await new Promise(r=>process.stdout.write('All packaged WASM custom-trim checks passed.\n',r));process.exit(0);
}catch(error){await new Promise(r=>process.stderr.write(String(error)+'\n',r));process.exit(1);}
