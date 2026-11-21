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
for(const name of ['rectangular','flexible','wing-body','powered','articulated','stepped-body','dae'])
  py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile('examples/'+name+'.asw'));
py.FS.mkdirTree('/home/pyodide/tests/fixtures');
py.FS.writeFile('/home/pyodide/tests/fixtures/dae-geometry-equilibrium.json',await readFile('tests/fixtures/dae-geometry-equilibrium.json'));
for(const name of ['test_direct_circulation','test_geometry_tangent'])
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
load_tests('test_direct_circulation');g=load_tests('test_geometry_tangent')
cases=0
def run(function,*args,patch=False):
 global cases
 p=Patch()
 try:function(*args,**({'monkeypatch':p} if patch else {}))
 finally:p.undo()
 cases+=1;print('WASM',cases,function.__name__,str(args),flush=True)
for case in g.CASES:run(g.test_complete_geometry_columns_match_refined_full_residual,*case)
for example in ['rectangular','stepped-wing-body','jet-2','dae']:
 run(g.test_field_only_evaluation_matches_original_queries,example)
run(g.test_full_dae_circulation_stencil_preserves_composed_finite_step_terms)
for frozen in [False,True]:run(g.test_spatial_gust_driven_jet_geometry_in_both_influence_modes,frozen)
for factor in [0.,.6,1.]:run(g.test_steady_chart_including_continuation_and_frame_loads,factor)
for example in ['wing-body','jet-2']:run(g.test_large_rotations_and_cached_pair_path_keep_complete_columns,example)
run(g.test_full_newton_correction_preserves_forward_order_and_refines_to_physical_columns)
for example in ['flexible','wing-body','dae']:run(g.test_newton_geometry_assembly_preserves_converged_physical_base,example,patch=True)
run(g.test_failed_local_partial_restores_full_load_cache,patch=True)
run(g.test_unavailable_field_derivative_restores_full_dynamic_stencils,patch=True)
run(g.test_jet_disk_crossing_refuses_split_geometry_columns)
assert cases==32
`);
if(process.env.OPENSWING_REPORT)await writeFile(process.env.OPENSWING_REPORT,
  JSON.stringify({status:'PASS',cases:32,pyodide:py.version,modules},null,2)+'\n');
console.log('32 full geometry derivative WebAssembly checks passed.');
