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
for(const name of ['test_direct_circulation','test_local_rate_tangent','test_compatibility_reuse','test_power_tangent']){
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
for name in ['test_direct_circulation','test_local_rate_tangent','test_compatibility_reuse','test_power_tangent']:module(name)
t=sys.modules['test_local_rate_tangent'];cases=0
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
for name,extra in [('flexible',{}),('flexible',{'circulation_modes':{1:3}}),('wing-body',{'ground_effect':1}),('stepped-wing-body',{'ground_effect':-1}),('stepped-wing-body',{'freeze_influences':True}),('stepped-body',{}),('jet-2',{'powers':{1:50000.}}),('dae',{})]:
 run(t.test_complete_local_motion_columns,name,extra)
run(t.test_unsupported_compositions_fall_back,'torsion-joint')
for stage in ['capture','late']:
 with Patch() as patch:run(t.test_failed_local_partial_restarts_original_complete_columns,stage,patch)
run(t.test_material_damping_and_arbitrary_combined_rate_directions)
with Patch() as patch:run(t.test_incident_field_budget_restores_physical_context,patch)
c=sys.modules['test_compatibility_reuse']
for name in ['flexible','wing-body','torsion-joint','stepped-body','jet-2']:run(c.test_compatibility_reuses_complete_section_jacobian,name)
run(c.test_shared_section_matrix_uses_current_compliance_and_invalidates_loaded_state)
with Patch() as patch:run(c.test_unavailable_section_composition_preserves_previous_complete_rows,patch)
p=sys.modules['test_power_tangent']
for name,frame,extra in [('jet-0','fixed',{'powers':{1:50000.}}),('jet-1','free',{'powers':{1:50000.}}),('jet-2','fixed',{'powers':{1:50000.}}),('jet-2','free',{'powers':{1:50000.},'freeze_influences':True}),('dae','fixed',{}),('dae','free',{}),('jet-0','fixed',{})]:
 run(p.test_complete_power_column_matches_refined_physical_stencils,name,frame,extra)
for stage in ['capture','late']:
 with Patch() as patch:run(p.test_unavailable_power_chain_keeps_original_full_stencils,stage,patch)
run(p.test_direct_power_fields_share_the_same_complete_jet_chain)

`);
if(py.globals.get('cases')!==30)throw new Error('Missing composed-matrix cases');
const result=JSON.stringify({status:'PASS',cases:py.globals.get('cases'),pyodide:py.version,modules},null,2)+'\n';
if(process.env.OPENSWING_RESULTS)await writeFile(process.env.OPENSWING_RESULTS,result);
console.log('PASS 30 local motion, compatibility reuse and power derivative checks in WebAssembly');
