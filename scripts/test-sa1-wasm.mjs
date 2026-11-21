import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=x=>createHash('sha256').update(x).digest('hex');
try {
  const bytes=await readFile('docs/validation/sa1.json'),study=JSON.parse(bytes);
  for(const [file,digest] of Object.entries(study.source_sha256))
    if(hash(await readFile(file))!==digest)throw new Error('Study source changed: '+file);
  const source=await readFile('.reference/isae-sa1/SA_1.asw');
  if(hash(source)!==study.provenance.files['SA_1.asw'].sha256)throw new Error('Reference source changed');
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});
  await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  const modules=JSON.parse(await readFile('dist/kernel/manifest.json','utf8'));
  for(const name of modules){
    const data=await readFile('dist/kernel/'+name);
    if(!data.equals(await readFile('openswing/'+name)))throw new Error('Stale packaged module: '+name);
    py.FS.writeFile('/home/pyodide/openswing/'+name,data);
  }
  py.FS.writeFile('/home/pyodide/scripts/verify-sa1.py',await readFile('scripts/verify-sa1.py'));
  py.globals.set('source',source.toString('utf8'));
  await py.runPythonAsync("import runpy,json,numpy as np\nhelpers=runpy.run_path('/home/pyodide/scripts/verify-sa1.py')");
  // Both PG choices, all five mesh levels at the last archived incidence,
  // zero incidence, measured CL/CD angles, and negative post-stall symmetry.
  const selected=new Set();
  study.cases.forEach((c,i)=>{
    const s=c.specification;
    if(s.name.includes('/ASWING/')&&s.alpha_deg===18.091)selected.add(i);
    if(s.name.includes('/symmetry/')&&[0,-18.091].includes(s.alpha_deg))selected.add(i);
  });
  for(const mode of Object.values(study.comparisons))
    for(const coefficient of ['CL','CD'])selected.add(mode.experiment_case_indices[coefficient].at(-1));
  if(selected.size!==18)throw new Error('SA-1 replay selection changed: '+selected.size);
  const cases=[];
  for(const index of selected){
    py.globals.set('case_json',JSON.stringify(study.cases[index]));
    const report=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);actual=helpers['compute'](source,c['specification'])
a,b=helpers['physical'](actual),helpers['physical'](c['result'])
assert a.shape==b.shape
difference=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
assert difference<2e-7,(c['specification'],difference)
json.dumps(dict(name=c['specification']['name'],actual=actual,
    physical_values_compared=a.size,maximum_scaled_native_difference=difference))
`));
    cases.push({native_case:index,...report});
    console.log('SA-1 packaged WASM:',report.name,'difference',report.maximum_scaled_native_difference);
  }
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>[name,hash(await readFile('dist/runtime/'+name))])));
  await writeFile('docs/validation/sa1-wasm.json',JSON.stringify({study_sha256:hash(bytes),module_count:modules.length,runtime_sha256,
    source_sha256:{...study.source_sha256,'scripts/test-sa1-wasm.mjs':hash(await readFile('scripts/test-sa1-wasm.mjs'))},cases},null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('SA-1 packaged replay passed; physical/reference discrepancies remain.\n',resolve));
  process.exit(0);
} catch(error){
  await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);
}
