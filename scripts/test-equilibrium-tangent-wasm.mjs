import {loadPyodide} from '../node_modules/pyodide/pyodide.mjs';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const py=await loadPyodide({indexURL:path.resolve('public/runtime')});
await py.loadPackage(['numpy','scipy']);
for(const dir of ['openswing','examples'])py.FS.mkdirTree('/home/pyodide/'+dir);
const modules={};
for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py'))){
  const bytes=await readFile('openswing/'+name);modules[name]=createHash('sha256').update(bytes).digest('hex');
  py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
}
for(const name of ['rectangular','flexible','wing-body','powered'])
  py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile('examples/'+name+'.asw'));
for(const name of ['test_network','test_time_integration','test_frequency_response','test_frequency_sweep','test_equilibrium_tangent','test_equilibrium_rank'])
  py.globals.set(name+'_source',await readFile('tests/'+name+'.py','utf8'));
await py.runPythonAsync(`
import ast,sys,types,re
from contextlib import contextmanager
import numpy as np
@contextmanager
def raises(kind,match=None):
 try:yield
 except kind as exc:assert match is None or re.search(match,str(exc))
 else:raise AssertionError('Expected exception was not raised')
class Patch:
 def __init__(self):self.saved=[]
 def setattr(self,obj,name,value):
  self.saved.append((obj,name,getattr(obj,name)));setattr(obj,name,value)
 @contextmanager
 def context(self):
  child=Patch()
  try:yield child
  finally:child.undo()
 def undo(self):
  for obj,name,value in reversed(self.saved):setattr(obj,name,value)
  self.saved=[]
def load_tests(name):
 tree=ast.parse(globals()[name+'_source'])
 tree.body=[n for n in tree.body if not isinstance(n,ast.Import) or all(a.name!='pytest' for a in n.names)]
 for node in tree.body:
  if isinstance(node,ast.FunctionDef):node.decorator_list=[]
 module=types.ModuleType(name);module.pytest=types.SimpleNamespace(raises=raises);sys.modules[name]=module
 exec(compile(tree,name+'.py','exec'),module.__dict__)
 return module
for name in ['test_network','test_time_integration','test_frequency_response']:load_tests(name)
g=load_tests('test_equilibrium_tangent');s=load_tests('test_frequency_sweep');r=load_tests('test_equilibrium_rank')
cases=0
def run(function,*args,patch=False):
 global cases
 p=Patch()
 try:function(*args,**({'monkeypatch':p} if patch else {}))
 finally:p.undo()
 cases+=1;print('WASM',cases,function.__name__,str(args),flush=True)
for case in g.CASES:run(g.test_warm_equilibrium_block_is_reused_without_changing_full_pencil,*case)
run(g.test_matrix_ownership_step_and_physical_changes_invalidate_reuse)
run(g.test_changed_difference_step_rebuilds_every_equilibrium_column)
for sparse in [False,True]:run(g.test_absolute_rotation_rank_map_uses_spatial_derivatives_at_large_rotation,sparse)
run(g.test_saved_unloaded_mechanism_cannot_bypass_final_rank_check)
run(s.test_new_run_reuses_loaded_matrices_after_grid_discard_and_input_change,patch=True)
for change in ['condition','mesh','step','frame','gravity','model','mutated_base']:
 run(s.test_changed_operator_cannot_reuse_loaded_matrices,change,patch=True)
run(r.test_large_sparse_check_avoids_dense_conversion_and_svd,patch=True)
for floor in [1e-25,1e-32,1e-35]:run(r.test_certificate_respects_original_column_norm_floor,floor)
for delta in [0.,1e-13,1.8e-10,2.2e-10,1e-9]:run(r.test_singular_and_threshold_cases_match_full_svd,delta)
run(r.test_dense_and_inconclusive_sparse_paths_keep_exact_svd_diagnostic,patch=True)
run(r.test_inverse_residual_prevents_a_false_certificate,patch=True)
run(r.test_general_nonnormal_matrices_have_conservative_bounds)
run(r.test_zero_matrix_and_nonfinite_data_cannot_be_certified)
assert cases==32
`);
if(process.env.OPENSWING_REPORT)await writeFile(process.env.OPENSWING_REPORT,
  JSON.stringify({status:'PASS',cases:32,pyodide:py.version,modules},null,2)+'\n');
console.log('32 equilibrium matrix reuse WebAssembly checks passed.');
