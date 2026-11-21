import {loadPyodide} from 'pyodide';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
py.FS.mkdirTree('/home/pyodide/openswing');
for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8')))py.FS.writeFile(`/home/pyodide/openswing/${name}`,await readFile(`dist/kernel/${name}`,'utf8'));
const study=JSON.parse(await readFile('docs/validation/time-checkpoints.json','utf8'));
for(const [name,source,checkpoint,reference] of [
  ['elastic motion',study.cases['release_0.01'].source,study.cases['release_0.01'].checkpoint,study.cases['release_0.01'].resumed],
  ['controller forcing jump',study.cases.controller.source,study.cases.controller.runs[0].checkpoint,study.cases.controller.runs[0].result]
]){
  py.globals.set('source',source);py.globals.set('saved_json',JSON.stringify(checkpoint));py.globals.set('reference_json',JSON.stringify(reference));
  await py.runPythonAsync(`
import json,numpy as np
from openswing.bridge import run_json
from openswing.time_state import checkpoint
saved=json.loads(saved_json);reference=json.loads(reference_json)
out=json.loads(run_json(json.dumps(dict(action='resume_time',source=source,checkpoint=saved,time=dict(duration=reference['duration'])))))
assert len(out['snapshots'])==len(reference['snapshots'])
for a,b in zip(out['snapshots'],reference['snapshots']):
    assert abs(a['time']-b['time'])<1e-12
    for key in ('local_velocity','local_rates','circulation_rate'):
        np.testing.assert_allclose(a[key],b[key],atol=2e-7,rtol=2e-7)
    np.testing.assert_allclose(a['frame']['position_earth'],b['frame']['position_earth'],atol=2e-8)
    np.testing.assert_allclose([n['position'] for n in a['nodes']],[n['position'] for n in b['nodes']],atol=2e-8)
    for group in ('actuators','integrals','states'):
        for key in b.get('feedback',{}).get(group,{}):
            assert abs(a['feedback'][group][key]-b['feedback'][group][key])<2e-7
assert out['snapshots'][1]['order']==reference['snapshots'][1]['order']
json.dumps(checkpoint(out),allow_nan=False)
`);
  console.log(`Packaged WebAssembly resumes native ${name} with the expected physical states and BDF order.`);
}
