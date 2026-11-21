// One actual offline workbench warm solve, against a retained native AE-2 state.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createReadStream} from 'node:fs';
import {readFile,writeFile,readdir,mkdir,stat} from 'node:fs/promises';
import {createServer} from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
import {expect} from '@playwright/test';
import {checkSourceWallContinuation} from './check-source-wall-continuation.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
assert.equal(process.argv.length,4,'Supply a new output directory and completed continuation study.');
const output=path.resolve(process.argv[2]),study=path.resolve(process.argv[3]);
await mkdir(output,{recursive:false});
const read=async p=>JSON.parse(await readFile(p,'utf8'));
const save=(name,value)=>writeFile(path.join(output,name),JSON.stringify(value,null,2)+'\n');
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const folder=path.join(study,'cases/ordered-m80-v02');
const request=await read(path.join(folder,'request.json')),native=await read(path.join(folder,'result.json'));
assert.equal((await read(path.join(folder,'report.json'))).status,'computed');
assert(request.initial_state&&request.numerics.structural_operator==='drela-steady-coupled-v1');
const plan=await read(path.join(study,'plan.json'));
const modules=Object.fromEntries(plan.pins.filter(p=>p.path.includes('/openswing/')).map(p=>[path.basename(p.path),p.sha256]));
for(const [name,hash] of Object.entries(modules))for(const dir of ['openswing','public/kernel','dist/kernel'])
  assert.equal(sha(await readFile(path.join(root,dir,name))),hash,dir+'/'+name);
const config=structuredClone((await read(path.join(root,'examples/isae-ae2-uncoupled-project.json'))).cases[0].configuration);
Object.assign(config,{source:request.source,filename:'[m15_02]_S.asw',mesh:request.panels,numerics:request.numerics,
  equilibrium:{state:request.initial_state,enabled:true,label:'Previous converged IAS1 state'}});
Object.assign(config.fields,{speed:'2',beta:'5',alpha:'0','freeze-influences':true,'pg-mach':'0','mach-mode':'fixed'});
const project={format:'openswing-project',version:2,name:'AE-2 source wall continuation',selected:'ae2',
  cases:[{id:'ae2',name:'IAS2 from IAS1 equilibrium',configuration:config}],solutions:[],selected_solution:null};
await save('input-project.json',project);
const audit={status:'RUNNING',modules,checks:[],page_errors:[],offline_requests:[],external_requests:[],
  absolute:2e-8,relative:2e-8,numeric_comparisons:0,maximum_fraction:0,
  excluded:['evaluations','equilibrium_initialization'],
  exclusion_reason:'Evaluation count and Newton execution diagnostics contain timings/counters. All physical outputs and the complete equilibrium state are compared; corrector behavior is checked separately.'};
audit.built_assets=Object.fromEntries(await Promise.all(['index.html',...(await readdir(path.join(root,'dist/assets'))).map(n=>'assets/'+n)]
  .map(async name=>[name,sha(await readFile(path.join(root,'dist',name)))])));
let browser,server,timer,offline=false;const began=performance.now();
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
  timer=setTimeout(()=>browser.close().catch(()=>{}),180000);
  const context=await browser.newContext({acceptDownloads:true,viewport:{width:1200,height:900}});
  await context.route(/^https?:/,route=>{
    if(new URL(route.request().url()).origin===url)return route.continue();
    audit.external_requests.push(route.request().url());return route.abort();
  });
  context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))audit.offline_requests.push(r.url());});
  const page=await context.newPage();page.setDefaultTimeout(60000);page.on('pageerror',e=>audit.page_errors.push(e.message));
  await page.addInitScript(()=>{window.capturedSolves=[];const W=window.Worker;
    window.Worker=class extends W{postMessage(m,...rest){if(m.request?.action==='solve')window.capturedSolves.push(structuredClone(m));return super.postMessage(m,...rest);}};});
  await page.goto(url);await expect(page.locator('#solve')).toBeEnabled({timeout:120000});
  await page.evaluate(async()=>{await Promise.all([...document.fonts].map(f=>f.load()));await document.fonts.ready;});
  await page.locator('#project-settings > summary').click();
  await page.locator('#project-file').setInputFiles({name:'source-wall.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});
  await expect(page.locator('#project-load')).toBeEnabled();await page.locator('#project-load').click();
  await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#structural-equations')).toHaveValue('aswing-coupled');
  await expect(page.locator('#equilibrium-enable')).toBeChecked();
  audit.startup_seconds=(performance.now()-began)/1000;await context.setOffline(true);offline=true;
  const started=performance.now();await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:90000});
  audit.solve_seconds=(performance.now()-started)/1000;
  const event=page.waitForEvent('download');await page.locator('#export-json').click();
  const bytes=await readFile(await(await event).path());await writeFile(path.join(output,'result.json'),bytes);
  const result=JSON.parse(bytes),messages=await page.evaluate(()=>window.capturedSolves);
  await save('requests.json',messages);
  checkSourceWallContinuation(request,native,result,messages,audit);audit.status='PASS';
}catch(error){audit.status='FAILURE_RETAINED';audit.error={message:error.message,stack:error.stack};process.exitCode=1;
}finally{
  clearTimeout(timer);await browser?.close();await new Promise(resolve=>server?server.close(resolve):resolve());
  audit.seconds=(performance.now()-began)/1000;await save('report.json',audit);console.log(JSON.stringify({status:audit.status,seconds:audit.seconds,checks:audit.checks.length,numeric:audit.numeric_comparisons}));
}
