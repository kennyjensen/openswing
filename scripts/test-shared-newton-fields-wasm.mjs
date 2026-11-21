process.on('uncaughtException',error=>{console.error(error.message);process.exit(1);});
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
for(const name of ['rectangular','flexible','wing-body','articulated','powered','dae','stepped-body'])
 py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile(root+'/examples/'+name+'.asw'));
for(const name of ['test_direct_circulation','test_newton_structure','test_static_reuse','test_structured_static','test_sparse_full_newton','test_newton_geometry_composition']){
 const folder=process.env.OPENSWING_TESTS||root+'/tests';
 py.globals.set(name+'_source',await readFile(folder+'/'+name+'.py','utf8'));
}
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
for name in ['test_direct_circulation','test_newton_structure','test_static_reuse','test_structured_static','test_sparse_full_newton','test_newton_geometry_composition']:module(name)
t=sys.modules['test_newton_structure'];s=sys.modules['test_static_reuse'];g=sys.modules['test_structured_static'];cases=0
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
for case in t.CASES:run(t.test_owned_factors_solve_original_full_matrix_for_multiple_rhs,*case)
with Patch() as patch:run(t.test_storage_and_corrupt_factor_guards_retain_original_equations,patch)
for failure in ['budget','factor','direction']:
 with Patch() as patch:run(t.test_full_factor_failure_recovers_and_preserves_cold_equilibrium,failure,patch)
for case in [('flexible','prescribed'),('wing-body','free'),('stepped-body','prescribed')]:
 run(s.test_fixed_factors_solve_multiple_original_matrix_right_hand_sides,*case)
for case in [('flexible',{},'prescribed'),('dae',{},'free'),('powered',{'powers':{1:30}},'mixed'),
 ('wing-body',{'ground_effect':1,'position_earth':[0,0,30],'attitude':[13,-7,21]},'free'),
 ('articulated',{},'prescribed'),('flexible',{'circulation_modes':{1:3}},'free')]:
 run(s.test_reuse_reaches_the_full_fresh_matrix_equilibrium,*case)
for failure in ['factor','direction']:
 with Patch() as patch:run(s.test_failed_reuse_rebuilds_at_same_state_before_full_fallback,patch,failure)
run(s.test_corrupt_factor_is_rejected_by_original_linear_equations)
with Patch() as patch:run(g.test_failed_sparse_direction_retries_the_full_physical_tangent,patch)
u=sys.modules['test_sparse_full_newton']
for case in u.CASES:run(u.test_complete_sparse_matrix_is_exactly_the_dense_control,*case)
for fallback in ['geometry','circulation','mechanics-grouped','mechanics-individual','residual-options']:
 with Patch() as patch:run(u.test_sparse_fallbacks_preserve_every_dense_column,fallback,patch)
with Patch() as patch:run(u.test_sparse_assembly_does_not_allocate_a_full_dense_matrix,patch)
assert cases==33,cases
v=sys.modules['test_newton_geometry_composition']
for args in v.CASES:run(v.test_newton_columns_match_refined_complete_physical_residual,*args)
for failure in ['constructor','late-column']:
 with Patch() as patch:run(v.test_unavailable_composition_retains_original_complete_newton_fallback,patch,failure)
run(v.test_refinement_of_local_partial_keeps_exact_shared_field_columns)
assert cases==45,cases
`);
const result=JSON.stringify({status:'PASS',cases:45,pyodide:py.version,modules},null,2)+'\n';
if(process.env.OPENSWING_RESULTS)await writeFile(process.env.OPENSWING_RESULTS,result);
console.log('PASS 45 Newton matrix composition, reuse and sparse-storage checks in WebAssembly');
