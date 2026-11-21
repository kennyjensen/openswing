import {loadPyodide} from '../node_modules/pyodide/pyodide.mjs';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const py=await loadPyodide({indexURL:path.resolve('public/runtime')});
await py.loadPackage(['numpy','scipy']);
for(const name of ['openswing','examples'])py.FS.mkdirTree('/home/pyodide/'+name);
const modules={};
for(const name of (await readdir('openswing')).filter(name=>name.endsWith('.py'))){
  const bytes=await readFile('openswing/'+name);
  modules[name]=createHash('sha256').update(bytes).digest('hex');
  py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
}
for(const name of ['axial-torsion','stress-wing'])py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile('examples/'+name+'.asw'));
py.globals.set('test_source',await readFile('tests/test_derivative_sections.py','utf8'));
const count=await py.runPythonAsync(`
import ast
module=ast.parse(test_source)
module.body=[node for node in module.body if not isinstance(node,ast.Import) or all(alias.name!='pytest' for alias in node.names)]
cases=[]
for node in module.body:
 if not isinstance(node,ast.FunctionDef) or not node.name.startswith('test_'):continue
 choices=[{}]
 for decorator in node.decorator_list:
  assert ast.unparse(decorator.func)=='pytest.mark.parametrize'
  names=ast.literal_eval(decorator.args[0]).split(',');values=ast.literal_eval(decorator.args[1])
  choices=[dict(old,**dict(zip(names,value if len(names)>1 else [value]))) for old in choices for value in values]
 node.decorator_list=[]
 cases.extend((node.name,choice) for choice in choices)
exec(compile(module,'test_derivative_sections.py','exec'))
for name,arguments in cases:
 globals()[name](**arguments)
 print('WASM section derivatives:',name,arguments,flush=True)
len(cases)
`);
console.log(`${count} section-derivative WASM checks passed.`);
if(process.env.OPENSWING_REPORT)await writeFile(process.env.OPENSWING_REPORT,JSON.stringify({status:'PASS',cases:count,pyodide:py.version,modules},null,2)+'\n');
