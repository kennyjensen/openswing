import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=data=>createHash('sha256').update(data).digest('hex');
try{
  const bytes=await readFile('docs/validation/discretization.json'),study=JSON.parse(bytes);
  for(const [file,wanted] of Object.entries(study.source_sha256))if(hash(await readFile(file))!==wanted)throw new Error('Study source changed: '+file);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8'))){
    const data=await readFile(`dist/kernel/${name}`);if(!data.equals(await readFile(`openswing/${name}`)))throw new Error('Stale packaged module: '+name);
    py.FS.writeFile(`/home/pyodide/openswing/${name}`,data);
  }
  py.FS.writeFile('/home/pyodide/scripts/verify-discretization.py',await readFile('scripts/verify-discretization.py'));
  await py.runPythonAsync(`import json, runpy, numpy as np
from openswing.bridge import dispatch
verify=runpy.run_path('/home/pyodide/scripts/verify-discretization.py')['verify']`);
  const cases=[];
  for(const c of study.cases){
    py.globals.set('case_json',JSON.stringify(c));
    const result=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);actual=dispatch(c['request']);checks=verify(c,actual)
a,b=np.array(checks.pop('physical_values')),np.array(c['checks']['physical_values'])
assert a.shape==b.shape and np.all(np.isfinite(a))
difference=float(np.max(abs(a-b)/np.maximum(1.,abs(b)),initial=0.))
assert difference<1e-7,(c['name'],difference)
base=actual.get('base',actual.get('snapshots',[actual])[0])
expected=c['result'].get('base',c['result'].get('snapshots',[c['result']])[0])
mesh,other=base['mesh_discretization'],expected['mesh_discretization']
assert mesh['settings']==other['settings']
for left,right in zip(mesh['beams'],other['beams']):
    assert left['beam']==right['beam'] and left['panels']==right['panels'] and len(left['nodes'])==len(right['nodes'])
    for x,y in zip(left['nodes'],right['nodes']):
        assert x['required']==y['required']
        np.testing.assert_allclose([x[k] for k in ('t','s','fraction','theta')],[y[k] for k in ('t','s','fraction','theta')],rtol=1e-13,atol=1e-14)
json.dumps(dict(name=c['name'],physical_values_compared=len(a),maximum_scaled_native_difference=difference,checks=checks))
`));cases.push(result);console.log('Packaged WASM material-mesh check passed:',JSON.stringify(result));
  }
  if(cases.length!==18)throw new Error('Incomplete material-mesh study.');
  const record={description:'Packaged WASM material-mesh checks, including direct import of native steady and BDF checkpoint states. Independent continuum/oscillator checks plus physical-state, load, harmonic and spectral comparisons.',study_sha256:hash(bytes),source_sha256:{...study.source_sha256,'scripts/test-discretization-wasm.mjs':hash(await readFile('scripts/test-discretization-wasm.mjs'))},cases};
  await writeFile('docs/validation/discretization-wasm.json',JSON.stringify(record,null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('All packaged WASM material-mesh checks passed.\n',resolve));process.exit(0);
}catch(error){await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
