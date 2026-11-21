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
for(const name of ['rectangular','flexible','wing-body','articulated','stepped-body','powered','dae'])
 py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile('examples/'+name+'.asw'));
for(const name of ['test_direct_circulation','test_geometry_tangent','test_field_products']){
 const bytes=await readFile((name==='test_field_products'?tests:root+'/tests')+'/'+name+'.py');
 testSources[name]=createHash('sha256').update(bytes).digest('hex');py.globals.set(name+'_source',bytes.toString());
}
const report={status:'RUNNING',modules,testSources,pyodide:py.version};
const destination=process.env.OPENSWING_REPORT||'/tmp/openswing-field-products-wasm.json';
await writeFile(destination,JSON.stringify(report,null,2)+'\n');
try{
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
module('test_direct_circulation');module('test_geometry_tangent');t=module('test_field_products')
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
for sources in [1,2,7,17]:run(t.test_packed_action_against_independent_80_digit_dot_products,sources)
run(t.test_packing_keeps_fifth_order_geometry_error_visible_to_refinement)
run(t.test_empty_receivers_and_zero_source_columns)
for row in t.PHYSICAL_CASES:
 patch=Patch()
 try:run(t.test_packed_complete_geometry_columns_against_full_physical_residual,*row,patch)
 finally:patch.restore()
for frozen in [False,True]:
 patch=Patch()
 try:run(t.test_packed_spatial_gust_jet_geometry_against_full_physical_residual,frozen,patch)
 finally:patch.restore()
assert cases==21,cases
`);
 report.status='PASS';report.cases=21;
}catch(error){report.status='FAILED';report.error=String(error);throw error;}
finally{await writeFile(destination,JSON.stringify(report,null,2)+'\n');}
console.log('21 field-product and physical geometry WebAssembly tests passed.');
