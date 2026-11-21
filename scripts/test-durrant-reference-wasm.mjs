import {loadPyodide} from 'pyodide';
import {readFile,writeFile,rename} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=b=>createHash('sha256').update(b).digest('hex');
const output='docs/validation/durrant-reference-wasm.json';
let record;
const save=async()=>{await writeFile(output+'.part',JSON.stringify(record,null,2)+'\n');await rename(output+'.part',output);};
try {
  const raw=await readFile('docs/validation/durrant-reference-wasm-input.json');
  const input=JSON.parse(raw);
  if(input.cases.length!==2)throw new Error('Expected two pinned independent reference meshes.');
  const verify=async()=>{for(const [file,wanted] of Object.entries(input.sources_sha256))if(hash(await readFile(file))!==wanted)throw new Error('Changed source '+file);};
  await verify();
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});
  await py.loadPackage(['numpy','scipy']);
  for(const dir of ['scripts','docs/validation'])py.FS.mkdirTree('/home/pyodide/'+dir);
  for(const file of Object.keys(input.sources_sha256))py.FS.writeFile('/home/pyodide/'+file,await readFile(file));
  await py.runPythonAsync(`
import sys,json,platform,numpy as np,scipy
from scipy.optimize import linear_sum_assignment
sys.path.insert(0,'/home/pyodide/scripts')
import durrant_unloaded_reference as reference
assert not any(name=='openswing' or name.startswith('openswing.') for name in sys.modules)
def unpack(a):return np.asarray(a['real'])+1j*np.asarray(a['imag'])
def roots(a):return np.asarray([complex(*v) for v in a])
def match(a,b):
    assert len(a)==len(b)>0
    rows,cols=linear_sum_assignment(abs(a[:,None]-b[None,:]))
    error=abs(a[rows]-b[cols])/np.maximum(1.,np.maximum(abs(a[rows]),abs(b[cols])))
    assert np.max(error)<2e-7,float(np.max(error))
    return rows,cols,error
`);
  record={status:'running',started:Date.now()/1000,scope:input.scope,input_sha256:hash(raw),
    source_sha256:input.sources_sha256,verifier_sha256:hash(await readFile('scripts/test-durrant-reference-wasm.mjs')),
    runtime_lock_sha256:hash(await readFile('dist/runtime/pyodide-lock.json')),
    versions:JSON.parse(await py.runPythonAsync("json.dumps(dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__))")),
    cases:[],production_kernel_loaded:false,
    limitations:['Checks the complete independent spectrum; the separate production search does not classify its full finite spectrum.',
      'Unloaded diagnostic analogue only; no experimental or loaded-flutter validation.']};
  await save();
  for(const item of input.cases){
    await verify();py.globals.set('item_json',JSON.stringify(item));
    const result=JSON.parse(await py.runPythonAsync(`
item=json.loads(item_json);s=item['spec'];wanted=item['reference']
actual=reference.solve(s['wing'],s['speed_m_s'],elements=s['mechanical_elements'],panels=s['aero_panels'],density=s['density_kg_m3'],lag=s['aero_lag'],retain=s['retained_modes'],shapes=True,sampling=s['sampling'],eigensystem_scaling=s.get('eigensystem_scaling','energy_convective'))
for key in ['wing','speed_m_s','sampling','sampling_options','requested_elements','actual_elements','requested_panels','actual_panels','retained_mechanical_modes','density_kg_m3','lag','computed_dimension','span_m']:assert wanted[key]==actual[key],key
assert wanted['eigensystem']['scaling']==actual['eigensystem']['scaling']=='energy_convective'
a,b=roots(wanted['roots_per_s']),roots(actual['roots_per_s']);rows,cols,error=match(a,b)
assert np.array_equal(np.sign(a[rows].real),np.sign(b[cols].real))
assert actual['maximum_backward_error']<1e-9
for key in ['maximum_scaled_right_backward_error','maximum_scaled_left_backward_error']:assert actual['eigensystem'][key]<1e-9
ia=[i for i,f in enumerate(wanted['positive_frequencies_Hz']) if .1<f<40]
ib=[i for i,f in enumerate(actual['positive_frequencies_Hz']) if .1<f<40]
rr,cc,low_error=match(roots([wanted['positive_roots_per_s'][i] for i in ia]),roots([actual['positive_roots_per_s'][i] for i in ib]))
assurance=[]
for i,j in zip(rr,cc):
    va,vb=unpack(wanted['positive_shapes'][ia[i]]).ravel(),unpack(actual['positive_shapes'][ib[j]]).ravel()
    mac=float(abs(np.vdot(va,vb))**2/(np.vdot(va,va).real*np.vdot(vb,vb).real));assert mac>1-1e-7,mac
    assurance.append(mac)
assert not any(name=='openswing' or name.startswith('openswing.') for name in sys.modules)
json.dumps(dict(id=item['id'],spec=s,native_record_sha256=item['native_record_sha256'],computed_roots=len(a),maximum_scaled_root_difference=float(max(error)),maximum_low_root_difference=float(max(low_error)),low_frequency_modal_assurance=assurance,actual=actual),allow_nan=False)
`));
    record.cases.push(result);await save();console.log('Independent WASM reference passed',result.id,result.computed_roots,result.maximum_scaled_root_difference);
  }
  await verify();record.status='passed';record.ended=Date.now()/1000;await save();process.exit(0);
}catch(error){if(record){record.status='failed';record.error=String(error.stack||error);record.ended=Date.now()/1000;await save();}console.error(error);process.exit(1);}
