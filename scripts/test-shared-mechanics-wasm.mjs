import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=process.cwd();
const kernel=process.env.OPENSWING_KERNEL||root;
const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
const py=await loadPyodide({indexURL:root+'/public/runtime'});
await py.loadPackage(['numpy','scipy']);
for(const dir of ['openswing','examples'])py.FS.mkdirTree('/home/pyodide/'+dir);
const modules={};
for(const name of (await readdir(kernel+'/openswing')).filter(n=>n.endsWith('.py'))){
 const bytes=await readFile(kernel+'/openswing/'+name);modules[name]=createHash('sha256').update(bytes).digest('hex');
 py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
}
for(const name of ['rectangular','flexible','wing-body','articulated','powered','dae'])
 py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile(root+'/examples/'+name+'.asw'));
for(const name of ['test_direct_circulation','test_network','test_joints','test_mechanical_groups','precision_reference','test_direct_mechanics','test_shared_newton_mechanics'])
 py.globals.set(name+'_source',await readFile((root+'/tests')+'/'+name+'.py','utf8'));
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
for name in ['test_direct_circulation','test_network','test_joints','test_mechanical_groups','precision_reference','test_direct_mechanics','test_shared_newton_mechanics']:module(name)
t=sys.modules['test_shared_newton_mechanics'];d=sys.modules['test_direct_mechanics'];cases=0
class Patch:
 def __init__(self):self.entries=[]
 def setattr(self,obj,name,value):
  self.entries.append((obj,name,getattr(obj,name)));setattr(obj,name,value)
 def restore(self):
  for obj,name,value in reversed(self.entries):setattr(obj,name,value)
 def __enter__(self):return self
 def __exit__(self,*args):self.restore()
 def context(self):return Patch()
def run(function,*args):
 global cases
 function(*args);cases+=1;print('PASS',cases,function.__name__,flush=True)
for factor in [0.,.37,1.]:
 for reverse in [False,True]:run(t.test_shared_hinge_partial_respects_continued_zero_angle_and_both_traces,factor,reverse)
for example,frame in [('flexible','prescribed'),('wing-body','free'),('powered','mixed'),('torsion-joint','prescribed'),('dae','free')]:
 run(t.test_shared_newton_blocks_match_full_residual_and_leave_other_columns,example,frame)
with Patch() as patch:run(t.test_direct_budget_fallback_restores_original_matrix_and_counts,patch)
for branch in [False,True]:run(t.test_continued_hinge_branch_falls_back_to_the_original_newton_stencil,branch)
for example,frame in [('flexible','prescribed'),('powered','mixed'),('torsion-joint','prescribed'),('wing-body','free')]:
 with Patch() as patch:run(t.test_shared_blocks_preserve_complete_converged_equilibrium,example,frame,patch)
with Patch() as patch:run(t.test_newton_capture_keeps_load_only_path_and_the_original_base_residual,patch)
for example in ['flexible','torsion-joint']:
 for factor in [0.,.37]:
  for moving in [False,True]:run(t.test_complete_newton_jacobian_shares_the_physical_load_columns,example,factor,moving)
with Patch() as patch:run(t.test_complete_newton_storage_fallback_preserves_legacy_columns,patch)
for stiffness in [1.,1e18]:run(d.test_axis_jumps_coupled_compliance_and_weak_entries_match_80_digit_physics,stiffness)
for case in [('flexible','free',{'circulation_modes':{1:3}}),('powered','fixed',{'powers':{1:7}}),('torsion-joint','fixed',{})]:
 run(d.test_all_internal_and_reaction_columns_match_full_physical_derivatives,*case)
for joint,ground in [(0,1),(1,2),(2,0)]:run(d.test_all_ground_joint_blocks_match_independent_force_couples,joint,ground)
run(d.test_hinge_slope_break_and_logarithm_branch_keep_original_probes)
assert cases==37,cases
`);
const result=JSON.stringify({status:'PASS',cases:37,pyodide:py.version,modules},null,2)+'\n';
if(process.env.OPENSWING_RESULTS)await writeFile(process.env.OPENSWING_RESULTS,result);
console.log('PASS 37 shared mechanical matrix checks in WebAssembly');
