import {loadPyodide} from 'pyodide';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const hash=x=>createHash('sha256').update(x).digest('hex');
try{
  const bytes=await readFile('docs/validation/dynamic-section-outputs.json'),study=JSON.parse(bytes);
  for(const [name,digest] of Object.entries(study.source_sha256))if(hash(await readFile(name))!==digest)throw Error('Changed study source: '+name);
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/scripts');
  const modules=JSON.parse(await readFile('dist/kernel/manifest.json'));
  for(const name of modules){const data=await readFile('dist/kernel/'+name);if(!data.equals(await readFile('openswing/'+name)))throw Error('Stale module: '+name);py.FS.writeFile('/home/pyodide/openswing/'+name,data);}
  py.FS.writeFile('/home/pyodide/scripts/verify-dynamic-section-outputs.py',await readFile('scripts/verify-dynamic-section-outputs.py'));
  py.FS.writeFile('/home/pyodide/scripts/verify-section-outputs.py',await readFile('scripts/verify-section-outputs.py'));
  py.FS.mkdirTree('/home/pyodide/examples');
  py.FS.writeFile('/home/pyodide/examples/heave-pitch.asw',await readFile('examples/heave-pitch.asw'));
  await py.runPythonAsync("import json,runpy,numpy as np\nh=runpy.run_path('/home/pyodide/scripts/verify-dynamic-section-outputs.py')");
  const cases=[];
  for(const c of study.cases){
    py.globals.set('case_json',JSON.stringify(c));
    const record=JSON.parse(await py.runPythonAsync(`
c=json.loads(case_json);result=h['compute'](c['specification'])
a,b=h['physical'](result),h['physical'](c['result'])
unaligned=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
phases=[];matching=[];root_error=0.;root_values=0
if c['specification']['kind']=='modes':
    # Eigenvector phase is arbitrary. Tied pivot magnitudes can select opposite
    # signs in different LAPACK runtimes. Align phase only, never amplitude;
    # every runtime has already checked its own physical output identities.
    from scipy.optimize import linear_sum_assignment
    roots=np.array([complex(*v) for v in result['eigenvalues']])
    target=np.array([complex(*v) for v in c['result']['eigenvalues']])
    cost=abs(target[:,None]-roots[None,:])/np.maximum(1,abs(target[:,None]))
    rows,columns=linear_sum_assignment(cost)
    root_error=float(max(cost[rows,columns]));root_values=2*len(roots)
    assert root_error<2e-8,('modal eigenvalues',root_error)
    matching=columns.tolist()
    aa,bb=h['z'](result['computed'])[columns],h['z'](c['result']['computed'])
    for j in range(len(aa)):
        inner=np.vdot(aa[j],bb[j]);phase=inner/abs(inner) if abs(inner) else 1+0j
        aa[j]*=phase;phases.append([float(phase.real),float(phase.imag)])
    a=np.r_[aa.real.ravel(),aa.imag.ravel()]
error=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
assert error<2e-8,(c['specification'],error)
json.dumps(dict(specification=c['specification'],result=result,physical_values_compared=a.size+root_values,section_values_compared=a.size,eigenvalue_values_compared=root_values,maximum_scaled_native_difference=max(error,root_error),maximum_unaligned_scaled_difference=unaligned,modal_phase_alignment=phases,modal_matching=matching,maximum_scaled_eigenvalue_difference=root_error))
`));cases.push(record);console.log('Dynamic section outputs WASM',JSON.stringify(record.specification),record.maximum_scaled_native_difference);
  }
  const runtime_sha256=Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>[name,hash(await readFile('dist/runtime/'+name))])));
  await writeFile('docs/validation/dynamic-section-outputs-wasm.json',JSON.stringify({study_sha256:hash(bytes),module_count:modules.length,runtime_sha256,
    source_sha256:{...study.source_sha256,'scripts/test-dynamic-section-outputs-wasm.mjs':hash(await readFile('scripts/test-dynamic-section-outputs-wasm.mjs'))},cases},null,2)+'\n');
  await new Promise(resolve=>process.stdout.write('Dynamic section outputs packaged replay passed.\n',resolve));process.exit(0);
}catch(error){await new Promise(resolve=>process.stderr.write(String(error)+'\n',resolve));process.exit(1);}
