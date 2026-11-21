import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
try{
  const bytes=await readFile('docs/validation/time-actuators.json'),study=JSON.parse(bytes);
  for(const [name,digest] of Object.entries(study.source_sha256))if(hash(await readFile(name))!==digest)throw Error('Changed study source: '+name);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  for(const name of ['openswing','scripts'])py.FS.mkdirTree('/home/pyodide/'+name);
  const modules=JSON.parse(await readFile('dist/kernel/manifest.json','utf8'));
  for(const name of modules){const bytes=await readFile('dist/kernel/'+name);if(!bytes.equals(await readFile('openswing/'+name)))throw Error('Stale bundled module '+name);py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);}
  py.FS.writeFile('/home/pyodide/scripts/verify-time-actuators.py',await readFile('scripts/verify-time-actuators.py'));
  await py.runPythonAsync("import runpy,json,numpy as np\nfrom openswing.bridge import dispatch\nhelpers=runpy.run_path('/home/pyodide/scripts/verify-time-actuators.py')");
  const cases=[];
  for(const index of [0,2,4,5]){
    py.globals.set('case_json',JSON.stringify(study.cases[index]));
    const result=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);out=dispatch(c['request']);spec=c['specification']
comparison=helpers['verify'](out,spec)
a=helpers['physical'](out,spec['units']);b=helpers['physical'](c['result'],spec['units'])
assert a.shape==b.shape
error=float(np.max(abs(a-b)/np.maximum(1,abs(b))))
assert error<2e-8,error
json.dumps(dict(result=out,comparison=comparison,maximum_scaled_native_difference=error,physical_values=int(a.size)))
`));
    cases.push({native_case:index,...result});console.log('Inverse time replay',index,result.maximum_scaled_native_difference);
  }
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>[name,hash(await readFile('dist/runtime/'+name))])));
  await writeFile('docs/validation/time-actuators-wasm.json',JSON.stringify({study_sha256:hash(bytes),source_sha256:study.source_sha256,
    runner_sha256:hash(await readFile('scripts/test-time-actuators-wasm.mjs')),runtime_sha256,module_count:modules.length,cases},null,2)+'\n');
  process.exit(0);
}catch(error){await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
