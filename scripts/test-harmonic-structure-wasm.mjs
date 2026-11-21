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
for(const name of ['rectangular.asw','flexible.asw','wing-body.asw','powered.asw','articulated.asw',
  'instrumented-oscillator.asw','forced-oscillator.asw','initial-spring.json'])
  py.FS.writeFile('/home/pyodide/examples/'+name,await readFile('examples/'+name));
const helpers=['test_network','test_feedback','test_harmonic_structure'];
for(const name of helpers)py.globals.set(name+'_source',await readFile('tests/'+name+'.py','utf8'));
await py.runPythonAsync(`
import ast,sys,types,re,builtins,inspect
from contextlib import contextmanager
import numpy as np
@contextmanager
def raises(kind,match=None):
 try:yield
 except kind as exc:assert match is None or re.search(match,str(exc))
 else:raise AssertionError('Expected exception was not raised')
class Approx:
 def __init__(self,value,rel=None,abs=None):
  self.value=value
  self.rel=(1e-6 if abs is None else 0.) if rel is None else rel
  self.abs=1e-12 if abs is None else abs
 def __eq__(self,actual):return builtins.abs(actual-self.value)<=max(self.abs,self.rel*builtins.abs(self.value))
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
 module=types.ModuleType(name);module.pytest=types.SimpleNamespace(raises=raises,approx=Approx);sys.modules[name]=module
 exec(compile(tree,name+'.py','exec'),module.__dict__)
 return module
for name in ['test_network','test_feedback']:load_tests(name)
t=load_tests('test_harmonic_structure')
cases=0
def run(function,*args,patch=False):
 global cases
 p=Patch()
 keywords=dict(zip((name for name in inspect.signature(function).parameters if name!='monkeypatch'),args))
 if patch:keywords['monkeypatch']=p
 try:function(**keywords)
 finally:p.undo()
 cases+=1;print('WASM',cases,function.__name__,str(args),flush=True)
for diagonal in [False,True]:
 for units in [False,True]:run(t.test_permuted_blocks_recover_all_rhs_and_full_inverse_adjoint,diagonal,units)
for example,frame,extra in [
 ('rectangular','fixed',{}),('flexible','free',{'circulation_modes':{1:3}}),
 ('wing-body','free',{'ground_effect':1,'attitude':[11,-7,23],'position_earth':[0,0,30]}),
 ('powered','fixed',{'powers':{1:7}}),('articulated','fixed',{})]:
 run(t.test_physical_pencils_keep_every_state_and_full_condition_gate,example,frame,extra)
run(t.test_controller_and_material_damping_preserve_rate_coupling)
run(t.test_rows_with_derivative_terms_are_not_treated_as_static)
for delta in [0.,1e-12]:run(t.test_singular_or_poorly_conditioned_optional_pivots_are_rejected,delta)
run(t.test_storage_mutability_missing_structure_and_owner_guards)
for delta in [0.,1e-13,1e-10,1e-7]:run(t.test_full_pencil_near_pole_gate_survives_a_well_conditioned_beam_block,delta)
for failure in ['factor','inverse','solution','residual']:run(t.test_failed_optional_reduction_uses_original_solver,failure,patch=True)
run(t.test_frequency_runs_and_extensions_share_only_matching_beam_factors,patch=True)
assert cases==23
`);
if(process.env.OPENSWING_REPORT)await writeFile(process.env.OPENSWING_REPORT,
  JSON.stringify({status:'PASS',cases:23,pyodide:py.version,modules},null,2)+'\n');
console.log('23 reusable harmonic structure WebAssembly checks passed.');
