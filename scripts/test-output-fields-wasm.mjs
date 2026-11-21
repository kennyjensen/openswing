import {loadPyodide} from '../node_modules/pyodide/pyodide.mjs';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const root=process.cwd();
const kernel=process.env.OPENSWING_KERNEL||root;
const py=await loadPyodide({indexURL:path.resolve('public/runtime')});
await py.loadPackage(['numpy','scipy']);
for(const dir of ['openswing','examples'])py.FS.mkdirTree('/home/pyodide/'+dir);
const modules={};
for(const name of (await readdir(kernel+'/openswing')).filter(n=>n.endsWith('.py'))){
 const bytes=await readFile(kernel+'/openswing/'+name);modules[name]=createHash('sha256').update(bytes).digest('hex');
 py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
}
for(const name of ['rectangular.asw','flexible.asw','wing-body.asw','powered.asw','articulated.asw'])
 py.FS.writeFile('/home/pyodide/examples/'+name,await readFile('examples/'+name));
py.globals.set('test_source',await readFile('tests/test_output_fields.py','utf8'));
for(const name of ['test_field_refinement','test_stable_vortex','test_output_moments','test_gust_phase_metadata'])
 py.globals.set(name+'_source',await readFile('tests/'+name+'.py','utf8'));
for(const name of ['test_direct_circulation','test_aero_lag'])
 py.globals.set(name+'_source',await readFile('tests/'+name+'.py','utf8'));
await py.runPythonAsync(`
import ast,sys,types,re,inspect
from contextlib import contextmanager
@contextmanager
def raises(kind,match=None):
 try:yield
 except kind as exc:assert match is None or re.search(match,str(exc))
 else:raise AssertionError('Expected exception was not raised')
class Patch:
 def __init__(self):self.saved=[]
 def setattr(self,obj,name,value):
  self.saved.append((obj,name,getattr(obj,name)));setattr(obj,name,value)
 def undo(self):
  for obj,name,value in reversed(self.saved):setattr(obj,name,value)
  self.saved=[]
tree=ast.parse(test_source)
tree.body=[n for n in tree.body if not isinstance(n,ast.Import) or all(a.name!='pytest' for a in n.names)]
for node in tree.body:
 if isinstance(node,ast.FunctionDef):node.decorator_list=[]
t=types.ModuleType('test_output_fields');t.pytest=types.SimpleNamespace(raises=raises)
exec(compile(tree,'test_output_fields.py','exec'),t.__dict__)
cases=0
def run(function,*args,patch=False):
 global cases
 p=Patch()
 keywords=dict(zip((name for name in inspect.signature(function).parameters if name!='monkeypatch'),args))
 if patch:keywords['monkeypatch']=p
 try:function(**keywords)
 finally:p.undo()
 cases+=1;print('WASM',cases,function.__name__,str(args),flush=True)
for example,frame,extra in [
 ('rectangular','fixed',{}),('flexible','free',{'circulation_modes':{1:3}}),
 ('wing-body','free',{'ground_effect':1}),('wing-body','fixed',{'freeze_influences':True}),
 ('powered','fixed',{'powers':{1:7}}),('articulated','fixed',{})]:
 run(t.test_shared_state_and_input_probes_preserve_full_matrices_and_physical_outputs,example,frame,extra)
run(t.test_owned_columns_step_and_memory_guards_and_exception_cleanup)
run(t.test_warm_equilibrium_keeps_stationary_fields_and_only_completes_motion_columns)
run(t.test_geometry_fallback_does_not_publish_partial_output_fields,patch=True)
run(t.test_unknown_receiver_restarts_all_output_stencils_on_the_original_path,patch=True)
run(t.test_input_stencil_failure_restores_fields_without_committing_columns,patch=True)
for point in [[1,2,0],[-1,.1,0],[1,-.1,0]]:
 run(t.test_jet_boundary_and_swirl_axis_changes_disable_the_linear_field,point)
class Approx:
 def __init__(self,value,rel=1e-6,abs=1e-12):self.value,self.rel,self.abs=value,rel,abs
 def __eq__(self,value):return abs(value-self.value)<=max(self.abs,self.rel*abs(self.value))
def more_tests(name):
 tree=ast.parse(globals()[name+'_source'])
 tree.body=[n for n in tree.body if not isinstance(n,ast.Import) or all(a.name!='pytest' for a in n.names)]
 for node in tree.body:
  if isinstance(node,ast.FunctionDef):node.decorator_list=[]
 module=types.ModuleType(name);module.pytest=types.SimpleNamespace(raises=raises,approx=Approx);sys.modules[name]=module
 exec(compile(tree,name+'.py','exec'),module.__dict__)
 return module
f=more_tests('test_field_refinement')
for units in [.01,1.,3.280839895,1000.]:run(f.test_narrow_smooth_fields_converge_in_physical_units,units)
run(f.test_zero_and_linear_columns_need_no_additional_field_evaluations)
run(f.test_fifth_order_error_is_not_missed_when_the_third_derivative_is_zero)
run(f.test_unresolved_or_interrupted_derivatives_are_not_silently_accepted)
v=more_tests('test_stable_vortex')
for core in [0.,1e-12,.003]:
 for finite in [False,True]:run(v.test_near_axis_and_far_fields_retain_small_nonzero_velocities,finite,core)
run(v.test_broadcast_cores_and_existing_principal_value_rule)
run(v.test_regularized_finite_and_wake_segments_match_numerical_integrals)
more_tests('test_direct_circulation')
m=more_tests('test_output_moments')
run(m.test_large_opposing_moments_against_decimal_reference)
for example,extra in [('wing-body',{'ground_effect':1}),('stepped-wing-body',{}),('jet-2',{'powers':{1:50000.}}),('articulated',{})]:
 run(m.test_complete_source_sum_matches_original_physical_moments,example,extra)
run(m.test_vacuum_and_empty_sources_keep_original_availability)
g=more_tests('test_gust_phase_metadata')
for example in ['wing-body','jet-2']:
 for sensors in [False,True]:run(g.test_phase_guard_positions_match_complete_snapshot,example,sensors)
a=more_tests('test_aero_lag')
run(a.test_lag_disabled_saved_launch_and_restart_follow_instantaneous_gust)
assert cases==40
`);
await writeFile(process.env.OPENSWING_REPORT||'/tmp/openswing-output-fields-wasm.json',JSON.stringify({status:'PASS',cases:40,pyodide:py.version,modules},null,2)+'\n');
console.log('40 output-field, moment, geometry and gust WebAssembly checks passed.');
