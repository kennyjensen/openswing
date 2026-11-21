import {loadPyodide} from '../node_modules/pyodide/pyodide.mjs';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const root=process.cwd(),kernel=process.env.OPENSWING_KERNEL||root;
const py=await loadPyodide({indexURL:path.resolve('public/runtime')});
await py.loadPackage(['numpy','scipy']);
for(const dir of ['openswing','examples'])py.FS.mkdirTree('/home/pyodide/'+dir);
const modules={};
for(const name of (await readdir(kernel+'/openswing')).filter(n=>n.endsWith('.py'))){
 const bytes=await readFile(kernel+'/openswing/'+name);modules[name]=createHash('sha256').update(bytes).digest('hex');
 py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
}
for(const name of ['rectangular','flexible','wing-body','articulated','stepped-body','powered','dae'])
 py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile('examples/'+name+'.asw'));
py.globals.set('helper_source',await readFile('tests/test_direct_circulation.py','utf8'));
const source=await readFile(process.env.OPENSWING_TEST_SOURCE||'tests/test_grouped_circulation_rates.py','utf8');
py.globals.set('test_source',source);
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
t=module('test_grouped_circulation_rates',test_source)
cases=0
for arguments in t.CASES:
 t.test_grouped_rate_columns_preserve_complete_matrix_and_physical_action(*arguments)
 cases+=1;print('PASS',cases,arguments,flush=True)
t.test_grouped_rates_do_not_discard_quadratic_shed_vorticity_drag();cases+=1
assert cases==14
`);
await writeFile(process.env.OPENSWING_REPORT||'/tmp/openswing-grouped-rates-wasm.json',
 JSON.stringify({status:'PASS',cases:14,pyodide:py.version,modules,
  test_source_sha256:createHash('sha256').update(source).digest('hex')},null,2)+'\n');
console.log('14 grouped circulation-rate WebAssembly checks passed.');
