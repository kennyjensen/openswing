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
for(const name of ['rectangular','flexible','wing-body','articulated','powered','instrumented-oscillator'])
 py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile('examples/'+name+'.asw'));
for(const [name,file] of [['test_direct_circulation','tests/test_direct_circulation.py'],
 ['test_feedback','tests/test_feedback.py'],['test_mechanical_groups',process.env.OPENSWING_TEST_SOURCE||'tests/test_mechanical_groups.py']])
 py.globals.set(name+'_source',await readFile(file,'utf8'));
await py.runPythonAsync(`
import ast,sys,types
def module(name):
 tree=ast.parse(globals()[name+'_source'])
 tree.body=[n for n in tree.body if not isinstance(n,ast.Import) or all(a.name!='pytest' for a in n.names)]
 for node in tree.body:
  if isinstance(node,ast.FunctionDef):node.decorator_list=[]
 result=types.ModuleType(name);sys.modules[name]=result
 exec(compile(ast.fix_missing_locations(tree),name+'.py','exec'),result.__dict__)
 return result
module('test_direct_circulation');module('test_feedback');t=module('test_mechanical_groups')
cases=0
def run(function,*args):
 global cases
 function(*args);cases+=1;print('PASS',cases,function.__name__,flush=True)
for joint in [0,1,2]:
 for ground in [0,1,2]:
  for frame in ['fixed','free']:run(t.test_reaction_columns_have_only_the_declared_physical_support,joint,ground,frame)
class Patch:
 def __init__(self):self.entries=[]
 def setattr(self,obj,name,value):
  self.entries.append((obj,name,getattr(obj,name)));setattr(obj,name,value)
 def restore(self):
  for obj,name,value in reversed(self.entries):setattr(obj,name,value)
for example,frame,extra in t.CASES:
 patch=Patch()
 try:run(t.test_complete_operators_equal_individual_reaction_probes,example,frame,extra,patch)
 finally:patch.restore()
run(t.test_hinge_context_uses_direct_mechanical_columns)
run(t.test_controller_context_retains_individual_reaction_columns)
assert cases==26
`);
await writeFile(process.env.OPENSWING_REPORT||'/tmp/openswing-mechanical-groups-wasm.json',
 JSON.stringify({status:'PASS',cases:26,pyodide:py.version,modules},null,2)+'\n');
console.log('26 mechanical-group WebAssembly tests passed.');
