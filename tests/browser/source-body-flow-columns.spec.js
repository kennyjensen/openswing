import {test,expect} from '@playwright/test';
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';

test('source body flow columns match complete physical residuals offline in WASM',async({page,context})=>{
  test.setTimeout(180000);
  const modules={},hash=b=>createHash('sha256').update(b).digest('hex');
  for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py'))){
    modules[name]=hash(await readFile('openswing/'+name));
    for(const folder of ['public/kernel','dist/kernel'])expect(hash(await readFile(folder+'/'+name))).toBe(modules[name]);
  }
  const helper=await readFile('tests/source_body_flow_case.py','utf8');
  const source=await readFile('examples/wing-body.asw','utf8');
  const errors=[],requests=[];let offline=false;
  page.on('pageerror',e=>errors.push(e.message));
  context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))requests.push(r.url());});
  // Use one numerical runtime. This exercises the shipped WASM and kernels,
  // without starting a second copy through the unchanged workbench UI.
  await page.goto('/kernel/manifest.json');
  const loaded=await page.evaluate(async()=>{
    const {loadPyodide}=await import('/runtime/pyodide.mjs');
    const py=window.bodyFlowRuntime=await loadPyodide({indexURL:'/runtime/'});
    await py.loadPackage(['numpy','scipy']);
    const files=await(await fetch('/kernel/manifest.json',{cache:'no-store'})).json();
    py.FS.mkdirTree('/home/pyodide/openswing');
    for(const name of files){const data=await(await fetch('/kernel/'+name,{cache:'no-store'})).text();py.FS.writeFile('/home/pyodide/openswing/'+name,data);}
    return JSON.parse(await py.runPythonAsync("import pathlib,hashlib,json\njson.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in pathlib.Path('/home/pyodide/openswing').glob('*.py')})"));
  });
  expect(loaded).toEqual(modules);
  await context.setOffline(true);offline=true;
  const results=await page.evaluate(async({helper,source})=>{
    const py=window.bodyFlowRuntime;py.globals.set('body_source',source);
    return JSON.parse(await py.runPythonAsync(helper+"\nimport json\njson.dumps([check_body_columns(body_source,0.,'fixed',False),check_body_columns(body_source,17.,'free',True)])"));
  },{helper,source});
  for(const result of results){
    expect(result.status).toBe('PASS_SOURCE_BODY_FLOW_COLUMNS');
    for(const check of result.checks)expect(check.maximum_scaled_error).toBeLessThan(2e-8);
  }
  expect(errors).toEqual([]);expect(requests).toEqual([]);
  if(process.env.OPENSWING_BODY_FLOW_EVIDENCE){
    const directory=process.env.OPENSWING_BODY_FLOW_EVIDENCE;await mkdir(directory,{recursive:true});
    await writeFile(directory+'/browser.json',JSON.stringify({status:'PASS_OFFLINE_SOURCE_BODY_COLUMNS',modules,errors,requests,results})+'\n');
  }
});
