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
const helpers=['test_network','test_time_integration','test_feedback','test_direct_circulation',
  'test_frequency_response','test_frequency_reuse','test_frequency_sweep','test_frequency_input_influences'];
for(const name of helpers)py.globals.set(name+'_source',await readFile('tests/'+name+'.py','utf8'));
await py.runPythonAsync(`
import ast,sys,types,re,builtins
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
for name in ['test_network','test_time_integration','test_feedback','test_direct_circulation','test_frequency_response']:load_tests(name)
r=load_tests('test_frequency_reuse');s=load_tests('test_frequency_sweep');i=load_tests('test_frequency_input_influences')
cases=0
def run(function,*args,patch=False):
 global cases
 p=Patch()
 try:function(*args,**({'monkeypatch':p} if patch else {}))
 finally:p.undo()
 cases+=1;print('WASM',cases,function.__name__,str(args),flush=True)
for example,frame in [('rectangular','fixed'),('wing-body','free'),('stepped-wing-body','free'),
 ('jet-0','free'),('jet-1','fixed'),('jet-2','free')]:
 for wave in ['convected','uniform']:
  run(i.test_complete_input_columns_match_uncached_fields_across_frequencies,example,frame,wave)
run(i.test_input_influence_owner_and_exception_cleanup,patch=True)
run(i.test_controller_commands_retain_original_side_and_load_evaluations)
run(i.test_reselected_inputs_share_only_the_matching_owned_model,patch=True)
run(r.test_mixed_inputs_keep_uncached_physical_columns_and_gust_phase)
run(r.test_mixed_sweep_matches_uncached_complete_outputs_and_extends_safely,patch=True)
run(r.test_failed_sweep_does_not_commit_partial_input_columns,patch=True)
run(s.test_refinement_retains_samples_and_exact_frozen_pencil_with_owned_inputs,patch=True)
run(s.test_failed_batch_is_transactional_and_can_be_retried)
run(s.test_gust_refinement_recomputes_streamwise_phase_for_every_new_frequency)
run(s.test_refinement_keeps_dc_gap_and_free_flight_finite_frequency_motion)
run(s.test_initial_spectrum_refinement_keeps_shift_and_initial_rate_subtraction)
run(s.test_json_boundary_rejects_changed_source_settings_expired_and_discarded_sessions)
run(s.test_new_run_reuses_loaded_matrices_after_grid_discard_and_input_change,patch=True)
run(s.test_feedback_refinement_preserves_pi_and_acceleration_feedback_dynamics)
run(s.test_millisecond_refinement_preserves_dimensional_mechanical_response)
for change in ['condition','mesh','step','frame','gravity','model','mutated_base']:
 run(s.test_changed_operator_cannot_reuse_loaded_matrices,change,patch=True)
assert cases==34
`);
if(process.env.OPENSWING_REPORT)await writeFile(process.env.OPENSWING_REPORT,
  JSON.stringify({status:'PASS',cases:34,pyodide:py.version,modules},null,2)+'\n');
console.log('34 frequency input influence and sweep WebAssembly checks passed.');
