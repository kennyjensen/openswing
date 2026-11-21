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
for(const name of ['test_network','test_direct_circulation','test_geometry_tangent','test_tangent_influences','test_body_tangent_reuse','test_propulsion'])
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
 module=types.ModuleType(name);module.pytest=types.SimpleNamespace(raises=raises,approx=lambda value,rel=1e-6,abs=1e-12:Approx(value,rel,abs));sys.modules[name]=module
 exec(compile(tree,name+'.py','exec'),module.__dict__)
 return module
class Approx:
 def __init__(self,value,rel,absolute):self.value,self.rel,self.absolute=value,rel,absolute
 def __eq__(self,other):return bool(np.isclose(other,self.value,rtol=self.rel,atol=self.absolute))
load_tests('test_network');load_tests('test_direct_circulation');g=load_tests('test_geometry_tangent')
t=load_tests('test_tangent_influences');b=load_tests('test_body_tangent_reuse');p=load_tests('test_propulsion')
cases=0
def run(function,*args,patch=False):
 global cases
 p=Patch()
 try:function(*args,**({'monkeypatch':p} if patch else {}))
 finally:p.undo()
 cases+=1;print('WASM',cases,function.__name__,str(args),flush=True)
for shape in [(72,72),(1,72),(72,1),(8,23)]:
 for flag in [0,1,-1]:
  for compressible in [False,True]:run(t.test_every_changed_pair_matches_full_kernel_exactly,flag,compressible,shape)
for change in ['wind','pg','ground','shape','mask','dtype']:
 run(t.test_changed_global_state_does_not_reuse_stale_values,change)
for shape in [(72,83),(1,83),(83,1),(8,23)]:
 run(b.test_volume_pairs_preserve_every_value_and_invalidate_changed_inputs,shape)
for flag in [0,1,-1]:run(b.test_volume_velocity_keeps_images_exclusions_and_sum_order,flag)
run(p.test_unloaded_jet_keeps_zero_field_and_arbitrarily_weak_power_response)
run(g.test_full_dae_circulation_stencil_preserves_composed_finite_step_terms)
for example,dynamic in [('wing-body',False),('wing-body',True),('dae',False)]:
 run(b.test_full_body_tangent_equals_original_residual_assembly,example,dynamic)
for index in [2,4,9,11]:run(g.test_complete_geometry_columns_match_refined_full_residual,*g.CASES[index])
assert cases==46
`);
if(process.env.OPENSWING_REPORT)await writeFile(process.env.OPENSWING_REPORT,
  JSON.stringify({status:'PASS',cases:46,pyodide:py.version,modules},null,2)+'\n');
console.log('46 influence-matrix reuse WebAssembly checks passed.');
