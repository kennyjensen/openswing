import {readFile,readdir,writeFile} from 'node:fs/promises';
import {dirname} from 'node:path';
import {createHash} from 'node:crypto';
const root=process.cwd(),sha=b=>createHash('sha256').update(b).digest('hex');
try {
 const bytes=await readFile('docs/validation/isae-sa11-wasm-native.json'),study=JSON.parse(bytes);
 const sourceBytes=await readFile('docs/validation/isae-sa11-sources.json'),sources=JSON.parse(sourceBytes);
 for(const c of study.cases)for(const r of c.runs){
  if(sha(await readFile(r.cache_path))!==r.cache_sha256)throw Error('Native cache changed: '+r.cache_path);
 }
 const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
 const py=await loadPyodide({indexURL:root+'/public/runtime'});await py.loadPackage(['numpy','scipy']);
 const modules={},scripts={};
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py'))){
  const b=await readFile('openswing/'+n);modules[n]=sha(b);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.writeFile('/home/pyodide/openswing/'+n,b);
 }
 for(const n of ['verify-isae-sa11.py','isae_sa11_reference.py']){
  const b=await readFile('scripts/'+n);scripts[n]=sha(b);
  py.FS.mkdirTree('/home/pyodide/scripts');py.FS.writeFile('/home/pyodide/scripts/'+n,b);
 }
 if(scripts['verify-isae-sa11.py']!==study.provenance.script_sha256||
    scripts['isae_sa11_reference.py']!==study.provenance.reference_script_sha256||
    sha(sourceBytes)!==study.provenance.source_report_sha256)throw Error('Native provenance changed');
 for(const c of sources.models){
  const name='.reference/isae-validation/'+study.provenance.revision+'/'+c.path,b=await readFile(name);
  if(sha(b)!==c.sha256)throw Error('Original input changed');
  py.FS.mkdirTree(dirname('/home/pyodide/'+name));py.FS.writeFile('/home/pyodide/'+name,b);
 }
 py.globals.set('study_json',bytes.toString());py.globals.set('sources_json',sourceBytes.toString());
 py.globals.set('modules_json',JSON.stringify(modules));
 const out=JSON.parse(await py.runPythonAsync(`
import json,sys,runpy,numpy as np
sys.path.insert(0,'/home/pyodide/scripts')
ns=runpy.run_path('/home/pyodide/scripts/verify-isae-sa11.py')
study=json.loads(study_json);sources=json.loads(sources_json)
assert study['provenance']['modules']==json.loads(modules_json)
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
literal=[]
for name in ['wingtip_up','wingtip_up_and_down','wingtip_up_cant0']:
    model=next(m for m in sources['models'] if m['name']==name)
    for panels in [25,50,100]:
        expected=model.get('error') or next(s['error'] for s in model['setups'] if s['panels']==panels)
        try:model_meshes(parse_asw(model['source']),panels)
        except ValueError as exc:
            assert str(exc)==expected
            literal.append(dict(case=name,panels=panels,error=str(exc)))
        else:raise AssertionError('Invalid original input accepted')
rows=[]
for case in study['cases']:
    for expected in case['runs']:
        try:actual=ns['compute'](case['source'],expected['specification'])
        except ns['AnalysisError'] as exc:
            assert expected['status']=='rejected'
            details=getattr(exc,'details',None);reference=expected['details']
            assert details['kind']==reference['kind']=='section_normal_mach'
            a,b=details['maximum'],reference['maximum']
            # Exact reflection symmetry can exchange the numerically largest
            # left/right sample. The cant0 source is asymmetric and excluded.
            mirror=case['name']!='wingtip_up_cant0' and a['position'][1]*b['position'][1]<0
            position=np.array(a['position']);velocity=np.array(a['relative_velocity'])
            if mirror:position[1]*=-1;velocity[1]*=-1
            else:assert a['beam']==b['beam']
            assert abs(abs(a['t'])-abs(b['t']))<1e-10
            position_error=float(np.max(abs(position-b['position'])))
            velocity_error=float(np.max(abs(velocity-b['relative_velocity'])))
            mach_error=abs(a['normal_mach']-b['normal_mach'])
            assert position_error<1e-9 and velocity_error<2e-6*max(1.,np.max(np.abs(b['relative_velocity'])))
            assert mach_error<2e-6*max(1.,b['normal_mach']) and details['sound_speed']==reference['sound_speed']
            rows.append(dict(specification=expected['specification'],status='matching_rejection',error=str(exc),details=details,
                reflected_tied_maximum=mirror,maximum_position_difference=position_error,
                maximum_velocity_difference=velocity_error,maximum_normal_mach_difference=mach_error));continue
        assert expected['status']=='computed'
        coefficient=max(abs(actual[k]-expected['result'][k]) for k in ns['COEFFICIENTS'])
        profile=float(np.max(abs(np.array([s['cl'] for s in actual['profiles']])-np.array([s['cl'] for s in expected['result']['profiles']]))))
        force=float(np.max(abs(np.array(actual['force'])-expected['result']['force'])))
        assert coefficient<2e-7 and profile<2e-6 and force<2e-4,(expected['specification'],coefficient,profile,force)
        rows.append(dict(specification=expected['specification'],status='matching_solution',maximum_coefficient_difference=coefficient,
            maximum_section_cl_difference=profile,maximum_force_difference=force,residual=actual['residual']))
    print('WASM',case['case_id'],len(case['runs']),'PASS',flush=True)
assert len(rows)==40 and len(literal)==9
json.dumps(dict(status='PASS',scope='Actual Pyodide replay of 40 native states plus nine original-input rejection checks. This verifies runtime agreement, not experimental accuracy.',rows=rows,literal_rejections=literal))
`));
 Object.assign(out,{modules,scripts,native_sample_sha256:sha(bytes),sources_sha256:sha(sourceBytes),
  script_sha256:sha(await readFile(new URL(import.meta.url))),pyodide:py.version,
  runtime_sha256:Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async n=>[n,sha(await readFile('public/runtime/'+n))])))});
 await writeFile('docs/validation/isae-sa11-wasm.json',JSON.stringify(out,null,2)+'\n');console.log('COMPLETE',out.rows.length,'replays');
} catch(e){console.error(String(e));process.exitCode=1;}
