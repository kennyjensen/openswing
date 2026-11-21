import {loadPyodide} from 'pyodide';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
py.FS.mkdirTree('/home/pyodide/openswing');
for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8')))py.FS.writeFile(`/home/pyodide/openswing/${name}`,await readFile(`dist/kernel/${name}`,'utf8'));
const study=JSON.parse(await readFile('docs/validation/steady-launch.json','utf8'));
for(const [name,duration] of [['lag_0.01',.04],['flight_0.025',.05]]){
  const c=study.cases[name];
  py.globals.set('request_json',JSON.stringify({action:'launch_time',source:c.source,equilibrium_state:c.seed,time:{...c.time,duration}}));
  py.globals.set('reference_json',JSON.stringify(c.trajectory));
  await py.runPythonAsync(`
import json,numpy as np
from openswing.bridge import run_json
from openswing.time_state import checkpoint
request=json.loads(request_json);reference=json.loads(reference_json)
out=json.loads(run_json(request_json))
assert out['continuation_steps']==0 and not out['initialization']['equilibrium_recomputed']
assert out['snapshots'][0]['initial_phase']=='saved_equilibrium_before_time_inputs'
for a,b in zip(out['snapshots'],reference['snapshots']):
    assert abs(a['time']-b['time'])<1e-12
    np.testing.assert_allclose(a['local_velocity'],b['local_velocity'],atol=2e-7,rtol=2e-7)
    np.testing.assert_allclose(a['frame']['position_earth'],b['frame']['position_earth'],atol=2e-7)
    np.testing.assert_allclose([n['position'] for n in a['nodes']],[n['position'] for n in b['nodes']],atol=2e-7)
    for group in ('actuators','integrals','states','commands'):
        for key in b.get('feedback',{}).get(group,{}):
            assert abs(a['feedback'][group][key]-b['feedback'][group][key])<2e-7
assert len(out['snapshots'])==round(request['time']['duration']/request['time']['dt'])+1
json.dumps(checkpoint(out),allow_nan=False)
`);
  console.log(`Packaged WebAssembly launches native ${name} with matching physical states and no equilibrium recomputation.`);
}
