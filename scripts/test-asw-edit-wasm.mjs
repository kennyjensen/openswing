import {loadPyodide} from 'pyodide';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
const study=JSON.parse(await readFile('docs/validation/asw-edit.json','utf8'));
for(const [file,hash] of Object.entries(study.source_sha256))if(createHash('sha256').update(await readFile(file)).digest('hex')!==hash)throw new Error('Study source changed: '+file);
const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
py.FS.mkdirTree('/home/pyodide/openswing');
for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8'))){
 const content=await readFile(`dist/kernel/${name}`);if(!content.equals(await readFile(`openswing/${name}`)))throw new Error('Packaged kernel differs: '+name);
 py.FS.writeFile(`/home/pyodide/openswing/${name}`,content);
}
for(const [name,c] of Object.entries(study.cases)){
 py.globals.set('case_json',JSON.stringify(c));
 await py.runPythonAsync(`
import json,numpy as np
from openswing.bridge import run_json
c=json.loads(case_json)
if 'edit_request' in c:
    edited=json.loads(run_json(json.dumps(c['edit_request'])))
    assert edited['source']==c['edited']['source']
    np.testing.assert_allclose(edited['distribution']['segments'][0]['values'],c['edited']['distribution']['segments'][0]['values'],atol=1e-10)
r=json.loads(run_json(json.dumps(c['request'])))
for key in ('force','moment'):
    np.testing.assert_allclose(r[key],c['response'][key],atol=1e-7,rtol=1e-9)
if 'nodes' in r:
    np.testing.assert_allclose([n['position'] for n in r['nodes']],[n['position'] for n in c['response']['nodes']],atol=1e-10)
    assert r['equilibrium_state']['identity']==c['response']['equilibrium_state']['identity']
if 'mode_request' in c:
    modes=json.loads(run_json(json.dumps(c['mode_request'])))
    poles=[complex(*v['eigenvalue']) for v in modes['modes']]
    for v in c['comparison']['exact_poles']:assert min(abs(p-complex(*v)) for p in poles)<1e-6
`);
 console.log('Packaged WebAssembly edit/solve agrees with native and analytical checks: '+name);
}
// This CLI owns the runtime. Exit after awaited assertions and flushed output;
// embedded WASM/host handles need not keep a completed verification alive.
await new Promise(resolve=>process.stdout.write('All four packaged WASM cases passed.\n',resolve));
process.exit(0);
