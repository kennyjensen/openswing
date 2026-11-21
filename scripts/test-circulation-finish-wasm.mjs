import {loadPyodide} from '../node_modules/pyodide/pyodide.mjs';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const py=await loadPyodide({indexURL:path.resolve('public/runtime')});
await py.loadPackage(['numpy','scipy']);
py.FS.mkdirTree('/home/pyodide/openswing');
py.FS.mkdirTree('/home/pyodide/tests/fixtures');
const modules={};
for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py')).sort()){
  const bytes=await readFile('openswing/'+name);
  modules[name]=createHash('sha256').update(bytes).digest('hex');
  py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
}
for(const name of ['isae-circulation-finish-request.json','isae-circulation-finish-state.npz'])
  py.FS.writeFile('/home/pyodide/tests/fixtures/'+name,await readFile('tests/fixtures/'+name));
py.globals.set('test_source',await readFile('tests/test_circulation_finish.py','utf8'));
const cases=JSON.parse(await py.runPythonAsync(`
import ast,json
tree=ast.parse(test_source)
tree.body=[n for n in tree.body if not (isinstance(n,ast.Import) and any(a.name=='pytest' for a in n.names))]
for node in tree.body:
 if isinstance(node,ast.FunctionDef):node.decorator_list=[]
__file__='/home/pyodide/tests/test_circulation_finish.py'
exec(compile(tree,__file__,'exec'))
class MonkeyPatch:
 def __init__(self):self.items=[]
 def setattr(self,obj,key,value):self.items.append((obj,key,getattr(obj,key)));setattr(obj,key,value)
 def undo(self):
  for obj,key,value in reversed(self.items):setattr(obj,key,value)
completed=[]
for function in [test_saved_browser_stall_reaches_unchanged_full_target,test_flow_correction_rejects_new_unbalanced_aerodynamic_loads]:
 function();completed.append(function.__name__)
for function in [test_unsatisfied_frame_load_rows_skip_circulation_finish,test_lagged_field_context_cannot_certify_a_finished_state]:
 patch=MonkeyPatch()
 try:function(patch);completed.append(function.__name__)
 finally:patch.undo()
for failure in ['unavailable','singular','nonfinite']:
 patch=MonkeyPatch()
 try:test_unavailable_correction_restores_context_and_original_state(patch,failure);completed.append(failure)
 finally:patch.undo()
json.dumps(completed)
`));
if(process.env.OPENSWING_REPORT)await writeFile(process.env.OPENSWING_REPORT,JSON.stringify({status:'PASS',cases,pyodide:py.version,modules},null,2)+'\n');
console.log(`${cases.length} WASM fixed-geometry circulation finish checks passed.`);
