import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=process.cwd(),kernel=process.env.OPENSWING_KERNEL||root,tests=process.env.OPENSWING_TEST_ROOT||root+'/tests';
const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
const py=await loadPyodide({indexURL:root+'/public/runtime'});
await py.loadPackage(['numpy','scipy']);
for(const dir of ['openswing','examples'])py.FS.mkdirTree('/home/pyodide/'+dir);
const modules={},testSources={};
for(const name of (await readdir(kernel+'/openswing')).filter(n=>n.endsWith('.py'))){
 const bytes=await readFile(kernel+'/openswing/'+name);modules[name]=createHash('sha256').update(bytes).digest('hex');
 py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
}
py.FS.writeFile('/home/pyodide/examples/rectangular.asw',await readFile('examples/rectangular.asw'));
for(const name of ['test_network','structural_output_reference','test_structural_outputs']){
 const bytes=await readFile((name==='test_network'?root+'/tests':tests)+'/'+name+'.py');
 testSources[name]=createHash('sha256').update(bytes).digest('hex');py.globals.set(name+'_source',bytes.toString());
}
const report={status:'RUNNING',modules,testSources,pyodide:py.version};
const destination=process.env.OPENSWING_REPORT||'/tmp/openswing-structural-outputs-wasm.json';
await writeFile(destination,JSON.stringify(report,null,2)+'\n');
try{
 await py.runPythonAsync(`
import ast,sys,types,re
class Raises:
 def __init__(self,expected,match=None):self.expected=expected;self.match=match
 def __enter__(self):return self
 def __exit__(self,kind,value,tb):
  assert kind is not None,'Expected exception was not raised'
  if not issubclass(kind,self.expected):return False
  assert self.match is None or re.search(self.match,str(value)),str(value)
  return True
pytest=types.SimpleNamespace(raises=Raises)
def module(name):
 tree=ast.parse(globals()[name+'_source'])
 tree.body=[n for n in tree.body if not isinstance(n,ast.Import) or all(a.name!='pytest' for a in n.names)]
 for node in tree.body:
  if isinstance(node,ast.FunctionDef):node.decorator_list=[]
 result=types.ModuleType(name);sys.modules[name]=result;result.pytest=pytest
 exec(compile(ast.fix_missing_locations(tree),name+'.py','exec'),result.__dict__)
 return result
module('test_network');module('structural_output_reference');t=module('test_structural_outputs');cases=0
def run(function,*args):
 global cases
 function(*args);cases+=1;print('PASS',cases,function.__name__,flush=True)
for name in t.CASES:run(t.test_full_section_matrix_matches_independent_80_digit_physical_values,name)
run(t.test_reuse_is_owned_immutable_and_tracks_every_physical_context)
run(t.test_budget_nonfinite_strain_law_and_rotation_branch_fallbacks)
run(t.test_public_section_outputs_are_linear_and_preserve_geometric_damping_strain)
run(t.test_prescribed_rates_and_aerodynamic_inputs_have_zero_explicit_section_partials)
assert cases==12,cases
`);
 report.status='PASS';report.cases=12;
}catch(error){report.status='FAILED';report.error=String(error);throw error;}
finally{await writeFile(destination,JSON.stringify(report,null,2)+'\n');}
console.log('12 physical structural-output WebAssembly tests passed.');
