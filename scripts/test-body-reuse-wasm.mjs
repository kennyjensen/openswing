import {loadPyodide} from 'pyodide';
import {readFile,readdir} from 'node:fs/promises';
import path from 'node:path';
const root=process.argv[2]??process.cwd(),py=await loadPyodide({indexURL:path.resolve('public/runtime')});
await py.loadPackage(['numpy','scipy']);
py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/examples');
for(const n of (await readdir(root+'/openswing')).filter(n=>n.endsWith('.py')))
 py.FS.writeFile('/home/pyodide/openswing/'+n,await readFile(root+'/openswing/'+n,'utf8'));
for(const n of ['wing-body','dae'])py.FS.writeFile('/home/pyodide/examples/'+n+'.asw',await readFile(root+'/examples/'+n+'.asw','utf8'));
const tests=(await readFile(root+'/tests/test_body_tangent_reuse.py','utf8')).replace('import pytest\n','').replace(/^@pytest.mark.parametrize.*\n/gm,'');
await py.runPythonAsync(tests);
await py.runPythonAsync(`
for shape in [(72,83),(1,83),(83,1),(8,23)]:
 test_volume_pairs_preserve_every_value_and_invalidate_changed_inputs(shape)
print('WASM exact volume pair input changes, mutation and budget checks passed',flush=True)
for flag in [0,1,-1]:
 test_volume_velocity_keeps_images_exclusions_and_sum_order(flag)
print('WASM exact full volume velocities, images and exclusions passed',flush=True)
for example,dynamic in [('wing-body',False),('wing-body',True),('dae',False)]:
 test_full_body_tangent_equals_original_residual_assembly(example,dynamic)
 print('WASM exact full body tangent passed:',example,'dynamic',dynamic,flush=True)
print('All 10 mirrored body-reuse WASM tests passed',flush=True)
`);
