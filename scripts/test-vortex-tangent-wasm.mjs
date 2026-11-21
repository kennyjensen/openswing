import {loadPyodide} from '../node_modules/pyodide/pyodide.mjs';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=process.cwd();
const kernel=process.env.OPENSWING_KERNEL||root;
const py=await loadPyodide({indexURL:root+'/public/runtime'});
await py.loadPackage(['numpy','scipy']);
py.FS.mkdirTree('/home/pyodide/openswing');
const modules={};
for(const name of (await readdir(kernel+'/openswing')).filter(n=>n.endsWith('.py'))){
 const bytes=await readFile(kernel+'/openswing/'+name);
 modules[name]=createHash('sha256').update(bytes).digest('hex');
 py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
}
py.globals.set('test_source',await readFile(root+'/tests/test_vortex_tangent.py','utf8'));
await py.runPythonAsync(`
import ast,re,types
from contextlib import contextmanager
@contextmanager
def raises(kind,match=None):
 try:yield
 except kind as exc:assert match is None or re.search(match,str(exc))
 else:raise AssertionError('Expected exception was not raised')
pytest=types.SimpleNamespace(raises=raises)
tree=ast.parse(test_source)
tree.body=[node for node in tree.body if not isinstance(node,ast.Import) or all(a.name!='pytest' for a in node.names)]
for node in tree.body:
 if isinstance(node,ast.FunctionDef):node.decorator_list=[]
exec(compile(ast.fix_missing_locations(tree),'<vortex derivative checks>','exec'))
cases=0
def run(function,*args):
 global cases
 function(*args);cases+=1;print('PASS',function.__name__,args,flush=True)
for finite in [False,True]:
 for core in [0.,.13]:run(test_direct_receiver_and_source_partials_match_integrated_physical_derivatives,finite,core)
 run(test_near_axis_and_far_field_partials_against_110_digit_reference,finite)
for flag in [-1,0,1]:
 run(test_complete_horseshoe_pg_images_direction_and_bound_exclusion,flag)
 run(test_retained_field_action_matches_full_moving_sources_receivers_and_cores,flag)
run(test_translation_normalization_principal_value_and_switch_guards)
for receiver_y in [.5,2.]:run(test_retained_field_rejects_masked_bound_stencils_but_preserves_exclusions,receiver_y)
assert cases==15
`);
await writeFile(process.env.OPENSWING_REPORT||root+'/vortex-tangent-wasm.json',JSON.stringify({status:'PASS',cases:15,pyodide:py.version,modules},null,2)+'\n');
console.log('15 direct-vortex derivative WASM checks passed.');
