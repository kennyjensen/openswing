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
 ['test_source',process.env.OPENSWING_TEST_SOURCE||'tests/test_support_outputs.py']])
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
module('test_direct_circulation',helper_source)
t=module('test_support_outputs',test_source)
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
for name in t.CASES:run(t.test_complete_support_matrix_against_high_precision_nonlinear_law,name)
run(t.test_reuse_ownership_and_physical_mutation_invalidation)
run(t.test_budget_nonfinite_and_wire_boundary_keep_physical_fallback)
run(t.test_public_output_has_exact_complex_linearity_across_input_amplitudes)
assert cases==13
`);
await writeFile(process.env.OPENSWING_REPORT||'/tmp/openswing-support-output-wasm.json',
 JSON.stringify({status:'PASS',cases:13,pyodide:py.version,modules},null,2)+'\n');
console.log('13 support output matrix WebAssembly checks passed.');
