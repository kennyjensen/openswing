import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=data=>createHash('sha256').update(data).digest('hex');
try{
  const bytes=await readFile('docs/validation/initial-response.json'),study=JSON.parse(bytes);
  for(const [file,wanted] of Object.entries(study.source_sha256))if(hash(await readFile(file))!==wanted)throw new Error('Study source changed: '+file);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8'))){
    const data=await readFile(`dist/kernel/${name}`);if(!data.equals(await readFile(`openswing/${name}`)))throw new Error('Stale packaged module: '+name);
    py.FS.writeFile(`/home/pyodide/openswing/${name}`,data);
  }
  py.FS.writeFile('/home/pyodide/scripts/verify-initial-response.py',await readFile('scripts/verify-initial-response.py'));
  await py.runPythonAsync(`import json, runpy, numpy as np
from openswing.bridge import dispatch
verify=runpy.run_path('/home/pyodide/scripts/verify-initial-response.py')['verify']`);
  const cases=[];
  for(const c of study.cases){
    py.globals.set('case_json',JSON.stringify(c));
    const result=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);actual=dispatch(c['request']);checks=verify(c,actual)
a,b=np.array(checks.pop('physical_values')),np.array(c['checks']['physical_values'])
assert a.shape==b.shape and np.all(np.isfinite(a))
difference=float(np.max(abs(a-b)/np.maximum(1.,abs(b)),initial=0.))
assert difference<1e-7,(c['name'],difference)
assert actual['converged']==c['result']['converged']
for x,y in zip(actual['samples'],c['result']['samples']):
    assert x['resolved_inputs']==y['resolved_inputs']
    assert [r['converged'] for r in x['responses']]==[r['converged'] for r in y['responses']]
assert actual['diagnostics']['initial_conditions']['finite_dimension']==c['result']['diagnostics']['initial_conditions']['finite_dimension']
consistency=max(channel['consistency']['dynamic_coordinate_mismatch'] for channel in actual['inputs'] if channel['kind']=='initial')
json.dumps(dict(name=c['name'],physical_values_compared=len(a),maximum_scaled_native_difference=difference,maximum_initial_coordinate_mismatch=consistency,checks=checks))
`));cases.push(result);console.log('Packaged WASM initial-response check passed:',JSON.stringify(result));
  }
  if(cases.length!==9)throw new Error('Incomplete initial-response study.');
  const record={description:'Packaged WASM one-sided initial-state spectra: all independent ODE, controller, unit, mesh and circulation checks, with selected physical-output and availability comparisons.',study_sha256:hash(bytes),source_sha256:{...study.source_sha256,'scripts/test-initial-response-wasm.mjs':hash(await readFile('scripts/test-initial-response-wasm.mjs'))},cases};
  await writeFile('docs/validation/initial-response-wasm.json',JSON.stringify(record,null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('All packaged WASM initial-response checks passed.\n',resolve));process.exit(0);
}catch(error){await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
