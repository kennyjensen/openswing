import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=process.cwd(),sha=b=>createHash('sha256').update(b).digest('hex');
try {
 const nativeBytes=await readFile('docs/validation/isae-sa13.json'),study=JSON.parse(nativeBytes);
 const sourceBytes=await readFile('docs/validation/isae-sa13-sources.json'),sources=JSON.parse(sourceBytes);
 for(const r of study.rows)if(sha(await readFile(r.cache_path))!==r.cache_sha256)throw Error('Changed native cache');
 const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
 const py=await loadPyodide({indexURL:root+'/public/runtime'});await py.loadPackage(['numpy','scipy']);
 const modules={},scripts={};
 py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py'))){
  const b=await readFile('openswing/'+n);modules[n]=sha(b);py.FS.writeFile('/home/pyodide/openswing/'+n,b);
 }
 for(const n of ['verify-isae-sa13.py','isae_sa13_reference.py','extract-isae-figures.py']){
  const b=await readFile('scripts/'+n);scripts[n]=sha(b);py.FS.writeFile('/home/pyodide/scripts/'+n,b);
 }
 if(scripts['verify-isae-sa13.py']!==study.provenance.script_sha256||
    scripts['isae_sa13_reference.py']!==study.provenance.reference_script_sha256||
    sha(sourceBytes)!==study.provenance.source_report_sha256)throw Error('Native provenance changed');
 // Reference-module path discovery only; compute consumes the pinned embedded
 // outline and never reads a substitute original ASW input or FIG here.
 py.FS.mkdirTree('/home/pyodide/.reference/isae-validation/'+study.provenance.revision+'/'+sources.cases[0].path.split('/').slice(0,-1).join('/'));
 py.globals.set('study_json',nativeBytes.toString());py.globals.set('sources_json',sourceBytes.toString());
 py.globals.set('modules_json',JSON.stringify(modules));
 const out=JSON.parse(await py.runPythonAsync(`
import json,sys,runpy,numpy as np
sys.path.insert(0,'/home/pyodide/scripts')
ns=runpy.run_path('/home/pyodide/scripts/verify-isae-sa13.py')
from openswing.geometry import geometry_summary
study=json.loads(study_json);sources=json.loads(sources_json)
assert study['provenance']['modules']==json.loads(modules_json)
cases={c['name']:c for c in sources['cases']}
rows=[]
for expected in study['rows']:
    q=expected['specification'];actual=ns['compute'](cases[q['case']],q);reference=expected['result']
    assert expected['status']=='computed'
    diffs={}
    for k,a in actual['coefficients'].items():
        b=reference['coefficients'][k]
        if a is None or b is None:assert a is b is None
        else:diffs[k]=abs(a-b)
    assert actual['actual_intervals']==reference['actual_intervals']
    force=float(np.max(abs(np.array(actual['force'])-reference['force'])))
    moment=float(np.max(abs(np.array(actual['moment'])-reference['moment'])))
    density=float(np.max(abs(np.array([r['transverse_density'] for r in actual['profiles']])-np.array([r['transverse_density'] for r in reference['profiles']]))))
    coefficient=max(diffs.values());pressure=velocity=0.
    if q['case']=='pressure':
        assert actual['flow_survey']['valid']==reference['flow_survey']['valid']
        assert actual['flow_survey']['inside_body']==reference['flow_survey']['inside_body']
        pressure=float(np.max(abs(np.array([p['Cp_percent'] for p in actual['pressure_profile']])-np.array([p['Cp_percent'] for p in reference['pressure_profile']]))))
        velocity=float(np.max(abs(np.array(actual['flow_survey']['velocity']['relative'])-reference['flow_survey']['velocity']['relative'])))
    assert coefficient<2e-10 and force<2e-9 and moment<2e-9 and density<2e-9 and pressure<2e-8 and velocity<2e-9,(q,coefficient,force,moment,density,pressure,velocity)
    rows.append(dict(specification=q,status='matching_solution',maximum_coefficient_difference=coefficient,
        maximum_force_difference=force,maximum_moment_difference=moment,maximum_density_difference=density,
        maximum_Cp_percent_difference=pressure,maximum_velocity_difference=velocity))
    print('WASM',len(rows),q,'PASS',flush=True)
display=[]
for c in sources['cases']:
    try:
        geometry_summary(ns['parse_asw'](c['derived_source']),32)
        result=dict(status='constructed',panels=32)
    except ValueError as exc:result=dict(status='rejected',panels=32,error=str(exc))
    model=ns['parse_asw'](c['derived_source'])
    display.append(dict(case=c['name'],result=result,native_result=c['display_geometry'],
        matches_native=result==c['display_geometry'],endpoint_radii=model.beams[0].value('radius',[0.,1.]).tolist()))
assert len(rows)==38
json.dumps(dict(status='PASS' if all(p['matches_native'] for p in display) else 'NUMERICAL_REPLAY_PASS_DISPLAY_DIVERGENCE',
    scope='Actual Pyodide replay of38 conditional outline-body computations and4 display outcomes. Display discrepancies are retained; runtime numerical agreement is not physical validation.',rows=rows,display=display))
`));
 Object.assign(out,{modules,scripts,native_sha256:sha(nativeBytes),sources_sha256:sha(sourceBytes),
  script_sha256:sha(await readFile(new URL(import.meta.url))),pyodide:py.version,
  runtime_sha256:Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async n=>[n,sha(await readFile('public/runtime/'+n))])))});
 await writeFile('docs/validation/isae-sa13-wasm.json',JSON.stringify(out,null,2)+'\n');console.log('COMPLETE',out.rows.length,'replays');
} catch(e){console.error(String(e));process.exitCode=1;}
