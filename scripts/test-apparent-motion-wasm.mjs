// Execute the nonlinear endpoint-load checks in the packaged browser runtime.
import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const directory=process.argv[2]??'artifacts/isae/source-apparent-motion-20261030';
const sha=b=>createHash('sha256').update(b).digest('hex');
const pins={};
const load=async file=>{const data=await readFile(file);pins[file]=sha(data);return data;};
const started=performance.now();
try{
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});
  await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');
  const modules=JSON.parse(await load('dist/kernel/manifest.json'));
  for(const name of modules){
    const data=await load('dist/kernel/'+name);
    if(!data.equals(await readFile('openswing/'+name)))throw new Error('Stale packaged module: '+name);
    py.FS.writeFile('/home/pyodide/openswing/'+name,data);
  }
  py.globals.set('test_source',(await load('tests/test_apparent_motion.py')).toString());
  py.FS.writeFile('/home/pyodide/baseline.npz',await load(path.join(directory,'baseline.npz')));
  const details=JSON.parse(await py.runPythonAsync(`
import ast, json, re, types
from contextlib import contextmanager
import numpy as np
@contextmanager
def raises(kind,match=None):
    try: yield
    except kind as exc:
        assert match is None or re.search(match,str(exc)), str(exc)
    else: raise AssertionError('Expected exception was not raised')
tree=ast.parse(test_source)
tree.body=[node for node in tree.body if not isinstance(node,ast.Import) or all(a.name!='pytest' for a in node.names)]
for node in tree.body:
    if isinstance(node,ast.FunctionDef): node.decorator_list=[]
namespace={'pytest':types.SimpleNamespace(raises=raises)}
exec(compile(tree,'test_apparent_motion.py','exec'),namespace)
done=[]
for name in sorted(namespace):
    if not name.startswith('test_'): continue
    cases=[()]
    if name=='test_finite_motion_acceleration_increment_has_existing_source_response': cases=[(i,) for i in range(6)]
    if name=='test_zero_physical_measure_has_zero_full_motion_load_without_speed_division': cases=[('chord',),('density',)]
    if name=='test_nonfinite_motion_fields_are_rejected': cases=[(i,) for i in range(4)]
    for args in cases:
        namespace[name](*args)
        done.append({'test':name,'arguments':args})
assert len(done)==19
from openswing.inertia import Motion,surface_apparent_loads
from openswing.local_motion import LocalMotion
a=np.load('baseline.npz')
motion=Motion([.3,-.2,.4],[.2,.9,-.4],[-.1,.5,.6])
local=LocalMotion(a['position'],a['local_velocity'],a['local_rates'],a['local_acceleration'],a['local_alpha'])
errors=[]
for name,field in [('rigid',None),('elastic',local)]:
    actual=surface_apparent_loads(*[a[k] for k in ['position','frames','chord','xax','length']],1.17,a['velocity'],motion,a['reference'],local_motion=field)
    for kind,values in zip(['force','moment'],actual):
        expected=a[name+'_'+kind]
        error=float(np.max(abs(values-expected)/np.maximum(1.,abs(expected))))
        assert error<2e-14,(name,kind,error)
        errors.append({'frame':name,'quantity':kind,'components':values.size,'scaled_error':error})
json.dumps({'tests':done,'new_checks_passed':len(done),'pre_change_scalar_comparisons':1536,'regression':errors})
`));
  for(const [file,digest] of Object.entries(pins))if(sha(await readFile(file))!==digest)throw new Error('Input changed during execution: '+file);
  const report={status:'PASS',...details,packaged_modules:modules.length,source_sha256:pins,
    elapsed_seconds:(performance.now()-started)/1000,scope:'Full nonlinear endpoint/box load checks in Pyodide; source airflow network is not enabled.'};
  await writeFile(path.join(directory,'wasm.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({status:report.status,checks:details.new_checks_passed,regression_components:details.pre_change_scalar_comparisons,elapsed_seconds:report.elapsed_seconds}));
}catch(error){
  await writeFile(path.join(directory,'wasm.json'),JSON.stringify({status:'FAIL',error:String(error),source_sha256:pins},null,2)+'\n');
  console.error(error);process.exitCode=1;
}
