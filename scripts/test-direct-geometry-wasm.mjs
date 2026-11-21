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
for(const name of ['test_direct_circulation','test_geometry_partials','test_geometry_induced','test_geometry_field_partials','test_direct_geometry_matrix']){
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
for name in ['test_direct_circulation','test_geometry_partials','test_geometry_induced','test_geometry_field_partials','test_direct_geometry_matrix']:module(name)
a=sys.modules['test_geometry_partials'];b=sys.modules['test_geometry_induced'];cases=0
for chart in ['spatial','absolute']:
 for name,extra in a.CASES:
  a.test_local_geometry_columns_match_independent_fourth_order_stencils(name,extra,chart)
  cases+=1;print('PASS',cases,'geometry',name,chart,flush=True)
  b.test_composed_induced_flow_against_original_moving_source_kernels(name,extra,chart)
  cases+=1;print('PASS',cases,'induced',name,chart,flush=True)
a.test_invalid_chart_direction_and_core_tie_are_explicit();cases+=1
b.test_missing_or_stale_maps_and_working_budget_fail_explicitly();cases+=1
c=sys.modules['test_geometry_field_partials']
for chart in ['spatial','absolute']:
 for name,extra in c.CASES:
  c.test_complete_field_jacobians_match_original_physical_stencils(name,extra,chart)
  cases+=1;print('PASS',cases,'complete field',name,chart,flush=True)
assert cases==68,cases
m=sys.modules['test_direct_geometry_matrix']
class Patch:
 def __init__(self):self.entries=[]
 def setattr(self,obj,name,value):
  self.entries.append((obj,name,getattr(obj,name)));setattr(obj,name,value)
 def __enter__(self):return self
 def __exit__(self,*args):
  for obj,name,value in reversed(self.entries):setattr(obj,name,value)
 def context(self):return Patch()
def run(function,*args):
 global cases
 function(*args);cases+=1;print('PASS',cases,function.__name__,flush=True)
for args in m.CASES:run(m.test_complete_geometry_columns_match_refined_full_residual,*args)
for frozen in [False,True]:run(m.test_spatial_gust_driven_jet_geometry_in_both_influence_modes,frozen)
for factor in [0.,.6,1.]:run(m.test_steady_chart_including_continuation_and_frame_loads,factor)
for example in ['wing-body','jet-2']:run(m.test_large_rotations_and_cached_pair_path_keep_complete_columns,example)
for failure in ['constructor','late-column']:
 with Patch() as patch:run(m.test_unavailable_composition_restores_original_complete_matrix,patch,failure)
assert cases==90,cases
`);
const result=JSON.stringify({status:'PASS',cases:90,pyodide:py.version,modules},null,2)+'\n';
if(process.env.OPENSWING_RESULTS)await writeFile(process.env.OPENSWING_RESULTS,result);
console.log('PASS 90 geometry composition checks in WebAssembly');
