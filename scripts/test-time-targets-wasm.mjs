import {loadPyodide} from 'pyodide';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const study=JSON.parse(await readFile('docs/validation/time-targets.json','utf8'));
for(const [file,hash] of Object.entries(study.source_sha256))if(createHash('sha256').update(await readFile(file)).digest('hex')!==hash)throw new Error('Study source changed: '+file);
const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);py.FS.mkdirTree('/home/pyodide/openswing');
for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8'))){const data=await readFile(`dist/kernel/${name}`);if(!data.equals(await readFile(`openswing/${name}`)))throw new Error('Stale packaged module: '+name);py.FS.writeFile(`/home/pyodide/openswing/${name}`,data);}
for(const name of ['Fx_0.01','Mz_0.01','controller_0.005','mixed_offsets']){
 py.globals.set('case_json',JSON.stringify(study.cases[name]));
 await py.runPythonAsync(`
import json,numpy as np
from openswing.bridge import run_json
from openswing.asw import parse_asw
from openswing.time_state import resume_time
c=json.loads(case_json);out=json.loads(run_json(json.dumps(c['request'])))
assert len(out['snapshots'])==len(c['trajectory']['snapshots'])
for a,b in zip(out['snapshots'],c['trajectory']['snapshots']):
    assert a['time']==b['time'] and a['order']==b['order'] and a['forcing_side']==b['forcing_side']
    assert a['forcing_values']==b['forcing_values']
    for key in ('position_earth','velocity_origin_body','rates_body','acceleration_reference_body','angular_acceleration_body','body_to_earth'):
        np.testing.assert_allclose(a['frame'][key],b['frame'][key],atol=3e-7,rtol=1e-9)
    np.testing.assert_allclose([n['position'] for n in a['nodes']],[n['position'] for n in b['nodes']],atol=3e-8)
    np.testing.assert_allclose(a['local_velocity'],b['local_velocity'],atol=3e-7)
    for row in a['operating_constraints']:assert abs(row['actual']-row['target'])<3e-7
    if 'feedback' in b:assert abs(a['feedback']['actuators']['E1']-b['feedback']['actuators']['E1'])<1e-8
if 'checkpoint' in c:
    resumed=resume_time(parse_asw(c['request']['source']),c['checkpoint'],duration=.04)
    assert resumed['snapshots'][1]['order']==1
    for a,b in zip(resumed['snapshots'],c['resumed']['snapshots']):
        np.testing.assert_allclose(a['frame']['velocity_origin_body'],b['frame']['velocity_origin_body'],atol=3e-7)
`);
 console.log('Packaged WASM mixed motion / finite forcing agrees with native: '+name);
}
await new Promise(resolve=>process.stdout.write('All four WASM forcing/constraint cases passed.\n',resolve));process.exit(0);
