import {loadPyodide} from 'pyodide';
import {readFile, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
try {
  const bytes = await readFile('docs/validation/durrant-low-speed.json');
  const study = JSON.parse(bytes);
  if (study.cases.length !== 20) throw new Error('Complete the native study first.');
  for (const [file, wanted] of Object.entries(study.source_sha256)) {
    if (hash(await readFile(file)) !== wanted) throw new Error('Study source changed: '+file);
  }
  const py = await loadPyodide({indexURL: path.resolve('dist/runtime')});
  await py.loadPackage(['numpy', 'scipy']);
  for (const dir of ['openswing', 'scripts', 'docs/validation']) py.FS.mkdirTree('/home/pyodide/'+dir);
  const packaged = {};
  for (const file of JSON.parse(await readFile('dist/kernel/manifest.json', 'utf8'))) {
    const data = await readFile('dist/kernel/'+file);
    if (!data.equals(await readFile('openswing/'+file))) throw new Error('Stale packaged kernel: '+file);
    packaged[file] = hash(data);
    py.FS.writeFile('/home/pyodide/openswing/'+file, data);
  }
  for (const file of ['scripts/verify-durrant-low-speed.py', 'scripts/verify-durrant-structure.py',
                      'docs/validation/durrant-reference.json', 'docs/validation/durrant-low-speed-reference.json']) {
    py.FS.writeFile('/home/pyodide/'+file, await readFile(file));
  }
  await py.runPythonAsync("import runpy\nstudy_module=runpy.run_path('/home/pyodide/scripts/verify-durrant-low-speed.py')");
  const selected = study.cases.filter(c => c.spec.panels === 8 || c.spec.speed_m_s === .001 || c.spec.time_unit_s);
  if (selected.length !== 6) throw new Error('Expected six low-speed/unit portability cases.');
  const cases = [];
  for (const c of selected) {
    py.globals.set('native_json', JSON.stringify(c));
    const actual = JSON.parse(await py.runPythonAsync(`
import json,numpy as np
native=json.loads(native_json)
actual=study_module['compute'](native['spec'])
assert actual['source']==native['source']
assert actual['actual_elements']==native['actual_elements']
assert actual['finite_dimension'] is None
roots=np.array(actual['roots_per_s']);wanted=np.array(native['roots_per_s'])
error=float(np.max(abs(roots-wanted)/np.maximum(1.,abs(wanted))))
assert error<2e-7
np.testing.assert_allclose(actual['circulation_per_mechanical_amplitude'],native['circulation_per_mechanical_amplitude'],rtol=2e-7,atol=1e-10)
macs=[]
for a,b in zip(actual['shapes'],native['shapes']):
    va=(np.array(a['real'])+1j*np.array(a['imag'])).ravel()
    vb=(np.array(b['real'])+1j*np.array(b['imag'])).ravel()
    mac=float(abs(np.vdot(va,vb))**2/np.vdot(va,va).real/np.vdot(vb,vb).real)
    assert mac>1-1e-9
    macs.append(mac)
actual['maximum_scaled_native_root_difference']=error
actual['native_modal_assurance']=macs
json.dumps(actual,allow_nan=False)
`));
    cases.push(actual);
    console.log('WASM low-speed check', actual.spec, actual.maximum_scaled_native_root_difference);
  }
  const result = {description: 'Positive low-airspeed modal portability; no exact-stagnation or experimental validation claim.',
    study_sha256: hash(bytes), source_sha256: study.source_sha256, packaged_kernel_sha256: packaged,
    verifier_sha256: hash(await readFile('scripts/test-durrant-low-speed-wasm.mjs')),
    runtime_lock_sha256: hash(await readFile('dist/runtime/pyodide-lock.json')), cases};
  await writeFile('docs/validation/durrant-low-speed-wasm.json', JSON.stringify(result, null, 2)+'\n');
  process.exit(0);
} catch (error) {console.error(error); process.exit(1);}
