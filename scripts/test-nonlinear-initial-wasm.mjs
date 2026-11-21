import {loadPyodide} from 'pyodide';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=data=>createHash('sha256').update(data).digest('hex');
try{
  const bytes=await readFile('docs/validation/nonlinear-initial.json'),study=JSON.parse(bytes);
  for(const [file,wanted] of Object.entries(study.source_sha256))if(hash(await readFile(file))!==wanted)throw new Error('Study source changed: '+file);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8'))){const data=await readFile(`dist/kernel/${name}`);if(!data.equals(await readFile(`openswing/${name}`)))throw new Error('Stale packaged module: '+name);py.FS.writeFile(`/home/pyodide/openswing/${name}`,data);}
  py.FS.writeFile('/home/pyodide/scripts/verify-nonlinear-initial.py',await readFile('scripts/verify-nonlinear-initial.py'));
  await py.runPythonAsync("import runpy,json,numpy as np\nhelpers=runpy.run_path('/home/pyodide/scripts/verify-nonlinear-initial.py')");
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>[name,hash(await readFile('dist/runtime/'+name))])));
  const cache='.reference/nonlinear-initial-wasm/'+hash(JSON.stringify({study:hash(bytes),runner:hash(await readFile('scripts/test-nonlinear-initial-wasm.mjs')),runtime_sha256}));await mkdir(cache,{recursive:true});
  const cases=[];
  for(const c of study.cases){
    py.globals.set('case_json',JSON.stringify(c));
    let cached='';try{cached=await readFile(cache+'/'+c.specification.name+'.json','utf8');}catch{}
    py.globals.set('cached_result',cached);
    py.globals.set('verification_progress',(stage,index,total)=>{if(stage==='initializing'&&(index===1||index===total))console.log(c.specification.name,'initializing',index+'/'+total);});
    const result=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);spec=c['specification'];expected=c['result'];actual=json.loads(cached_result) if cached_result else helpers['compute'](spec,verification_progress);checks=helpers['verify'](spec,actual)
maximum=0.;count=0
for key in ('trajectory','refined','restarted'):
    first,second=actual[key]['snapshots'],expected[key]['snapshots'];assert len(first)==len(second)
    for a,b in zip(first,second):
        assert a['time']==b['time'] and a['order']==b['order']
        x,y=helpers['physical'](spec,a),helpers['physical'](spec,b);count+=x.size
        maximum=max(maximum,float(np.max(abs(x-y)/np.maximum(1.,abs(y)))))
assert maximum<2e-7,(spec['name'],maximum)
report=actual['trajectory']['initialization']['consistency']
assert report['prescribed_coordinate_error']==0
json.dumps(dict(name=spec['name'],physical_values_compared=count,maximum_scaled_native_physical_difference=maximum,initial_consistency=report,**checks))
`));if(!cached)await writeFile(cache+'/'+c.specification.name+'.json',await py.runPythonAsync('json.dumps(actual,allow_nan=False)'));cases.push(result);console.log('Packaged WASM nonlinear initialization passed:',JSON.stringify(result));
  }
  if(cases.length!==6)throw new Error('Incomplete nonlinear-initial study.');
  await writeFile('docs/validation/nonlinear-initial-wasm.json',JSON.stringify({description:'Current packaged WASM nonlinear initial-state completion, independent mechanics references, temporal refinement and checkpoint checks.',study_sha256:hash(bytes),runtime_sha256,source_sha256:{...study.source_sha256,'scripts/test-nonlinear-initial-wasm.mjs':hash(await readFile('scripts/test-nonlinear-initial-wasm.mjs'))},cases},null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('All packaged WASM nonlinear-initial checks passed.\n',resolve));process.exit(0);
}catch(error){await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
