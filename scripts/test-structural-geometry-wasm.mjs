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
for(const name of ['test_direct_circulation','test_structural_geometry','test_shared_transfer_matrices']){
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
for name in ['test_direct_circulation','test_structural_geometry','test_shared_transfer_matrices']:module(name)
t=sys.modules['test_structural_geometry'];cases=0
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
for chart in ['absolute','spatial']:
 for name,typ in [('flexible',0),('wing-body',0),('articulated',0),('articulated',1),('articulated',2)]:
  run(t.test_structural_geometry_against_complete_unloaded_residual,name,typ,chart)
for name,frame,extra in [('flexible','free',{'circulation_modes':{1:3}}),('wing-body','prescribed',{'ground_effect':1}),('jet-2','free',{'powers':{1:50000.}}),('stepped-wing-body','fixed',{'freeze_influences':True})]:
 run(t.test_shared_structural_and_flow_columns_preserve_complete_physics,name,frame,extra)
with Patch() as patch:run(t.test_unsupported_hinge_and_storage_retain_original_geometry,patch)
u=sys.modules['test_shared_transfer_matrices']
for quadrature in [False,True]:
 for width in [1,4,16]:
  with Patch() as patch:run(u.test_physical_and_derivative_loads_share_exact_owned_weights,patch,quadrature,width)
run(u.test_actual_geometry_fraction_dtype_and_shape_invalidate_transfer_weights)
with Patch() as patch:run(u.test_zero_storage_budget_preserves_uncached_physical_transfer,patch)
`);
if(py.globals.get('cases')!==23)throw new Error('Missing structural geometry cases');
const result=JSON.stringify({status:'PASS',cases:py.globals.get('cases'),pyodide:py.version,modules},null,2)+'\n';
if(process.env.OPENSWING_RESULTS)await writeFile(process.env.OPENSWING_RESULTS,result);
console.log('PASS 23 structural geometry and shared transfer checks in WebAssembly');
