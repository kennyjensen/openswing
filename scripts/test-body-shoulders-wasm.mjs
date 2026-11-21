import {loadPyodide} from 'pyodide';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=x=>createHash('sha256').update(x).digest('hex');
try{
  const bytes=await readFile('docs/validation/body-shoulders.json'),study=JSON.parse(bytes);
  for(const [file,value] of Object.entries(study.source_sha256))if(hash(await readFile(file))!==value)throw new Error('Study source changed: '+file);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8'))){const data=await readFile('dist/kernel/'+name);if(!data.equals(await readFile('openswing/'+name)))throw new Error('Stale packaged module: '+name);py.FS.writeFile('/home/pyodide/openswing/'+name,data);}
  py.FS.writeFile('/home/pyodide/scripts/verify-body-shoulders.py',await readFile('scripts/verify-body-shoulders.py'));await py.runPythonAsync("import runpy,json,numpy as np\nhelpers=runpy.run_path('/home/pyodide/scripts/verify-body-shoulders.py')");
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async n=>[n,hash(await readFile('dist/runtime/'+n))])));
  const cache='.reference/body-shoulders-wasm/'+hash(JSON.stringify({study:hash(bytes),runner:hash(await readFile('scripts/test-body-shoulders-wasm.mjs')),runtime_sha256}));await mkdir(cache,{recursive:true});const cases=[];
  for(const c of study.cases){const name=c.specification.name;py.globals.set('case_json',JSON.stringify(c));let cached='';try{cached=await readFile(cache+'/'+name+'.json','utf8');}catch{}py.globals.set('cached',cached);
    const report=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);spec=c['specification'];actual=json.loads(cached) if cached else helpers['compute'](spec);checks=helpers['verify'](spec,actual)
a,b=helpers['physical'](actual),helpers['physical'](c['result']);error=float(np.max(abs(a-b)/np.maximum(1.,abs(b))));assert error<2e-7,(spec['name'],error)
assert actual['plane']['valid']==c['result']['plane']['valid']
json.dumps(dict(name=spec['name'],physical_values_compared=a.size,maximum_scaled_native_difference=error,**checks))
`));if(!cached)await writeFile(cache+'/'+name+'.json',await py.runPythonAsync('json.dumps(actual,allow_nan=False)'));cases.push(report);console.log('Packaged WASM shoulder check passed:',JSON.stringify(report));}
  if(cases.length!==8)throw new Error('Incomplete study.');await writeFile('docs/validation/body-shoulders-wasm.json',JSON.stringify({study_sha256:hash(bytes),runtime_sha256,source_sha256:{...study.source_sha256,'scripts/test-body-shoulders-wasm.mjs':hash(await readFile('scripts/test-body-shoulders-wasm.mjs'))},cases},null,2)+'\n');await new Promise(r=>process.stdout.write('All packaged WASM shoulder checks passed.\n',r));process.exit(0);
}catch(e){await new Promise(r=>process.stderr.write(String(e)+'\n',r));process.exit(1);}
