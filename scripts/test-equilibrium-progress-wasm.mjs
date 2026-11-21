// Actual local Pyodide warm-equilibrium progress contract. Caller owns timeout.
import {readFile,readdir,mkdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
const root=process.cwd();
const sourceRoot=process.env.OPENSWING_SOURCE_ROOT||path.join(root,'openswing');
const fixture=process.env.OPENSWING_PROGRESS_FIXTURE||path.join(root,'examples/flexible.asw');
const runtime=process.env.OPENSWING_RUNTIME_ROOT||path.join(root,'public/runtime');
const output=process.env.OPENSWING_RESULTS||path.join(root,'test-results',`equilibrium-progress-wasm-${Date.now()}.json`);
const pin=b=>({bytes:b.length,sha256:createHash('sha256').update(b).digest('hex')});
const result={status:'RUNNING',modules:{},runtime:{},network_fetch_attempts:[],sourceRoot,fixture};
const started=performance.now();let py;
globalThis.fetch=async(...args)=>{result.network_fetch_attempts.push(String(args[0]));throw Error('Network fetch prohibited');};
const code=String.raw`
import importlib,json,math,sys,traceback
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import numpy as np
from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.network import StaticNetwork,equilibrate
from openswing.equilibrium_state import capture
import openswing.seeded_corrector as seeded

report=dict(status='RUNNING',checks=[],cases=[],operations=dict(network_constructions=0,equilibrium_API_calls=0,extra_residual_checks=0))
def save():Path('/test-data/result.json').write_text(json.dumps(report,indent=2,allow_nan=False))
def check(name,value,**details):
    report['checks'].append(dict(name=name,pass_=bool(value),**details));save()
    if not value:raise AssertionError(name)
def network(target):
    source=Path('/test-data/flexible.asw').read_text()
    source=source.replace('0 .008 2 -.035 0','0 0 0 0 0').replace('8 .008 2 -.035 -2','8 0 0 0 0')
    model=parse_asw(source)
    assert not model.diagnostics
    report['operations']['network_constructions']+=1
    return StaticNetwork(model,4,FlightCondition(speed=8,alpha=0,mach=.03),[0,0,0],[],
        operating_constraints=[dict(variable='alpha',quantity='force.z',target=target)])
def owners(n):
    return n.iteration_fields is None and n.tangent_influences is None and n._tangent_loads is None
original_attach=seeded.attach
observations=[]
@contextmanager
def observe_attach(*args,**kwargs):
    function=args[1];entry=dict(builder_declined=False,detached=False)
    observations.append(entry)
    try:
        with original_attach(*args,**kwargs) as builder:
            entry['builder_declined']=builder is None
            check('actual native builder declined '+str(len(observations)),builder is None)
            yield builder
    finally:
        entry['detached']=not hasattr(function,'factorization_builder')
        entry['report']=deepcopy(kwargs.get('report'))
try:
    names=json.loads(Path('/test-data/module-names.json').read_text())
    origins={name:str(Path(importlib.import_module('openswing.'+name[:-3]).__file__).resolve()) for name in names}
    check('all imports use supplied source',all(value=='/home/pyodide/openswing/'+name for name,value in origins.items()))
    report['import_origins']=origins
    seeded.attach=observe_attach
    solved=[]
    for enabled in (False,True):
        n=network(10.);initial=capture(n,np.zeros(n.size),residual=None);untouched=deepcopy(initial);events=[]
        progress=(lambda *event:events.append(event)) if enabled else None
        report['operations']['equilibrium_API_calls']+=1;save()
        x,steps=equilibrate(n,tolerance=1e-9,initial_state=initial,progress=progress)
        nfev=n.nfev;diagnostics=deepcopy(n.equilibrium_diagnostics)
        report['operations']['extra_residual_checks']+=1
        residual=n.residual(x);norm=float(np.max(abs(residual)))
        check('finite physical solution '+str(enabled),np.isfinite(x).all() and np.isfinite(residual).all() and norm<=1e-8,residual=norm)
        check('original dense rank gate '+str(enabled),diagnostics['rank_check']=='full-Jacobian SVD' and diagnostics['column_scaled_reciprocal_condition']>=1e-10)
        check('nontrivial correction '+str(enabled),diagnostics['newton_iterations']>0 and diagnostics['tangent_builds']>0)
        check('successful cleanup '+str(enabled),owners(n) and observations[-1]['detached'] and not hasattr(n,'_seeded_corrector_diagnostics'))
        check('unchanged initial seed '+str(enabled),initial==untouched and steps==1)
        if enabled:
            stages={event[0] for event in events}
            check('all declined native progress phases',{'equilibrium_iteration','equilibrium_iteration_tangent','equilibrium_final_tangent','equilibrium_rank_svd'}<=stages,stages=sorted(stages))
            check('finite callback coordinates',all(len(e)==3 and math.isfinite(e[1]) and math.isfinite(e[2]) for e in events))
            for stage in ('equilibrium_iteration_tangent','equilibrium_final_tangent'):
                columns=[event for event in events if event[0]==stage]
                check('complete native column progress '+stage,columns[0]==(stage,0,n.size) and columns[-1]==(stage,n.size,n.size))
            check('warm progress uses equilibrium names',not any(event[0].startswith('time_') or event[0]=='equilibrium_tangent' for event in events))
        else:check('callback absent has no events',events==[])
        solved.append((x.copy(),nfev,diagnostics,norm))
        report['cases'].append(dict(name='callback_on' if enabled else 'callback_off',size=n.size,state=x.tolist(),source_nfev=nfev,diagnostics=diagnostics,fresh_residual=norm,events=events));save()
    check('callback on off state bitwise equality',np.array_equal(solved[0][0],solved[1][0]))
    check('callback on off residual call identity',solved[0][1]==solved[1][1],off=solved[0][1],on=solved[1][1])
    check('callback on off rank and iteration identity',solved[0][2]==solved[1][2])
    check('callback on off fresh residual identity',solved[0][3]==solved[1][3])
    class CallbackFailure(RuntimeError):pass
    for stage in ('equilibrium_iteration','equilibrium_iteration_tangent','equilibrium_final_tangent'):
        n=network(0. if stage=='equilibrium_final_tangent' else 10.)
        initial=capture(n,np.zeros(n.size),residual=None);untouched=deepcopy(initial);events=[]
        error=CallbackFailure(stage);caught=None
        def failing_progress(name,current,total):
            events.append((name,current,total))
            if name==stage:raise error
        report['operations']['equilibrium_API_calls']+=1;save()
        try:equilibrate(n,tolerance=1e-9,initial_state=initial,progress=failing_progress)
        except CallbackFailure as exc:caught=exc
        check('callback failure preserved '+stage,caught is error and events[-1][0]==stage)
        check('callback failure restores owners '+stage,owners(n) and observations[-1]['detached'] and not hasattr(n,'_seeded_corrector_diagnostics'))
        check('callback failure preserves seed and native methods '+stage,initial==untouched and
            n.residual.__func__ is StaticNetwork.residual and n.jacobian.__func__ is StaticNetwork.jacobian)
        check('callback failure has no success diagnostics '+stage,not hasattr(n,'equilibrium_diagnostics'))
        report['cases'].append(dict(name='failure_'+stage,size=n.size,source_nfev=n.nfev,events=events,exception_preserved=True,owners_restored=True));save()
    check('bounded five actual API attempts',report['operations']==dict(network_constructions=5,equilibrium_API_calls=5,extra_residual_checks=2))
    check('all builder contexts detached',len(observations)==5 and all(row['builder_declined'] and row['detached'] for row in observations))
    report['status']='PASS_EQUILIBRIUM_PROGRESS_WASM'
except BaseException as exc:
    report['status']='FAIL_EQUILIBRIUM_PROGRESS_WASM_RETAINED';report['error']=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
    raise
finally:
    seeded.attach=original_attach
    report['builder_observations']=observations
    report['counts']=dict(passed=sum(x['pass_'] for x in report['checks']),total=len(report['checks']),cases_completed=len(report['cases']))
    save()
`;
try{
  const names=(await readdir(sourceRoot)).filter(n=>n.endsWith('.py')).sort();
  const modules=await Promise.all(names.map(async n=>[n,await readFile(path.join(sourceRoot,n))]));
  for(const [n,b] of modules)result.modules[n]=pin(b);
  const model=await readFile(fixture);result.fixture_pin=pin(model);
  for(const n of (await readdir(runtime)).sort())result.runtime[n]=pin(await readFile(path.join(runtime,n)));
  const {loadPyodide}=await import(pathToFileURL(path.join(root,'node_modules/pyodide/pyodide.mjs')).href);
  py=await loadPyodide({indexURL:runtime});result.pyodide=py.version;await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/test-data');
  for(const [n,b] of modules)py.FS.writeFile('/home/pyodide/openswing/'+n,new Uint8Array(b));
  py.FS.writeFile('/test-data/flexible.asw',new Uint8Array(model));
  py.FS.writeFile('/test-data/module-names.json',JSON.stringify(names));
  await py.runPythonAsync(code);
  result.test=JSON.parse(py.FS.readFile('/test-data/result.json',{encoding:'utf8'}));result.status=result.test.status;
  for(const [n,p] of Object.entries(result.modules))if(JSON.stringify(pin(await readFile(path.join(sourceRoot,n))))!==JSON.stringify(p))throw Error('Source changed: '+n);
  if(JSON.stringify(pin(await readFile(fixture)))!==JSON.stringify(result.fixture_pin))throw Error('Fixture changed');
  for(const [n,p] of Object.entries(result.runtime))if(JSON.stringify(pin(await readFile(path.join(runtime,n))))!==JSON.stringify(p))throw Error('Runtime changed: '+n);
  if(result.network_fetch_attempts.length)throw Error('Unexpected network fetch');
  result.inputs_unchanged=true;
}catch(error){
  result.status='FAIL_EQUILIBRIUM_PROGRESS_WASM_RETAINED';result.error={message:String(error),stack:error.stack};
  if(py){try{result.test=JSON.parse(py.FS.readFile('/test-data/result.json',{encoding:'utf8'}));}catch{}}
}finally{
  result.script_pin=pin(await readFile(fileURLToPath(import.meta.url)));result.elapsed_seconds=(performance.now()-started)/1000;
  await mkdir(path.dirname(output),{recursive:true});await writeFile(output,JSON.stringify(result,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({status:result.status,counts:result.test?.counts,operations:result.test?.operations,output,error:result.error??result.test?.error}));
  if(result.status!=='PASS_EQUILIBRIUM_PROGRESS_WASM')process.exitCode=1;
}
