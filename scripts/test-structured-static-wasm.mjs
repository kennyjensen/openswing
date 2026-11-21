import {loadPyodide} from 'pyodide';
import {readFile,readdir} from 'node:fs/promises';
import path from 'node:path';
const root=process.argv[2]??process.cwd(),py=await loadPyodide({indexURL:path.resolve('public/runtime')});
await py.loadPackage(['numpy','scipy']);
py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/examples');
for(const n of (await readdir(root+'/openswing')).filter(n=>n.endsWith('.py')))
 py.FS.writeFile('/home/pyodide/openswing/'+n,await readFile(root+'/openswing/'+n,'utf8'));
for(const n of ['rectangular','flexible','wing-body','powered','articulated','dae'])py.FS.writeFile('/home/pyodide/examples/'+n+'.asw',await readFile(root+'/examples/'+n+'.asw','utf8'));
const tests=(await Promise.all(['test_structured_static.py','test_structured_dispatch.py','test_structured_rank.py'].map(n=>readFile(root+'/tests/'+n,'utf8')))).join('\n');
py.globals.set('test_source',tests);
await py.runPythonAsync(`
import ast,unittest
from types import SimpleNamespace
module=ast.parse(test_source)
module.body=[node for node in module.body if not (isinstance(node,ast.Import) and any(a.name=='pytest' for a in node.names))]
for node in module.body:
 if isinstance(node,ast.FunctionDef): node.decorator_list=[]
exec(compile(module,'test_structured_static.py','exec'))
def fail(message):raise AssertionError(message)
pytest=SimpleNamespace(raises=lambda exc,match:unittest.TestCase().assertRaisesRegex(exc,match),fail=fail)
class MonkeyPatch:
 def __init__(self):self.items=[]
 def setattr(self,obj,key,value):
  self.items.append((obj,key,getattr(obj,key)));setattr(obj,key,value)
 def undo(self):
  for obj,key,value in reversed(self.items):setattr(obj,key,value)
for example,extra in [('rectangular',{}),('flexible',{}),('wing-body',{}),('powered',{'powers':{1:50.}}),('articulated',{}),('dae',{}),('flexible',{'circulation_modes':{1:3}}),('wing-body',{'freeze_influences':True})]:
 test_grouped_structural_columns_equal_the_entire_lagged_linearization(example,extra)
 print('WASM structured derivative and block-solve check passed:',example,extra,flush=True)
test_failed_linearization_restores_full_fields()
for asymmetric in [False,True]:
 for example in ['flexible','wing-body']:
  test_nonlinear_prototype_converges_to_full_physical_equilibrium(example,asymmetric)
  print('WASM complete physical equilibrium check passed:',example,'asymmetric',asymmetric,flush=True)
for case in ['mounted','vacuum','trim','seed','dynamic']:
 patch=MonkeyPatch()
 try:test_dispatch_and_fallback(patch,case)
 finally:patch.undo()
for function in [test_direct_structured_fallback_uses_original_solver,test_inconclusive_certificate_uses_exact_full_check,test_failed_sparse_direction_retries_the_full_physical_tangent,test_field_budget_failure_restores_physics_before_full_solver_fallback]:
 patch=MonkeyPatch()
 try:function(patch)
 finally:patch.undo()
test_certificate_is_conservative_for_ill_conditioned_and_singular_blocks()
for ground in ['1 0 1','1 0 0'+chr(10)+'1 0 0']:
 test_coupled_mechanisms_and_redundant_reactions_are_rejected(ground)
print('All 25 mirrored sparse structured WASM checks passed',flush=True)
`);
