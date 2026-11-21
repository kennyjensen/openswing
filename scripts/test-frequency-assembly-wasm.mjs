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
for(const name of ['rectangular','flexible','wing-body','powered','articulated','instrumented-oscillator'])
  py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile('examples/'+name+'.asw'));
for(const name of ['test_network','test_feedback','test_direct_circulation','test_frequency_reuse','test_frequency_assembly','test_small_motion_reuse'])
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
for name in ['test_network','test_feedback','test_direct_circulation']:load_tests(name)
r=load_tests('test_frequency_reuse');a=load_tests('test_frequency_assembly');s=load_tests('test_small_motion_reuse')
cases=0
def run(function,*args,patch=False):
 global cases
 p=Patch()
 try:function(*args,**({'monkeypatch':p} if patch else {}))
 finally:p.undo()
 cases+=1;print('WASM',cases,function.__name__,str(args),flush=True)
for example,frame,extra,circulation in [
 ('rectangular','fixed',{},.08),('flexible','free',{'circulation_modes':{1:3}},.3),
 ('wing-body','free',{'ground_effect':1},.08),('wing-body','fixed',{'ground_effect':-1},.08),
 ('stepped-wing-body','free',{'freeze_influences':True},.08),('torsion-joint','free',{},.3),
 ('rectangular','free',{},1.2),('rectangular','free',{'aero_lag':False},.3),
 ('jet-0','free',{'powers':{1:50000.}},.3),('jet-1','free',{'powers':{1:50000.}},.3),
 ('jet-2','free',{'powers':{1:50000.}},.3)]:
 run(a.test_direct_dynamic_columns_match_complete_refined_residual,example,frame,extra,circulation)
for example,frame in [('wing-body','fixed'),('wing-body','free'),('powered','free'),('controlled','fixed')]:
 run(a.test_single_evaluation_outputs_equal_original_including_input_and_rate_feedthrough,example,frame,patch=True)
run(a.test_unavailable_direct_columns_fall_back_to_original_pencil,patch=True)
run(a.test_failed_capture_restores_physical_fields,patch=True)
for example in ['wing-body','powered']:
 for frame in ['fixed','free']:
  for panels in [4,16]:run(r.test_cached_node_and_element_rotations_preserve_complete_moving_residual,example,frame,panels)
for dtype in [np.float16,np.float32,np.float64]:
 for count in [1,2,4,8,32]:run(r.test_row_keys_preserve_signed_zero_on_noncontiguous_views,dtype,count)
run(r.test_mixed_inputs_keep_uncached_physical_columns_and_gust_phase)
run(r.test_mixed_sweep_matches_uncached_complete_outputs_and_extends_safely,patch=True)
run(r.test_failed_sweep_does_not_commit_partial_input_columns,patch=True)
for count in [1,2,4,8]:
 for rate in [0.,1e-18,.2]:run(s.test_short_arc_and_wrench_maps_equal_full_recalculation,count,rate)
for count in [1,4,8]:run(s.test_cached_stationary_arc_still_rejects_pi_rotation,count)
run(s.test_short_maps_respect_budget_and_changed_shapes_and_types)
run(s.test_empty_row_maps_keep_original_empty_result)
for example in ['wing-body','jet-2']:
 for kind in ['zero','negative_zero','tiny','moving']:
  run(s.test_stationary_fields_and_motion_fallback_equal_original_physics,example,kind,patch=True)
for change in ['shape','nan']:run(s.test_malformed_motion_fields_keep_the_original_validation,change)
run(s.test_stationary_field_shortcut_keeps_the_surface_arc_domain_check,patch=True)
assert cases==71
`);
if(process.env.OPENSWING_REPORT)await writeFile(process.env.OPENSWING_REPORT,
  JSON.stringify({status:'PASS',cases:71,pyodide:py.version,modules},null,2)+'\n');
console.log('71 frequency assembly and motion reuse WebAssembly checks passed.');
