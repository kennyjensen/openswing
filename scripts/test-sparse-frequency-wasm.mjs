import {loadPyodide} from '../node_modules/pyodide/pyodide.mjs';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const py=await loadPyodide({indexURL:path.resolve('public/runtime')});
await py.loadPackage(['numpy','scipy']);
for(const name of ['openswing','examples'])py.FS.mkdirTree('/home/pyodide/'+name);
const modules={};
for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py'))){
  const bytes=await readFile('openswing/'+name);modules[name]=createHash('sha256').update(bytes).digest('hex');
  py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
}
for(const name of ['rectangular','flexible','wing-body','powered','articulated','instrumented-oscillator'])
  py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile('examples/'+name+'.asw'));
for(const name of ['test_network','test_joints','test_feedback','test_sparse_frequency','test_frequency_local_maps'])
  py.globals.set(name+'_source',await readFile('tests/'+name+'.py','utf8'));
await py.runPythonAsync(`
import ast,sys,types
import numpy as np
from scipy.sparse import csc_matrix
from openswing.frequency_response import harmonic_solve,HarmonicPole

def load_tests(name,source):
 tree=ast.parse(source)
 tree.body=[node for node in tree.body if not isinstance(node,ast.Import) or all(a.name!='pytest' for a in node.names)]
 for node in tree.body:
  if isinstance(node,ast.FunctionDef):node.decorator_list=[]
 module=types.ModuleType(name);sys.modules[name]=module
 exec(compile(tree,name+'.py','exec'),module.__dict__)
 return module
for name in ['test_network','test_joints','test_feedback']:load_tests(name,globals()[name+'_source'])
t=load_tests('test_sparse_frequency',test_sparse_frequency_source)
local=load_tests('test_frequency_local_maps',test_frequency_local_maps_source)
from contextlib import contextmanager
import re
@contextmanager
def raises(kind,match=None):
 try:yield
 except kind as exc:
  assert match is None or re.search(match,str(exc))
 else:raise AssertionError('Expected exception was not raised')
local.pytest=types.SimpleNamespace(raises=raises)
for quadrature in [False,True]:
 for moving in [False,True]:
  local.test_row_maps_match_complete_original_functions_after_every_input_changes(quadrature,moving)
local.test_row_map_budget_disable_shape_change_and_rotation_domain()
print('WASM exact local maps, changed inputs, bounds and domain: PASS',flush=True)
for example,frame,extra in [
 ('rectangular','fixed',{}),('flexible','free',{'circulation_modes':{1:3}}),
 ('wing-body','free',{'ground_effect':1,'attitude':[11,-7,23],'position_earth':[0,0,30]}),
 ('wing-body','fixed',{'ground_effect':-1,'position_earth':[0,0,30]}),
 ('powered','free',{'powers':{1:7}}),('powered','fixed',{'powers':{1:7}}),('articulated','fixed',{})]:
 t.test_sparse_complete_pencil_matches_original_fourth_order_equations(example,frame,extra)
 print('WASM full sparse/dense pencil and harmonic solution:',example,frame,extra,flush=True)
for w in [0.,.7,13.]:t.test_sparse_solve_is_covariant_with_units_and_keeps_algebraic_feedthrough(w)
for a,m,w in [(np.zeros((2,2)),np.eye(2),0.),(np.array([[0.,1.],[-4.,0.]]),np.eye(2),2.),
 (np.array([[1.,1.],[1.,1.+1e-13]]),np.zeros((2,2)),1.)]:
 try:harmonic_solve(csc_matrix(a),csc_matrix(m),np.ones((2,1)),w)
 except HarmonicPole:pass
 else:raise AssertionError('Singularity must remain a gap')
t.test_sparse_feedback_inertia_and_cubic_hinge_match_dense_equations()
print('WASM units, feedthrough, singularities, controller and cubic hinge: PASS',flush=True)
`);
if(process.env.OPENSWING_REPORT)await writeFile(process.env.OPENSWING_REPORT,JSON.stringify({status:'PASS',cases:19,pyodide:py.version,modules},null,2)+'\n');
console.log('19 sparse-frequency WebAssembly checks passed.');
