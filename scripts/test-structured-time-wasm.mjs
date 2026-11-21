import {loadPyodide} from '../node_modules/pyodide/pyodide.mjs';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const py=await loadPyodide({indexURL:path.resolve('public/runtime')});
await py.loadPackage(['numpy','scipy']);
for(const name of ['openswing','examples'])py.FS.mkdirTree('/home/pyodide/'+name);
const modules={};
for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py'))){
  const bytes=await readFile('openswing/'+name);
  modules[name]=createHash('sha256').update(bytes).digest('hex');
  py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
}
for(const name of ['flexible','powered','wing-body','transient-wing'])
  py.FS.writeFile('/home/pyodide/examples/'+name+'.asw',await readFile('examples/'+name+'.asw'));
py.globals.set('test_source',await readFile('tests/test_structured_time.py','utf8'));
py.globals.set('rank_source',await readFile('tests/test_sparse_rank.py','utf8'));
await py.runPythonAsync(`
import ast
module=ast.parse(test_source)
module.body=[n for n in module.body if not isinstance(n,ast.Import) or all(a.name!='pytest' for a in n.names)]
for node in module.body:
 if isinstance(node,ast.FunctionDef):node.decorator_list=[]
exec(compile(module,'test_structured_time.py','exec'))
for example,extra in [('powered',{'powers':{1:30}}),('flexible',{'circulation_modes':{1:3}}),
 ('wing-body',{'ground_effect':1,'position_earth':[0,0,30],'attitude':[13,-7,21],'rates':[.003,-.002,.001]})]:
 test_grouped_matrix_covers_entire_lagged_bdf_linearization(example,extra)
 print('WASM grouped matrix/full border/sparse solve:',example,flush=True)
test_zero_rate_base_retains_new_apparent_mass_velocity_terms()
print('WASM zero-rate apparent-mass velocity columns: PASS',flush=True)
module=ast.parse(rank_source)
module.body=[n for n in module.body if not isinstance(n,ast.Import) or all(a.name!='pytest' for a in n.names)]
for node in module.body:
 if isinstance(node,ast.FunctionDef):node.decorator_list=[]
exec(compile(module,'test_sparse_rank.py','exec'))
test_matching_equals_exhaustive_rank_on_square_rectangular_and_empty_graphs(csr_matrix)
test_explicit_zeros_and_duplicate_cancellation_are_not_nonzero_edges()
test_transient_wing_48_panel_graph_has_complete_independent_witness()
print('WASM bounded rank: exhaustive small graphs, zero/cancellation and 48-panel witness PASS',flush=True)
`);
if(process.env.OPENSWING_REPORT)await writeFile(process.env.OPENSWING_REPORT,JSON.stringify({status:'PASS',cases:7,pyodide:py.version,modules},null,2)+'\n');
console.log('7 structured-time WASM checks passed.');
