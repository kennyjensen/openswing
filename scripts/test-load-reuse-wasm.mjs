import {loadPyodide} from 'pyodide';
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const [baseline,output]=process.argv.slice(2);
if(!baseline||!output)throw Error('Usage: node scripts/test-load-reuse-wasm.mjs BASELINE_KERNEL_DIRECTORY OUTPUT_DIRECTORY');
await mkdir(output,{recursive:false});
const hash=b=>createHash('sha256').update(b).digest('hex');
const started=Date.now(),status={status:'RUNNING',cases:[],source_sha256:{}};
const save=()=>writeFile(path.join(output,'status.json'),JSON.stringify({...status,seconds:(Date.now()-started)/1000},null,2)+'\n');
try{
  const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});
  await py.loadPackage(['numpy','scipy']);
  const names=JSON.parse(await readFile('dist/kernel/manifest.json','utf8'));
  const oldNames=(await readdir(baseline)).filter(n=>n.endsWith('.py')).sort();
  if(JSON.stringify(oldNames)!==JSON.stringify([...names].sort()))throw Error('Different kernel membership');
  for(const [kind,folder] of [['baseline',baseline],['candidate','dist/kernel']]){
    py.FS.mkdirTree('/'+kind+'/openswing');
    status.source_sha256[kind]={};
    for(const name of names){
      const bytes=await readFile(path.join(folder,name));
      if(kind==='candidate'&&!bytes.equals(await readFile('openswing/'+name)))throw Error('Stale bundle '+name);
      status.source_sha256[kind][name]=hash(bytes);
      py.FS.writeFile('/'+kind+'/openswing/'+name,bytes);
    }
  }
  for(const name of ['pyodide.asm.wasm','pyodide-lock.json'])
    status[name+'_sha256']=hash(await readFile('dist/runtime/'+name));
  const checker=await readFile('scripts/verify-inverse-histories.py','utf8');
  status.checker_sha256=hash(checker);
  py.globals.set('checks_source',checker);
  py.globals.set('mounted_source',await readFile('examples/rectangular.asw','utf8'));
  py.globals.set('curved_source',await readFile('tests/fixtures/inverse-history-curved.asw','utf8'));
  py.globals.set('progress_js',(...args)=>{
    if(args[0]!=='initializing'||args[1]===1||args[1]===args[2])console.log('progress',...args);
  });
  await py.runPythonAsync(`
import sys,json
scope={'__name__':'load_reuse_checks'}
exec(checks_source,scope)
def canonical(result):
    return json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False)
`);
  const results={};
  for(const kind of ['baseline','candidate']){
    py.globals.set('kernel_kind',kind);
    await py.runPythonAsync(`
for name in list(sys.modules):
    if name=='openswing' or name.startswith('openswing.'):del sys.modules[name]
sys.path[:]=[p for p in sys.path if p not in ('/baseline','/candidate')]
sys.path.insert(0,'/'+kernel_kind)
import openswing
assert openswing.__file__=='/'+kernel_kind+'/openswing/__init__.py'
from openswing.bridge import dispatch
`);
    for(const name of ['mounted48','curved4']){
      console.log('Running',kind,name);await save();
      const start=Date.now();
      const command=name==='mounted48'
        ? `actual=dispatch(dict(action='solve',mode='mounted',source=mounted_source,panels=48,condition=dict(controls={1:0.},circulation_modes={1:0})),progress_js)\nassert actual['converged'] and actual['residual']<=1e-8\ncanonical(actual)`
        : `actual=scope['run_curved'](curved_source,progress_js)\ncanonical(actual)`;
      const result=await py.runPythonAsync(command);
      await writeFile(path.join(output,kind+'-'+name+'.json'),result+'\n');
      const record={kind,name,status:'PASS',seconds:(Date.now()-start)/1000,sha256:hash(result)};
      if(kind==='baseline')results[name]=result;
      else{
        record.entire_output_bytes_exact=result===results[name];
        if(!record.entire_output_bytes_exact)throw Error('Full output differs: '+name);
      }
      status.cases.push(record);await save();console.log(JSON.stringify(record));
    }
  }
  for(const [kind,folder] of [['baseline',baseline],['candidate','dist/kernel']])
    for(const [name,wanted] of Object.entries(status.source_sha256[kind])){
      if(hash(await readFile(path.join(folder,name)))!==wanted)throw Error('Kernel changed: '+kind+'/'+name);
      if(kind==='candidate'&&hash(await readFile('openswing/'+name))!==wanted)throw Error('Production changed: '+name);
    }
  status.status='PASS';await save();
}catch(error){status.status='FAIL';status.error=String(error?.stack??error);await save();throw error;}
