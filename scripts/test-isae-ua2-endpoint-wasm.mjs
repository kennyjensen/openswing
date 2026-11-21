import {loadPyodide} from 'pyodide';
import {readFile, readdir, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const assets = process.argv[2] || 'public';
if (!['public', 'dist'].includes(assets)) throw Error('Use public or dist assets.');
const output = 'docs/validation/isae-ua2-time-endpoint-wasm-20261101.json';
try {
  try { await readFile(output); throw Error('Preserve the existing WASM report.'); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  const fixtureBytes = await readFile('tests/fixtures/isae-ua2-endpoint.json');
  const fixture = JSON.parse(fixtureBytes);
  const modules = JSON.parse(await readFile(`${assets}/kernel/manifest.json`));
  const current = (await readdir('openswing')).filter(n => n.endsWith('.py')).sort();
  if (JSON.stringify([...modules].sort()) !== JSON.stringify(current)) throw Error('Incomplete packaged kernel.');
  const sources = {};
  for (const name of modules) {
    const bytes = await readFile(`${assets}/kernel/${name}`);
    const digest = hash(bytes);
    if (digest !== fixture.production_sha256[`openswing/${name}`] ||
        digest !== hash(await readFile(`openswing/${name}`))) throw Error(`Stale kernel module: ${name}`);
    sources[name] = bytes;
  }
  const started = performance.now();
  const py = await loadPyodide({indexURL: path.resolve(`${assets}/runtime`)});
  await py.loadPackage(['numpy', 'scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');
  for (const [name, bytes] of Object.entries(sources)) py.FS.writeFile(`/home/pyodide/openswing/${name}`, bytes);
  py.globals.set('fixture_json', JSON.stringify(fixture));
  const result = JSON.parse(await py.runPythonAsync(`
import json, numpy as np
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.forcing import TimeForcing
from openswing.bridge import dispatch
f=json.loads(fixture_json)
c=FlightCondition(speed=10,alpha=9,mach=0,stall=False)
history=TimeForcing(f['checkpoint']['context']['setup']['forcing'],parse_asw(f['source']),
    c,c.motion(),f['rounded_end'],'prescribed',start_time=f['original_segment_start'])
assert f['exact_knot'] in history.events
out=dispatch(dict(action='resume_time',mode=f['mode'],panels=f['panels'],numerics=f['numerics'],
    source=f['source'],checkpoint=f['checkpoint'],
    time=dict(duration=f['duration'],max_steps=4)))
assert out['converged'] and out['accepted_steps']==1 and out['rejected_steps']==0
a=out['snapshots'][-1];b=f['expected']
assert a['time']==b['time'] and a['order']==b['order']==2
assert a['residual']<1e-10
errors={}
def compare(name,actual,expected):
    x,y=np.asarray(actual),np.asarray(expected)
    assert x.shape==y.shape
    errors[name]=float(np.max(abs(x-y)/np.maximum(1.,abs(y))))
for key in ('force','circulation_rate','local_velocity','local_acceleration'):
    compare(key,a[key],b[key])
compare('circulation',[r['circulation'] for r in a['strips']],[r['circulation'] for r in b['strips']])
for key in ('position_earth','velocity_origin_body','attitude','rates_body'):
    compare('frame_'+key,a['frame'][key],b['frame'][key])
assert max(errors.values())<2e-8,errors
json.dumps(dict(passed=True,endpoint_event_retained=True,accepted_steps=out['accepted_steps'],
    rejected_steps=out['rejected_steps'],time=a['time'],residual=a['residual'],
    maximum_scaled_CPython_difference=max(errors.values()),differences=errors,
    native_ASWING_comparison=False,full_periodic_WASM_validation=False))
`));
  const runtime = {};
  for (const name of ['pyodide.asm.wasm', 'pyodide-lock.json']) runtime[name] = hash(await readFile(`${assets}/runtime/${name}`));
  const report = {...result, asset_root: assets, module_count: modules.length,
    runtime_seconds: (performance.now()-started)/1000, runtime_sha256: runtime,
    production_sha256: fixture.production_sha256,
    source_sha256: {
      'tests/fixtures/isae-ua2-endpoint.json': hash(fixtureBytes),
      'scripts/test-isae-ua2-endpoint-wasm.mjs': hash(await readFile('scripts/test-isae-ua2-endpoint-wasm.mjs')),
    }};
  await writeFile(output, JSON.stringify(report, null, 2)+'\n');
  await new Promise(resolve => process.stdout.write(JSON.stringify(result)+'\n', resolve));
  process.exit(0);
} catch (error) {
  await new Promise(resolve => process.stderr.write(String(error)+'\n', resolve));
  process.exit(1);
}
