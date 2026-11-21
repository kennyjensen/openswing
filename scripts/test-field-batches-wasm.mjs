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
 ['geometry_source','tests/test_geometry_stencil.py'],['tangent_source','tests/test_geometry_tangent.py'],['volume_source','tests/test_volume_tangent.py'],['vortex_source','tests/test_shared_vortex_sources.py'],['primitive_source',process.env.OPENSWING_PRIMITIVE_SOURCE||'scripts/check-field-batches.py'],['test_source',process.env.OPENSWING_TEST_SOURCE||'tests/test_field_batches.py']])
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
module('test_geometry_stencil',geometry_source)
module('test_geometry_tangent',tangent_source)
module('test_volume_tangent',volume_source)
module('test_shared_vortex_sources',vortex_source)
t=module('test_field_batches',test_source)
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
for example,extra in t.CASES:run(t.test_every_batched_field_sample_equals_original_evaluation,example,extra)
run(t.test_storage_limit_and_missing_query_maps_keep_individual_paths)
run(t.test_batch_length_source_identity_and_receiver_layout_guards)
run(t.test_nonzero_elastic_motion_and_negative_zero_keep_individual_physics)
for example,extra in [('flexible',{'circulation_modes':{1:3}}),('wing-body',{'ground_effect':1}),
 ('wing-body',{'ground_effect':-1}),('wing-body',{'freeze_influences':True}),('powered',{'powers':{1:7}})]:
 patch=Patch()
 try:run(t.test_complete_operators_equal_individual_field_application,example,extra,patch)
 finally:patch.restore()
assert cases==21
from pathlib import Path
Path('/tmp/openswing-batched-field-actions-20261013').mkdir(parents=True,exist_ok=True)
exec(compile(primitive_source,'primitive_source','exec'),{})
`);
const primitive=JSON.parse(py.FS.readFile('/tmp/openswing-batched-field-actions-20261013/primitive-comparison.json',{encoding:'utf8'}));
if(primitive.status!=='PASS')throw new Error('Primitive batch comparisons differ');
await writeFile(process.env.OPENSWING_REPORT||'/tmp/openswing-field-batches-wasm.json',
 JSON.stringify({status:'PASS',cases:21,primitive,pyodide:py.version,modules},null,2)+'\n');
console.log('21 field-batch WebAssembly tests and432primitive comparisons passed.');
