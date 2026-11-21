import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=x=>createHash('sha256').update(x).digest('hex');
try {
  const bytes=await readFile('docs/validation/reference-flow.json'),study=JSON.parse(bytes);
  for(const [file,value] of Object.entries(study.source_sha256))if(hash(await readFile(file))!==value)throw new Error('Study source changed: '+file);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  const modules=JSON.parse(await readFile('dist/kernel/manifest.json','utf8'));
  for(const name of modules){const data=await readFile('dist/kernel/'+name);if(!data.equals(await readFile('openswing/'+name)))throw new Error('Stale packaged module: '+name);py.FS.writeFile('/home/pyodide/openswing/'+name,data);}
  py.FS.writeFile('/home/pyodide/scripts/verify-reference-flow.py',await readFile('scripts/verify-reference-flow.py'));
  await py.runPythonAsync("import runpy,json,numpy as np\nhelpers=runpy.run_path('/home/pyodide/scripts/verify-reference-flow.py')");
  const cases=[];
  for(const c of study.cases){py.globals.set('case_json',JSON.stringify(c));const report=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);spec=c['specification'];actual=helpers['compute'](spec);checks=helpers['verify'](spec,actual)
a,b=helpers['physical'](actual),helpers['physical'](c['result']);difference=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
assert difference<2e-7,(spec['name'],difference)
json.dumps(dict(name=spec['name'],physical_values_compared=a.size,maximum_scaled_native_difference=difference,**checks))
`));cases.push(report);console.log('Packaged WASM reference flow passed:',JSON.stringify(report));}
  if(cases.length!==8)throw new Error('Incomplete reference-flow study.');
  const singularity_checks=await py.runPythonAsync("helpers['singularity_checks']()");
  if(singularity_checks!==3 || singularity_checks!==study.singularity_checks)throw new Error('Singular air-data checks differ.');
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>[name,hash(await readFile('dist/runtime/'+name))])));
  await writeFile('docs/validation/reference-flow-wasm.json',JSON.stringify({study_sha256:hash(bytes),module_count:modules.length,runtime_sha256,source_sha256:{...study.source_sha256,'scripts/test-reference-flow-wasm.mjs':hash(await readFile('scripts/test-reference-flow-wasm.mjs'))},cases,singularity_checks},null,2)+'\n');
  await new Promise(r=>process.stdout.write('All packaged WASM reference-flow checks passed.\n',r));process.exit(0);
}catch(error){await new Promise(r=>process.stderr.write(String(error)+'\n',r));process.exit(1);}
