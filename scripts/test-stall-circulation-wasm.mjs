import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=x=>createHash('sha256').update(x).digest('hex');
try {
  const bytes=await readFile('docs/validation/stall-circulation.json'),study=JSON.parse(bytes);
  for(const [file,digest] of Object.entries(study.source_sha256))
    if(hash(await readFile(file))!==digest)throw new Error('Study source changed: '+file);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});
  await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  const modules=JSON.parse(await readFile('dist/kernel/manifest.json','utf8'));
  for(const name of modules){
    const data=await readFile('dist/kernel/'+name);
    if(!data.equals(await readFile('openswing/'+name)))throw new Error('Stale packaged module: '+name);
    py.FS.writeFile('/home/pyodide/openswing/'+name,data);
  }
  py.FS.writeFile('/home/pyodide/scripts/verify-stall-circulation.py',await readFile('scripts/verify-stall-circulation.py'));
  py.globals.set('source',await readFile('examples/stall-branch.asw','utf8'));
  await py.runPythonAsync("import runpy,json,numpy as np\nhelpers=runpy.run_path('/home/pyodide/scripts/verify-stall-circulation.py')");
  const cases=[];
  for(const [index,c] of study.cases.entries()){
    py.globals.set('case_json',JSON.stringify(c));
    const result=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);actual=helpers['compute'](source,c['specification'])
a,b=helpers['physical_values'](actual),helpers['physical_values'](c['result'])
assert a.shape==b.shape
difference=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
assert difference<2e-9,(c['specification'],difference)
json.dumps(dict(actual=actual,physical_values_compared=a.size,maximum_scaled_native_difference=difference))
`));
    cases.push({native_case:index,specification:c.specification,...result});
    console.log('Packaged stall circulation:',index,c.specification.alpha,'difference',result.maximum_scaled_native_difference);
  }
  const diagnostics=[];
  for(const c of study.finite_wing_diagnostics){
    py.globals.set('case_json',JSON.stringify(c));
    const actual=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json)
try:
    r=helpers['compute'](source,c['specification'])
    result=dict(status='solved',result=r)
except helpers['AnalysisError'] as error:
    result=dict(status='unresolved',error=str(error))
assert result['status']==c['status'],(c['specification'],result['status'],c['status'])
if result['status']=='solved':
    a,b=helpers['physical_values'](r),helpers['physical_values'](c['result'])
    difference=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
    assert difference<2e-9,(c['specification'],difference)
    result['maximum_scaled_native_difference']=difference
else:
    assert 'no full physical solution' in result['error']
json.dumps(result)
`));
    diagnostics.push({specification:c.specification,...actual});
    console.log('Finite-wing diagnostic',c.specification.alpha,actual.status);
  }
  for(const c of cases.filter(c=>c.specification.span===59000)){
    py.globals.set('alpha',c.specification.alpha);
    const reference=JSON.parse(await py.runPythonAsync("json.dumps(helpers['two_dimensional'](alpha))"));
    for(const key of ['CL','CD'])if(Math.abs(c.actual.coefficients[key]-reference[key])>=1e-4)throw new Error('2D limit failed');
  }
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>[name,hash(await readFile('dist/runtime/'+name))])));
  await writeFile('docs/validation/stall-circulation-wasm.json',JSON.stringify({study_sha256:hash(bytes),module_count:modules.length,runtime_sha256,
    source_sha256:{...study.source_sha256,'scripts/test-stall-circulation-wasm.mjs':hash(await readFile('scripts/test-stall-circulation-wasm.mjs'))},cases,diagnostics},null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('Packaged stall circulation study passed.\n',resolve));process.exit(0);
}catch(error){await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
