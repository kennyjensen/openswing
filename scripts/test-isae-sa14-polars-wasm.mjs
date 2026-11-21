import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=process.cwd(),sha=b=>createHash('sha256').update(b).digest('hex');
try{
 const bytes=await readFile('docs/validation/isae-sa14-polars.json'),study=JSON.parse(bytes);
 const sourceBytes=await readFile('docs/validation/isae-sa14-sources.json'),sources=JSON.parse(sourceBytes);
 const selected=new Map();
 for(const row of study.rows){
  const q=row.specification;
  if([25,100].includes(q.panels)&&[0,15,31].includes(q.alpha)&&['zero','speed'].includes(q.pg))selected.set(row.cache_path,row);
 }
 for(const label of ['CL_WB_S_WB','CL_WB_SW','CL_W_SW']){
  const refs=study.references.filter(r=>r.label===label).sort((a,b)=>a.alpha-b.alpha);
  for(const ref of [refs[0],refs.at(-1)]){
   const row=study.rows.find(r=>r.specification.case===ref.case&&r.specification.alpha===ref.alpha&&r.specification.panels===100&&r.specification.pg==='primary_0.19'&&!r.specification.frozen);
   if(!row)throw Error('Missing exact-angle state');selected.set(row.cache_path,row);
  }
 }
 if(selected.size!==78)throw Error('Unexpected selection '+selected.size);
 for(const row of selected.values())if(sha(await readFile(row.cache_path))!==row.cache_sha256)throw Error('Native cache changed');
 const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
 const py=await loadPyodide({indexURL:root+'/public/runtime'});await py.loadPackage(['numpy','scipy']);
 py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
 const modules={};
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py'))){
  const b=await readFile('openswing/'+n);modules[n]=sha(b);py.FS.writeFile('/home/pyodide/openswing/'+n,b);
 }
 const script=await readFile('scripts/verify-isae-sa14-polars.py');
 if(sha(script)!==study.provenance.inputs['scripts/verify-isae-sa14-polars.py']||sha(sourceBytes)!==study.provenance.inputs['docs/validation/isae-sa14-sources.json'])throw Error('Input provenance changed');
 py.FS.writeFile('/home/pyodide/scripts/verify-isae-sa14-polars.py',script);
 py.globals.set('selected_json',JSON.stringify([...selected.values()]));py.globals.set('sources_json',sourceBytes.toString());
 py.globals.set('expected_modules_json',JSON.stringify(study.provenance.modules));py.globals.set('modules_json',JSON.stringify(modules));
 const out=JSON.parse(await py.runPythonAsync(`
import json,runpy,numpy as np
ns=runpy.run_path('/home/pyodide/scripts/verify-isae-sa14-polars.py')
assert json.loads(expected_modules_json)==json.loads(modules_json)
sources=json.loads(sources_json);models={c['name']:ns['parse_asw'](c['source']) for c in sources['models']};rows=[]
for expected in json.loads(selected_json):
    q=expected['specification']
    try:actual=dict(status='computed',result=ns['compute'](models[q['case']],q,sources))
    except (ns['AnalysisError'],ValueError) as exc:actual=dict(status='rejected',error=str(exc),details=getattr(exc,'details',None))
    assert actual['status']==expected['status'],(q,actual['status'],expected['status'])
    row=dict(specification=q,native_status=expected['status'])
    if actual['status']=='rejected':
        a=actual['details'];b=expected['details'];assert a is not None and b is not None and a['kind']==b['kind']=='section_normal_mach'
        difference=abs(a['maximum']['normal_mach']-b['maximum']['normal_mach']);assert difference<2e-7
        row.update(status='matching_rejection',maximum_normal_mach_difference=difference,error=actual['error'])
    else:
        a=actual['result'];b=expected['result'];differences=[]
        for k,v in a['coefficients'].items():
            if v is None or b['coefficients'][k] is None:assert v is b['coefficients'][k] is None
            else:differences.append(abs(v-b['coefficients'][k]))
        coefficient=max(differences);primary=max(abs(a['primary_normalization'][k]-b['primary_normalization'][k]) for k in b['primary_normalization'] if k.startswith('CL_'))
        force=float(np.max(abs(np.array(a['force'])-b['force'])));moment=float(np.max(abs(np.array(a['moment'])-b['moment'])))
        mach=abs(a['maximum_section_normal_mach']-b['maximum_section_normal_mach'])
        assert coefficient<2e-8 and primary<2e-8 and force<2e-5 and moment<2e-5 and mach<2e-7,(q,coefficient,primary,force,moment,mach)
        row.update(status='matching_solution',maximum_coefficient_difference=coefficient,maximum_primary_difference=primary,
            maximum_force_difference=force,maximum_moment_difference=moment,maximum_normal_mach_difference=mach)
    rows.append(row);print('WASM',len(rows),q,row['status'],flush=True)
assert len(rows)==78
json.dumps(dict(status='PASS_EXTENDED_POLAR_RUNTIME_REPLAY',rows=rows,
    scope='78 actual Pyodide states spanning original polars, exact experimental angles, PG alternatives, live/frozen influences and physical-validity rejections. Not experimental validation.'))
`));
 Object.assign(out,{modules,native_sha256:sha(bytes),sources_sha256:sha(sourceBytes),runner_sha256:sha(script),
  script_sha256:sha(await readFile(new URL(import.meta.url))),pyodide:py.version,
  runtime_sha256:Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async n=>[n,sha(await readFile('public/runtime/'+n))])))});
 await writeFile('docs/validation/isae-sa14-polars-wasm.json',JSON.stringify(out,null,2)+'\n');console.log('COMPLETE',out.rows.length);
}catch(e){console.error(String(e));process.exitCode=1;}
