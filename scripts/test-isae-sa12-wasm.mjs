import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {dirname} from 'node:path';
const root=process.cwd(),sha=b=>createHash('sha256').update(b).digest('hex');
try {
 const bytes=await readFile('docs/validation/isae-sa12-wasm-native.json'),study=JSON.parse(bytes);
 const sourceBytes=await readFile('docs/validation/isae-sa12-sources.json'),sources=JSON.parse(sourceBytes);
 for(const r of study.rows)if(sha(await readFile(r.cache_path))!==r.cache_sha256)throw Error('Changed native cache');
 const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
 const py=await loadPyodide({indexURL:root+'/public/runtime'});await py.loadPackage(['numpy','scipy']);
 const modules={},scripts={};
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py'))){
  const b=await readFile('openswing/'+n);modules[n]=sha(b);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.writeFile('/home/pyodide/openswing/'+n,b);
 }
 for(const n of ['verify-isae-sa12.py','isae_sa12_reference.py']){
  const b=await readFile('scripts/'+n);scripts[n]=sha(b);
  py.FS.mkdirTree('/home/pyodide/scripts');py.FS.writeFile('/home/pyodide/scripts/'+n,b);
 }
 if(scripts['verify-isae-sa12.py']!==study.provenance.script_sha256||
    scripts['isae_sa12_reference.py']!==study.provenance.reference_script_sha256||
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
ns=runpy.run_path('/home/pyodide/scripts/verify-isae-sa12.py')
study=json.loads(study_json);sources=json.loads(sources_json)
assert study['provenance']['modules']==json.loads(modules_json)
source_map={c['name']:c['source'] for c in sources['models']}
rows=[]
for expected in study['rows']:
    request=expected['specification'];actual=ns['compute'](source_map[request['case']],request)
    assert expected['status']=='computed'
    differences={}
    for k in ns['COEFFICIENTS']+['CD_friction','CD_specified_pressure','CD_stall_pressure']:
        a,b=actual[k],expected['result'][k]
        if a is None or b is None:assert a is b is None
        else:differences[k]=abs(a-b)
    coefficient=max(differences.values())
    assert actual['actual_strips']==expected['result']['actual_strips']
    assert actual['trefftz']['available']==expected['result']['trefftz']['available']
    force=float(np.max(abs(np.array(actual['force'])-expected['result']['force'])))
    profile=float(np.max(abs(np.array([r['cl'] for r in actual['profiles']])-np.array([r['cl'] for r in expected['result']['profiles']]))))
    assert coefficient<2e-7 and force<2e-4 and profile<2e-6,(request,coefficient,force,profile)
    rows.append(dict(specification=request,status='matching_solution',maximum_coefficient_difference=coefficient,
        maximum_force_difference=force,maximum_section_cl_difference=profile,CDi=actual['CDi'],
        residual=actual['residual'],maximum_local_residual=actual['maximum_local_residual']))
    print('WASM',len(rows),request['case'],request['height_label'],request['alpha'],request['pose'],request['modes'],'PASS',flush=True)
assert len(rows)==33
json.dumps(dict(status='PASS',scope='Actual Pyodide replay of 33 ground-effect states. Runtime agreement is not experimental validation.',rows=rows))
`));
 Object.assign(out,{modules,scripts,native_sample_sha256:sha(bytes),sources_sha256:sha(sourceBytes),
  script_sha256:sha(await readFile(new URL(import.meta.url))),pyodide:py.version,
  runtime_sha256:Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async n=>[n,sha(await readFile('public/runtime/'+n))])))});
 await writeFile('docs/validation/isae-sa12-wasm.json',JSON.stringify(out,null,2)+'\n');console.log('COMPLETE',out.rows.length,'replays');
} catch(e){console.error(String(e));process.exitCode=1;}
