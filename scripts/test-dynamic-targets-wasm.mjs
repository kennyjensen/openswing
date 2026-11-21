import {loadPyodide} from 'pyodide';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
try {
const study=JSON.parse(await readFile('docs/validation/dynamic-targets.json','utf8'));
for(const [file,hash] of Object.entries(study.source_sha256))if(createHash('sha256').update(await readFile(file)).digest('hex')!==hash)throw new Error('Study source changed: '+file);
const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);py.FS.mkdirTree('/home/pyodide/openswing');
for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8'))){const data=await readFile(`dist/kernel/${name}`);if(!data.equals(await readFile(`openswing/${name}`)))throw new Error('Stale packaged module: '+name);py.FS.writeFile(`/home/pyodide/openswing/${name}`,data);}
for(const name of ['six_inputs','prescribed','offsets_1e-05','gyro_y','feedback','rom']){
 py.globals.set('case_json',JSON.stringify(study.cases[name]));
 await py.runPythonAsync(`
import json,numpy as np
from openswing.bridge import run_json
c=json.loads(case_json);actual=json.loads(run_json(json.dumps(c['request'])));expected=c['result']
def z(v):return np.asarray(v['real'])+1j*np.asarray(v['imag'])
assert actual['frame_mode']==expected['frame_mode']
assert actual['frame_load_targets']==expected['frame_load_targets']
if actual['analysis']=='eigenmodes':
    roots=np.array([complex(*m['eigenvalue']) for m in actual['modes']])
    assert actual['diagnostics']['finite_dimension']==expected['diagnostics']['finite_dimension']==12
    for key in ['A','M']:np.testing.assert_allclose(actual['matrices'][key],expected['matrices'][key],atol=3e-9,rtol=3e-8)
    for root in c['comparison']['expected_pair']:assert min(abs(roots-complex(*root)))<3e-7
    for mode in expected['modes']:
        root=complex(*mode['eigenvalue'])
        if abs(root)>.1:assert min(abs(roots-root))<3e-7
    # The rigid model has eight defective kinematic zero roots. Their forward
    # errors are sensitive to roundoff; verify the pencil, cluster and isolated
    # physical roots instead of treating tiny split roots as distinct modes.
    assert sum(abs(roots)<1e-4)==c['comparison']['near_zero_roots']==8
    assert max(m['right_backward_error'] for m in actual['modes'])<1e-7
elif actual['analysis']=='frequency_response':
    assert actual['inputs']==expected['inputs']
    for a,b in zip(actual['samples'],expected['samples']):
        assert a['converged']==b['converged'] and a['omega']==b['omega']
        for aa,bb in zip(a['responses'],b['responses']):
            for group,keys in [('frame',['velocity_origin_body','rates_body','position_earth','attitude_rad']),('global',['applied_force','applied_moment','support_force','support_moment'])]:
                for key in keys:np.testing.assert_allclose(z(aa['output'][group][key]),z(bb['output'][group][key]),atol=3e-6,rtol=3e-7)
            if 'feedback' in bb['output']:
                for key in bb['output']['feedback']:np.testing.assert_allclose(z(aa['output']['feedback'][key]),z(bb['output']['feedback'][key]),atol=3e-6,rtol=3e-7)
else:
    assert actual['diagnostics']['dimension']==1 and actual.get('legacy_export')
    for a,b in zip(actual['samples'],expected['samples']):
        for key in ['full','reduced']:np.testing.assert_allclose(z(a[key]),z(b[key]),atol=3e-6,rtol=3e-7)
`);
 console.log('Packaged WASM mixed continuous dynamics agrees with native: '+name);
}
await new Promise(resolve=>process.stdout.write('All six WASM dynamic-constraint cases passed.\n',resolve));process.exit(0);
} catch(error) {await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
