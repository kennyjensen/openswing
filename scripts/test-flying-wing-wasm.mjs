import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=data=>createHash('sha256').update(data).digest('hex');
try {
  const bytes=await readFile('docs/validation/flying-wing.json'),study=JSON.parse(bytes);
  for(const [file,wanted] of Object.entries(study.source_sha256))if(hash(await readFile(file))!==wanted)throw new Error('Study source changed: '+file);
  const source=await readFile('.reference/fw.asw');
  if(hash(source)!==study.reference.aircraft.sha256)throw new Error('Fetch the pinned official flying-wing input first.');
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');
  for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8'))){
    const data=await readFile(`dist/kernel/${name}`);
    if(!data.equals(await readFile(`openswing/${name}`)))throw new Error('Stale packaged module: '+name);
    py.FS.writeFile(`/home/pyodide/openswing/${name}`,data);
  }
  py.globals.set('source',source.toString());
  const results=[];
  for(const c of study.cases.filter(c=>c.difference_step===1e-5&&((c.speed_ft_s===64&&c.requested_panels<=16)||(c.speed_ft_s===62&&c.requested_panels===16)))){
    py.globals.set('case_json',JSON.stringify(c));
    const result=JSON.parse(await py.runPythonAsync(`
import json,numpy as np
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.operating import OperatingConstraint
from openswing.linear_dynamics import make_system,linearize,eigensystem
c=json.loads(case_json)
constraints=[OperatingConstraint('alpha','force.z'),OperatingConstraint('attitude.elevation','force.x'),OperatingConstraint('control.2','moment.y')]
condition=FlightCondition(speed=c['speed_ft_s'],alpha=c['trim']['alpha_deg'],controls={2:c['trim']['control_2_deg']},attitude=[0,c['trim']['elevation_deg'],0])
system,_=make_system(parse_asw(source),condition,c['requested_panels'],frame='free',operating_constraints=constraints,initial_state=c['base']['equilibrium_state'])
base=system.base_report()
assert base['modal_base']['continuous_residual']<1e-8
for key in ('CL','CD','efficiency'):np.testing.assert_allclose(base[key],c['base'][key],rtol=1e-8,atol=1e-9)
a,m=linearize(system,step=c['difference_step'])
modes,meta=eigensystem(a,m,time_scale=system.W,count=4,shift=(-.1,18),method='full_shift_invert')
assert meta['finite_dimension'] is None and meta['rank_tolerance'] is None
found=[d for d in modes if d['eigenvalue'][0]>-3 and 15<d['eigenvalue'][1]<24]
assert len(found)==1
value=found[0]['eigenvalue'];error=float(np.linalg.norm(np.array(value)-c['bff_root_per_s']))
assert error<1e-5
maximum=0.
for mode in modes:
    lam=complex(*mode['eigenvalue']);v,w=mode['right'],mode['left']
    norm=np.linalg.norm(a)+abs(lam)*np.linalg.norm(m)
    er=np.linalg.norm(a@v-lam*m@v)/(norm*np.linalg.norm(v))
    el=np.linalg.norm(w.conj()@a-lam*(w.conj()@m))/(norm*np.linalg.norm(w))
    maximum=max(maximum,float(er),float(el),mode['right_backward_error'],mode['left_backward_error'])
assert maximum<1e-9
json.dumps(dict(requested_panels=c['requested_panels'],speed_ft_s=c['speed_ft_s'],bff_root_per_s=value,native_difference_per_s=error,maximum_original_pencil_backward_error=maximum,base_residual=base['modal_base']['continuous_residual']))
`));
    results.push(result);console.log('Packaged WASM flying-wing check passed:',JSON.stringify(result));
  }
  if(results.length!==3)throw new Error('Expected three published-case portability checks.');
  const record={description:'Packaged WASM portability of three published flying-wing comparison points; physical discrepancies remain in the native study.',study_sha256:hash(bytes),source_sha256:{...study.source_sha256,'scripts/test-flying-wing-wasm.mjs':hash(await readFile('scripts/test-flying-wing-wasm.mjs'))},cases:results};
  await writeFile('docs/validation/flying-wing-wasm.json',JSON.stringify(record,null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('All three packaged WASM flying-wing cases passed.\n',resolve));process.exit(0);
} catch(error){await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
