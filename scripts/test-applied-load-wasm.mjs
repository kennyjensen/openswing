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
for(const name of ['test_direct_circulation','test_support_outputs','test_applied_load_outputs','test_applied_load_guards']){
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
for name in ['test_direct_circulation','test_support_outputs','test_applied_load_outputs','test_applied_load_guards']:module(name)
t=sys.modules['test_applied_load_outputs'];cases=0
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
for name,frame,extra in [('flexible','fixed',{}),('flexible','free',{'circulation_modes':{1:3}}),('wing-body','prescribed',{'ground_effect':1}),('powered','free',{'powers':{1:7}})]:
 run(t.test_complete_applied_C_Q_D_matches_full_physical_outputs,name,frame,extra)
run(t.test_off_equilibrium_position_term_is_required)
run(t.test_initial_rates_and_complex_scaling_retain_no_direct_input)
run(t.test_operator_input_and_physical_context_ownership)
with Patch() as patch:run(t.test_unavailable_output_matrix_preserves_full_physical_fallback,patch)
run(t.test_internal_resultants_have_exactly_zero_applied_load_partial)
g=sys.modules['test_applied_load_guards']
run(g.test_wire_and_clipping_branches_preserve_physical_output_fallback)
run(g.test_nested_fields_and_controller_context_keep_original_output_path)
run(g.test_frequency_model_reuse_retains_C_Q_and_rebinds_D)
`);
if(py.globals.get('cases')!==12)throw new Error('Missing applied-load cases');
const result=JSON.stringify({status:'PASS',cases:py.globals.get('cases'),pyodide:py.version,modules},null,2)+'\n';
if(process.env.OPENSWING_RESULTS)await writeFile(process.env.OPENSWING_RESULTS,result);
console.log('PASS 12 applied-load C/Q/D and ownership checks in WebAssembly');
