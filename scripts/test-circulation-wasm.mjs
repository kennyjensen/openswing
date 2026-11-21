import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=data=>createHash('sha256').update(data).digest('hex');
try{
  const bytes=await readFile('docs/validation/circulation.json'),study=JSON.parse(bytes);
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
  py.FS.writeFile('/home/pyodide/scripts/verify-circulation.py',await readFile('scripts/verify-circulation.py'));
  py.globals.set('source',source.toString());py.globals.set('study_json',JSON.stringify(study));
  py.globals.set('rectangular_source',await readFile('examples/rectangular.asw','utf8'));
  py.globals.set('heave_source',await readFile('examples/heave-pitch.asw','utf8'));
  const analytic=JSON.parse(await py.runPythonAsync(`
import json, runpy, numpy as np
from scipy.optimize import linear_sum_assignment
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.operating import OperatingConstraint
from openswing.linear_dynamics import make_system
helpers=runpy.run_path('/home/pyodide/scripts/verify-circulation.py')
study=json.loads(study_json)
maximum=0.
for group,src in [(study['analytical']['cases'],study['analytical']['source']),(study['rectangular'],rectangular_source)]:
    for expected in group:
        actual=helpers['rigid_case'](src,expected['panels'],expected['modes'],alpha=expected['alpha'])
        for key in ('CL','CD','CDi','CDi_near','efficiency','residual'):
            maximum=max(maximum,abs(actual['result'][key]-expected['result'][key]))
        np.testing.assert_allclose(actual['result']['circulation_discretization']['coefficients'],expected['result']['circulation_discretization']['coefficients'],rtol=1e-9,atol=1e-9)
assert maximum<1e-9
json.dumps(dict(elliptic_cases=len(study['analytical']['cases']),rectangular_cases=len(study['rectangular']),maximum_native_coefficient_difference=maximum))
`));
  console.log('Packaged WASM Fourier steady checks passed:',JSON.stringify(analytic));
  const modes=[];
  for(const c of study.coupled_modes){
    py.globals.set('case_json',JSON.stringify(c));
    const result=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);actual=helpers['modal_case'](heave_source,c['modes'])
assert actual['finite_dimension']==c['finite_dimension']
roots=np.array([complex(*z) for z in actual['roots']]);expected=np.array([complex(*z) for z in c['roots']])
assert roots.shape==expected.shape
cost=abs(roots[:,None]-expected[None,:]);rows,cols=linear_sum_assignment(cost)
maximum=float(np.max(cost[rows,cols]))
assert maximum<1e-6
json.dumps(dict(panels=c['panels'],modes=c['modes'],finite_dimension=actual['finite_dimension'],roots=actual['roots'],maximum_native_root_difference_per_s=maximum,maximum_original_pencil_backward_error=actual['maximum_original_pencil_backward_error']))
`));
    modes.push(result);console.log('Packaged WASM Fourier modes passed:',JSON.stringify(result));
  }
  const cases=[];
  for(const c of study.flying_wing){
    py.globals.set('case_json',JSON.stringify(c));
    const result=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);v=c['base']['operating_values']
condition=FlightCondition(speed=64.,alpha=v['alpha'],controls={2:v['control.2']},attitude=[0.,v['attitude.elevation'],0.],circulation_modes={1:c['modes']})
constraints=[OperatingConstraint('alpha','force.z'),OperatingConstraint('attitude.elevation','force.x'),OperatingConstraint('control.2','moment.y')]
system,_=make_system(parse_asw(source),condition,c['panels'],frame='free',operating_constraints=constraints,initial_state=c['base']['equilibrium_state'])
base=system.base_report()
assert base['modal_base']['continuous_residual']<1e-8 and base['trefftz']['available']
keys=('CL','CD','CDi','CDi_near','CLi','CYi','efficiency','efficiency_near')
maximum=max(abs(base[k]-c['base'][k]) for k in keys)
assert maximum<1e-8
np.testing.assert_allclose(base['circulation_discretization']['coefficients'],c['base']['circulation_discretization']['coefficients'],rtol=1e-8,atol=1e-8)
np.testing.assert_allclose(base['circulation_local_residual'],c['base']['circulation_local_residual'],rtol=1e-8,atol=1e-8)
json.dumps(dict(panels=c['panels'],modes=c['modes'],actual_lifting_panels=base['lifting_panels'],circulation_unknowns=system.network.ng,efficiency=base['efficiency'],CDi=base['CDi'],maximum_native_coefficient_difference=maximum,continuous_residual=base['modal_base']['continuous_residual']))
`));
    cases.push(result);console.log('Packaged WASM flying-wing Fourier check passed:',JSON.stringify(result));
  }
  if(cases.length!==6||modes.length!==3)throw new Error('Incomplete Fourier comparison.');
  const record={description:'Current packaged WASM Fourier circulation: independent elliptic continuum and mode refinement, three coupled spectra, six flying-wing equilibria restored from native physical states.',study_sha256:hash(bytes),source_sha256:{...study.source_sha256,'scripts/test-circulation-wasm.mjs':hash(await readFile('scripts/test-circulation-wasm.mjs'))},analytical:analytic,coupled_modes:modes,flying_wing:cases};
  await writeFile('docs/validation/circulation-wasm.json',JSON.stringify(record,null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('All packaged WASM Fourier circulation checks passed.\n',resolve));process.exit(0);
}catch(error){await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
