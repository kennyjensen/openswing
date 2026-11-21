import {loadPyodide} from 'pyodide';
import {readFile,readdir} from 'node:fs/promises';
import path from 'node:path';
const root=process.argv[2]??process.cwd(),py=await loadPyodide({indexURL:path.resolve('public/runtime')});
await py.loadPackage(['numpy','scipy']);
py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/examples');
for(const name of (await readdir(root+'/openswing')).filter(n=>n.endsWith('.py')))
 py.FS.writeFile('/home/pyodide/openswing/'+name,await readFile(root+'/openswing/'+name,'utf8'));
for(const name of ['rectangular','flexible','wing-body','stepped-body','powered','articulated','dae'])
 py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile(root+'/examples/'+name+'.asw','utf8'));
py.globals.set('test_source',await readFile(root+'/tests/test_steady_geometry_reuse.py','utf8'));
await py.runPythonAsync(`
import ast
module=ast.parse(test_source)
module.body=[node for node in module.body if not (isinstance(node,ast.Import) and any(a.name=='pytest' for a in node.names))]
for node in module.body:
 if isinstance(node,ast.FunctionDef):node.decorator_list=[]
exec(compile(module,'test_steady_geometry_reuse.py','exec'))
class MonkeyPatch:
 def __init__(self):self.items=[]
 def setattr(self,obj,key,value):
  self.items.append((obj,key,getattr(obj,key)));setattr(obj,key,value)
 def undo(self):
  for obj,key,value in reversed(self.items):setattr(obj,key,value)
for example,extra in [('rectangular',{}),('flexible',{}),('wing-body',{}),('stepped-body',{}),('powered',{'powers':{1:50.}}),('articulated',{}),('dae',{}),('flexible',{'circulation_modes':{1:3}}),('wing-body',{'freeze_influences':True})]:
 patch=MonkeyPatch()
 try:test_structured_tangent_is_exact_with_geometry_recomputation(example,extra,patch)
 finally:patch.undo()
 print('WASM exact structured tangent:',example,extra,flush=True)
for scope in ['steady','trim','dynamic']:
 patch=MonkeyPatch()
 try:test_full_physical_tangent_is_exact_with_geometry_recomputation(scope,patch)
 finally:patch.undo()
 print('WASM exact full tangent:',scope,flush=True)
test_steady_geometry_invalidates_actual_state_and_obeys_its_budget()
test_fixed_setup_reuses_only_base_circulation_geometry()
print('All 14 exact geometry-reuse WASM checks passed',flush=True)
`);
