// Public JSON API replay against the retained native flutter boundary.
import {loadPyodide} from 'pyodide';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import assert from 'node:assert/strict';

const [bundlePath, output] = process.argv.slice(2);
assert(bundlePath && output, 'Usage: node scripts/test-loaded-flutter-wasm.mjs BUNDLE NEW_OUTPUT_DIR');
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
await mkdir(output, {recursive: false});
const bytes = await readFile(bundlePath), bundle = JSON.parse(bytes);
const status = {status: 'RUNNING', bundle_sha256: hash(bytes), cases: [], modules: bundle.modules};
const save = () => writeFile(path.join(output, 'status.json'), JSON.stringify(status, null, 2)+'\n');
await save();
try {
  const packaged = JSON.parse(await readFile('dist/kernel/manifest.json'));
  assert.deepEqual([...packaged].sort(), Object.keys(bundle.modules).sort());
  const py = await loadPyodide({indexURL: path.resolve('dist/runtime')});
  await py.loadPackage(['numpy', 'scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');
  for (const file of packaged) {
    const data = await readFile('dist/kernel/'+file);
    assert.equal(hash(data), bundle.modules[file], 'Packaged source: '+file);
    assert.equal(hash(await readFile('openswing/'+file)), bundle.modules[file], 'Main source: '+file);
    py.FS.writeFile('/home/pyodide/openswing/'+file, data);
  }
  await py.runPythonAsync('from openswing.bridge import run_json\nimport sys, numpy, scipy, json');
  status.runtime = JSON.parse(await py.runPythonAsync('json.dumps(dict(python=sys.version, numpy=numpy.__version__, scipy=scipy.__version__))'));
  status.runtime.pyodide = py.version;
  status.runtime_lock_sha256 = hash(await readFile('dist/runtime/pyodide-lock.json'));
  for (const entry of bundle.cases) {
    status.current = entry.id;
    await save();
    console.log('Starting', entry.id);
    py.globals.set('request_json', JSON.stringify(entry.request));
    const start = performance.now();
    const result = JSON.parse(await py.runPythonAsync('run_json(request_json)'));
    const data = JSON.stringify(result, null, 2)+'\n';
    await writeFile(path.join(output, entry.id+'.json'), data);
    status.cases.push({id: entry.id, seconds: (performance.now()-start)/1000, result_sha256: hash(data)});
    console.log('Computed', status.cases.at(-1));
    await save();
  }
  for (const [file, wanted] of Object.entries(bundle.modules)) {
    assert.equal(hash(await readFile('openswing/'+file)), wanted, 'Source changed during run: '+file);
  }
  status.status = 'COMPUTED_PENDING_INDEPENDENT_COMPARISON';
  delete status.current;
} catch (error) {
  status.status = 'FAIL';
  status.error = error.stack;
  process.exitCode = 1;
} finally {
  await save();
  console.log(JSON.stringify(status));
}
