import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=process.cwd(),sha=b=>createHash('sha256').update(b).digest('hex');
try{
 const bytes=await readFile('docs/validation/isae-sa14-incidence.json'),study=JSON.parse(bytes);
 const sourceBytes=await readFile('docs/validation/isae-sa14-sources.json'),sources=JSON.parse(sourceBytes);
 const incidenceBytes=await readFile('docs/validation/isae-sa14-incidence-sources.json'),incidence=JSON.parse(incidenceBytes);
 const selected=study.rows.filter(r=>r.specification.case!=='iw0'&&r.specification.pg==='primary_0.19');
 for(const r of selected)if(sha(await readFile(r.cache_path))!==r.cache_sha256)throw Error('Native cache changed');
 const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
 const py=await loadPyodide({indexURL:root+'/public/runtime'});await py.loadPackage(['numpy','scipy']);
 py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
 const modules={},scripts={};
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py'))){
  const b=await readFile('openswing/'+n);modules[n]=sha(b);py.FS.writeFile('/home/pyodide/openswing/'+n,b);
 }
 for(const n of ['verify-isae-sa14.py','isae_sa14_reference.py']){
  const b=await readFile('scripts/'+n);scripts[n]=sha(b);py.FS.writeFile('/home/pyodide/scripts/'+n,b);
 }
 if(scripts['verify-isae-sa14.py']!==study.provenance.compute_script_sha256||sha(sourceBytes)!==study.provenance.source_report_sha256||sha(incidenceBytes)!==study.provenance.incidence_source_sha256)throw Error('Source provenance changed');
 const folder=sources.models[0].path.split('/').slice(0,-2).join('/');
 py.FS.mkdirTree('/home/pyodide/.reference/isae-validation/'+study.provenance.revision+'/'+folder);
 py.globals.set('selected_json',JSON.stringify(selected));py.globals.set('sources_json',sourceBytes.toString());
 py.globals.set('incidence_json',incidenceBytes.toString());py.globals.set('modules_json',JSON.stringify(modules));
 const out=JSON.parse(await py.runPythonAsync(`
import json,sys,runpy,numpy as np
sys.path.insert(0,'/home/pyodide/scripts')
ns=runpy.run_path('/home/pyodide/scripts/verify-isae-sa14.py')
from openswing.geometry import geometry_summary
sources=json.loads(sources_json);incidence=json.loads(incidence_json)
assert incidence['modules']==json.loads(modules_json)
rows=[]
for expected in json.loads(selected_json):
    q=expected['specification'];assert expected['status']=='computed'
    a=ns['compute'](incidence['variants'][q['case']]['source'],q,sources);b=expected['result']
    differences={}
    for k,v in a['coefficients'].items():
        if v is None or b['coefficients'][k] is None:assert v is b['coefficients'][k] is None
        else:differences[k]=abs(v-b['coefficients'][k])
    coefficient=max(differences.values())
    observables=max(abs(v-b['primary_normalization'][k]) for k,v in a['primary_normalization'].items() if k.startswith('CL_'))
    assert len(a['profiles'])==len(b['profiles']) and len(a['body_strips'])==len(b['body_strips'])
    local=max(abs(x['primary_local_load']-y['primary_local_load']) for x,y in zip(a['profiles'],b['profiles']))
    velocity=max(float(np.max(abs(np.array(x['relative_velocity'])-y['relative_velocity']))) for x,y in zip(a['profiles'],b['profiles']))
    force=max(float(np.max(abs(np.array(x['force'])-y['force']))) for x,y in zip(a['profiles']+a['body_strips'],b['profiles']+b['body_strips']))
    mach=abs(a['maximum_section_normal_mach']-b['maximum_section_normal_mach'])
    assert coefficient<2e-8 and observables<2e-8 and local<2e-7 and velocity<2e-6 and force<2e-5 and mach<2e-8,(q,coefficient,observables,local,velocity,force,mach)
    rows.append(dict(specification=q,status='matching_solution',maximum_coefficient_difference=coefficient,
        maximum_primary_observable_difference=observables,maximum_local_load_difference=local,
        maximum_velocity_difference=velocity,maximum_strip_force_difference=force,maximum_normal_mach_difference=mach))
    print('WASM',len(rows),q,'PASS',flush=True)
display=[]
for name,variant in incidence['variants'].items():
    geometry_summary(ns['parse_asw'](variant['source']),50)
    display.append(dict(case=name,status='constructed'))
assert len(rows)==18
json.dumps(dict(status='PASS_18_INCIDENCE_WASM_REPLAYS',rows=rows,display=display,
    scope='18 actual Pyodide states: two equivalent frames, three meshes, three wing angles at primary Mach0.19. Runtime agreement does not establish experimental validity.'))
`));
 Object.assign(out,{modules,scripts,native_sha256:sha(bytes),sources_sha256:sha(sourceBytes),incidence_sources_sha256:sha(incidenceBytes),
  script_sha256:sha(await readFile(new URL(import.meta.url))),pyodide:py.version,
  runtime_sha256:Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async n=>[n,sha(await readFile('public/runtime/'+n))])))});
 await writeFile('docs/validation/isae-sa14-incidence-wasm.json',JSON.stringify(out,null,2)+'\n');console.log('COMPLETE',out.rows.length);
}catch(e){console.error(String(e));process.exitCode=1;}
