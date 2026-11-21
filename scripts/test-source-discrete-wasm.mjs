// One cold source-discrete ST5 solve in local Node/Pyodide, not browser UI.
// Usage: node scripts/test-source-discrete-wasm.mjs [--prepare] [--stage PATH]
import {readFile, readdir, writeFile, mkdir, access} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {syncBuiltinESMExports} from 'node:module';
import http from 'node:http';
import https from 'node:https';
import net from 'node:net';
import tls from 'node:tls';
import dgram from 'node:dgram';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const stageIndex = args.indexOf('--stage');
const STAGE = path.resolve(stageIndex < 0 ? '/tmp/openswing-source-discrete-wasm-20261026' : args[stageIndex+1]);
const NATIVE = '/tmp/openswing-source-discrete-integration-20261026/st5';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const json = (file, value) => writeFile(file, JSON.stringify(value, null, 2)+'\n');
const pin = async file => {
  const bytes = await readFile(file);
  return {path: path.resolve(file), bytes: bytes.length, sha256: sha(bytes)};
};
const requireThat = (condition, message) => { if (!condition) throw Error(message); };
const exists = async file => { try { await access(file); return true; } catch { return false; } };
const started = performance.now();
await mkdir(STAGE, {recursive:true});
const nativePlanPath = path.join(NATIVE, 'plan.json');
const nativeResultPath = path.join(NATIVE, 'level0/result.json');
const nativePlan = JSON.parse(await readFile(nativePlanPath, 'utf8'));
const native = JSON.parse(await readFile(nativeResultPath, 'utf8'));
const sourcePath = path.join(ROOT, nativePlan.source);
const source = await readFile(sourcePath, 'utf8');
const moduleNames = (await readdir(path.join(ROOT, 'openswing'))).filter(n => n.endsWith('.py')).sort();
const runtimeNames = (await readdir(path.join(ROOT, 'public/runtime'))).sort();
const files = [fileURLToPath(import.meta.url), nativePlanPath, nativeResultPath, sourcePath,
  ...moduleNames.map(n => path.join(ROOT, 'openswing', n)),
  ...runtimeNames.map(n => path.join(ROOT, 'public/runtime', n)),
  ...['package.json', 'pyodide.mjs', 'pyodide.asm.mjs', 'pyodide-lock.json'].map(n => path.join(ROOT, 'node_modules/pyodide', n))];
const pins = await Promise.all(files.map(pin));
requireThat(moduleNames.length === 114, 'Expected exactly 114 current Python modules');
requireThat(sha(Buffer.from(source)) === nativePlan.source_sha256, 'Literal source differs from native plan');
requireThat(Object.keys(nativePlan.kernel_pins).length === moduleNames.length, 'Native module count differs');
for (const name of moduleNames) {
  const key = `openswing/${name}`;
  requireThat((await pin(path.join(ROOT, key))).sha256 === nativePlan.kernel_pins[key], `Native source pin mismatch: ${key}`);
}
const plan = {
  scope:'Node/Pyodide WASM runtime parity; not browser UI integration or an independent ASWING reference validation.',
  native_plan: nativePlanPath, native_result: nativeResultPath,
  source: sourcePath, source_sha256: nativePlan.source_sha256,
  panels: nativePlan.meshes[0].panels,
  interpolation:'drela-segspl-v1', structural_operator:'drela-steady-zero-offset-v1',
  solve:{tolerance:1e-8, continuation_steps:4, initial_state:null,
    allow_signed_point_weights:true, allow_signed_distributed_weights:true},
  operations:{cold_wasm_solves:1, native_solves:0, extra_fresh_residual_calls:0, automatic_retries:0},
  parity:{absolute_tolerance:2e-8, relative_tolerance:2e-8, numeric_exclusions:['evaluations'],
    native_wrapper_only_fields:['source_policy','strips','structural_only'],
    rule:'Visit every actual core key; require all native-only keys to be exactly the three declared wrapper fields.'},
  residual_gate:1e-8, process_cap_seconds:120,
  remote_network:'Block and record fetch, HTTP(S), TCP, TLS, UDP and WebSocket before importing Pyodide; use only local runtime/wheels.',
  pins
};
if (args.includes('--prepare')) {
  requireThat(!await exists(path.join(STAGE,'plan.json')), 'Prepared plan already exists; refusing overwrite');
  await json(path.join(STAGE,'plan.json'), plan);
  console.log(JSON.stringify({status:'PREPARED_NO_PHYSICS', pins:pins.length, modules:moduleNames.length, plan:await pin(path.join(STAGE,'plan.json'))}));
  process.exit(0);
}
requireThat(await exists(path.join(STAGE,'plan.json')), 'Run --prepare before execution');
const frozenPlan = JSON.parse(await readFile(path.join(STAGE,'plan.json'),'utf8'));
requireThat(JSON.stringify(plan) === JSON.stringify(frozenPlan), 'Prepared inputs or execution protocol changed');
requireThat(!await exists(path.join(STAGE,'execution.json')), 'One attempt already launched; no automatic retry');
const networkAttempts = [];
const blocked = kind => (...arguments_) => {
  const description = arguments_.map(v => typeof v === 'string' ? v : v?.href || v?.hostname || typeof v).join(' ');
  networkAttempts.push({kind, description});
  throw Error(`Network disabled in this offline WASM test (${kind}): ${description}`);
};
globalThis.fetch = blocked('fetch');
http.request = blocked('http.request'); http.get = blocked('http.get');
https.request = blocked('https.request'); https.get = blocked('https.get');
net.connect = blocked('net.connect'); net.createConnection = blocked('net.createConnection');
net.Socket.prototype.connect = blocked('Socket.connect');
tls.connect = blocked('tls.connect'); dgram.createSocket = blocked('dgram.createSocket');
globalThis.WebSocket = class {constructor(...values) {blocked('WebSocket')(...values);}};
syncBuiltinESMExports();
const receipt = {status:'RUNNING', scope:plan.scope, node:process.version,
  plan:await pin(path.join(STAGE,'plan.json')), network_blocker_installed:true, network_attempts:networkAttempts,
  operation_counts:{cold_wasm_solves_started:0,cold_wasm_solves_completed:0,native_solves:0,extra_fresh_residual_calls:0},
  limits:['This invokes the opted-in Python API in Node/Pyodide, not a browser or the default UI solver.',
    'Full-result native/WASM parity does not establish complete archived ASWING agreement.',
    'Only evaluations is excluded from numeric comparison; three native wrapper fields are absent from the core API.']};
