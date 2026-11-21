/** Exercise sailplane gust integration and the browser's compressed result reader. */
import assert from 'node:assert/strict';
import {readFile, readdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {loadPyodide} from 'pyodide';
import {readSolverReply} from '../web/solver-json.js';
import {restoreWorkerTimeHistory} from '../web/worker-time-history.js';
import {timeHistory} from '../web/time-history-source.js';

const root = new URL('../', import.meta.url);
const read = name => readFile(new URL(name, root), 'utf8');
const py = await loadPyodide({indexURL:fileURLToPath(new URL('public/runtime/', root))});
await py.loadPackage(['numpy', 'scipy']);
const kernel = '/home/pyodide/openswing';
py.FS.mkdirTree(kernel);
for (const name of await readdir(new URL('openswing/', root))) {
  if (name.endsWith('.py')) py.FS.writeFile(`${kernel}/${name}`, await read(`openswing/${name}`));
}
await py.runPythonAsync('from openswing.bridge import run_worker_parts');
const request = {
  action:'time',
  source:await read('examples/usa.asw'),
  panels:JSON.parse(await read('web/sailplane-mesh.json')),
  numerics:{beam_interpolation:'drela-segspl-v1', structural_operator:'drela-moving-airflow-v1'},
  condition:{
    speed:21.981627296587927, alpha:3, beta:0, stall:true, freeze_influences:true, aero_lag:true,
    gust:{type:'cosine', amplitude:[0,0,.6], normal:[1,0,0], origin:[-2,0,0], length:10, speed:0},
  },
  time:{duration:.2, dt:.025, order:2, frame:'prescribed'},
};
py.globals.set('request_json', JSON.stringify(request));
py.globals.set('time_progress', () => {});
const reply = await readSolverReply(py, request.action);
assert.ok(!reply.error, reply.error);
const result = restoreWorkerTimeHistory(reply.result);
const history = timeHistory(result);
assert.equal(result.converged, true);
assert.equal(result.temporal_policy, 'drela-euler-bdf-v1');
assert.equal(result.accepted_steps, 8);
assert.equal(result.rejected_steps, 0);
assert.equal(history.count, 9);
const first = await history.read(0);
const last = await history.read(8);
assert.ok(Math.abs(last.time-.2) < 1e-12);
assert.equal(last.gust.type, 'cosine');
// Native run of the same request. This checks portability, not ASWING parity.
assert.ok(Math.abs(first.CL-.8085698469722777) < 5e-7, `Initial CL ${first.CL}`);
assert.ok(Math.abs(last.CL-.7960161793510094) < 5e-7, `Final CL ${last.CL}`);
console.log(`Sailplane gust WASM: ${result.accepted_steps} steps, ${history.count} decoded snapshots, CL ${first.CL.toFixed(6)} → ${last.CL.toFixed(6)}`);

const checkpoint = await history.checkpoint(4);
const resume = {
  action:'resume_time', source:request.source, numerics:request.numerics,
  checkpoint, time:{duration:.1},
};
py.globals.set('request_json', JSON.stringify(resume));
const resumedReply = await readSolverReply(py, resume.action);
assert.ok(!resumedReply.error, resumedReply.error);
const resumed = restoreWorkerTimeHistory(resumedReply.result);
const resumedHistory = timeHistory(resumed);
assert.equal(resumed.converged, true);
assert.equal(resumed.accepted_steps, 4);
assert.equal(resumed.rejected_steps, 0);
for (let i=0; i<resumedHistory.count; i++) {
  const uninterrupted = await history.read(4+i);
  const saved = await resumedHistory.read(i);
  assert.ok(Math.abs(uninterrupted.time-saved.time) < 1e-12);
  assert.ok(Math.abs(uninterrupted.CL-saved.CL) < 5e-7, `Resumed CL at t=${saved.time}`);
  assert.ok(Math.abs(uninterrupted.max_displacement-saved.max_displacement) < 5e-7,
    `Resumed displacement at t=${saved.time}`);
}
console.log('WASM continuation matched all remaining gust snapshots after a JSON checkpoint round trip.');
