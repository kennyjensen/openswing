import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=x=>createHash('sha256').update(x).digest('hex');
try{
  const bytes=await readFile('docs/validation/section-airflow.json'),study=JSON.parse(bytes);
  for(const [name,digest] of Object.entries(study.source_sha256))if(hash(await readFile(name))!==digest)throw Error('Changed study source: '+name);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  const modules=JSON.parse(await readFile('dist/kernel/manifest.json'));
  for(const name of modules){const data=await readFile('dist/kernel/'+name);if(!data.equals(await readFile('openswing/'+name)))throw Error('Stale module: '+name);py.FS.writeFile('/home/pyodide/openswing/'+name,data);}
  py.FS.writeFile('/home/pyodide/scripts/verify-section-airflow.py',await readFile('scripts/verify-section-airflow.py'));
  await py.runPythonAsync("import json,runpy,numpy as np\nh=runpy.run_path('/home/pyodide/scripts/verify-section-airflow.py')");
  const cases=[];
  for(const c of study.cases){
    py.globals.set('case_json',JSON.stringify(c));
    const record=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);result=h['compute'](c['specification'])
a,b=h['physical'](result),h['physical'](c['result'])
error=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
assert error<2e-8,(c['specification'],error)
json.dumps(dict(specification=c['specification'],result=result,physical_values_compared=a.size,maximum_scaled_native_difference=error))
`));cases.push(record);console.log('Section airflow WASM',JSON.stringify(record.specification),record.maximum_scaled_native_difference);
  }
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>[name,hash(await readFile('dist/runtime/'+name))])));
  await writeFile('docs/validation/section-airflow-wasm.json',JSON.stringify({study_sha256:hash(bytes),module_count:modules.length,runtime_sha256,
    source_sha256:{...study.source_sha256,'scripts/test-section-airflow-wasm.mjs':hash(await readFile('scripts/test-section-airflow-wasm.mjs'))},cases},null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('Section airflow packaged replay passed.\n',resolve));process.exit(0);
}catch(error){await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
