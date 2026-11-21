import {loadPyodide} from '../node_modules/pyodide/pyodide.mjs';
import {readFile,readdir} from 'node:fs/promises';
import path from 'node:path';

const root=path.resolve(process.argv[2]??'.');
const py=await loadPyodide({indexURL:path.join(root,'public/runtime')});
await py.loadPackage(['numpy','scipy']);
for(const name of ['openswing','examples'])py.FS.mkdirTree('/home/pyodide/'+name);
for(const name of (await readdir(root+'/openswing')).filter(n=>n.endsWith('.py')))
  py.FS.writeFile('/home/pyodide/openswing/'+name,await readFile(root+'/openswing/'+name,'utf8'));
for(const name of ['rectangular','flexible','wing-body','stepped-body','powered','articulated','dae'])
  py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile(root+'/examples/'+name+'.asw','utf8'));
for(const name of ['test_network','test_dynamic_inertia','test_steady_mass_loads'])
  py.globals.set(name+'_source',await readFile(root+'/tests/'+name+'.py','utf8'));
await py.runPythonAsync(`
import ast,inspect
def imports(node):
 if isinstance(node,ast.Import):return not any(a.name=='pytest' for a in node.names)
 return isinstance(node,ast.ImportFrom) and not node.module.startswith('test_')
for source,names in [(test_network_source,['beam','model']),(test_dynamic_inertia_source,['network'])]:
 module=ast.parse(source)
 module.body=[node for node in module.body if imports(node) or isinstance(node,ast.FunctionDef) and node.name in names]
 exec(compile(module,'fixtures','exec'))
mass_network=network
module=ast.parse(test_steady_mass_loads_source);parameters=[]
for node in module.body:
 if not isinstance(node,ast.FunctionDef) or not node.name.startswith('test_'):continue
 parameters.append((node.name,node.decorator_list));node.decorator_list=[]
module.body=[node for node in module.body if not isinstance(node,(ast.Import,ast.ImportFrom)) or imports(node)]
exec(compile(module,'test_steady_mass_loads.py','exec'))
class MonkeyPatch:
 def __init__(self):self.items=[]
 def setattr(self,obj,key,value):
  self.items.append((obj,key,getattr(obj,key)));setattr(obj,key,value)
 def undo(self):
  for obj,key,value in reversed(self.items):setattr(obj,key,value)
count=0
for name,decorators in parameters:
 cases=[{}]
 for decorator in decorators:
  assert isinstance(decorator,ast.Call) and ast.unparse(decorator.func)=='pytest.mark.parametrize'
  names=[name.strip() for name in ast.literal_eval(decorator.args[0]).split(',')]
  values=eval(compile(ast.Expression(decorator.args[1]),'parameters','eval'))
  choices=[dict(zip(names,value if len(names)>1 else [value])) for value in values]
  cases=[dict(old,**choice) for old in cases for choice in choices]
 for arguments in cases:
  patch=MonkeyPatch();kwargs=dict(arguments);function=globals()[name]
  if 'monkeypatch' in inspect.signature(function).parameters:kwargs['monkeypatch']=patch
  assert set(kwargs)==set(inspect.signature(function).parameters),(name,kwargs)
  try:function(**kwargs)
  finally:patch.undo()
  count+=1;print('WASM steady mass:',name,arguments,flush=True)
print('All',count,'mirrored steady-mass WASM checks passed',flush=True)
`);
