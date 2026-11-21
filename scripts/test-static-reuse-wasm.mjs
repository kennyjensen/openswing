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
for(const name of ['flexible','wing-body','stepped-body','dae','powered','articulated','inertial'])
  py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile('examples/'+name+'.asw'));
for(const name of ['test_static_reuse','test_network','test_time_integration'])
  py.globals.set(name+'_source',await readFile('tests/'+name+'.py','utf8'));
await py.runPythonAsync(`
import ast,sys,types

def load_tests(name,source):
 tree=ast.parse(source)
 tree.body=[node for node in tree.body if not isinstance(node,ast.Import) or all(a.name!='pytest' for a in node.names)]
 for node in tree.body:
  if isinstance(node,ast.FunctionDef):node.decorator_list=[]
 module=types.ModuleType(name);sys.modules[name]=module
 exec(compile(tree,name+'.py','exec'),module.__dict__)
 return module

reuse=load_tests('test_static_reuse',test_static_reuse_source)
for example,frame in [('flexible','prescribed'),('wing-body','free'),('stepped-body','prescribed')]:
 reuse.test_fixed_factors_solve_multiple_original_matrix_right_hand_sides(example,frame)
 print('WASM fixed factors versus complete original equations:',example,flush=True)
for example,extra,frame in [
 ('flexible',{},'prescribed'),('dae',{},'free'),('powered',{'powers':{1:30}},'mixed'),
 ('wing-body',{'ground_effect':1,'position_earth':[0,0,30],'attitude':[13,-7,21]},'free'),
 ('articulated',{},'prescribed'),('flexible',{'circulation_modes':{1:3}},'free')]:
 reuse.test_reuse_reaches_the_full_fresh_matrix_equilibrium(example,extra,frame)
 print('WASM reused/fresh equilibrium, full residual and stage safeguards:',example,frame,flush=True)
load_tests('test_network',test_network_source)
physical=load_tests('test_time_integration',test_time_integration_source)
physical.test_rigid_free_fall_has_second_order_position_and_exact_velocity()
physical.test_free_aerodynamic_trajectory_satisfies_independent_rigid_newton_euler_balance()
print('WASM independent free fall/refinement and aerodynamic Newton-Euler balance: PASS',flush=True)
`);
if(process.env.OPENSWING_REPORT)await writeFile(process.env.OPENSWING_REPORT,JSON.stringify({status:'PASS',cases:11,pyodide:py.version,modules},null,2)+'\n');
console.log('11 static matrix reuse WASM checks passed.');
