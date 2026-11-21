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
for(const [name,source] of [['helper_source','tests/test_direct_circulation.py'],['geometry_source','tests/test_geometry_tangent.py'],
 ['test_source',process.env.OPENSWING_TEST_SOURCE||'tests/test_volume_tangent.py']])
 py.globals.set(name,await readFile(source,'utf8'));
py.globals.set('only_fallback',process.env.OPENSWING_ONLY_FALLBACK==='1');
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
module('test_geometry_tangent',geometry_source)
t=module('test_volume_tangent',test_source)
cases=0
def run(function,*args):
 global cases
 function(*args);cases+=1;print('PASS',cases,function.__name__,flush=True)
if not only_fallback:
 run(t.test_partials_against_110_digit_independent_differences)
 for flag in [-1,0,1]:
  for exclusion in ['none','body','bodies','point','points','both']:
   run(t.test_retained_field_matches_complete_source_and_receiver_motion,flag,exclusion)
 run(t.test_singular_excluded_sources_empty_queries_ownership_and_guards)
class Patch:
 def __init__(self):self.entries=[]
 def setattr(self,obj,name,value):
  self.entries.append((obj,name,getattr(obj,name)));setattr(obj,name,value)
 def restore(self):
  for obj,name,value in reversed(self.entries):setattr(obj,name,value)
if not only_fallback:
 for arguments in t.CASES:
  patch=Patch()
  try:run(t.test_complete_coupled_columns_with_both_retained_maps,*arguments,patch)
  finally:patch.restore()
patch=Patch()
try:run(t.test_storage_limit_keeps_complete_physical_stencils,patch)
finally:patch.restore()
assert cases==(1 if only_fallback else 34)
`);
await writeFile(process.env.OPENSWING_REPORT||'/tmp/openswing-volume-tangent-wasm.json',
 JSON.stringify({status:'PASS',cases:py.globals.get('cases'),fallback_only:process.env.OPENSWING_ONLY_FALLBACK==='1',pyodide:py.version,modules},null,2)+'\n');
console.log(py.globals.get('cases')+' retained volume-field WebAssembly checks passed.');
