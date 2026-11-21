import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
try{
  const bytes=await readFile('docs/validation/weber-lifting-line.json'),study=JSON.parse(bytes);
  for(const [name,wanted] of Object.entries(study.source_sha256))
    if(hash(await readFile(name))!==wanted)throw Error('Study source changed: '+name);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});
  await py.loadPackage(['numpy','scipy']);
  for(const directory of ['openswing','scripts','docs/validation'])py.FS.mkdirTree('/home/pyodide/'+directory);
  const modules=JSON.parse(await readFile('dist/kernel/manifest.json','utf8'));
  for(const name of modules){
    const bytes=await readFile('dist/kernel/'+name);
    if(!bytes.equals(await readFile('openswing/'+name)))throw Error('Stale packaged kernel: '+name);
    py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
  }
  for(const name of ['scripts/verify-weber-lifting-line.py','docs/validation/weber-planform.json'])
    py.FS.writeFile('/home/pyodide/'+name,await readFile(name));
  py.globals.set('source',await readFile('examples/weber-tabulated.asw','utf8'));
  await py.runPythonAsync("import runpy,json,numpy as np\nhelpers=runpy.run_path('/home/pyodide/scripts/verify-weber-lifting-line.py')");
  const geometry=JSON.parse(await py.runPythonAsync("json.dumps([helpers['geometry_check'](source,n) for n in [24,512]])"));
  const independent=JSON.parse(await py.runPythonAsync("json.dumps(helpers['independent_case'](source,24,False))"));
  const chosen=study.cases.map((c,i)=>({c,i})).filter(({c})=>[24,512].includes(c.specification.panels)&&[2.1,10.5].includes(c.specification.alpha_deg));
  if(chosen.length!==16)throw Error('Replay selection changed');
  const cases=[];
  for(const {c,i} of chosen){
    py.globals.set('case_json',JSON.stringify(c));
    const result=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);out=helpers['compute'](source,c['specification'])
assert out['status']==c['status'],out
if out['status']=='computed':
    a,b=helpers['physical'](out['result']),helpers['physical'](c['result'])
    assert a.shape==b.shape
    error=float(np.max(abs(a-b)/np.maximum(1,abs(b))))
    assert error<2e-7,error
    out.update(physical_values_compared=int(a.size),maximum_scaled_native_difference=error)
else:
    assert out['details']['kind']==c['details']['kind']=='section_normal_mach'
    assert out['details']['maximum']['beam']==c['details']['maximum']['beam']
    def diagnostic(d):
        p=d['maximum'];return np.r_[p['t'],p['position'],p['relative_velocity'],p['normal_speed'],p['normal_mach'],d['sound_speed']]
    a,b=diagnostic(out['details']),diagnostic(c['details'])
    error=float(np.max(abs(a-b)/np.maximum(1,abs(b))))
    assert error<2e-7,error
    out.update(rejection_values_compared=int(a.size),maximum_scaled_native_difference=error)
json.dumps(out)
`));
    cases.push({native_case:i,specification:c.specification,...result});
    console.log('Weber packaged replay:',c.specification.mode,c.specification.panels,c.specification.alpha_deg,result.status,result.maximum_scaled_native_difference);
  }
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>[name,hash(await readFile('dist/runtime/'+name))])));
  await writeFile('docs/validation/weber-lifting-line-wasm.json',JSON.stringify({study_sha256:hash(bytes),module_count:modules.length,runtime_sha256,
    source_sha256:{...study.source_sha256,'scripts/test-weber-lifting-line-wasm.mjs':hash(await readFile('scripts/test-weber-lifting-line-wasm.mjs'))},geometry,independent,cases},null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('Weber packaged replay passed; physical/reference limitations remain.\n',resolve));process.exit(0);
}catch(error){await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
