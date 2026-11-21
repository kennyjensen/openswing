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
for(const name of ['transient-wing','flexible','powered','wing-body','articulated','guided-body','inertial'])
  py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile('examples/'+name+'.asw'));
for(const name of ['test_structured_initial_frames','test_network','test_time_integration','test_operating'])
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

initial=load_tests('test_structured_initial_frames',test_structured_initial_frames_source)
for example,extra,frame,targets in [
 ('flexible',{'circulation_modes':{1:3}},'free',None),
 ('powered',{'powers':{1:30}},'mixed',{'force.x':.1,'moment.y':.2}),
 ('wing-body',{'position_earth':[0,0,30],'attitude':[13,-7,21],'ground_effect':1},'free',None),
 ('guided-body',None,'free',None)]:
 initial.test_initial_matrix_local_rows_global_wrenches_and_complete_border(example,extra,frame,targets)
 print('WASM initial matrix, complete global border and zero-load rank:',example,flush=True)
load_tests('test_network',test_network_source)
physical=load_tests('test_time_integration',test_time_integration_source)
physical.test_rigid_free_fall_has_second_order_position_and_exact_velocity()
print('WASM independent rigid free fall and temporal refinement: PASS',flush=True)
physical.test_free_aerodynamic_trajectory_satisfies_independent_rigid_newton_euler_balance()
print('WASM independent aerodynamic Newton-Euler balance: PASS',flush=True)
`);
if(process.env.OPENSWING_REPORT)await writeFile(process.env.OPENSWING_REPORT,JSON.stringify({status:'PASS',cases:6,pyodide:py.version,modules},null,2)+'\n');
console.log('6 structured frame initialization WASM checks passed.');
