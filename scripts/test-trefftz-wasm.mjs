import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=data=>createHash('sha256').update(data).digest('hex');
try{
  const bytes=await readFile('docs/validation/trefftz.json'),study=JSON.parse(bytes);
  for(const [file,wanted] of Object.entries(study.source_sha256))if(hash(await readFile(file))!==wanted)throw new Error('Study source changed: '+file);
  const source=await readFile('.reference/fw.asw');
  if(hash(source)!==study.reference.aircraft.sha256)throw new Error('Fetch the pinned official flying-wing input first.');
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8'))){
    const data=await readFile(`dist/kernel/${name}`);
    if(!data.equals(await readFile(`openswing/${name}`)))throw new Error('Stale packaged module: '+name);
    py.FS.writeFile(`/home/pyodide/openswing/${name}`,data);
  }
  py.FS.writeFile('/home/pyodide/scripts/verify-trefftz.py',await readFile('scripts/verify-trefftz.py'));
  py.globals.set('source',source.toString());py.globals.set('analytic_json',JSON.stringify(study.analytical));
  const analytic=JSON.parse(await py.runPythonAsync(`
import json, runpy, numpy as np
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.operating import OperatingConstraint
from openswing.linear_dynamics import make_system, linearize, eigensystem
actual=runpy.run_path('/home/pyodide/scripts/verify-trefftz.py')['analytical']()
expected=json.loads(analytic_json)
maximum=0.
for a,b in zip(actual['cases'],expected['cases']):
    for key in a['result']:
        error=abs(a['result'][key]-b['result'][key])/max(1.,abs(b['result'][key]))
        maximum=max(maximum,error)
for a,b in zip(actual['ground_center_cases'],expected['ground_center_cases']):
    maximum=max(maximum,abs(a['center_downwash']-b['center_downwash']))
assert maximum<1e-10
json.dumps(dict(fourier_cases=len(actual['cases']),ground_cases=len(actual['ground_center_cases']),maximum_scaled_native_difference=maximum))
`));
  console.log('Packaged WASM analytical wake checks passed:',JSON.stringify(analytic));
  const cases=[];
  for(const c of study.flying_wing){
    py.globals.set('case_json',JSON.stringify(c));
    const result=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);v=c['base']['operating_values']
condition=FlightCondition(speed=64.,alpha=v['alpha'],controls={2:v['control.2']},attitude=[0.,v['attitude.elevation'],0.])
constraints=[OperatingConstraint('alpha','force.z'),OperatingConstraint('attitude.elevation','force.x'),OperatingConstraint('control.2','moment.y')]
system,_=make_system(parse_asw(source),condition,c['requested_panels'],frame='free',operating_constraints=constraints,initial_state=c['base']['equilibrium_state'])
base=system.base_report()
assert base['modal_base']['continuous_residual']<1e-8 and base['trefftz']['available']
keys=('CL','CD','CDi','CDi_near','CLi','CYi','efficiency','efficiency_near')
maximum=max(abs(base[k]-c['base'][k]) for k in keys)
assert maximum<1e-8
np.testing.assert_allclose(base['trefftz']['velocity_body'],c['base']['trefftz']['velocity_body'],rtol=1e-8,atol=1e-8)
root=None
if c['modal_regression']:
    a,m=linearize(system,step=1e-5)
    modes,meta=eigensystem(a,m,time_scale=system.W,count=4,shift=(-.1,18.),method='full_shift_invert')
    assert meta['finite_dimension'] is None
    selected=[d for d in modes if d['eigenvalue'][0]>-3 and 15<d['eigenvalue'][1]<24]
    assert len(selected)==1
    difference=float(np.linalg.norm(np.array(selected[0]['eigenvalue'])-c['modal_regression']['value_per_s']))
    backward=max(max(d['right_backward_error'],d['left_backward_error']) for d in modes)
    assert difference<1e-6 and backward<1e-9
    root=dict(value_per_s=selected[0]['eigenvalue'],native_difference_per_s=difference,maximum_backward_error=backward)
json.dumps(dict(requested_panels=c['requested_panels'],actual_lifting_panels=base['lifting_panels'],efficiency=base['efficiency'],CDi=base['CDi'],maximum_native_coefficient_difference=maximum,continuous_residual=base['modal_base']['continuous_residual'],modal_regression=root))
`));
    cases.push(result);console.log('Packaged WASM flying-wing wake check passed:',JSON.stringify(result));
  }
  if(cases.length!==4)throw new Error('Expected four flying-wing wake comparisons.');
  const record={description:'Current packaged WASM Trefftz continuum checks, four current flying-wing equilibria and one original-pencil modal regression.',study_sha256:hash(bytes),source_sha256:{...study.source_sha256,'scripts/test-trefftz-wasm.mjs':hash(await readFile('scripts/test-trefftz-wasm.mjs'))},analytical:analytic,flying_wing:cases};
  await writeFile('docs/validation/trefftz-wasm.json',JSON.stringify(record,null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('All packaged WASM Trefftz checks passed.\n',resolve));process.exit(0);
}catch(error){await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
