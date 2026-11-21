import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
try{
  const bytes=await readFile('docs/validation/stall-parameters.json'),study=JSON.parse(bytes);
  for(const [name,wanted] of Object.entries(study.source_sha256))if(hash(await readFile(name))!==wanted)throw Error('Study source changed: '+name);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  for(const directory of ['openswing','scripts'])py.FS.mkdirTree('/home/pyodide/'+directory);
  const modules=JSON.parse(await readFile('dist/kernel/manifest.json','utf8'));
  for(const name of modules){
    const bytes=await readFile('dist/kernel/'+name);if(!bytes.equals(await readFile('openswing/'+name)))throw Error('Stale packaged kernel: '+name);
    py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
  }
  py.FS.writeFile('/home/pyodide/scripts/verify-stall-parameters.py',await readFile('scripts/verify-stall-parameters.py'));
  await py.runPythonAsync("import runpy,json,numpy as np\nhelpers=runpy.run_path('/home/pyodide/scripts/verify-stall-parameters.py')");
  const selected=study.cases.map((c,i)=>({c,i})).filter(({c})=>!c.specification.span||(c.specification.span===590000&&(c.specification.alpha===25||c.specification.high_precision_reference)));
  if(selected.length!==19)throw Error('Replay selection changed');
  const cases=[];
  for(const {c,i} of selected){
    py.globals.set('case_json',JSON.stringify(c));
    const result=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);spec=c['specification'];out=helpers['compute'](spec)
a,b=helpers['physical'](out),helpers['physical'](c['result'])
assert a.shape==b.shape
error=float(np.max(abs(a-b)/np.maximum(1,abs(b))))
assert error<2e-7,error
reference_error=None
if spec.get('span')==590000:
    ref=helpers['reference'](spec['alpha'],spec['factor'],spec['width'],high_precision=spec.get('high_precision_reference',False))
    reference_error=max(abs(out['coefficients'][k]-ref[k]) for k in ['CL','CD'])
    assert reference_error<1e-4,reference_error
json.dumps(dict(result=out,physical_values_compared=int(a.size),maximum_scaled_native_difference=error,reference_error=reference_error))
`));
    cases.push({native_case:i,specification:c.specification,...result});console.log('Stall parameters replay',i,result.maximum_scaled_native_difference);
  }
  const invalid=JSON.parse(await py.runPythonAsync(`
from openswing.aero import AnalysisError,FlightCondition,solve_rigid
from openswing.asw import parse_asw
model=parse_asw(helpers['source_for']());invalid=[]
for name,values in [('stall_factor',[-1,float('nan'),float('inf'),None,True,'40',10**400]),('stall_width',[0,-1,float('nan'),float('inf'),None,False,'.05',10**400])]:
    for value in values:
        for enabled in [True,False]:
            try: solve_rigid(model,FlightCondition(stall=enabled,**{name:value}),4)
            except AnalysisError as error: invalid.append(dict(parameter=name,value=repr(value),enabled=enabled,message=str(error)))
            else: raise AssertionError((name,value,enabled))
assert len(invalid)==30
json.dumps(invalid)
`));
  py.globals.set('leakage_json',JSON.stringify(study.leakage_checks));
  const leakage_checks=JSON.parse(await py.runPythonAsync(`
from openswing.aero import _stall_leakage
checks=[]
for c in json.loads(leakage_json):
    args=[c[k] for k in ['cl','lower','upper','width']]
    ref=np.array(helpers['reference_leakage'](*args))
    with np.errstate(all='raise'): actual=np.array(_stall_leakage(*args))
    error=float(np.max(abs(actual-ref)/np.maximum(1,abs(ref))))
    assert np.all(np.isfinite(actual)) and error<3e-15,(args,actual,ref,error)
    checks.append(dict(arguments=args,value=float(actual[0]),derivative=float(actual[1]),reference=ref.tolist(),maximum_scaled_error=error))
assert len(checks)==270
json.dumps(checks)
`));
  const corner_checks=JSON.parse(await py.runPythonAsync("json.dumps([helpers['corner_reference'](spread) for spread in [.01,.2]])"));
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>[name,hash(await readFile('dist/runtime/'+name))])));
  await writeFile('docs/validation/stall-parameters-wasm.json',JSON.stringify({study_sha256:hash(bytes),module_count:modules.length,runtime_sha256,
    source_sha256:{...study.source_sha256,'scripts/test-stall-parameters-wasm.mjs':hash(await readFile('scripts/test-stall-parameters-wasm.mjs'))},cases,invalid,leakage_checks,corner_checks},null,2)+'\n');
  process.exit(0);
}catch(error){await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
