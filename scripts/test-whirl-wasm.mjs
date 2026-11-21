import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=x=>createHash('sha256').update(x).digest('hex');
try{
  const bytes=await readFile('docs/validation/whirl.json'),study=JSON.parse(bytes);
  for(const [file,digest] of Object.entries(study.source_sha256))if(hash(await readFile(file))!==digest)throw new Error('Study source changed: '+file);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  const modules=JSON.parse(await readFile('dist/kernel/manifest.json','utf8'));
  for(const name of modules){const data=await readFile('dist/kernel/'+name);if(!data.equals(await readFile('openswing/'+name)))throw new Error('Stale packaged module: '+name);py.FS.writeFile('/home/pyodide/openswing/'+name,data);}
  py.FS.writeFile('/home/pyodide/scripts/verify-whirl.py',await readFile('scripts/verify-whirl.py'));
  await py.runPythonAsync("import runpy,json,numpy as np\nhelpers=runpy.run_path('/home/pyodide/scripts/verify-whirl.py')");
  const cases=[];
  for(const c of study.cases){
    py.globals.set('case_json',JSON.stringify(c));
    const report=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);spec=c['specification'];actual=helpers['compute'](spec);checks=helpers['verify'](spec,actual)
a,b=helpers['physical'](actual),helpers['physical'](c['result']);assert a.shape==b.shape
# Conjugate roots can differ in |imaginary part| by roundoff after a rotated
# constraint reduction. Match each four-root spectrum instead of relying on
# identical sorting of those nearly tied magnitudes across platforms.
raw_difference=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
for start in ([1,10] if 'stability' in actual else [0]):
    av=a[start:start+8].reshape(4,2).copy();bv=b[start:start+8].reshape(4,2).copy()
    i,j=helpers['linear_sum_assignment'](np.linalg.norm(av[:,None,:]-bv[None,:,:],axis=2))
    a[start:start+8]=av[i].ravel();b[start:start+8]=bv[j].ravel()
difference=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
assert difference<5e-6,(spec['name'],difference)
json.dumps(dict(name=spec['name'],physical_values_compared=a.size,maximum_scaled_native_difference=difference,unmatched_scaled_native_difference=raw_difference,**checks))
`));cases.push(report);console.log('Packaged WASM whirl passed:',JSON.stringify(report));
  }
  if(cases.length!==11)throw new Error('Incomplete whirl study.');
  const errors=cases.slice(0,3).map(c=>c.continuum_root_relative_error);
  if(!(errors[1]<.27*errors[0]&&errors[2]<.27*errors[1]))throw new Error('Rotor-mount spatial refinement did not converge.');
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>[name,hash(await readFile('dist/runtime/'+name))])));
  await writeFile('docs/validation/whirl-wasm.json',JSON.stringify({study_sha256:hash(bytes),module_count:modules.length,runtime_sha256,source_sha256:{...study.source_sha256,'scripts/test-whirl-wasm.mjs':hash(await readFile('scripts/test-whirl-wasm.mjs'))},cases},null,2)+'\n');
  await new Promise(r=>process.stdout.write('All packaged WASM whirl checks passed.\n',r));process.exit(0);
}catch(error){await new Promise(r=>process.stderr.write(String(error)+'\n',r));process.exit(1);}
