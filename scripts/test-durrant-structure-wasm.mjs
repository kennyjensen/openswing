import {loadPyodide} from 'pyodide';
import {readFile, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const hash = data => createHash('sha256').update(data).digest('hex');
try {
  const bytes = await readFile('docs/validation/durrant-structure.json');
  const study = JSON.parse(bytes);
  if (!study.complete_planned_grid) throw new Error('Complete the native study first.');
  for (const [file, wanted] of Object.entries(study.source_sha256)) {
    if (hash(await readFile(file)) !== wanted) throw new Error('Study source changed: '+file);
  }
  const py = await loadPyodide({indexURL: path.resolve('dist/runtime')});
  await py.loadPackage(['numpy', 'scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');
  py.FS.mkdirTree('/home/pyodide/scripts');
  py.FS.mkdirTree('/home/pyodide/docs/validation');
  const packaged = {};
  for (const name of JSON.parse(await readFile('dist/kernel/manifest.json', 'utf8'))) {
    const data = await readFile('dist/kernel/'+name);
    if (!data.equals(await readFile('openswing/'+name))) throw new Error('Stale packaged module: '+name);
    packaged[name] = hash(data);
    py.FS.writeFile('/home/pyodide/openswing/'+name, data);
  }
  for (const file of ['scripts/verify-durrant-structure.py', 'docs/validation/durrant-reference.json']) {
    py.FS.writeFile('/home/pyodide/'+file, await readFile(file));
  }
  await py.runPythonAsync("import runpy\nstudy_module=runpy.run_path('/home/pyodide/scripts/verify-durrant-structure.py')");
  const cases = [];
  for (const c of study.cases.filter(c => Object.keys(c.spec).length === 2 && c.spec.panels <= 16)) {
    py.globals.set('native_json', JSON.stringify(c));
    const actual = JSON.parse(await py.runPythonAsync(`
import json,numpy as np
native=json.loads(native_json)
actual=study_module['compute'](native['spec'])
assert actual['source']==native['source']
assert actual['actual_elements']==native['actual_elements']
assert actual['finite_dimension'] is None
np.testing.assert_allclose(actual['roots_per_s'],native['roots_per_s'],rtol=2e-8,atol=2e-7)
root_error=float(np.max(abs(np.array(actual['roots_per_s'])-native['roots_per_s'])/np.maximum(1,abs(np.array(native['roots_per_s'])))))
assurance=[]
for a,b in zip(actual['shapes'],native['shapes']):
    va=(np.array(a['real'])+1j*np.array(a['imag'])).ravel()
    vb=(np.array(b['real'])+1j*np.array(b['imag'])).ravel()
    mac=float(abs(np.vdot(va,vb))**2/np.vdot(va,va).real/np.vdot(vb,vb).real)
    assert mac>1-1e-10
    assurance.append(mac)
actual['maximum_scaled_native_root_difference']=root_error
actual['native_modal_assurance']=assurance
json.dumps(actual,allow_nan=False)
`));
    cases.push(actual);
    console.log('Packaged WASM structural reconstruction:', actual.spec,
      'maximum scaled root difference', actual.maximum_scaled_native_root_difference);
  }
  if (cases.length !== 4) throw new Error('Expected four native/WASM reconstruction cases.');
  const result = {
    description: 'Portability of reconstructed vacuum structural modes; unresolved thesis setup and experimental differences remain.',
    study_sha256: hash(bytes), source_sha256: study.source_sha256, packaged_kernel_sha256: packaged,
    verifier_sha256: hash(await readFile('scripts/test-durrant-structure-wasm.mjs')),
    runtime_lock_sha256: hash(await readFile('dist/runtime/pyodide-lock.json')),
    cases,
  };
  await writeFile('docs/validation/durrant-structure-wasm.json', JSON.stringify(result, null, 2)+'\n');
  process.exit(0);
} catch (error) {
  console.error(error);
  process.exit(1);
}
