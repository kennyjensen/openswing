import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=x=>createHash('sha256').update(x).digest('hex');
try{
  const bytes=await readFile('docs/validation/aero-lag.json'),study=JSON.parse(bytes);
  for(const [name,digest] of Object.entries(study.source_sha256))if(hash(await readFile(name))!==digest)throw new Error('Study source changed: '+name);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  const modules=JSON.parse(await readFile('dist/kernel/manifest.json','utf8'));
  for(const name of modules){const b=await readFile('dist/kernel/'+name);if(!b.equals(await readFile('openswing/'+name)))throw new Error('Stale packaged module: '+name);py.FS.writeFile('/home/pyodide/openswing/'+name,b);}
  for(const name of ['verify-aero-lag.py','modal-benchmark.py'])py.FS.writeFile('/home/pyodide/scripts/'+name,await readFile('scripts/'+name));
  await py.runPythonAsync("import runpy,json,numpy as np\nhelpers=runpy.run_path('/home/pyodide/scripts/verify-aero-lag.py')");
  const cases=[];
  for(const [index,c] of study.cases.entries()){
    py.globals.set('case_json',JSON.stringify(c));
    const result=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);actual=helpers['compute'](c['specification'])
a,b=helpers['physical'](actual),helpers['physical'](c['result'])
assert a.shape==b.shape,(c['name'],a.shape,b.shape)
if actual['kind']=='modes':
    # Repeated/clustered poles have no portable ordering. Match the physical
    # complex values without changing or dropping any member of the spectrum.
    av=np.array(actual['poles']);bv=np.array(c['result']['poles'])
    rows,cols=helpers['linear_sum_assignment'](np.linalg.norm(av[:,None,:]-bv[None,:,:],axis=2))
    a=av[rows[np.argsort(cols)]].ravel()
difference=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
assert difference<2e-8,(c['name'],difference)
json.dumps(dict(actual=actual,physical_values_compared=a.size,maximum_scaled_native_difference=difference))
`));
    cases.push({native_case:index,name:c.name,...result});console.log('Aerodynamic lag WASM',c.name,result.maximum_scaled_native_difference);
  }
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async n=>[n,hash(await readFile('dist/runtime/'+n))])));
  await writeFile('docs/validation/aero-lag-wasm.json',JSON.stringify({study_sha256:hash(bytes),module_count:modules.length,runtime_sha256,
    source_sha256:{...study.source_sha256,'scripts/test-aero-lag-wasm.mjs':hash(await readFile('scripts/test-aero-lag-wasm.mjs'))},cases},null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('Aerodynamic-lag WASM study passed.\n',resolve));process.exit(0);
}catch(e){await new Promise(resolve=>process.stderr.write(String(e)+'\n',resolve));process.exit(1);}
