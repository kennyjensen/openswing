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
for(const name of ['rectangular','transient-wing','flexible','powered','wing-body','articulated','inertial'])
  py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile('examples/'+name+'.asw'));
for(const name of ['test_direct_circulation','test_direct_time_circulation','test_network','test_time_integration'])
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

load_tests('test_direct_circulation',test_direct_circulation_source)
direct=load_tests('test_direct_time_circulation',test_direct_time_circulation_source)
for example,extra,frame,circulation,previous_step in [
 ('flexible',{'circulation_modes':{1:3}},'mixed',.3,.013),
 ('wing-body',{'ground_effect':1,'position_earth':[0,0,30],'attitude':[13,-7,21]},'free',.08,None),
 ('jet-2',{'powers':{1:50000.}},'free',.3,.013),
 ('rectangular',{'aero_lag':False},'free',.3,None),
 ('torsion-joint',{},'mixed',.3,.013)]:
 direct.test_direct_bdf_columns_match_refined_full_physical_differences(example,extra,frame,circulation,previous_step)
 print('WASM complete BDF circulation and rate columns:',example,flush=True)
 direct.test_load_only_time_residual_is_identical_to_detailed_equations(example,extra,frame,circulation)
 print('WASM load-only and complete reporting residuals are identical:',example,flush=True)
load_tests('test_network',test_network_source)
physical=load_tests('test_time_integration',test_time_integration_source)
physical.test_rigid_free_fall_has_second_order_position_and_exact_velocity()
print('WASM independent rigid free fall and temporal refinement: PASS',flush=True)
physical.test_free_aerodynamic_trajectory_satisfies_independent_rigid_newton_euler_balance()
print('WASM independent aerodynamic Newton-Euler balance: PASS',flush=True)
`);
if(process.env.OPENSWING_REPORT)await writeFile(process.env.OPENSWING_REPORT,JSON.stringify({status:'PASS',cases:12,pyodide:py.version,modules},null,2)+'\n');
console.log('12 direct unsteady circulation WASM checks passed.');
