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
for(const name of ['rectangular','flexible'])py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile('examples/'+name+'.asw'));
for(const [name,path] of [['helper_source','tests/test_frequency_reuse.py'],
 ['test_source',process.env.OPENSWING_TEST_SOURCE||'tests/test_input_column_reuse.py']])
 py.globals.set(name,await readFile(path,'utf8'));
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
module('test_frequency_reuse',helper_source)
t=module('test_input_column_reuse',test_source)
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
for gust in (False,True):run(t.test_reordered_input_columns_are_exact_and_skip_full_probes,gust)
run(t.test_new_inputs_are_built_and_gusts_never_transfer)
run(t.test_mutated_previous_channel_is_rejected_and_new_forcing_is_independent)
patch=Patch()
try:run(t.test_missing_or_failed_sweep_has_no_columns_to_transfer,patch)
finally:patch.restore()
run(t.test_sparse_input_field_columns_and_complete_outputs_transfer_exactly)
for frame,inputs in [('prescribed',['acceleration.x','angular_acceleration.y']),('free',['target.force.x','target.moment.y'])]:
 run(t.test_canonical_frame_input_columns_transfer_with_original_units,frame,inputs)
assert cases==8
`);
await writeFile(process.env.OPENSWING_REPORT||'/tmp/openswing-input-column-reuse-wasm.json',
 JSON.stringify({status:'PASS',cases:8,pyodide:py.version,modules},null,2)+'\n');
console.log('8 input-column reuse WebAssembly tests passed.');
