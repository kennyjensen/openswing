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
for(const name of ['test_direct_circulation','test_support_outputs','test_strut_matrix_reuse']){
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
for name in ['test_direct_circulation','test_support_outputs','test_strut_matrix_reuse']:module(name)
t=sys.modules['test_strut_matrix_reuse'];cases=0
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
for name in ['dae','tension','compression','wire_taut','wire_slack','zero_stiffness']:
 run(t.test_same_strut_blocks_supply_nodal_and_output_matrices,name)
for name in ['dae','tension','wire_taut','wire_slack']:
 run(t.test_complete_geometry_reuses_strut_blocks_without_subtraction,name)
run(t.test_stale_or_wrong_owner_strut_context_restores_full_physics)
i=sys.modules['test_support_outputs']
for name in i.CASES:run(i.test_complete_support_matrix_against_high_precision_nonlinear_law,name)
run(i.test_reuse_ownership_and_physical_mutation_invalidation)
run(i.test_budget_nonfinite_and_wire_boundary_keep_physical_fallback)
run(i.test_public_output_has_exact_complex_linearity_across_input_amplitudes)
`);
if(py.globals.get('cases')!==24)throw new Error('Missing gust cases');
const result=JSON.stringify({status:'PASS',cases:py.globals.get('cases'),pyodide:py.version,modules},null,2)+'\n';
if(process.env.OPENSWING_RESULTS)await writeFile(process.env.OPENSWING_RESULTS,result);
console.log('PASS 24 strut matrix reuse and ownership checks in WebAssembly');
