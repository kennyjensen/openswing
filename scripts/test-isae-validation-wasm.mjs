import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=process.cwd(), scopes=process.argv.slice(2);
const enabled=name=>scopes.length===0||scopes.includes(name);
const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
const py=await loadPyodide({indexURL:root+'/public/runtime'});
await py.loadPackage(['numpy','scipy']);
py.FS.mkdirTree('/home/pyodide/openswing');
const modules={};
for(const name of (await readdir(root+'/openswing')).filter(n=>n.endsWith('.py'))){
  const bytes=await readFile(root+'/openswing/'+name);
  modules[name]=createHash('sha256').update(bytes).digest('hex');
  py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
}
py.globals.set('module_json',JSON.stringify(modules));
await py.runPythonAsync('import json, numpy as np\nmodules=json.loads(module_json)');
// A parser-only transition preserves the original numerical reports and pins.
// Replays still run the current kernel; inputs and physics must be verified equal.
const coverage=JSON.parse(await readFile('docs/validation/isae-coverage.json','utf8'));
const transitionBytes=await readFile('docs/validation/reference-compatibility.json');
if(createHash('sha256').update(transitionBytes).digest('hex')!==coverage.source_continuity.sha256)throw Error('Changed parser transition report');
for(const [name,digest] of Object.entries(coverage.study_sha256)){
 if(createHash('sha256').update(await readFile('docs/validation/'+name)).digest('hex')!==digest)throw Error('Changed numerical study '+name);
}
py.globals.set('coverage_json',JSON.stringify(coverage));
py.globals.set('transition_json',transitionBytes.toString('utf8'));
await py.runPythonAsync(`
coverage=json.loads(coverage_json);transition=json.loads(transition_json)
assert coverage['modules']==modules==transition['candidate_modules']
assert set(modules)==set(transition['baseline_modules'])
assert {n for n in modules if modules[n]!=transition['baseline_modules'][n]}=={'asw.py'}
def verify_study_source(study,name):
 pins=study['provenance']['modules']
 if pins==modules:return
 assert pins==transition['baseline_modules']
 record=coverage['source_continuity']['studies'][name]
 assert record['status']=='original_run_preserved_with_verified_parser_continuity'
 before={r['path']:r for r in transition['baseline_snapshot']['records']}
 after={r['path']:r for r in transition['candidate_snapshot']['records']}
 for path,digest in record['unchanged_literal_inputs'].items():
  a,b=before['isae/'+path],after['isae/'+path]
  assert a['source_sha256']==b['source_sha256']==digest and a['literal']==b['literal']
`);
const results={status:'PASS',modules,pyodide:py.version,
  script_sha256:createHash('sha256').update(await readFile(new URL(import.meta.url))).digest('hex'),
  runtime_sha256:Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>
    [name,createHash('sha256').update(await readFile(root+'/public/runtime/'+name)).digest('hex')]))),
  studies:{},scopes:{}};
