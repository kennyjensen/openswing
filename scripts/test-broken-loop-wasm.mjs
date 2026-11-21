import {loadPyodide} from 'pyodide';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
try {
const study=JSON.parse(await readFile('docs/validation/broken-loop.json','utf8'));
for(const [file,hash] of Object.entries(study.source_sha256))if(createHash('sha256').update(await readFile(file)).digest('hex')!==hash)throw new Error('Study source changed: '+file);
const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);py.FS.mkdirTree('/home/pyodide/openswing');
for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8'))){const data=await readFile(`dist/kernel/${name}`);if(!data.equals(await readFile(`openswing/${name}`)))throw new Error('Stale packaged module: '+name);py.FS.writeFile(`/home/pyodide/openswing/${name}`,data);}
for(const [name,c] of Object.entries(study.cases)){
 py.globals.set('case_json',JSON.stringify(c));
 await py.runPythonAsync(`
import json,numpy as np
from openswing.bridge import run_json
c=json.loads(case_json);actual=json.loads(run_json(json.dumps(c['request'])));expected=c['result']
def z(v):return np.asarray(v['real'])+1j*np.asarray(v['imag'])
assert actual['inputs']==expected['inputs']
for a,b in zip(actual['samples'],expected['samples']):
    assert a['converged']==b['converged'] and a['omega']==b['omega']
    assert max(a['diagnostics']['backward_errors'])<1e-9
    for aa,bb in zip(a['responses'],b['responses']):
        x,y=aa['broken_loop'],bb['broken_loop'];assert x['available']==y['available']
        if x['available']:
            np.testing.assert_allclose(z(x['response_gain']),z(y['response_gain']),atol=3e-7,rtol=3e-6)
            np.testing.assert_allclose(z(x['value']),z(y['value']),atol=3e-7,rtol=3e-6)
        else:assert x['error']==y['error']
        for key in ['state']:np.testing.assert_allclose(z(aa[key]),z(bb[key]),atol=3e-7,rtol=3e-6)
    for key in ['A','M']:np.testing.assert_allclose(actual['matrices'][key],expected['matrices'][key],atol=3e-8,rtol=3e-7)
`);
 console.log('Packaged WASM broken-loop case passed: '+name);
}
await new Promise(resolve=>process.stdout.write('All eight WASM broken-loop cases passed.\n',resolve));process.exit(0);
} catch(error) {await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
