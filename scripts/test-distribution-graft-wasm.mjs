import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=x=>createHash('sha256').update(x).digest('hex');
try{
 const bytes=await readFile('docs/validation/distribution-graft.json'),study=JSON.parse(bytes);
 for(const [file,digest] of Object.entries(study.source_sha256))if(hash(await readFile(file))!==digest)throw new Error('Study source changed: '+file);
 const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
 py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
 const modules=JSON.parse(await readFile('dist/kernel/manifest.json','utf8'));
 for(const name of modules){const data=await readFile('dist/kernel/'+name);if(!data.equals(await readFile('openswing/'+name)))throw new Error('Stale packaged module: '+name);py.FS.writeFile('/home/pyodide/openswing/'+name,data);}
 py.FS.writeFile('/home/pyodide/scripts/verify-distribution-graft.py',await readFile('scripts/verify-distribution-graft.py'));
 await py.runPythonAsync("import runpy,json,numpy as np\nhelpers=runpy.run_path('/home/pyodide/scripts/verify-distribution-graft.py')");
 const cases=[];
 for(const c of study.cases){
  py.globals.set('case_json',JSON.stringify(c));
  const report=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);spec=c['specification'];actual=helpers['compute'](spec);checks=helpers['verify'](spec,actual)
a,b=helpers['physical'](actual),helpers['physical'](c['result']);assert a.shape==b.shape
difference=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
assert difference<2e-7,(spec['name'],difference)
if 'poles' in actual:
    roots=[complex(*z) for z in actual['poles']];reference=[complex(*z) for z in c['result']['poles']]
    pole_difference=max(min(abs(a-b) for a in roots)/max(1,abs(b)) for b in reference)
    assert len(roots)==len(reference) and pole_difference<2e-7
else: pole_difference=None
json.dumps(dict(name=spec['name'],physical_values_compared=a.size,maximum_scaled_native_difference=difference,maximum_relative_pole_difference=pole_difference,**checks))
`));cases.push(report);console.log('Packaged WASM graft passed:',JSON.stringify(report));
 }
 if(cases.length!==5)throw new Error('Incomplete graft study.');
 const errors=cases.slice(2).map(c=>c.relative_displacement_error);
 if(!(errors.at(-1)<errors[0]/8&&errors.at(-1)<2e-5))throw new Error('Variable-stiffness spatial refinement did not converge.');
 const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>[name,hash(await readFile('dist/runtime/'+name))])));
 await writeFile('docs/validation/distribution-graft-wasm.json',JSON.stringify({study_sha256:hash(bytes),module_count:modules.length,runtime_sha256,source_sha256:{...study.source_sha256,'scripts/test-distribution-graft-wasm.mjs':hash(await readFile('scripts/test-distribution-graft-wasm.mjs'))},cases},null,2)+'\n');
 await new Promise(r=>process.stdout.write('All five packaged WASM graft cases passed.\n',r));process.exit(0);
}catch(error){await new Promise(r=>process.stderr.write(String(error)+'\n',r));process.exit(1);}
