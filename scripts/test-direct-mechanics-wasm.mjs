import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=process.cwd(),kernel=process.env.OPENSWING_KERNEL||root,tests=process.env.OPENSWING_TEST_ROOT||root+'/tests';
const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
const py=await loadPyodide({indexURL:root+'/public/runtime'});
await py.loadPackage(['numpy','scipy']);
for(const dir of ['openswing','examples'])py.FS.mkdirTree('/home/pyodide/'+dir);
const modules={};
for(const name of (await readdir(kernel+'/openswing')).filter(n=>n.endsWith('.py'))){
 const bytes=await readFile(kernel+'/openswing/'+name);modules[name]=createHash('sha256').update(bytes).digest('hex');
 py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
}
for(const name of ['rectangular','flexible','wing-body','articulated','powered','instrumented-oscillator'])
 py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile('examples/'+name+'.asw'));
for(const name of ['test_direct_circulation','test_feedback','test_network','test_joints','test_mechanical_groups','precision_reference','test_direct_mechanics'])
 py.globals.set(name+'_source',await readFile((['test_mechanical_groups','precision_reference','test_direct_mechanics'].includes(name)?tests:root+'/tests')+'/'+name+'.py','utf8'));
const firstCase=Number(process.env.OPENSWING_FIRST_CASE||1);
py.globals.set('first_case',firstCase);
await py.runPythonAsync(`
import ast,sys,types,re
class Raises:
 def __init__(self,expected,match=None):self.expected=expected;self.match=match
 def __enter__(self):return self
 def __exit__(self,kind,value,tb):
  assert kind is not None,'Expected exception was not raised'
  if not issubclass(kind,self.expected):return False
  assert self.match is None or re.search(self.match,str(value)),str(value)
  return True
pytest=types.SimpleNamespace(raises=Raises)
def module(name):
 tree=ast.parse(globals()[name+'_source'])
 tree.body=[n for n in tree.body if not isinstance(n,ast.Import) or all(a.name!='pytest' for a in n.names)]
 for node in tree.body:
  if isinstance(node,ast.FunctionDef):node.decorator_list=[]
 result=types.ModuleType(name);sys.modules[name]=result;result.pytest=pytest
 exec(compile(ast.fix_missing_locations(tree),name+'.py','exec'),result.__dict__)
 return result
for name in ['test_direct_circulation','test_feedback','test_network','test_joints','test_mechanical_groups','precision_reference']:module(name)
t=module('test_direct_mechanics');g=sys.modules['test_mechanical_groups'];cases=0
class Patch:
 def __init__(self):self.entries=[]
 def setattr(self,obj,name,value):
  self.entries.append((obj,name,getattr(obj,name)));setattr(obj,name,value)
 def restore(self):
  for obj,name,value in reversed(self.entries):setattr(obj,name,value)
def run(function,*args):
 global cases
 cases+=1
 if cases>=first_case:
  function(*args);print('PASS',cases,function.__name__,flush=True)
def patched(function,*args):
 patch=Patch()
 try:run(function,*args,patch)
 finally:patch.restore()
for example,frame,extra in t.CASES:run(t.test_all_internal_and_reaction_columns_match_full_physical_derivatives,example,frame,extra)
for joint in [0,1,2]:
 for ground in [0,1,2]:
  run(t.test_all_ground_joint_blocks_match_independent_force_couples,joint,ground)
  for frame in ['fixed','free']:run(g.test_reaction_columns_have_only_the_declared_physical_support,joint,ground,frame)
patched(t.test_direct_storage_limit_keeps_existing_physical_fallback)
for example in ['flexible','torsion-joint']:
 for stationary in [False,True]:patched(t.test_dense_dynamic_and_stationary_operators_keep_physical_partials,example,stationary)
for stiffness in [1.,1e18]:run(t.test_axis_jumps_coupled_compliance_and_weak_entries_match_80_digit_physics,stiffness)
for reverse in [False,True]:run(t.test_nonlinear_hinge_chain_includes_both_moment_traces_and_offset_axes,reverse)
run(t.test_hinge_slope_break_and_logarithm_branch_keep_original_probes)
for example,frame,extra in g.CASES:patched(g.test_complete_operators_equal_individual_reaction_probes,example,frame,extra)
run(g.test_hinge_context_uses_direct_mechanical_columns)
run(g.test_controller_context_retains_individual_reaction_columns)
assert cases==52,cases
`);
await writeFile(process.env.OPENSWING_REPORT||'/tmp/openswing-direct-mechanics-wasm.json',
 JSON.stringify({status:'PASS',cases:53-firstCase,firstCase,lastCase:52,pyodide:py.version,modules},null,2)+'\n');
console.log((53-firstCase)+' direct mechanical and fallback WebAssembly tests passed.');
