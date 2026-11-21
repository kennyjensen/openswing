import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=x=>createHash('sha256').update(x).digest('hex');
try {
  const bytes=await readFile('docs/validation/sa2.json'),study=JSON.parse(bytes);
  for(const [file,digest] of Object.entries(study.source_sha256))
    if(hash(await readFile(file))!==digest)throw new Error('Study source changed: '+file);
  const source=await readFile('.reference/isae-sa2/SA_2.asw');
  if(hash(source)!==study.provenance.files['SA_2.asw'].sha256)throw new Error('Reference source changed');
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});
  await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  const modules=JSON.parse(await readFile('dist/kernel/manifest.json','utf8'));
  for(const name of modules){
    const data=await readFile('dist/kernel/'+name);
    if(!data.equals(await readFile('openswing/'+name)))throw new Error('Stale packaged module: '+name);
    py.FS.writeFile('/home/pyodide/openswing/'+name,data);
  }
  py.FS.writeFile('/home/pyodide/scripts/verify-sa2.py',await readFile('scripts/verify-sa2.py'));
  py.globals.set('source',source.toString('utf8'));
  await py.runPythonAsync("import runpy,json,numpy as np\nhelpers=runpy.run_path('/home/pyodide/scripts/verify-sa2.py')");
  // All mesh levels at the highest incidence, all K/F and PG combinations,
  // the analytical zero-lift limit, mirrored incidence and pressure similarity.
  const selected=[];
  study.cases.forEach((c,i)=>{
    const s=c.specification;
    if((s.name.includes('/polar/')&&s.alpha_deg===10.5)||
       (s.name.includes('/symmetry/')&&[0,-10.5].includes(s.alpha_deg))||
       s.name.endsWith('/similarity/scaled'))selected.push(i);
  });
  if(selected.length!==30)throw new Error('SA-2 replay selection changed: '+selected.length);
  const cases=[];
  for(const index of selected){
    py.globals.set('case_json',JSON.stringify(study.cases[index]));
    const report=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);record=helpers['outcome'](source,c['specification'])
assert record['status']==c['status'],(c['specification'],record)
if record['status']=='rejected':
    assert record['error']==c['error']
    report=dict(name=c['specification']['name'],**record,physical_values_compared=0)
else:
    a,b=helpers['physical'](record['result']),helpers['physical'](c['result'])
    assert a.shape==b.shape
    difference=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
    assert difference<2e-7,(c['specification'],difference)
    report=dict(name=c['specification']['name'],**record,
        physical_values_compared=a.size,maximum_scaled_native_difference=difference)
json.dumps(report)
`));
    cases.push({native_case:index,...report});
    console.log('SA-2 packaged WASM:',report.name,report.status,report.maximum_scaled_native_difference??report.error);
  }
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>[name,hash(await readFile('dist/runtime/'+name))])));
  await writeFile('docs/validation/sa2-wasm.json',JSON.stringify({study_sha256:hash(bytes),module_count:modules.length,runtime_sha256,
    source_sha256:{...study.source_sha256,'scripts/test-sa2-wasm.mjs':hash(await readFile('scripts/test-sa2-wasm.mjs'))},cases},null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('SA-2 packaged replay passed; source and physical discrepancies remain.\n',resolve));
  process.exit(0);
} catch(error){
  await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);
}
