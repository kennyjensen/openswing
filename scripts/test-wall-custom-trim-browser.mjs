// One offline public UI sensor-constrained wall solve against a known-speed control.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createReadStream} from 'node:fs';
import {readFile,writeFile,readdir,mkdir,stat} from 'node:fs/promises';
import {createServer} from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
import {expect} from '@playwright/test';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
assert.equal(process.argv.length,4,'Supply new output directory and native fixture directory.');
const output=path.resolve(process.argv[2]),study=path.resolve(process.argv[3]);
await mkdir(output,{recursive:false});
const read=async p=>JSON.parse(await readFile(p,'utf8'));
const save=(name,value)=>writeFile(path.join(output,name),JSON.stringify(value,null,2)+'\n');
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const request=await read(path.join(study,'native-request.json')),native=await read(path.join(study,'native-result.json'));
const report=await read(path.join(study,'native-report.json')),project=await read(path.join(study,'input-project.json'));
assert.equal(report.status,'PASS_NATIVE_WALL_CUSTOM_TRIM');const modules=report.modules;
for(const [name,digest] of Object.entries(modules))for(const folder of ['openswing','public/kernel','dist/kernel'])
  assert.equal(sha(await readFile(path.join(root,folder,name))),digest,folder+'/'+name);
const audit={status:'RUNNING',modules,checks:[],page_errors:[],offline_requests:[],external_requests:[],
  absolute:2e-8,relative:2e-8,numeric_comparisons:0,maximum_fraction:0,
  excluded:['evaluations','equilibrium_initialization','custom_trim.one_sided_tangent_ratio'],
  exclusion_reason:'Execution counters and cancellation-sensitive one-sided slope diagnostics are not physical quantities. The original smoothness and rank gates are checked independently.'};
audit.built_assets=Object.fromEntries(await Promise.all(['index.html',...(await readdir(path.join(root,'dist/assets'))).map(n=>'assets/'+n)]
  .map(async name=>[name,sha(await readFile(path.join(root,'dist',name)))])));
const check=(name,ok)=>{audit.checks.push({name,passed:!!ok});assert(ok,name);};
function compare(a,b,p=''){
  if(audit.excluded.includes(p))return;
  if(typeof a==='number'){
    assert.equal(typeof b,'number',p);assert(Number.isFinite(a)&&Number.isFinite(b),p);
    const fraction=Math.abs(a-b)/(audit.absolute+audit.relative*Math.abs(a));
    audit.numeric_comparisons++;audit.maximum_fraction=Math.max(audit.maximum_fraction,fraction);assert(fraction<=1,p);
  }else if(Array.isArray(a)){
    assert(Array.isArray(b)&&a.length===b.length,p);a.forEach((v,i)=>compare(v,b[i],`${p}[${i}]`));
  }else if(a!==null&&typeof a==='object'){
    assert(b!==null&&typeof b==='object',p);
    for(const [key,value] of Object.entries(a)){assert(Object.hasOwn(b,key),p+'.'+key);compare(value,b[key],p?p+'.'+key:key);}
  }else assert.deepEqual(b,a,p);
}
let browser,server,page,timer,offline=false;const began=performance.now();
try{
  const dist=path.join(root,'dist'),mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.css':'text/css','.svg':'image/svg+xml','.woff2':'font/woff2'};
  server=createServer(async(req,res)=>{try{
    const name=decodeURIComponent(new URL(req.url,'http://local').pathname),file=path.resolve(dist,'.'+(name==='/'?'/index.html':name));
    assert(file.startsWith(dist+path.sep)&&(await stat(file)).isFile());
    res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream'});createReadStream(file).pipe(res);
  }catch{res.writeHead(404);res.end();}});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const url=`http://127.0.0.1:${server.address().port}`;
  browser=await chromium.launch({headless:true,executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,
    args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-webgl','--js-flags=--max-old-space-size=192']});
  timer=setTimeout(()=>browser.close().catch(()=>{}),210000);
  const context=await browser.newContext({acceptDownloads:true,viewport:{width:1200,height:900}});
  await context.route(/^https?:/,route=>{if(new URL(route.request().url()).origin===url)return route.continue();
    audit.external_requests.push(route.request().url());return route.abort();});
  context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))audit.offline_requests.push(r.url());});
  page=await context.newPage();page.setDefaultTimeout(60000);page.on('pageerror',e=>audit.page_errors.push(e.message));
  await page.addInitScript(()=>{window.capturedSolves=[];const W=window.Worker;
    window.Worker=class extends W{postMessage(m,...rest){if(m.request?.action==='solve')window.capturedSolves.push(structuredClone(m));return super.postMessage(m,...rest);}};});
  await page.goto(url);await expect(page.locator('#solve')).toBeEnabled({timeout:120000});
  await page.evaluate(async()=>{await Promise.all([...document.fonts].map(f=>f.load()));await document.fonts.ready;});
  await page.locator('#project-settings > summary').click();
  await page.locator('#project-file').setInputFiles({name:'wall-custom.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});
  await expect(page.locator('#project-load')).toBeEnabled();await page.locator('#project-load').click();
  await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#structural-equations')).toHaveValue('aswing-coupled');
  await expect(page.locator('#equilibrium-enable')).toBeChecked();
  await expect(page.locator('[data-custom="expression"]')).toHaveValue('sensor("1.position_earth.z")');
  audit.startup_seconds=(performance.now()-began)/1000;await context.setOffline(true);offline=true;
  const started=performance.now();await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:120000});
  audit.solve_seconds=(performance.now()-started)/1000;
  const event=page.waitForEvent('download');await page.locator('#export-json').click();
  const bytes=await readFile(await(await event).path());await writeFile(path.join(output,'result.json'),bytes);
  const result=JSON.parse(bytes),messages=await page.evaluate(()=>window.capturedSolves);await save('requests.json',messages);
  check('one actual custom warm solve',messages.length===1);
  assert.deepEqual(JSON.parse(JSON.stringify(messages[0].request)),request);check('exact native wire request',true);
  assert.deepEqual(result.software_provenance.modules,modules);check('tested kernel',true);
  compare(native,result);check('complete native physical parity',true);
  check('independent known speed',Math.abs(result.operating_values.speed-10)<2e-6);
  check('full residual',result.converged&&result.residual<=1e-8);
  check('custom target',Math.abs(result.sensors[0].position_earth[2]-request.operating_constraints[0].target)<=1e-8);
  check('full custom rank',result.custom_trim.column_scaled_reciprocal_condition>1e-10);
  check('one-sided smoothness',result.custom_trim.one_sided_tangent_ratio<=1);
  check('offline execution',!audit.offline_requests.length&&!audit.external_requests.length);
  check('no page errors',!audit.page_errors.length);audit.status='PASS';
}catch(error){audit.status='FAILURE_RETAINED';audit.error={message:error.message,stack:error.stack};process.exitCode=1;
  if(page&&!page.isClosed())audit.failure_state=await page.evaluate(()=>({
    runtime:document.getElementById('runtime-status')?.textContent,
    detail:document.getElementById('runtime-detail')?.textContent,
    error:document.getElementById('error')?.textContent,solves:window.capturedSolves})).catch(()=>null);
}finally{
  clearTimeout(timer);await browser?.close();await new Promise(resolve=>server?server.close(resolve):resolve());
  audit.seconds=(performance.now()-began)/1000;await save('report.json',audit);
  console.log(JSON.stringify({status:audit.status,checks:audit.checks.length,numeric:audit.numeric_comparisons,seconds:audit.seconds}));
}
