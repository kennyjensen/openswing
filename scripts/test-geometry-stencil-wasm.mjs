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
 ['test_source',process.env.OPENSWING_TEST_SOURCE||'tests/test_geometry_stencil.py']])
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
t=module('test_geometry_stencil',test_source)
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
for example,extra in t.CASES:
 run(t.test_all_grouped_samples_match_individual_fields,example,extra)
run(t.test_absolute_chart_and_forward_stencil_match_each_sample)
run(t.test_budget_layout_and_declared_dependency_guards)
for example,extra in [('flexible',{'circulation_modes':{1:3}}),('wing-body',{'ground_effect':1}),
 ('wing-body',{'ground_effect':-1}),('wing-body',{'freeze_influences':True}),('powered',{'powers':{1:7}})]:
 patch=Patch()
 try:run(t.test_complete_pencil_and_output_fields_equal_individual_geometry,example,extra,patch)
 finally:patch.restore()
run(t.test_nonzero_local_motion_and_signed_zero_keep_individual_fields)
patch=Patch()
try:run(t.test_failed_group_preparation_releases_reserved_budget_and_context,patch)
finally:patch.restore()
assert cases==22
`);
await writeFile(process.env.OPENSWING_REPORT||'/tmp/openswing-geometry-stencil-wasm.json',
 JSON.stringify({status:'PASS',cases:22,pyodide:py.version,modules},null,2)+'\n');
console.log('22 grouped geometry WebAssembly checks passed.');
