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
py.globals.set('test_source',await readFile(root+'/tests/test_direct_circulation.py','utf8'));
await py.runPythonAsync(`
import ast, inspect, itertools
module=ast.parse(test_source)
cases=[]
for node in module.body:
 if not isinstance(node,ast.FunctionDef) or not node.name.startswith('test_'):continue
 rows=[{}]
 for decorator in node.decorator_list:
  assert isinstance(decorator,ast.Call) and ast.unparse(decorator.func)=='pytest.mark.parametrize'
  names=[name.strip() for name in ast.literal_eval(decorator.args[0]).split(',')]
  values=ast.literal_eval(decorator.args[1])
  choices=[dict(zip(names,value if len(names)>1 else [value])) for value in values]
  rows=[dict(old,**choice) for old in rows for choice in choices]
 cases.extend((node.name,row) for row in rows)
 node.decorator_list=[]
module.body=[node for node in module.body if not (isinstance(node,ast.Import) and any(a.name=='pytest' for a in node.names))]
exec(compile(module,'test_direct_circulation.py','exec'))
class MonkeyPatch:
 def __init__(self):self.items=[]
 def setattr(self,obj,key,value):
  self.items.append((obj,key,getattr(obj,key)));setattr(obj,key,value)
 def undo(self):
  for obj,key,value in reversed(self.items):setattr(obj,key,value)
for name,arguments in cases:
 function=globals()[name];patch=MonkeyPatch();kwargs=dict(arguments)
 if 'monkeypatch' in inspect.signature(function).parameters:kwargs['monkeypatch']=patch
 assert set(kwargs)==set(inspect.signature(function).parameters),(name,kwargs)
 try:function(**kwargs)
 finally:patch.undo()
 print('WASM direct circulation:',name,arguments,flush=True)
print('All',len(cases),'mirrored direct-circulation WASM checks passed',flush=True)
`);
