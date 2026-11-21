import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=data=>createHash('sha256').update(data).digest('hex');
try{
  const bytes=await readFile('docs/validation/rom-initial.json'),study=JSON.parse(bytes);
  for(const [file,wanted] of Object.entries(study.source_sha256))if(hash(await readFile(file))!==wanted)throw new Error('Study source changed: '+file);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8'))){const data=await readFile(`dist/kernel/${name}`);if(!data.equals(await readFile(`openswing/${name}`)))throw new Error('Stale packaged module: '+name);py.FS.writeFile(`/home/pyodide/openswing/${name}`,data);}
  py.FS.writeFile('/home/pyodide/scripts/verify-rom-initial.py',await readFile('scripts/verify-rom-initial.py'));
  await py.runPythonAsync(`import runpy,json,numpy as np
from openswing.bridge import dispatch
helpers=runpy.run_path('/home/pyodide/scripts/verify-rom-initial.py')`);
  const cases=[];
  for(const c of study.cases){
    py.globals.set('case_json',JSON.stringify(c));
    const result=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);spec=c['specification'];expected=c['result'];actual=dispatch(spec['request']);checks=helpers['verify'](spec,actual)
assert actual['diagnostics']['dimension']==expected['diagnostics']['dimension']
assert actual['diagnostics']['initial_conditions']['finite_dimension']==expected['diagnostics']['initial_conditions']['finite_dimension']
maximum=0.;state_error=0.;count=0
for first,second in zip(actual['initial_responses'],expected['initial_responses']):
    assert first['converged']==second['converged']
    assert ('spectrum_error' in first)==('spectrum_error' in second)
    for key in ('resolved_state','represented_state','omitted_state'):
        a,b=np.array(first[key]),np.array(second[key]);state_error=max(state_error,float(np.max(abs(a-b)/np.maximum(1.,abs(b)))))
    for key in ('time_samples','samples'):
        assert len(first[key])==len(second[key])
        for x,y in zip(first[key],second[key]):
            assert x['converged']==y['converged']
            if not x['converged']:continue
            for kind in ('full','reduced'):
                for part in (('real','imag') if key=='samples' else (None,)):
                    a,b=np.array(x[kind] if part is None else x[kind][part]),np.array(y[kind] if part is None else y[kind][part]);count+=a.size
                    maximum=max(maximum,float(np.max(abs(a-b)/np.maximum(1.,abs(b)))))
assert maximum<1e-7,maximum
assert state_error<1e-8,state_error
json.dumps(dict(name=spec['name'],real_dimension=actual['diagnostics']['dimension'],finite_dimension=actual['diagnostics']['initial_conditions']['finite_dimension'],physical_values_compared=count,maximum_scaled_native_physical_difference=maximum,maximum_scaled_native_state_difference=state_error,**checks))
`));cases.push(result);console.log('Packaged WASM initial-ROM check passed:',JSON.stringify(result));
  }
  if(cases.length!==8)throw new Error('Incomplete initial-ROM study.');
  await writeFile('docs/validation/rom-initial-wasm.json',JSON.stringify({description:'Current packaged WASM physical initial-state projection, free histories and one-sided spectra; independent ODE references and native physical-output comparisons.',study_sha256:hash(bytes),source_sha256:{...study.source_sha256,'scripts/test-rom-initial-wasm.mjs':hash(await readFile('scripts/test-rom-initial-wasm.mjs'))},cases},null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('All packaged WASM initial-ROM checks passed.\n',resolve));process.exit(0);
}catch(error){await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
