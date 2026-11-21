import {loadPyodide} from '../node_modules/pyodide/pyodide.mjs';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const py=await loadPyodide({indexURL:path.resolve('public/runtime')});
await py.loadPackage(['numpy','scipy']);
for(const name of ['openswing','examples'])py.FS.mkdirTree('/home/pyodide/'+name);
const modules={};
for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py'))){
  const bytes=await readFile('openswing/'+name);
  modules[name]=createHash('sha256').update(bytes).digest('hex');
  py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
}
for(const name of ['dae','inertial','rectangular'])
  py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile('examples/'+name+'.asw'));
for(const name of ['test_vector_ops','test_frame_influence_reuse','test_network','test_time_integration','test_aero','test_volume'])
  py.globals.set(name+'_source',await readFile('tests/'+name+'.py','utf8'));
await py.runPythonAsync(`
import ast,sys,types
import numpy as np

def load_tests(name,source):
 tree=ast.parse(source)
 tree.body=[node for node in tree.body if not isinstance(node,ast.Import) or all(a.name!='pytest' for a in node.names)]
 for node in tree.body:
  if isinstance(node,ast.FunctionDef):node.decorator_list=[]
 module=types.ModuleType(name);sys.modules[name]=module
 exec(compile(tree,name+'.py','exec'),module.__dict__)
 return module

vectors=load_tests('test_vector_ops',test_vector_ops_source)
for dtype in [np.float16,np.float32,np.float64,np.complex128,np.int16,np.int64,np.uint64,np.bool_]:
 vectors.test_dot_preserves_numpy_reduction_values_dtype_and_input_arrays(dtype)
for layout in ['strided','fortran','readonly']:
 vectors.test_dot_handles_layout_and_mixed_precision_without_mutation(layout)
for dtype in [np.float32,np.float64]:vectors.test_dot_retains_signed_zero_and_nonfinite_behavior(dtype)
print('WASM thirteen xyz-reduction checks: PASS',flush=True)
frames=load_tests('test_frame_influence_reuse',test_frame_influence_reuse_source)
for kind in ['static','time']:
 for ground in [0,1,-1]:
  frames.test_every_frame_column_equals_original_uncached_equations(kind,ground)
  print('WASM every full frame column matches uncached physics:',kind,ground,flush=True)
load_tests('test_network',test_network_source)
aero=load_tests('test_aero',test_aero_source)
aero.test_finite_vortex_matches_biot_savart_at_segment_midpoint()
aero.test_semi_infinite_vortex_known_solution()
aero.test_regularized_integral_matches_numerical_quadrature()
volume=load_tests('test_volume',test_volume_source)
volume.test_unregularized_singularities_are_the_gradient_of_their_potential()
physical=load_tests('test_time_integration',test_time_integration_source)
physical.test_rigid_free_fall_has_second_order_position_and_exact_velocity()
physical.test_free_aerodynamic_trajectory_satisfies_independent_rigid_newton_euler_balance()
print('WASM six independent kernel and trajectory checks: PASS',flush=True)
`);
if(process.env.OPENSWING_REPORT)await writeFile(process.env.OPENSWING_REPORT,JSON.stringify({status:'PASS',cases:25,pyodide:py.version,modules},null,2)+'\n');
console.log('25 influence-kernel and full-frame WASM checks passed.');
