// Actual local Pyodide regression. Run under the caller's process timeout.
import {readFile,readdir,mkdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
const root=process.cwd();
const sourceRoot=process.env.OPENSWING_SOURCE_ROOT||path.join(root,'openswing');
const testRoot=process.env.OPENSWING_TEST_ROOT||path.join(root,'tests');
const output=process.env.OPENSWING_RESULTS||path.join(root,'test-results',`seeded-corrector-wasm-${Date.now()}.json`);
const pin=bytes=>({bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')});
let py;const result={status:'RUNNING',modules:{},inputs:{},runtime:{},sourceRoot,testRoot};
try{
  const names=(await readdir(sourceRoot)).filter(name=>name.endsWith('.py')).sort();
  if(!names.includes('seeded_corrector.py'))throw Error('Source lacks the seeded corrector; integrate the tested candidate before this regression.');
  const moduleBytes=await Promise.all(names.map(async name=>[name,await readFile(path.join(sourceRoot,name))]));
  for(const [name,bytes] of moduleBytes)result.modules[name]=pin(bytes);
  const dataNames=['seeded-corrector-reference.json','seeded-corrector-flexible.asw','seeded-corrector-wasm.py'];
  const data=Object.fromEntries(await Promise.all(dataNames.map(async name=>[name,await readFile(path.join(testRoot,'data',name))])));
  for(const name of dataNames)result.inputs[name]=pin(data[name]);
  const reference=JSON.parse(data['seeded-corrector-reference.json'].toString('utf8'));
  if(result.inputs['seeded-corrector-flexible.asw'].sha256!==reference.model.sha256)throw Error('Shared baseline fixture changed.');
  for(const name of (await readdir(path.join(root,'public/runtime'))).sort()){
    const bytes=await readFile(path.join(root,'public/runtime',name));result.runtime[name]=pin(bytes);
  }
  const {loadPyodide}=await import(pathToFileURL(path.join(root,'node_modules/pyodide/pyodide.mjs')).href);
  py=await loadPyodide({indexURL:path.join(root,'public/runtime')});result.pyodide=py.version;
  await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/test-data');
  for(const [name,bytes] of moduleBytes)py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
  for(const name of dataNames)py.FS.writeFile('/test-data/'+name,data[name]);
  await py.runPythonAsync(data['seeded-corrector-wasm.py'].toString('utf8'));
  result.test=JSON.parse(py.FS.readFile('/test-data/result.json',{encoding:'utf8'}));
  result.status=result.test.status;
  for(const [name,expected] of Object.entries(result.modules)){
    const actual=pin(await readFile(path.join(sourceRoot,name)));
    if(actual.sha256!==expected.sha256||actual.bytes!==expected.bytes)throw Error('Source changed during test: '+name);
  }
  for(const [name,expected] of Object.entries(result.inputs)){
    const actual=pin(await readFile(path.join(testRoot,'data',name)));
    if(actual.sha256!==expected.sha256||actual.bytes!==expected.bytes)throw Error('Input changed during test: '+name);
  }
  result.source_and_inputs_unchanged=true;
}catch(error){
  result.status='FAIL_SEEDED_CORRECTOR_WASM_RETAINED';result.error={message:String(error),stack:error.stack};
  if(py){try{result.test=JSON.parse(py.FS.readFile('/test-data/result.json',{encoding:'utf8'}));}catch{}}
}finally{
  result.script_pin=pin(await readFile(fileURLToPath(import.meta.url)));
  await mkdir(path.dirname(output),{recursive:true});await writeFile(output,JSON.stringify(result,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({status:result.status,counts:result.test?.counts,operations:result.test?.operations,output,error:result.error??result.test?.error}));
  if(result.status!=='PASS_SEEDED_CORRECTOR_WASM')process.exitCode=1;
}
