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
for(const name of ['test_direct_circulation','test_frequency_reuse','test_frequency_input_influences','test_gust_tangent']){
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
for name in ['test_direct_circulation','test_frequency_reuse','test_frequency_input_influences','test_gust_tangent']:module(name)
t=sys.modules['test_gust_tangent'];cases=0
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
for name,frame,extra in [('flexible','fixed',{'circulation_modes':{1:3}}),('wing-body','free',{'ground_effect':1}),('stepped-wing-body','fixed',{'ground_effect':-1}),('stepped-wing-body','free',{'freeze_influences':True}),('stepped-body','fixed',{}),('torsion-joint','free',{}),('jet-0','fixed',{'powers':{1:50000.}}),('jet-1','free',{'powers':{1:50000.}}),('jet-2','fixed',{'powers':{1:50000.}}),('dae','fixed',{})]:
 for wave in ['uniform','convected']:run(t.test_complete_complex_gust_column_matches_refined_physical_stencils,name,frame,extra,wave)
for stage in ['capture','late']:
 with Patch() as patch:run(t.test_failed_gust_partial_restores_full_input_stencil,stage,patch)
run(t.test_gust_field_packet_contains_only_the_induced_chain)
i=sys.modules['test_frequency_input_influences']
for name,frame,wave in [('jet-2','free','uniform'),('jet-2','free','convected'),('wing-body','free','convected')]:
 run(i.test_complete_input_columns_match_uncached_fields_across_frequencies,name,frame,wave)
with Patch() as patch:run(i.test_input_influence_owner_and_exception_cleanup,patch)
`);
if(py.globals.get('cases')!==27)throw new Error('Missing gust cases');
const result=JSON.stringify({status:'PASS',cases:py.globals.get('cases'),pyodide:py.version,modules},null,2)+'\n';
if(process.env.OPENSWING_RESULTS)await writeFile(process.env.OPENSWING_RESULTS,result);
console.log('PASS 27 gust input and matrix ownership checks in WebAssembly');
