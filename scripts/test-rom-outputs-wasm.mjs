import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=x=>createHash('sha256').update(x).digest('hex');
try{
  const bytes=await readFile('docs/validation/rom-outputs.json'),study=JSON.parse(bytes);
  for(const [name,digest] of Object.entries(study.source_sha256))if(hash(await readFile(name))!==digest)throw Error('Changed study source: '+name);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  for(const folder of ['openswing','scripts','examples'])py.FS.mkdirTree('/home/pyodide/'+folder);
  const modules=JSON.parse(await readFile('dist/kernel/manifest.json'));
  for(const name of modules){const data=await readFile('dist/kernel/'+name);if(!data.equals(await readFile('openswing/'+name)))throw Error('Stale module: '+name);py.FS.writeFile('/home/pyodide/openswing/'+name,data);}
  for(const file of ['scripts/verify-rom-outputs.py','scripts/verify-section-outputs.py','scripts/modal-benchmark.py','examples/instrumented-oscillator.asw'])py.FS.writeFile('/home/pyodide/'+file,await readFile(file));
  await py.runPythonAsync("import json,runpy,numpy as np\nh=runpy.run_path('/home/pyodide/scripts/verify-rom-outputs.py')");
  const cases=[];
  // Cover each physical system, changed units, and the refined coupled mesh.
  const selected=study.cases.filter(c=>(c.spec.kind==='rigid'&&(c.spec.panels===4||c.spec.units))||
    (c.spec.kind==='mechanical'&&c.spec.units)||(c.spec.kind==='coupled'&&!c.spec.step));
  for(const c of selected){
    py.globals.set('case_json',JSON.stringify(c));
    const record=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);result=h['compute'](c['spec'])
def physical(row):
    values=[]
    for key in ['computed','full']:
        for part in ['real','imag']:values.extend(np.asarray(row[key][part]).ravel())
    for item in row.get('initial_computed',{}).values():
        for part in ['real','imag']:values.extend(np.asarray(item[part]).ravel())
    values.extend(row['output_base'])
    return np.asarray(values)
a,b=physical(result),physical(c)
error=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
assert error<2e-8,(c['spec'],error)
assert len(result['matrices']['A'])==len(c['matrices']['A'])
assert bool(result['legacy_export'])==bool(c['legacy_export']),(result['legacy_export_error'],c['legacy_export_error'])
for actual,expected in zip(result['outputs'],c['outputs']):
    assert actual['unit']==expected['unit']
    x,y=actual['selector'].copy(),expected['selector'].copy()
    if 't' in x:assert abs(x.pop('t')-y.pop('t'))<1e-12
    assert x==y
json.dumps(dict(spec=c['spec'],result=result,physical_values_compared=len(a),maximum_scaled_native_difference=error),allow_nan=False)
`));
    cases.push(record);console.log('Physical ROM outputs WASM',JSON.stringify(record.spec),record.maximum_scaled_native_difference);
  }
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>[name,hash(await readFile('dist/runtime/'+name))])));
  await writeFile('docs/validation/rom-outputs-wasm.json',JSON.stringify({study_sha256:hash(bytes),module_count:modules.length,runtime_sha256,
    source_sha256:{...study.source_sha256,'scripts/test-rom-outputs-wasm.mjs':hash(await readFile('scripts/test-rom-outputs-wasm.mjs'))},cases},null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('Physical ROM outputs packaged replay passed.\n',resolve));process.exit(0);
}catch(error){await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
