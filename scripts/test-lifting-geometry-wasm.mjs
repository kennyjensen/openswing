import {loadPyodide} from '../node_modules/pyodide/pyodide.mjs';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=process.cwd(),kernel=process.env.OPENSWING_KERNEL||root;
const py=await loadPyodide({indexURL:root+'/public/runtime'});
await py.loadPackage(['numpy','scipy']);
for(const dir of ['openswing','examples'])py.FS.mkdirTree('/home/pyodide/'+dir);
const modules={};
for(const name of (await readdir(kernel+'/openswing')).filter(n=>n.endsWith('.py'))){
 const bytes=await readFile(kernel+'/openswing/'+name);modules[name]=createHash('sha256').update(bytes).digest('hex');
 py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
}
for(const name of ['rectangular','flexible','wing-body','articulated','stepped-body','powered','dae'])
 py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile('examples/'+name+'.asw'));
py.globals.set('helper_source',await readFile('tests/test_direct_circulation.py','utf8'));
py.globals.set('test_source',await readFile(process.env.OPENSWING_TEST_SOURCE||'tests/test_lifting_geometry_reuse.py','utf8'));
await py.runPythonAsync(`
import ast,sys,types
def module(name,source):
 tree=ast.parse(source)
 tree.body=[n for n in tree.body if not isinstance(n,ast.Import) or all(a.name!='pytest' for a in n.names)]
 for node in tree.body:
  if isinstance(node,ast.FunctionDef):node.decorator_list=[]
 result=types.ModuleType(name);sys.modules[name]=result
 exec(compile(ast.fix_missing_locations(tree),name+'.py','exec'),result.__dict__)
 return result
module('test_direct_circulation',helper_source)
t=module('test_lifting_geometry_reuse',test_source)
class Patch:
 def __init__(self):self.entries=[]
 def setattr(self,obj,name,value):
  self.entries.append((obj,name,getattr(obj,name)));setattr(obj,name,value)
 def restore(self):
  for obj,name,value in reversed(self.entries):setattr(obj,name,value)
cases=0
def run(function,*args):
 global cases
 function(*args);cases+=1;print('PASS',cases,function.__name__,flush=True)
for example in ['rectangular','flexible','wing-body','articulated','dae','stepped-body']:
 run(t.test_each_geometry_dependency_preserves_complete_uncached_values,example)
patch=Patch()
try:run(t.test_whole_surface_reuse_and_storage_fallback,patch)
finally:patch.restore()
for location in ['frames','frame0','frame1']:
 run(t.test_changed_wind_alignment_keeps_original_rejection,location)
for example,extra in [('flexible',{'circulation_modes':{1:3}}),('wing-body',{'ground_effect':1}),
 ('wing-body',{'ground_effect':-1}),('wing-body',{'freeze_influences':True}),('powered',{'powers':{1:7}})]:
 patch=Patch()
 try:run(t.test_complete_pencil_and_output_fields_equal_full_recomputation,example,extra,patch)
 finally:patch.restore()
run(t.test_array_map_owns_exact_typed_keys_and_results)
run(t.test_array_map_nonfinite_inputs_keep_physical_evaluation)
assert cases==17
`);
await writeFile(process.env.OPENSWING_REPORT||'/tmp/openswing-lifting-geometry-wasm.json',
 JSON.stringify({status:'PASS',cases:17,pyodide:py.version,modules},null,2)+'\n');
console.log('17 retained lifting-geometry WebAssembly checks passed.');
