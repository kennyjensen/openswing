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
for(const name of ['transient-wing','powered','wing-body','inertial'])
  py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile('examples/'+name+'.asw'));
for(const name of ['test_structured_time','test_structured_time_frames','test_network','test_time_integration'])
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

load_tests('test_structured_time',test_structured_time_source)
frames=load_tests('test_structured_time_frames',test_structured_time_frames_source)
for example,extra,frame,targets in [
 ('transient-wing',{'circulation_modes':{1:3}},'free',None),
 ('powered',{'powers':{1:30}},'mixed',{'force.x':.1,'moment.y':.2}),
 ('wing-body',{'position_earth':[0,0,30],'attitude':[13,-7,21],'rates':[.003,-.002,.001],'ground_effect':1},'mixed',{'force.z':.5})]:
 frames.test_grouped_load_rows_match_individual_columns_and_full_border(example,extra,frame,targets)
 print('WASM grouped frame loads and full border:',example,frame,flush=True)
load_tests('test_network',test_network_source)
physical=load_tests('test_time_integration',test_time_integration_source)
physical.test_rigid_free_fall_has_second_order_position_and_exact_velocity()
print('WASM independent rigid free fall and temporal refinement: PASS',flush=True)
physical.test_free_aerodynamic_trajectory_satisfies_independent_rigid_newton_euler_balance()
print('WASM independent aerodynamic Newton-Euler balance: PASS',flush=True)
`);
if(process.env.OPENSWING_REPORT)await writeFile(process.env.OPENSWING_REPORT,JSON.stringify({status:'PASS',cases:5,pyodide:py.version,modules},null,2)+'\n');
console.log('5 structured free/mixed time WASM checks passed.');
