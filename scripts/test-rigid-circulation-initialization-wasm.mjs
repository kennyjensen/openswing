// Offline packaged-kernel replay of the two synthetic native warm-start cases.
// Run the matching native helper first; neither runner reads archived aircraft.
import {readFile, writeFile, readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const options = {
  '--output-dir': 'artifacts/isae/sa4-operating-sequence-20261029/wasm',
  '--kernel-dir': 'dist/kernel',
  '--runtime-dir': 'dist/runtime',
};
for (let i = 2; i < process.argv.length; i += 2) {
  const name = process.argv[i];
  if (!(name in options) || !process.argv[i + 1]) throw new Error(`Unknown or incomplete option: ${name}`);
  options[name] = process.argv[i + 1];
}
const output = path.resolve(root, options['--output-dir']);
const kernel = path.resolve(root, options['--kernel-dir']);
const runtime = path.resolve(root, options['--runtime-dir']);
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const must = (condition, message) => { if (!condition) throw new Error(message); };
async function pin(file) {
  const raw = await readFile(file);
  return {path: path.relative(root, file), bytes: raw.length, sha256: hash(raw)};
}
async function verifyPins(pins) {
  for (const expected of pins) must(same(await pin(path.resolve(root, expected.path)), expected), `Changed evidence: ${expected.path}`);
}
const save = (name, value) => writeFile(path.join(output, name), JSON.stringify(value, null, 2) + '\n', {flag: 'wx'});

function parity(name, actual, native, tolerance) {
  let count = 0, maximum = 0, worst = null;
  function walk(a, b, location) {
    if (a === null || b === null) {
      must(a === b, `Null mismatch: ${location}`);
    } else if (Array.isArray(a) || Array.isArray(b)) {
      must(Array.isArray(a) && Array.isArray(b) && a.length === b.length, `Shape mismatch: ${location}`);
      for (let i = 0; i < a.length; i++) walk(a[i], b[i], `${location}[${i}]`);
    } else if (typeof a === 'object' || typeof b === 'object') {
      must(typeof a === 'object' && typeof b === 'object' && same(Object.keys(a).sort(), Object.keys(b).sort()), `Keys mismatch: ${location}`);
      for (const key of Object.keys(a)) walk(a[key], b[key], `${location}.${key}`);
    } else if (typeof a === 'number' || typeof b === 'number') {
      must(typeof a === 'number' && typeof b === 'number' && Number.isFinite(a) && Number.isFinite(b), `Nonfinite/type mismatch: ${location}`);
      const error = Math.abs(a - b) / Math.max(1, Math.abs(b));
      count++;
      if (error > maximum) { maximum = error; worst = {path: location, native: b, wasm: a}; }
    } else {
      must(a === b, `Metadata mismatch: ${location}`);
    }
  }
  walk(actual, native, name);
  return {name, scalar_comparisons: count, maximum_scaled_error: maximum, worst, tolerance, passed: maximum <= tolerance};
}

const report = {
  schema: 'rigid-circulation-initialization-offline-wasm-v1',
  kernel_dir: options['--kernel-dir'], runtime_dir: options['--runtime-dir'],
  qualification: 'Offline packaged modules, byte-verified against native sources. Synthetic warm-start API witnesses; no archived aircraft or historical startup claim.',
  network_requests: [], cases: [], passed: false,
};
const started = performance.now();
try {
  const protocolPath = path.join(output, 'protocol.json');
  const protocol = JSON.parse(await readFile(protocolPath, 'utf8'));
  const nativePath = path.join(output, 'native-report.json');
  const native = JSON.parse(await readFile(nativePath, 'utf8'));
  report.protocol = await pin(protocolPath);
  report.native_report = await pin(nativePath);
  must(same(native.protocol, report.protocol), 'Native protocol mismatch');
  must(native.passed && native.sources_unchanged, 'Native witnesses are incomplete');
  must(protocol.kernel_dir === options['--kernel-dir'] && protocol.runtime_dir === options['--runtime-dir'], 'Native/package directory mismatch');
  must(protocol.residual_gate === 1e-8 && protocol.scaled_native_parity_gate === 1e-9, 'Unexpected witness gate');
  must(same(protocol.cases, [{id: 'pointwise', modes: 0}, {id: 'fourier4', modes: 4}]), 'Unexpected witness scope');
  must(native.cases.length === 2 && same(native.cases.map(row => row.id).sort(), ['fourier4', 'pointwise']), 'Native witness identities are incomplete or duplicated');
  await verifyPins(protocol.source_pins);
  const names = JSON.parse(await readFile(path.join(kernel, 'manifest.json'), 'utf8'));
  const nativeNames = (await readdir(path.join(root, 'openswing'))).filter(name => name.endsWith('.py')).sort();
  must(names.length === new Set(names).size && same([...names].sort(), nativeNames) && same(nativeNames, protocol.module_names), 'Kernel module inventory mismatch');
  const modules = [];
  for (const name of names) {
    must(path.basename(name) === name && name.endsWith('.py'), 'Unsafe module name');
    const bytes = await readFile(path.join(kernel, name));
    must(bytes.equals(await readFile(path.join(root, 'openswing', name))), `Stale packaged module: ${name}`);
    modules.push({name, bytes, pin: await pin(path.join(kernel, name))});
  }
  report.packaged_modules = modules.map(module => module.pin);
  report.module_count = modules.length;
  globalThis.fetch = async (...args) => {
    report.network_requests.push(String(args[0]));
    throw new Error('Network access is disabled for this offline witness');
  };
  const {loadPyodide} = await import(pathToFileURL(path.join(runtime, 'pyodide.mjs')).href);
  const py = await loadPyodide({indexURL: runtime + path.sep});
  await py.loadPackage(['numpy', 'scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');
  py.FS.mkdirTree('/home/pyodide/scripts');
  for (const module of modules) py.FS.writeFile('/home/pyodide/openswing/' + module.name, module.bytes);
  py.FS.writeFile('/home/pyodide/scripts/initialization_witness.py',
    await readFile(path.join(root, 'scripts/test-rigid-circulation-initialization-native.py')));
  py.globals.set('synthetic_source', await readFile(path.join(root, 'examples/stall-branch.asw'), 'utf8'));
  await py.runPythonAsync(`
import json, os, runpy, sys
os.chdir('/home/pyodide')
sys.path.insert(0, '/home/pyodide')
import openswing
assert openswing.__file__.startswith('/home/pyodide/openswing/')
helpers = runpy.run_path('/home/pyodide/scripts/initialization_witness.py')
`);
  report.pyodide_version = py.version;
  for (const spec of protocol.cases) {
    const nativeCase = native.cases.find(row => row.id === spec.id);
    must(nativeCase.status === 'computed' && nativeCase.passed, 'Native case failed');
    await verifyPins([nativeCase.output]);
    const expected = JSON.parse(await readFile(path.resolve(root, nativeCase.output.path), 'utf8'));
    py.globals.set('initialization_case_json', JSON.stringify(spec));
    const actual = JSON.parse(await py.runPythonAsync(
      "json.dumps(helpers['run_case'](json.loads(initialization_case_json), synthetic_source), allow_nan=False)"));
    await save(spec.id + '-wasm.json', actual);
    const checks = [...actual.checks];
    if (actual.status === 'computed') {
      for (const name of ['seed_input', 'seed_after', 'endpoint_circulation', 'comparison_fields']) {
        checks.push(parity(name, actual[name], expected[name], protocol.scaled_native_parity_gate));
      }
      for (const name of ['method']) must(actual.warm.circulation_solver[name] === expected.warm.circulation_solver[name], 'Solver route mismatch');
    }
    const row = {id: spec.id, status: actual.status, seconds: actual.seconds, checks,
      passed: actual.status === 'computed' && checks.every(check => check.passed),
      output: await pin(path.join(output, spec.id + '-wasm.json'))};
    report.cases.push(row);
    console.log(JSON.stringify({id: row.id, passed: row.passed, seconds: row.seconds,
      failed: row.checks.filter(check => !check.passed)}));
  }
  await verifyPins(protocol.source_pins);
  await verifyPins([report.protocol, report.native_report, ...native.cases.map(row => row.output)]);
  report.sources_unchanged = true;
  report.passed = report.cases.length === 2 && report.cases.every(row => row.passed) && report.network_requests.length === 0;
} catch (error) {
  report.error = String(error);
  report.stack = error.stack;
}
report.seconds = (performance.now() - started) / 1000;
await save('wasm-report.json', report);
console.log(JSON.stringify({passed: report.passed, cases: report.cases.length, seconds: report.seconds, error: report.error}));
process.exitCode = report.passed ? 0 : 1;
