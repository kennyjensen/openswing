import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=x=>createHash('sha256').update(x).digest('hex');
try{
  const bytes=await readFile('docs/validation/legacy-gust.json'),study=JSON.parse(bytes);
  for(const [name,digest] of Object.entries(study.source_sha256))if(hash(await readFile(name))!==digest)throw new Error('Study source changed: '+name);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  const modules=JSON.parse(await readFile('dist/kernel/manifest.json','utf8'));
  for(const name of modules){const b=await readFile('dist/kernel/'+name);if(!b.equals(await readFile('openswing/'+name)))throw new Error('Stale packaged module: '+name);py.FS.writeFile('/home/pyodide/openswing/'+name,b);}
  py.FS.writeFile('/home/pyodide/scripts/verify-legacy-gust.py',await readFile('scripts/verify-legacy-gust.py'));
  py.globals.set('source',await readFile('examples/gust-probe.asw','utf8'));
  await py.runPythonAsync("import runpy,json,numpy as np\nhelpers=runpy.run_path('/home/pyodide/scripts/verify-legacy-gust.py')");
  const original_inputs=[];
  for(const [name,spec] of Object.entries(study.provenance.files)){
    const b=await readFile('.reference/legacy-gust/'+name);if(hash(b)!==spec.sha256)throw new Error('Reference changed: '+name);
    py.globals.set('original',b.toString('utf8'));
    const imported=JSON.parse(await py.runPythonAsync("json.dumps(helpers['import_gust'](original))"));
    const expected=JSON.parse(await py.runPythonAsync('json.dumps(helpers["import_gust"](helpers["export_legacy_gust"](helpers["import_gust"](original)["gust"])["text"])["gust"])'));
    if(JSON.stringify(imported.gust)!==JSON.stringify(expected))throw new Error('Original gust round trip changed field');
    original_inputs.push({name,sha256:hash(b),imported});
  }
  const cases=[];
  for(const [index,c] of study.cases.entries()){
    py.globals.set('case_json',JSON.stringify(c));
    const result=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);actual=helpers['compute'](source,c['text'],c['specification'])
a,b=helpers['physical'](actual),helpers['physical'](c['result'])
assert a.shape==b.shape,(c['name'],a.shape,b.shape)
difference=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
assert difference<2e-9,(c['name'],difference)
json.dumps(dict(actual=actual,physical_values_compared=a.size,maximum_scaled_native_difference=difference))
`));
    cases.push({native_case:index,name:c.name,...result});console.log('Legacy gust WASM',c.name,result.maximum_scaled_native_difference);
  }
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async n=>[n,hash(await readFile('dist/runtime/'+n))])));
  await writeFile('docs/validation/legacy-gust-wasm.json',JSON.stringify({study_sha256:hash(bytes),module_count:modules.length,runtime_sha256,
    source_sha256:{...study.source_sha256,'scripts/test-legacy-gust-wasm.mjs':hash(await readFile('scripts/test-legacy-gust-wasm.mjs'))},original_inputs,cases},null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('Legacy gust WASM study passed.\n',resolve));process.exit(0);
}catch(e){await new Promise(resolve=>process.stderr.write(String(e)+'\n',resolve));process.exit(1);}
