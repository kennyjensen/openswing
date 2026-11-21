import {loadPyodide} from 'pyodide';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const output=process.argv[2];
if(!output)throw Error('Usage: node scripts/test-inverse-histories-wasm.mjs OUTPUT_DIRECTORY');
await mkdir(output,{recursive:false});
const hash=b=>createHash('sha256').update(b).digest('hex');
const started=Date.now(),status={status:'RUNNING',cases:[],source_sha256:{}};
const save=async()=>writeFile(path.join(output,'status.json'),JSON.stringify({...status,seconds:(Date.now()-started)/1000},null,2)+'\n');
try{
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});
  await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');
  const names=JSON.parse(await readFile('dist/kernel/manifest.json','utf8'));
  for(const name of names){
    const bytes=await readFile('dist/kernel/'+name);
    if(!bytes.equals(await readFile('openswing/'+name)))throw Error('Stale bundled module '+name);
    status.source_sha256[name]=hash(bytes);
    py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
  }
  const checks=await readFile('scripts/verify-inverse-histories.py');
  status.checker_sha256=hash(checks);status.module_count=names.length;
  await save();
  py.globals.set('checks_source',checks.toString());
  await py.runPythonAsync("scope={'__name__':'inverse_history_checks'}\nexec(checks_source,scope)\nimport json");
  const inputs='tests/inverse_history/saved/inputs/';
  py.globals.set('saved_source',await readFile(inputs+'both-root.asw','utf8'));
  py.globals.set('saved_json',await readFile(inputs+'saved-equilibrium.json','utf8'));
  console.log('Running actual saved spring history launch in packaged WASM');
  const result=await py.runPythonAsync("json.dumps(scope['run_saved'](saved_source,json.loads(saved_json)),allow_nan=False)");
  await writeFile(path.join(output,'saved-output.json'),result+'\n');
  status.cases.push({name:'saved_spring_radau',status:'PASS',metrics:JSON.parse(result).metrics});
  for(const [name,wanted] of Object.entries(status.source_sha256)){
    if(hash(await readFile('openswing/'+name))!==wanted)throw Error('Source changed during WASM replay: '+name);
  }
  status.status='PASS';await save();console.log(JSON.stringify(status.cases));
}catch(error){status.status='FAIL';status.error=String(error?.stack??error);await save();throw error;}
