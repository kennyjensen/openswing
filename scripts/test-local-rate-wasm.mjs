// Exercise the complete canonical-frame derivative tests in the browser runtime.
import {loadPyodide} from '../node_modules/pyodide/pyodide.mjs';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const hash=data=>createHash('sha256').update(data).digest('hex');
const pins={};
const load=async file=>{const bytes=await readFile(file);pins[file]=hash(bytes);return bytes;};
const started=performance.now();
try {
  const py=await loadPyodide({indexURL:path.resolve('public/runtime')});
  await py.loadPackage(['numpy','scipy']);
  for(const directory of ['openswing','examples'])py.FS.mkdirTree('/home/pyodide/'+directory);
  for(const name of (await readdir('openswing')).filter(name=>name.endsWith('.py')))
    py.FS.writeFile('/home/pyodide/openswing/'+name,await load('openswing/'+name));
  for(const name of ['wing-body','flexible','powered'])
    py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await load('examples/'+name+'.asw'));
  for(const name of ['test_direct_circulation','test_output_fields','test_local_rate_tangent'])
    py.globals.set(name+'_source',(await load('tests/'+name+'.py')).toString());
  await py.runPythonAsync(`
import ast,sys,types,re
from contextlib import contextmanager
@contextmanager
def raises(kind,match=None):
 try:yield
 except kind as exc:assert match is None or re.search(match,str(exc)),str(exc)
 else:raise AssertionError('Expected exception was not raised')
class Patch:
 def __init__(self):self.saved=[]
 def setattr(self,obj,name,value):
  self.saved.append((obj,name,getattr(obj,name)));setattr(obj,name,value)
 @contextmanager
 def context(self):
  child=Patch()
  try:yield child
  finally:child.undo()
 def undo(self):
  for obj,name,value in reversed(self.saved):setattr(obj,name,value)
  self.saved=[]
def load_tests(name):
 tree=ast.parse(globals()[name+'_source'])
 tree.body=[node for node in tree.body if not isinstance(node,ast.Import) or all(alias.name!='pytest' for alias in node.names)]
 for node in tree.body:
  if isinstance(node,ast.FunctionDef):node.decorator_list=[]
 module=types.ModuleType(name);module.pytest=types.SimpleNamespace(raises=raises);sys.modules[name]=module
 exec(compile(tree,name+'.py','exec'),module.__dict__)
 return module
load_tests('test_direct_circulation');load_tests('test_output_fields')
tests=load_tests('test_local_rate_tangent');completed=[]
def run(function,*args,patch=False):
 owner=Patch()
 try:function(*args,**({'monkeypatch':owner} if patch else {}))
 finally:owner.undo()
 completed.append(dict(test=function.__name__,arguments=[str(x) for x in args]))
 print('WASM local rates:',len(completed),function.__name__,str(args),flush=True)
run(tests.test_canonical_frame_load_rows_match_full_rate_columns_and_combined_directions,'wing-body','free',{})
run(tests.test_canonical_frame_load_rows_match_full_rate_columns_and_combined_directions,'jet-2','mixed',{'powers':{1:50000.}})
for kind in ['cross_axis','custom','feedback','owned_capture']:
 run(tests.test_canonical_extension_preserves_unsupported_contexts,kind)
for failure in [RuntimeError,MemoryError,KeyboardInterrupt]:
 run(tests.test_canonical_rate_capture_releases_owner_when_a_group_fails,failure,patch=True)
run(tests.test_free_frame_optimization_preserves_full_matrices_and_output_field_recovery,patch=True)
run(tests.test_material_damping_and_arbitrary_combined_rate_directions)
assert len(completed)==11
`);
  for(const [file,expected] of Object.entries(pins))
    if(hash(await readFile(file))!==expected)throw new Error('Source changed during tests: '+file);
  const report={status:'PASS',cases:11,pyodide:py.version,elapsed_seconds:(performance.now()-started)/1000,
    scope:'Current source modules in actual Pyodide; canonical frame-load columns, full-residual comparisons, matrix/output parity and cleanup.',
    source_sha256:pins,tests:JSON.parse(await py.runPythonAsync('import json\njson.dumps(completed)'))};
  if(process.env.OPENSWING_REPORT)await writeFile(process.env.OPENSWING_REPORT,JSON.stringify(report,null,2)+'\n');
  console.log('11 local-rate WebAssembly checks passed in',report.elapsed_seconds.toFixed(2),'seconds.');
  process.exit(0);
} catch(error) {
  const report={status:'FAIL',error:String(error),elapsed_seconds:(performance.now()-started)/1000,source_sha256:pins};
  if(process.env.OPENSWING_REPORT)await writeFile(process.env.OPENSWING_REPORT,JSON.stringify(report,null,2)+'\n');
  console.error(error);process.exit(1);
}