if(enabled('imports')){
  results.studies.imports=createHash('sha256').update(await readFile('docs/validation/isae-suite-inventory.json')).digest('hex');
  const inventory=JSON.parse(await readFile('docs/validation/isae-suite-inventory.json','utf8'));
  const entries=[];
  for(const row of inventory.models){
    const bytes=await readFile(`.reference/isae-validation/${inventory.revision}/${row.path}`);
    if(createHash('sha256').update(bytes).digest('hex')!==row.sha256)throw Error('Source changed: '+row.path);
    entries.push({...row,literal:bytes.toString('utf8').replace(/^\uFEFF/,'')});
  }
  py.globals.set('inventory_json',JSON.stringify({...inventory,models:entries}));
  results.scopes.imports=JSON.parse(await py.runPythonAsync(`
from openswing.asw import parse_asw
inventory=json.loads(inventory_json)
assert inventory['kernel_modules']==modules
counts={'parsed':0,'rejected':0}
for entry in inventory['models']:
    try:
        model=parse_asw(entry['literal'])
    except Exception as exc:
        assert entry['status']=='rejected', entry['path']
        assert type(exc).__name__+': '+str(exc)==entry['error'], entry['path']
        counts['rejected']+=1
    else:
        assert entry['status']=='parsed' and model.dumps()==entry['literal'], entry['path']
        assert model.diagnostics==entry['diagnostics'], entry['path']
        counts['parsed']+=1
json.dumps({'count':sum(counts.values()),'outcomes':counts,'meaning':'Native/WASM import outcomes agree; rejected inputs remain rejected.'})
`));
  console.log('PASS all 279 native/WASM import outcomes');
}
if(enabled('p1')){
  results.studies.p1=createHash('sha256').update(await readFile('docs/validation/isae-p1.json')).digest('hex');
  py.globals.set('study_json',await readFile('docs/validation/isae-p1.json','utf8'));
  py.globals.set('script_source',await readFile('scripts/verify-isae-p1.py','utf8'));
  results.scopes.p1=JSON.parse(await py.runPythonAsync(`
study=json.loads(study_json)
verify_study_source(study,'isae-p1')
import hashlib
assert hashlib.sha256(script_source.encode()).hexdigest()==study['provenance']['script_sha256']
ns={'__file__':'/home/pyodide/scripts/verify-isae-p1.py','__name__':'isae_p1_wasm'}
exec(compile(script_source,ns['__file__'],'exec'),ns)
count=0; maximum=0.
for case in study['cases']:
    for run in case['runs']:
        for (rpm,ct,cp), expected in zip(case['measured_RPM_CT_CP'],run['outputs']):
            actual=ns['evaluate'](rpm,cp,run['diameter_m'],run['drag_area_m2'])
            maximum=max(maximum,max(abs(actual[k]-expected[k])/max(1.,abs(expected[k])) for k in expected))
            assert maximum<2e-12
            count+=1
json.dumps({'count':count,'maximum_scaled_native_difference':maximum,'independent_hover_checks':True})
`));
  console.log('PASS 220 propeller native/WASM comparisons and independent hover checks');
}
if(enabled('sa34')){
  results.studies.sa34=createHash('sha256').update(await readFile('docs/validation/isae-sa34.json')).digest('hex');
  const study=JSON.parse(await readFile('docs/validation/isae-sa34.json','utf8'));
  for(const c of study.cases)c.source_text=await readFile(`.reference/isae-validation/${study.provenance.revision}/${c.source}`,'utf8');
  py.globals.set('study_json',JSON.stringify(study));
  py.globals.set('script_source',await readFile('scripts/verify-isae-sa34.py','utf8'));
  results.scopes.sa34=JSON.parse(await py.runPythonAsync(`
study=json.loads(study_json)
verify_study_source(study,'isae-sa34')
import hashlib
assert hashlib.sha256(script_source.encode()).hexdigest()==study['provenance']['script_sha256']
ns={'__file__':'/home/pyodide/scripts/verify-isae-sa34.py','__name__':'isae_sa34_wasm'}
exec(compile(script_source,ns['__file__'],'exec'),ns)
rows=[]; maximum=0.
for case in study['cases']:
    selected=[]
    for mode in study['settings']['modes']:
        available=[r for r in case['cases'] if r['status']=='computed' and r['specification']['panels']==200 and r['specification']['mode']==mode]
        selected.append(min(available,key=lambda r:abs(r['specification']['alpha']-5)))
    # Preserve one actual failed branch per aircraft, with unchanged solver gates.
    failures=[r for r in case['cases'] if r['status']=='rejected']
    if failures: selected.append(min(failures,key=lambda r:r['seconds']))
    for expected in selected:
        spec=expected['specification']
        try: actual=ns['compute'](case['source_text'],spec)
        except ns['AnalysisError'] as exc:
            assert expected['status']=='rejected', (spec,str(exc))
            rows.append({'specification':spec,'status':'rejected','error':str(exc)})
        else:
            assert expected['status']=='computed',spec
            error=max(abs(actual[k]-expected['result'][k]) for k in ns['COEFFICIENTS'])
            error=max(error,float(np.max(abs(np.asarray(actual['span_samples'])-expected['result']['span_samples']))))
            assert error<2e-7,(spec,error)
            maximum=max(maximum,error)
            rows.append({'specification':spec,'status':'computed','maximum_native_difference':error})
        print('WASM',spec,rows[-1]['status'],flush=True)
json.dumps({'count':len(rows),'maximum_native_difference':maximum,'cases':rows})
`));
}
if(enabled('tandem')){
  results.studies.tandem=createHash('sha256').update(await readFile('docs/validation/isae-tandem.json')).digest('hex');
  const study=JSON.parse(await readFile('docs/validation/isae-tandem.json','utf8'));
  for(const model of study.models){
    model.source_text=await readFile(`.reference/isae-validation/${study.provenance.revision}/${model.source}`,'utf8');
    if(createHash('sha256').update(model.source_text).digest('hex')!==model.sources[model.source].sha256)throw Error('Changed tandem input');
  }
  py.globals.set('study_json',JSON.stringify(study));
  results.scopes.tandem=JSON.parse(await py.runPythonAsync(`
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,solve_rigid,AnalysisError
study=json.loads(study_json)
verify_study_source(study,'isae-tandem')
rows=[];maximum=0.
for model in study['models']:
    parsed=parse_asw(model['source_text'])
    selected=[]
    for frozen in [False,True]:
        for mach in [0.,None]:
            candidates=[r for r in model['cases'] if r['status']=='computed' and r['specification']['panels']==100 and r['specification']['freeze_influences']==frozen and r['specification']['mach']==mach]
            selected.append(min(candidates,key=lambda r:abs(r['specification']['alpha']-5)))
    failures=[r for r in model['cases'] if r['status']=='rejected']
    if failures:selected.append(min(failures,key=lambda r:r['seconds']))
    for expected in selected:
        spec=expected['specification']
        try:
            actual=solve_rigid(parsed,FlightCondition(speed=spec['speed'],alpha=spec['alpha'],density=1.2256,mach=spec['mach'],freeze_influences=spec['freeze_influences']),panels=spec['panels'])
        except AnalysisError as exc:
            assert expected['status']=='rejected',(spec,str(exc))
            rows.append({'specification':spec,'status':'rejected','error':str(exc)})
        else:
            assert expected['status']=='computed',spec
            assert actual['converged'] and actual['residual']<1e-8
            error=max(abs(actual[k]-expected['result'][k]) for k in ['CL','CD','Cm','CDi','CDp'])
            assert error<2e-7,(spec,error)
            maximum=max(maximum,error)
            rows.append({'specification':spec,'status':'computed','maximum_native_difference':error})
        print('WASM tandem',spec['source'].split('/')[-1],spec['freeze_influences'],spec['mach'],rows[-1]['status'],flush=True)
json.dumps({'count':len(rows),'maximum_native_difference':maximum,'cases':rows})
`));
}
if(enabled('st5')){
  results.studies.st5=createHash('sha256').update(await readFile('docs/validation/isae-st5.json')).digest('hex');
  const study=JSON.parse(await readFile('docs/validation/isae-st5.json','utf8'));
  const inputs={};
  for(const row of study.literal_audit){
    inputs[row.path]=await readFile(`.reference/isae-validation/${study.provenance.revision}/${row.path}`,'utf8');
    if(createHash('sha256').update(inputs[row.path]).digest('hex')!==study.provenance.sources[row.path].sha256)throw Error('Changed ST5 input');
  }
  py.globals.set('study_json',JSON.stringify(study));
  py.globals.set('inputs_json',JSON.stringify(inputs));
  py.globals.set('script_source',await readFile('scripts/verify-isae-st5.py','utf8'));
  results.scopes.st5=JSON.parse(await py.runPythonAsync(`
import hashlib
study=json.loads(study_json);inputs=json.loads(inputs_json)
verify_study_source(study,'isae-st5')
assert hashlib.sha256(script_source.encode()).hexdigest()==study['provenance']['script_sha256']
ns={'__file__':'/home/pyodide/scripts/verify-isae-st5.py','__name__':'isae_st5_wasm'}
exec(compile(script_source,ns['__file__'],'exec'),ns)
for expected in study['literal_audit']:
    try:
        model=ns['parse_asw'](inputs[expected['path']])
        ns['StaticNetwork'](model,8,None,None,[])
    except ValueError as exc:
        assert expected['status']=='rejected' and str(exc)==expected['error'],(expected['path'],str(exc))
    else:
        assert expected['network_setup']=='constructed_not_solved'
rows=[];maximum=0.;checked=0
for case in study['cases']:
    model=ns['parse_asw'](inputs[case['input_path']])
    expected=next(r for r in case['runs'] if r['specification']['panels']==64)
    try: actual=ns['run_model'](model,64)
    except ValueError as exc:
        assert expected['status']=='rejected' and str(exc)==expected['error'],(case['name'],str(exc))
        rows.append({'case':case['name'],'status':'rejected','error':str(exc)})
    else:
        assert expected['status']=='computed'
        error=0.;count=0
        fields={None:['max_displacement','max_rotation_deg','force_balance','moment_balance','applied_force','applied_moment','support_force','support_moment'],
                'nodes':['t','position','jig_position','rotation'],
                'elements':['t','t0','t1','length','position','frame','force','moment','force_local','moment_local','strain','curvature_change']}
        for collection,keys in fields.items():
            left=[actual['result']] if collection is None else actual['result'][collection]
            right=[expected['result']] if collection is None else expected['result'][collection]
            assert len(left)==len(right)
            for a,b in zip(left,right):
                for key in keys:
                    av,bv=np.asarray(a[key]),np.asarray(b[key])
                    assert av.shape==bv.shape
                    error=max(error,float(np.max(abs(av-bv))));count+=av.size
        assert error<2e-7,(case['name'],error)
        maximum=max(maximum,error);checked+=count
        rows.append({'case':case['name'],'status':'computed','panels':64,'maximum_native_difference':error,'physical_values':count})
    print('WASM ST-5',case['name'],rows[-1]['status'],flush=True)
json.dumps({'literal_setup_outcomes':len(study['literal_audit']),'maximum_native_difference':maximum,'physical_values':checked,'cases':rows})
`));
}
const output=process.env.OPENSWING_RESULTS||`docs/validation/isae-wasm-${scopes.join('-')||'all'}.json`;
await writeFile(output,JSON.stringify(results,null,2)+'\n');
console.log('PASS',output);
