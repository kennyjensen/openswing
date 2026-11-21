import {readFile,readdir,writeFile,mkdir} from 'node:fs/promises';
import {dirname} from 'node:path';
import {createHash} from 'node:crypto';
const root=process.cwd(),sha=b=>createHash('sha256').update(b).digest('hex');
try {
 const bytes=await readFile('docs/validation/isae-sa6.json'),study=JSON.parse(bytes);
 const checks=await readFile('docs/validation/isae-sa6-checks.json');
 const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
 const py=await loadPyodide({indexURL:root+'/public/runtime'});await py.loadPackage(['numpy','scipy']);
 const modules={},scripts={};
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py'))){const b=await readFile('openswing/'+n);modules[n]=sha(b);py.FS.mkdirTree('/home/pyodide/openswing');py.FS.writeFile('/home/pyodide/openswing/'+n,b);}
 for(const n of ['verify-isae-sa6.py','isae_sa6_reference.py']){const b=await readFile('scripts/'+n);scripts[n]=sha(b);py.FS.mkdirTree('/home/pyodide/scripts');py.FS.writeFile('/home/pyodide/scripts/'+n,b);}
 for(const c of study.cases){const name='.reference/isae-validation/'+study.provenance.revision+'/'+c.path,b=await readFile(name);if(sha(b)!==c.sha256)throw Error('Input changed');py.FS.mkdirTree(dirname('/home/pyodide/'+name));py.FS.writeFile('/home/pyodide/'+name,b);}
 py.globals.set('study_json',bytes.toString());py.globals.set('checks_json',checks.toString());py.globals.set('modules_json',JSON.stringify(modules));
 const out=JSON.parse(await py.runPythonAsync(`
import json,sys,runpy,numpy as np
from pathlib import Path
sys.path.insert(0,'/home/pyodide/scripts')
ns=runpy.run_path('/home/pyodide/scripts/verify-isae-sa6.py')
study=json.loads(study_json);checks=json.loads(checks_json);assert study['provenance']['modules']==checks['modules']==json.loads(modules_json)
rows=[];maximum=0.
for case in study['cases']:
    source=(ns['CACHE']/case['path']).read_text()
    selected=[r for r in case['runs'] if r['specification']['panels']==80 and ((not r['specification']['frozen'] and r['specification']['delta'] in [4,32]) or (r['specification']['frozen'] and r['specification']['delta']==32 and r['specification']['alpha']==12))]
    for r in selected:
        actual=ns['compute'](source,r['specification']);assert r['status']=='computed'
        diff=max(abs(actual[k]-r['result'][k]) for k in ['Cl','Cn','CL','CD','Cm','Cl_stability','Cn_stability'])
        assert diff<2e-8,(r['specification'],diff);maximum=max(maximum,diff)
        rows.append(dict(specification=r['specification'],maximum_coefficient_difference=diff,residual=actual['residual']))
    print('WASM',case['case_id'],len(selected),'PASS',flush=True)
from openswing.bridge import dispatch
tangents=[]
for t in checks['tangents']:
    if t['panels']!=40:continue
    r=dispatch(t['request']);d=np.array(r['derivatives']['matrices']['coefficients'])[:,0]
    diff=float(max(abs(d-t['implicit_coefficients'])));assert diff<2e-7
    tangents.append(dict(case=t['case'],delta=t['delta'],panels=40,maximum_derivative_difference=diff))
    print('WASM tangent',t['case'],t['delta'],'PASS',flush=True)
assert len(rows)==56 and len(tangents)==8
json.dumps(dict(status='PASS',scope='Actual Pyodide native/WASM replay; browser UI tested separately',rows=rows,tangents=tangents,maximum_coefficient_difference=maximum))
`));
 Object.assign(out,{modules,scripts,study_sha256:sha(bytes),checks_sha256:sha(checks),script_sha256:sha(await readFile(new URL(import.meta.url))),pyodide:py.version,
  runtime_sha256:Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async n=>[n,sha(await readFile('public/runtime/'+n))])))});
 await writeFile('docs/validation/isae-sa6-wasm.json',JSON.stringify(out,null,2)+'\n');console.log('COMPLETE',out.rows.length,out.tangents.length);
} catch(e){console.error(String(e));process.exitCode=1;}
