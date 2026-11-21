import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=data=>createHash('sha256').update(data).digest('hex');
try{
  const bytes=await readFile('docs/validation/feedback-derivatives.json'),study=JSON.parse(bytes);
  for(const [file,wanted] of Object.entries(study.source_sha256))if(hash(await readFile(file))!==wanted)throw new Error('Study source changed: '+file);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8'))){
    const data=await readFile(`dist/kernel/${name}`);
    if(!data.equals(await readFile(`openswing/${name}`)))throw new Error('Stale packaged module: '+name);
    py.FS.writeFile(`/home/pyodide/openswing/${name}`,data);
  }
  py.FS.writeFile('/home/pyodide/scripts/verify-feedback-derivatives.py',await readFile('scripts/verify-feedback-derivatives.py'));
  await py.runPythonAsync(`
import json, runpy, numpy as np
from openswing.bridge import dispatch
verify=runpy.run_path('/home/pyodide/scripts/verify-feedback-derivatives.py')['verify']
`);
  const cases=[];
  for(const c of study.cases){
    py.globals.set('case_json',JSON.stringify(c));
    const result=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);actual=dispatch(c['request']);checks=verify(c,actual)
d=actual['derivatives'];expected=c['result']['derivatives']
assert len(d['parameters'])==len(expected['parameters'])
for a,b in zip(d['parameters'],expected['parameters']):
    assert (a['name'],a['unit'],a.get('kind'))==(b['name'],b['unit'],b.get('kind'))
    np.testing.assert_allclose([a[k] for k in ('scale','step','output_step')],[b[k] for k in ('scale','step','output_step')],rtol=1e-7,atol=1e-14)
assert d['feedback_rows']==expected['feedback_rows']
maximum=raw_maximum=0.;wrench_differences={}
parameter_scales=np.array([p['scale'] for p in d['parameters']])
force_scale=d['normalization']['dynamic_pressure_area']
wrench_scales=force_scale*np.r_[np.ones(3),d['normalization']['moment_lengths']]
for name,value in d['matrices'].items():
    a,b=np.asarray(value),np.asarray(expected['matrices'][name])
    assert a.shape==b.shape
    assert np.all(np.isfinite(a)) and np.all(np.isfinite(b))
    difference=abs(a-b)
    raw_maximum=max(raw_maximum,float(np.max(difference/np.maximum(1.,abs(b)),initial=0.)))
    scale=np.maximum(1.,abs(b))
    if name.endswith('_wrench'):
        # Dimensional near-zero moments require a physical reference scale;
        # a tolerance in arbitrary file F*L units is not unit covariant.
        scale=np.maximum(wrench_scales[:,None]/parameter_scales,abs(b))
        wrench_differences[name]=dict(maximum_absolute=float(np.max(difference)),maximum_reference_scaled=float(np.max(difference/scale)))
    maximum=max(maximum,float(np.max(difference/scale,initial=0.)))
assert maximum<1e-6,(c['name'],maximum)
symmetry=None
if c['name'].startswith('wing'):
    symmetry=max(float(np.max(abs(np.asarray(result['matrices']['coefficients'])[[3,5]]))) for result in (d,expected))
    assert symmetry<1e-9
np.testing.assert_allclose(actual['force'],c['result']['force'],rtol=1e-8,atol=1e-7)
json.dumps(dict(name=c['name'],system_size=d['system_size'],base_residual=actual['residual'],maximum_scaled_native_derivative_difference=maximum,maximum_entry_scaled_native_derivative_difference=raw_maximum,wrench_differences=wrench_differences,maximum_symmetric_roll_yaw_coefficient_derivative=symmetry,checks=checks))
`));
    cases.push(result);console.log('Packaged WASM closed-loop derivative check passed:',JSON.stringify(result));
  }
  if(cases.length!==12)throw new Error('Incomplete closed-loop derivative comparison.');
  const record={description:'Packaged WASM closed-loop equilibrium derivatives: all twelve independent and refinement cases, with full physical derivative-matrix comparisons.',comparison_scaling:'Dimensional wrench rows use max(base q*S*[1,1,1,b,c,b]/input scale, abs(native derivative)); other matrices use max(1, abs(native derivative)) in their reported file units. The original per-entry comparison and absolute wrench differences are retained. Symmetric wing roll/yaw coefficient derivatives are checked independently against zero.',study_sha256:hash(bytes),source_sha256:{...study.source_sha256,'scripts/test-feedback-derivatives-wasm.mjs':hash(await readFile('scripts/test-feedback-derivatives-wasm.mjs'))},cases};
  await writeFile('docs/validation/feedback-derivatives-wasm.json',JSON.stringify(record,null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('All packaged WASM closed-loop derivative checks passed.\n',resolve));process.exit(0);
}catch(error){await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
