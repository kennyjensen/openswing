import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=b=>createHash('sha256').update(b).digest('hex');
try{
  const bytes=await readFile('docs/validation/flow-survey.json'),study=JSON.parse(bytes);
  for(const [file,wanted] of Object.entries(study.source_sha256))if(hash(await readFile(file))!==wanted)throw new Error('Study source changed: '+file);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8'))){const data=await readFile('dist/kernel/'+name);if(!data.equals(await readFile('openswing/'+name)))throw new Error('Stale packaged module: '+name);py.FS.writeFile('/home/pyodide/openswing/'+name,data);}
  py.FS.writeFile('/home/pyodide/scripts/verify-flow-survey.py',await readFile('scripts/verify-flow-survey.py'));await py.runPythonAsync("import runpy,json,numpy as np\nfrom copy import deepcopy\nhelpers=runpy.run_path('/home/pyodide/scripts/verify-flow-survey.py')");
  const cases=[];
  for(const c of study.cases){py.globals.set('case_json',JSON.stringify(c));const check=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);before=deepcopy(c['request']);out=helpers['dispatch'](c['request']);assert before==c['request'];checks=helpers['verify'](c,out)
maximum=0.;count=0
for group in ('velocity','plane_velocity'):
    for key,values in out.get(group,{}).items():
        a,b=np.asarray(values),np.asarray(c['result'][group][key]);count+=a.size;maximum=max(maximum,float(np.max(abs(a-b)/np.maximum(1.,abs(b)))))
assert maximum<2e-8,(c['name'],maximum)
for key in ('valid','inside_body','fluid_side'):assert out[key]==c['result'][key],(c['name'],key)
json.dumps(dict(name=c['name'],native_values_compared=count,maximum_scaled_native_difference=maximum,**checks))
`));cases.push(check);console.log('Packaged WASM survey passed:',JSON.stringify(check));}
  if(cases.length!==8)throw new Error('Incomplete survey study.');
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async n=>[n,hash(await readFile('dist/runtime/'+n))])));
  await writeFile('docs/validation/flow-survey-wasm.json',JSON.stringify({study_sha256:hash(bytes),runtime_sha256,source_sha256:{...study.source_sha256,'scripts/test-flow-survey-wasm.mjs':hash(await readFile('scripts/test-flow-survey-wasm.mjs'))},cases},null,2)+'\n');
  await new Promise(r=>process.stdout.write('All packaged WASM flow survey checks passed.\n',r));process.exit(0);
}catch(e){await new Promise(r=>process.stderr.write(String(e)+'\n',r));process.exit(1);}
