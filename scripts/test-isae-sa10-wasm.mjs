import {readFile,readdir,writeFile} from 'node:fs/promises';
import {dirname} from 'node:path';
import {createHash} from 'node:crypto';
const root=process.cwd(),sha=b=>createHash('sha256').update(b).digest('hex');
try {
 const bytes=await readFile('docs/validation/isae-sa10.json'),study=JSON.parse(bytes);
 const sourceBytes=await readFile('docs/validation/isae-sa10-sources.json');
 const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
 const py=await loadPyodide({indexURL:root+'/public/runtime'});await py.loadPackage(['numpy','scipy']);
 const modules={},scripts={};
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py'))){
  const b=await readFile('openswing/'+n);modules[n]=sha(b);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.writeFile('/home/pyodide/openswing/'+n,b);
 }
 for(const n of ['verify-isae-sa10.py','isae_sa10_reference.py']){
  const b=await readFile('scripts/'+n);scripts[n]=sha(b);
  py.FS.mkdirTree('/home/pyodide/scripts');py.FS.writeFile('/home/pyodide/scripts/'+n,b);
 }
 for(const c of study.cases){
  const name='.reference/isae-validation/'+study.provenance.revision+'/'+c.path,b=await readFile(name);
  if(sha(b)!==c.source_sha256)throw Error('Input changed');
  py.FS.mkdirTree(dirname('/home/pyodide/'+name));py.FS.writeFile('/home/pyodide/'+name,b);
 }
 py.globals.set('study_json',bytes.toString());py.globals.set('sources_json',sourceBytes.toString());py.globals.set('modules_json',JSON.stringify(modules));
 const out=JSON.parse(await py.runPythonAsync(`
import json,sys,runpy,numpy as np
sys.path.insert(0,'/home/pyodide/scripts')
ns=runpy.run_path('/home/pyodide/scripts/verify-isae-sa10.py')
study=json.loads(study_json);sources=json.loads(sources_json)
assert study['provenance']['modules']==json.loads(modules_json)
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
bad=next(c for c in sources['models'] if c['name']=='TS_60_45_30');rejections=[]
for panels in [25,50,100]:
    try:model_meshes(parse_asw(bad['source']),panels)
    except ValueError as exc:
        assert str(exc)=="Attachment station is outside beam 2's parameter range."
        rejections.append(dict(panels=panels,error=str(exc)))
    else:raise AssertionError('Invalid attachment accepted')
rows=[]
for case in study['cases']:
    selected=[r for r in case['runs'] if
        (r['specification']['panels']==25 and not r['specification']['frozen'] and r['specification']['pg']=='zero' and r['specification']['alpha'] in [5,15,25]) or
        (r['specification']['panels']==50 and not r['specification']['frozen'] and r['specification']['pg']=='zero' and r['specification']['alpha']==15) or
        (r['specification']['panels']==25 and r['specification']['frozen'] and r['specification']['pg']=='speed' and r['specification']['alpha']==15)]
    for expected in selected:
        try:actual=ns['compute'](case['source'],expected['specification'])
        except ns['AnalysisError'] as exc:
            assert expected['status']=='rejected'
            details=getattr(exc,'details',None);reference=expected['details']
            assert details['kind']==reference['kind']=='section_normal_mach'
            assert details['maximum']['beam']==reference['maximum']['beam']
            assert abs(details['maximum']['t']-reference['maximum']['t'])<1e-10
            mach_difference=abs(details['maximum']['normal_mach']-reference['maximum']['normal_mach'])
            assert mach_difference<1e-5 and details['sound_speed']==reference['sound_speed']
            rows.append(dict(specification=expected['specification'],status='matching_rejection',error=str(exc),
                details=details,maximum_normal_mach_difference=mach_difference));continue
        assert expected['status']=='computed'
        coefficient=max(abs(actual[k]-expected['result'][k]) for k in ns['COEFFICIENTS'])
        profiles=max(abs(np.array([s['cl'] for s in actual['profiles']])-np.array([s['cl'] for s in expected['result']['profiles']])))
        force=float(np.max(abs(np.array(actual['force'])-expected['result']['force'])))
        assert coefficient<2e-7 and profiles<2e-6 and force<2e-4,(expected['specification'],coefficient,profiles,force)
        rows.append(dict(specification=expected['specification'],status='matching_solution',maximum_coefficient_difference=coefficient,
            maximum_section_cl_difference=float(profiles),maximum_force_difference=force,residual=actual['residual']))
    print('WASM',case['case_id'],len(selected),'PASS',flush=True)
assert len(rows)==30 and len(rejections)==3
json.dumps(dict(status='PASS',scope='Actual Pyodide native/WASM coefficient and sectional-load replay; browser UI checked separately',rows=rows,literal_rejections=rejections))
`));
 Object.assign(out,{modules,scripts,study_sha256:sha(bytes),sources_sha256:sha(sourceBytes),script_sha256:sha(await readFile(new URL(import.meta.url))),pyodide:py.version,
  runtime_sha256:Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async n=>[n,sha(await readFile('public/runtime/'+n))])))});
 await writeFile('docs/validation/isae-sa10-wasm.json',JSON.stringify(out,null,2)+'\n');console.log('COMPLETE',out.rows.length,'replays');
} catch(e){console.error(String(e));process.exitCode=1;}
