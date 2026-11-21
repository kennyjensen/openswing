import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=x=>createHash('sha256').update(x).digest('hex');
try{
  const bytes=await readFile('docs/validation/frozen-influences.json'),study=JSON.parse(bytes);
  for(const [name,digest] of Object.entries(study.source_sha256))if(hash(await readFile(name))!==digest)throw new Error('Study source changed: '+name);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  const modules=JSON.parse(await readFile('dist/kernel/manifest.json','utf8'));
  for(const name of modules){const b=await readFile('dist/kernel/'+name);if(!b.equals(await readFile('openswing/'+name)))throw new Error('Stale packaged module: '+name);py.FS.writeFile('/home/pyodide/openswing/'+name,b);}
  py.FS.writeFile('/home/pyodide/scripts/verify-wake-core.py',await readFile('scripts/verify-wake-core.py'));
  py.FS.writeFile('/home/pyodide/scripts/verify-frozen-influences.py',await readFile('scripts/verify-frozen-influences.py'));
  await py.runPythonAsync("import runpy,json,numpy as np\nhelpers=runpy.run_path('/home/pyodide/scripts/verify-frozen-influences.py')");
  const cases=[];
  for(const c of study.cases){
    py.globals.set('case_json',JSON.stringify(c));
    const result=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);actual=helpers['compute'](c['specification'])
a,b,r=map(helpers['physical'],[actual,c['result'],c['reference']])
difference=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
reference_error=float(np.max(abs(a-r)/np.maximum(1.,abs(r))))
assert difference<2e-9 and reference_error<2e-9,(c['name'],difference,reference_error)
assert actual['metadata']==c['result']['metadata'],c['name']
json.dumps(dict(actual=actual,physical_values_compared=a.size,maximum_scaled_native_difference=difference,maximum_scaled_reference_error=reference_error))
`));
    cases.push({name:c.name,...result});console.log('Frozen influences WASM',c.name,result.maximum_scaled_native_difference);
  }
  for(const [name,digest] of Object.entries(study.source_sha256))if(hash(await readFile(name))!==digest)throw new Error('Study source changed during replay: '+name);
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async n=>[n,hash(await readFile('dist/runtime/'+n))])));
  await writeFile('docs/validation/frozen-influences-wasm.json',JSON.stringify({study_sha256:hash(bytes),module_count:modules.length,runtime_sha256,
    source_sha256:{...study.source_sha256,'scripts/test-frozen-influences-wasm.mjs':hash(await readFile('scripts/test-frozen-influences-wasm.mjs'))},cases},null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('Frozen-influences WASM study passed.\n',resolve));process.exit(0);
}catch(e){await new Promise(resolve=>process.stderr.write(String(e)+'\n',resolve));process.exit(1);}
