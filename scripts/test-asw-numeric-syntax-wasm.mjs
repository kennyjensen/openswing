import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=process.cwd(),kernel=process.env.OPENSWING_KERNEL||root;
const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
try {
 const py=await loadPyodide({indexURL:root+'/public/runtime'});await py.loadPackage(['numpy','scipy']);
 py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/examples');
 const modules={};
 for(const name of (await readdir(kernel+'/openswing')).filter(n=>n.endsWith('.py'))){
  const bytes=await readFile(kernel+'/openswing/'+name);modules[name]=createHash('sha256').update(bytes).digest('hex');
  py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
 }
 py.FS.writeFile('/home/pyodide/examples/rectangular.asw',await readFile(root+'/examples/rectangular.asw'));
 py.globals.set('source',await readFile(root+'/tests/test_asw_numeric_syntax.py','utf8'));
 const count=await py.runPythonAsync(`
import ast,types,re
class Raises:
 def __init__(self,expected,match=None):self.expected=expected;self.match=match
 def __enter__(self):return self
 def __exit__(self,kind,value,tb):
  assert kind is not None
  if not issubclass(kind,self.expected):return False
  assert self.match is None or re.search(self.match,str(value))
  return True
pytest=types.SimpleNamespace(raises=Raises)
tree=ast.parse(source)
tree.body=[n for n in tree.body if not isinstance(n,ast.Import) or all(a.name!='pytest' for a in n.names)]
for node in tree.body:
 if isinstance(node,ast.FunctionDef):node.decorator_list=[]
exec(compile(ast.fix_missing_locations(tree),'test_asw_numeric_syntax.py','exec'))
test_implicit_exponents_match_fortran_read_values()
for token in ['1+-3','1.2.3-4','1e2-3','1-','--1','1+2+3','1e','nan','inf','1.0+999']:
 test_malformed_or_nonfinite_numbers_still_report_the_source_line(token)
test_literal_and_canonical_save_preserve_the_same_physical_model()
12
`);
 const result={status:'PASS',cases:count,modules,pyodide:py.version};
 if(process.env.OPENSWING_RESULTS)await writeFile(process.env.OPENSWING_RESULTS,JSON.stringify(result,null,2)+'\n');
 console.log('PASS',count,'Fortran numeric input WebAssembly checks');
} catch(error){console.error(String(error));process.exitCode=1;}
