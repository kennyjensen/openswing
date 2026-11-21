// Exercise the shipped source-box operator against the native SA-6 evidence.
import {loadPyodide} from 'pyodide';
import {readFile, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const directory = process.argv[2] ?? 'artifacts/isae/apparent-inertia-box-20261029';
const hash = data => createHash('sha256').update(data).digest('hex');
const input = await readFile(path.join(directory, 'sa6/comparison.json'));
const study = JSON.parse(input);
for (const pin of study.code_pins) {
  if (hash(await readFile(pin.path)) !== pin.sha256) throw new Error(`Native evidence code changed: ${pin.path}`);
}
const py = await loadPyodide({indexURL: path.resolve('dist/runtime')});
await py.loadPackage(['numpy', 'scipy']);
py.FS.mkdirTree('/home/pyodide/openswing');
const modules = JSON.parse(await readFile('dist/kernel/manifest.json', 'utf8'));
for (const name of modules) {
  const data = await readFile(`dist/kernel/${name}`);
  if (!data.equals(await readFile(`openswing/${name}`))) throw new Error(`Stale packaged module: ${name}`);
  py.FS.writeFile(`/home/pyodide/openswing/${name}`, data);
}
py.globals.set('study_json', input.toString());
const result = JSON.parse(await py.runPythonAsync(`
import json
import numpy as np
from openswing.apparent_box import rigid_acceleration_response, endpoint_acceleration_wrench
from openswing.source_quiescent import source_apparent_wrench
assert source_apparent_wrench is endpoint_acceleration_wrench
study = json.loads(study_json)
results = []
for name, case in study['calculations'].items():
    actual = np.zeros((6, 6))
    for sample in case['samples']:
        values = [np.array(sample[k]) for k in (
            'r0', 'r1', 'frame0', 'frame1', 'chord0', 'chord1', 'xax0', 'xax1', 'length')]
        actual += rigid_acceleration_response(*values, case['density'], np.zeros(3)).sum(axis=0)
    expected = np.array(case['box_matrix'])
    error = float(np.max(abs(actual-expected))/max(1., float(np.max(abs(expected)))))
    assert error < 2e-13, (name, error)
    results.append(dict(case=name, intervals=case['actual_intervals'], maximum_scaled_native_difference=error))
assert len(results) == 8
json.dumps(dict(status='PASSED', cases=results, comparisons=8*36, nonlinear_solves=0))
`));
result.native_evidence_sha256 = hash(input);
result.modules_checked = modules.length;
result.script_sha256 = hash(await readFile('scripts/test-apparent-box-wasm.mjs'));
await writeFile(path.join(directory, 'wasm.json'), JSON.stringify(result, null, 2)+'\n');
console.log(JSON.stringify(result, null, 2));
