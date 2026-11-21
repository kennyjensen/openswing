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
for(const [name,path] of [['helper_source','tests/test_direct_circulation.py'],
 ['test_source',process.env.OPENSWING_TEST_SOURCE||'tests/test_shared_vortex_sources.py']])
 py.globals.set(name,await readFile(path,'utf8'));
py.FS.writeFile('/home/pyodide/field_product_assertions.py',await readFile((process.env.OPENSWING_TEST_ROOT||root+'/tests')+'/field_product_assertions.py'));
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
t=module('test_shared_vortex_sources',test_source)
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
for flag in [-1,0,1]:
 for kind in ['none','mixed','one','all','empty','single']:
  run(t.test_shared_vortex_changes_equal_separate_evaluation,flag,kind)
run(t.test_source_context_layout_ownership_and_core_mask_guards)
for example,extra in [('flexible',{'circulation_modes':{1:3}}),('wing-body',{'ground_effect':1}),
 ('wing-body',{'ground_effect':-1}),('wing-body',{'freeze_influences':True}),('powered',{'powers':{1:7}})]:
 patch=Patch()
 try:run(t.test_complete_operators_equal_separate_vortex_changes,example,extra,patch)
 finally:patch.restore()
for function in [t.test_one_source_change_per_field_and_complete_budget_accounting,
                 t.test_shared_storage_and_query_fallback_preserve_fields]:
 patch=Patch()
 try:run(function,patch)
 finally:patch.restore()
assert cases==26
`);
await writeFile(process.env.OPENSWING_REPORT||'/tmp/openswing-shared-vortex-wasm.json',
 JSON.stringify({status:'PASS',cases:26,pyodide:py.version,modules},null,2)+'\n');
console.log('26 shared vortex-source WebAssembly checks passed.');