await json(path.join(STAGE,'execution.json'), {status:'RUNNING', pid:process.pid, retry:0, plan:receipt.plan});
try {
  const runtimeStart = performance.now();
  const {loadPyodide} = await import('pyodide');
  const py = await loadPyodide({indexURL:path.join(ROOT,'public/runtime')});
  await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');
  for (const name of moduleNames) py.FS.writeFile(`/home/pyodide/openswing/${name}`, await readFile(path.join(ROOT,'openswing',name)));
  receipt.runtime_setup_seconds = (performance.now()-runtimeStart)/1000;
  receipt.pyodide_version = py.version;
  py.globals.set('literal_source', source);
  py.globals.set('request_json', JSON.stringify(plan));
  receipt.operation_counts.cold_wasm_solves_started = 1;
  await json(path.join(STAGE,'report.json'), receipt);
  console.log('BEGIN one cold ST5 level-0 WASM source-discrete solve');
  const encoded = await py.runPythonAsync(`
import hashlib, json, sys, time
from openswing.asw import parse_asw
from openswing.source_discrete import solve_source_discrete, STRUCTURAL_POLICY
import openswing.source_discrete as source_module
request = json.loads(request_json)
assert STRUCTURAL_POLICY == request['structural_operator']
model = parse_asw(literal_source, beam_interpolation=request['interpolation'])
assert model.dumps() == literal_source
progress = []
started = time.perf_counter()
result = solve_source_discrete(model, request['panels'], tolerance=request['solve']['tolerance'],
    continuation_steps=request['solve']['continuation_steps'], initial_state=None,
    allow_signed_point_weights=True, allow_signed_distributed_weights=True,
    progress=lambda *value: progress.append(value))
solve_seconds = time.perf_counter()-started
assert model.dumps() == literal_source
state = result['equilibrium_state']
assert state['identity']['model_sha256'] == hashlib.sha256(literal_source.encode()).hexdigest()
assert state['identity']['beam_interpolation'] == request['interpolation']
assert state['identity']['structural_operator'] == request['structural_operator']
assert result['structural_operator'] == request['structural_operator']
assert 'launch' not in state and len(state['circulation']) == 0
assert result['converged'] and result['residual'] <= request['residual_gate']
assert result['equilibrium_initialization']['initialization'] == 'undeformed load continuation'
json.dumps(dict(result=result, progress=progress, solve_seconds=solve_seconds,
    python=sys.version, module_path=source_module.__file__), allow_nan=False)
`);
  const packet = JSON.parse(encoded);
  receipt.operation_counts.cold_wasm_solves_completed = 1;
  receipt.solve_seconds = packet.solve_seconds;
  receipt.python = packet.python;
  receipt.python_module_path = packet.module_path;
  receipt.residual = packet.result.residual;
  receipt.evaluations = {wasm:packet.result.evaluations, native:native.evaluations};
  await json(path.join(STAGE,'result.json'), packet.result);
  await json(path.join(STAGE,'progress.json'), packet.progress);
  const comparison = {numeric_count:0, exact_count:0, container_count:0, failures:[],
    max_absolute_difference:0, max_gate_fraction:0, worst_absolute_path:null, worst_gate_path:null,
    absolute_tolerance:plan.parity.absolute_tolerance, relative_tolerance:plan.parity.relative_tolerance,
    excluded_numeric_paths:['evaluations']};
  function compare(actual, expected, at) {
    if (at === 'evaluations') return;
    if (typeof actual === 'number' && typeof expected === 'number') {
      comparison.numeric_count++;
      const error = Math.abs(actual-expected), gate = comparison.absolute_tolerance+comparison.relative_tolerance*Math.abs(expected);
      if (error > comparison.max_absolute_difference) {comparison.max_absolute_difference=error; comparison.worst_absolute_path=at;}
      if (error/gate > comparison.max_gate_fraction) {comparison.max_gate_fraction=error/gate; comparison.worst_gate_path=at;}
      if (!Number.isFinite(actual) || !Number.isFinite(expected) || error > gate) comparison.failures.push({path:at,actual,expected,error,gate});
    } else if (Array.isArray(actual)) {
      comparison.container_count++;
      if (!Array.isArray(expected) || actual.length !== expected.length) comparison.failures.push({path:at,error:'Array shape mismatch'});
      else actual.forEach((value,i) => compare(value,expected[i],`${at}[${i}]`));
    } else if (actual !== null && typeof actual === 'object') {
      comparison.container_count++;
      if (expected === null || typeof expected !== 'object' || Array.isArray(expected)
          || JSON.stringify(Object.keys(actual).sort()) !== JSON.stringify(Object.keys(expected).sort())) comparison.failures.push({path:at,error:'Object keys mismatch'});
      else for (const key of Object.keys(actual)) compare(actual[key],expected[key],at ? `${at}.${key}`:key);
    } else {
      comparison.exact_count++;
      if (actual !== expected) comparison.failures.push({path:at,actual,expected});
    }
  }
  const nativeOnly = Object.keys(native).filter(key => !(key in packet.result)).sort();
  comparison.native_only_fields = nativeOnly;
  requireThat(JSON.stringify(nativeOnly) === JSON.stringify(plan.parity.native_wrapper_only_fields), 'Unexpected native-only fields');
  for (const key of Object.keys(packet.result)) {
    requireThat(key in native, `Core result field absent from native target: ${key}`);
    compare(packet.result[key],native[key],key);
  }
  comparison.status = comparison.failures.length ? 'FAIL' : 'PASS';
  await json(path.join(STAGE,'comparison.json'),comparison);
  receipt.comparison = comparison;
  requireThat(comparison.failures.length === 0, `${comparison.failures.length} native/WASM parity failures`);
  requireThat(networkAttempts.length === 0, 'Runtime attempted network access');
  receipt.status = 'PASS';
} catch (error) {
  receipt.status = 'FAIL'; receipt.error = String(error.stack || error); process.exitCode=1;
  console.error(receipt.error);
} finally {
  const changed = [];
  for (const original of pins) {
    try {if (JSON.stringify(await pin(original.path)) !== JSON.stringify(original)) changed.push(original.path);}
    catch {changed.push(original.path);}
  }
  receipt.pins_unchanged = changed.length === 0;
  receipt.changed_inputs = changed;
  if (changed.length) {receipt.status='FAIL';process.exitCode=1;}
  receipt.elapsed_seconds = (performance.now()-started)/1000;
  receipt.outputs = {};
  for (const name of ['result.json','progress.json','comparison.json']) if (await exists(path.join(STAGE,name))) receipt.outputs[name]=await pin(path.join(STAGE,name));
  await json(path.join(STAGE,'report.json'),receipt);
  await json(path.join(STAGE,'execution.json'), {status:'TERMINAL', pid:process.pid, exit_code:process.exitCode || 0,
    child_reaping:'External supervisor owns process wait/reap.', report:await pin(path.join(STAGE,'report.json'))});
  console.log(JSON.stringify({status:receipt.status, solve_seconds:receipt.solve_seconds,
    residual:receipt.residual, numeric_count:receipt.comparison?.numeric_count,
    max_absolute_difference:receipt.comparison?.max_absolute_difference, pins_unchanged:receipt.pins_unchanged}));
}
