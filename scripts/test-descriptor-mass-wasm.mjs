import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=data=>createHash('sha256').update(data).digest('hex');
try{
  const bytes=await readFile('docs/validation/descriptor-mass.json'),study=JSON.parse(bytes);
  for(const [file,wanted] of Object.entries(study.source_sha256))if(hash(await readFile(file))!==wanted)throw new Error('Study source changed: '+file);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8'))){
    const data=await readFile(`dist/kernel/${name}`);if(!data.equals(await readFile(`openswing/${name}`)))throw new Error('Stale packaged module: '+name);
    py.FS.writeFile(`/home/pyodide/openswing/${name}`,data);
  }
  py.FS.writeFile('/home/pyodide/scripts/verify-descriptor-mass.py',await readFile('scripts/verify-descriptor-mass.py'));
  await py.runPythonAsync(`import json, runpy, numpy as np
helpers=runpy.run_path('/home/pyodide/scripts/verify-descriptor-mass.py')`);
  const cases=[];
  for(const c of study.cases){
    py.globals.set('case_json',JSON.stringify(c));
    const result=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);expected=c['result'];actual=helpers['compute'](c['specification'],phase_index=expected['initial_mode']['phase_index'])
root_error=helpers['root_error'](expected,actual)
assert root_error<1e-6,root_error
assert expected['finite_dimension']==actual['finite_dimension']
assert expected['mass_rank']==actual['mass_rank']
a,b=np.array(actual['mass']['real']),np.array(expected['mass']['real'])
mass_error=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
assert mass_error<1e-10,mass_error
assert actual['initial_mode']['phase_index']==expected['initial_mode']['phase_index']
def complex_array(value):return np.array(value['real'])+1j*np.array(value['imag'])
mode_error=float(np.max(abs(complex_array(actual['initial_mode']['right'])-complex_array(expected['initial_mode']['right']))))
assert mode_error<1e-8,mode_error
physical=0.;count=0
for first,second in zip(actual['initial_spectra'],expected['initial_spectra']):
    for group,key in [('nodes','displacement'),('nodes','velocity'),('sections','force_local'),('sections','moment_local')]:
        for x,y in zip(first['output'][group],second['output'][group]):
            for part in ('real','imag'):
                a,b=np.array(x[key][part]),np.array(y[key][part]);count+=a.size
                physical=max(physical,float(np.max(abs(a-b)/np.maximum(1.,abs(b)),initial=0.)))
assert physical<1e-7,physical
json.dumps(dict(name=c['specification']['name'],finite_dimension=actual['finite_dimension'],maximum_scaled_native_root_difference=root_error,maximum_scaled_native_mass_difference=mass_error,initial_phase_index=actual['initial_mode']['phase_index'],maximum_native_initial_mode_difference=mode_error,physical_values_compared=count,maximum_scaled_native_physical_difference=physical,maximum_odd_residual_error=actual['maximum_odd_residual_error'],maximum_initial_resolvent_error=actual['maximum_initial_resolvent_error'],largest_discarded_derivative=actual['largest_discarded_derivative']))
`));cases.push(result);console.log('Packaged WASM descriptor-mass check passed:',JSON.stringify(result));
  }
  if(cases.length!==8)throw new Error('Incomplete descriptor-mass study.');
  const record={description:'Current packaged WASM loaded-aircraft mass tangent, full finite spectra and initial spectra, including mesh/step/rank/time-unit and controller comparisons.',study_sha256:hash(bytes),source_sha256:{...study.source_sha256,'scripts/test-descriptor-mass-wasm.mjs':hash(await readFile('scripts/test-descriptor-mass-wasm.mjs'))},cases};
  await writeFile('docs/validation/descriptor-mass-wasm.json',JSON.stringify(record,null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('All packaged WASM descriptor-mass checks passed.\n',resolve));process.exit(0);
}catch(error){await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
