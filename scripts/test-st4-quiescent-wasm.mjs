/** Compare the exact quiescent kernel against source-pinned native primary cases.
 * Usage: node scripts/test-st4-quiescent-wasm.mjs <work-directory> [--kernel <repository>]
 * Each invocation creates a new report directory; previous reports are preserved.
 */
import {readFile, readdir, writeFile, mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const repository = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const arguments_ = process.argv.slice(2);
if (!arguments_[0] || (arguments_.length !== 1 && !(arguments_.length === 3 && arguments_[1] === '--kernel'))) {
  throw Error('Usage: test-st4-quiescent-wasm.mjs <work-directory> [--kernel <repository>]');
}
const work = path.resolve(arguments_[0]);
const kernel = arguments_.length === 3 ? path.resolve(arguments_[2]) : repository;
const nativeDirectory = path.join(work, 'quiescent-primary');
const outputParent = path.join(work, 'quiescent-runtime');
await mkdir(outputParent, {recursive: true});
const runId = new Date().toISOString().replaceAll(':', '-').replaceAll('.', '-') + '-' + process.pid;
const output = path.join(outputParent, runId);
await mkdir(output);
const reportPath = path.join(output, 'report.json');
const scriptHash = sha(await readFile(fileURLToPath(import.meta.url)));
const modules = {};
let inputHash;
let pyodideVersion;
const writeJSON = (file, value) => writeFile(file, JSON.stringify(value, null, 2) + '\n');
const sameModules = (a, b) => {
  const names = Object.keys(a).sort();
  return JSON.stringify(names) === JSON.stringify(Object.keys(b).sort()) && names.every(name => a[name] === b[name]);
};
const readPinned = async (file, digest) => {
  const bytes = await readFile(file);
  if (digest && sha(bytes) !== digest) throw Error('Changed pinned artifact: ' + file);
  return bytes;
};

try {
  for (const name of (await readdir(path.join(kernel, 'openswing'))).filter(name => name.endsWith('.py')).sort()) {
    modules[name] = sha(await readFile(path.join(kernel, 'openswing', name)));
  }
  if (Object.keys(modules).length !== 98) throw Error('Expected the exact 98-module quiescent kernel.');
  const manifestPath = path.join(nativeDirectory, 'primary-quiescent.json');
  const manifestBytes = await readFile(manifestPath);
  const nativeManifest = JSON.parse(manifestBytes);
  if (!sameModules(nativeManifest.candidate_modules, modules)) throw Error('Kernel differs from the native quiescent candidate.');
  const selections = [['unloaded', null, 'lower', 8], ['7a', 11, 'lower', 16], ['7f', 48, 'upper', 16]];
  const requests = [];
  for (const [variant, position, endpoint, panels] of selections) {
    const entry = nativeManifest.runs.find(row => {
      const spec = row.specification;
      return spec.variant === variant && spec.position_in === position && spec.icc_endpoint === endpoint && spec.panels === panels;
    });
    if (!entry) throw Error('Missing native quiescent case: ' + JSON.stringify([variant, position, endpoint, panels]));
    // Cache paths were recorded on the producing host. Resolve filenames under
    // the supplied work directory so the complete evidence bundle is portable.
    const cachePath = path.join(nativeDirectory, path.basename(entry.output));
    const saved = JSON.parse(await readPinned(cachePath, entry.sha256));
    if (saved.status !== 'computed' || saved.errors.length) throw Error('Native case rejected or failed controls: ' + cachePath);
    if (!sameModules(saved.candidate_modules, modules)) throw Error('Mixed kernel inside native case: ' + cachePath);
    const sourcePath = path.join(nativeDirectory, path.basename(saved.source_path));
    const source = (await readPinned(sourcePath, saved.source_sha256)).toString();
    const matrixPath = path.join(nativeDirectory, path.basename(saved.matrices.path));
    await readPinned(matrixPath, saved.matrices.sha256);
    requests.push({...saved, source, native_cache_path: cachePath, native_cache_sha256: entry.sha256,
      native_matrix_path: matrixPath, wasm_matrix_path: '/home/pyodide/native-cache/' + path.basename(matrixPath)});
  }
  const inputs = {kernel, modules, requests, native_manifest: {path: manifestPath, sha256: sha(manifestBytes)},
    script_sha256: scriptHash, full_physical_validation: false};
  const inputPath = path.join(output, 'inputs.json');
  await writeJSON(inputPath, inputs);
  inputHash = sha(await readFile(inputPath));
  const {loadPyodide} = await import(pathToFileURL(path.join(repository, 'node_modules/pyodide/pyodide.mjs')).href);
  const py = await loadPyodide({indexURL: path.join(repository, 'public/runtime')});
  pyodideVersion = py.version;
  await py.loadPackage(['numpy', 'scipy']);
  const put = (file, bytes) => {py.FS.mkdirTree(path.posix.dirname(file)); py.FS.writeFile(file, bytes);};
  for (const name of Object.keys(modules)) put('/home/pyodide/openswing/' + name, await readPinned(path.join(kernel, 'openswing', name), modules[name]));
  for (const saved of requests) put(saved.wasm_matrix_path, await readPinned(saved.native_matrix_path, saved.matrices.sha256));
  py.FS.mkdirTree('/home/pyodide/quiescent-runtime');
  py.globals.set('requests_json', JSON.stringify(requests));
  const result = JSON.parse(await py.runPythonAsync(`
import json, time, traceback, numpy as np
from openswing.bridge import dispatch

def compare_metadata(actual, expected, location):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys(), location
        for key in expected: compare_metadata(actual[key], expected[key], location+'.'+key)
    elif isinstance(expected, list):
        assert len(actual) == len(expected), location
        for i, (a, b) in enumerate(zip(actual, expected)): compare_metadata(a, b, location+'.'+str(i))
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=1e-12, err_msg=location)
    else:
        assert actual == expected, (location, actual, expected)

def complex_array(value):
    return np.asarray(value['real']) + 1j*np.asarray(value['imag'])

rows=[]
for saved in json.loads(requests_json):
    spec=saved['specification']; settings=saved['settings']; g=settings['gravity']; rho=settings['quiescent_density']
    start=time.perf_counter()
    row=dict(specification=spec, cache_sha256=saved['native_cache_sha256'], source_sha256=saved['source_sha256'])
    try:
        result=dispatch(dict(action='modes',source=saved['source'],panels=spec['panels'],gravity=g,
            condition=dict(speed=0.,density=rho), modes=dict(vacuum=False,quiescent_density=rho,frame='fixed',count=12,
            shift=settings['shift'],method='dense',step=settings['difference_step'],rank_tolerance=settings['rank_tolerance'],matrices=True)))
        pencil=np.load(saved['wasm_matrix_path']); checks={}; matrices={}
        for name in ['A','M']:
            actual=np.asarray(result['matrices'][name]); expected=pencil[name]
            assert actual.shape==expected.shape and np.isfinite(actual).all(), name
            scale=np.maximum(1.,np.max(abs(expected),axis=1))[:,None]
            delta=float(np.max(abs(actual-expected)/scale))
            assert delta<2e-8, (name,delta)
            checks[name]=dict(row_scaled_max_difference=delta,max_abs_difference=float(np.max(abs(actual-expected))),shape=list(actual.shape))
            matrices[name]=actual
        air=sorted([m for m in result['modes'] if m['eigenvalue'][1]>0],key=lambda m:m['frequency'])
        native=sorted([m for m in saved['result']['modes'] if m['eigenvalue'][1]>0],key=lambda m:m['frequency'])
        assert len(air)==len(native)==6
        frequency_difference=max(abs(a['frequency']-b['frequency']) for a,b in zip(air,native))
        pole_difference=max(abs(complex(*a['eigenvalue'])-complex(*b['eigenvalue'])) for a,b in zip(air,native))
        assert frequency_difference<2e-6 and pole_difference<2e-5, (frequency_difference,pole_difference)
        assert result['converged'] and not result['vacuum'] and result['frame_mode']=='fixed'
        compare_metadata(result['fluid'],saved['result']['fluid'],'fluid')
        compare_metadata(result['base']['fluid'],result['fluid'],'base.fluid')
        compare_metadata(result['base']['mass_properties'],saved['result']['base']['mass_properties'],'real_mass_properties')
        assert result['fluid']['kind']=='quiescent' and result['fluid']['density']==rho
        assert result['fluid']['wind_direction'] is None and result['fluid']['circulatory'] is False
        assert 'CL' not in result['base'] and 'strips' not in result['base']
        np.testing.assert_array_equal(result['fluid']['mean_velocity_body'],[0.,0.,0.])
        np.testing.assert_array_equal(result['base']['modal_base']['velocity_origin_body'],[0.,0.,0.])
        np.testing.assert_allclose(result['base']['gravity_body'],g,atol=1e-14,rtol=0)
        assert result['diagnostics']['finite_dimension']==saved['result']['diagnostics']['finite_dimension']
        assert result['diagnostics']['state_layout']['circulation']['width']==0
        assert result['base']['equilibrium_state']['identity']['quiescent_density']==rho
        assert result['base']['equilibrium_state']['launch']['quiescent_density']==rho
        reported=max(max(m['left_backward_error'],m['right_backward_error']) for m in result['modes'])
        assert reported<1e-9 and result['diagnostics']['base_residual']<1e-8
        a,m=matrices['A'],matrices['M']; an,mn=np.linalg.norm(a),np.linalg.norm(m); recomputed=[]
        for mode in result['modes']:
            lam=complex(*mode['eigenvalue']); right,left=complex_array(mode['right']),complex_array(mode['left']); scale=an+abs(lam)*mn
            recomputed.append([float(np.linalg.norm(a@right-lam*(m@right))/(scale*np.linalg.norm(right))),
                float(np.linalg.norm(left.conj()@a-lam*(left.conj()@m))/(scale*np.linalg.norm(left)))])
        assert np.max(recomputed)<1e-9
        filename=spec['variant']+'-'+str(spec['position_in'])+'-'+spec['icc_endpoint']+'-p'+str(spec['panels'])+'.npz'
        matrix_path='/home/pyodide/quiescent-runtime/'+filename
        np.savez_compressed(matrix_path,**matrices)
        result.pop('matrices')
        row.update(status='PASS',matrix_differences=checks,frequency_max_difference_Hz=frequency_difference,
            positive_pole_max_abs_difference=pole_difference,reported_backward_error_max=reported,
            recomputed_right_pencil_error_max=float(np.max(np.array(recomputed)[:,0])),
            recomputed_left_pencil_error_max=float(np.max(np.array(recomputed)[:,1])),
            metadata_checks='fluid, real mass, gravity, zero base velocity, no circulation or CL, density identity/launch',
            wasm_matrix_path=matrix_path,matrix_filename=filename,result=result)
    except Exception as exc:
        row.update(status='FAIL',error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc())
    row['seconds']=time.perf_counter()-start
    rows.append(row)
    print('QUIESCENT_WASM',spec,row['seconds'],row['status'],flush=True)
json.dumps(dict(status='PASS_ST4_QUIESCENT_WASM' if all(r['status']=='PASS' for r in rows) else 'FAIL_ST4_QUIESCENT_WASM',
    rows=rows,full_physical_validation=False,scope='Exact candidate98 native/WASM parity for three conditional primary still-air cases; no experimental or ASWING parity claim.'))
`));
  for (const row of result.rows) {
    if (!row.wasm_matrix_path) continue;
    const bytes = py.FS.readFile(row.wasm_matrix_path);
    const file = path.join(output, row.matrix_filename);
    await writeFile(file, bytes);
    row.matrices = {path: file, sha256: sha(bytes)};
    delete row.wasm_matrix_path;
  }
  Object.assign(result, {kernel, modules, script_sha256: scriptHash, runtime_inputs_sha256: inputHash, pyodide: pyodideVersion,
    native_manifest_sha256: sha(manifestBytes), thresholds: {matrix_row_scaled: 2e-8, frequency_Hz: 2e-6, positive_complex_pole: 2e-5, backward_error: 1e-9}});
  await writeJSON(reportPath, result);
  console.log(result.status, reportPath);
  if (result.status !== 'PASS_ST4_QUIESCENT_WASM') process.exitCode = 1;
} catch (error) {
  await writeJSON(reportPath, {status: 'FAIL_ST4_QUIESCENT_WASM_SETUP', kernel, modules, script_sha256: scriptHash,
    runtime_inputs_sha256: inputHash, pyodide: pyodideVersion, error: String(error), stack: error.stack, full_physical_validation: false});
  console.error(error);
  console.error('Failure report:', reportPath);
  process.exitCode = 1;
}
