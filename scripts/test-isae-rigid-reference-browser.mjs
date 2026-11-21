// One real offline browser replay of a saved native rigid-reference case.
// node scripts/test-isae-rigid-reference-browser.mjs NEW_OUTPUT_DIR NATIVE_CASE_DIR
import {chromium} from 'playwright';
import {expect} from '@playwright/test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {createReadStream} from 'node:fs';
import {readFile,writeFile,readdir,mkdir,stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
assert.equal(process.argv.length,4,'Supply a new output directory and completed native case directory.');
const output=path.resolve(process.argv[2]),nativeDir=path.resolve(process.argv[3]);
await mkdir(output,{recursive:false});
const sha=b=>createHash('sha256').update(b).digest('hex');
const pin=async p=>{const b=await readFile(p);return {path:p,bytes:b.length,sha256:sha(b)};};
const audit={status:'PREPARING',scope:'One current built UI/Pyodide rigid solve, offline after startup, full native-result parity and saved-project restore.',checks:[],page_errors:[],offline_requests:[],network_failures:[],planned_solves:1,gates:{absolute:2e-8,relative:2e-8,residual:1e-8},exclusions:['evaluations','circulation_solver.evaluations']};
const save=()=>writeFile(path.join(output,'report.json'),JSON.stringify(audit,null,2)+'\n');
const check=(name,ok,details={})=>{audit.checks.push({name,passed:!!ok,...details});assert(ok,name);};
function compare(expected,actual){
 const stats={numeric:0,leaves:0,max_absolute:0,max_fraction:0,worst:null};
 function visit(e,a,p){
  if(audit.exclusions.includes(p))return;
  if(typeof e==='number'){
   assert.equal(typeof a,'number',p);assert(Number.isFinite(a)&&Number.isFinite(e),p);
   const d=Math.abs(a-e),limit=audit.gates.absolute+audit.gates.relative*Math.abs(e);stats.numeric++;stats.leaves++;stats.max_absolute=Math.max(stats.max_absolute,d);
   if(d/limit>stats.max_fraction)Object.assign(stats,{max_fraction:d/limit,worst:p});assert(d<=limit,p+' numerical parity');
  }else if(Array.isArray(e)){assert(Array.isArray(a)&&a.length===e.length,p);e.forEach((v,i)=>visit(v,a[i],`${p}[${i}]`));}
  else if(e!==null&&typeof e==='object'){assert(a!==null&&typeof a==='object',p);for(const [k,v] of Object.entries(e)){assert(Object.hasOwn(a,k),p+'.'+k);visit(v,a[k],p?p+'.'+k:k);}}
  else{stats.leaves++;assert.deepEqual(a,e,p);}
 }
 visit(expected,actual,'');return stats;
}
const normalized=c=>({...c,controls:Object.fromEntries(Object.entries(c.controls).filter(([,v])=>v!==0)),circulation_modes:Object.fromEntries(Object.entries(c.circulation_modes).filter(([,v])=>v!==0))});
let browser,server,page,timer;let offline=false;const started=performance.now();
try{
 const inputs=JSON.parse(await readFile(path.join(nativeDir,'inputs.json'))),native=JSON.parse(await readFile(path.join(nativeDir,'result.json'))),report=JSON.parse(await readFile(path.join(nativeDir,'report.json'))),c=inputs.condition;
 audit.inputs=await pin(path.join(nativeDir,'inputs.json'));audit.native=await pin(path.join(nativeDir,'result.json'));audit.native_report=await pin(path.join(nativeDir,'report.json'));audit.script=await pin(fileURLToPath(import.meta.url));
 check('native numerical checks passed',report.status==='PASS_NUMERICAL_STATE'&&report.fresh_residual<=1e-8);
 assert.equal(c.ground_effect,0);assert.equal(c.gust,null);assert.equal(c.time,0);assert.equal(c.mach,0);assert.deepEqual(c.powers,{});
 for(const k of ['rates','acceleration','angular_acceleration','position_earth','attitude'])assert.deepEqual(c[k],[0,0,0]);
 audit.modules={};const names=(await readdir(path.join(root,'openswing'))).filter(n=>n.endsWith('.py')).sort();
 assert.deepEqual(names,inputs.source_pins.map(p=>path.basename(p.path)).sort(),'all native kernel modules are present');
 for(const n of names){const p=inputs.source_pins.find(p=>path.basename(p.path)===n);assert(p,n);audit.modules[n]=p.sha256;for(const folder of ['openswing','public/kernel','dist/kernel'])check(folder+'/'+n,sha(await readFile(path.join(root,folder,n)))===p.sha256);}
 const serveRoot=path.join(root,'dist'),mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.css':'text/css','.svg':'image/svg+xml','.woff2':'font/woff2'};
 audit.built_assets=[];for(const n of ['index.html',...(await readdir(path.join(serveRoot,'assets'))).map(n=>'assets/'+n)])audit.built_assets.push(await pin(path.join(serveRoot,n)));
 server=createServer(async(req,res)=>{try{const rel=decodeURIComponent(new URL(req.url,'http://local').pathname),p=path.resolve(serveRoot,'.'+(rel==='/'?'/index.html':rel));assert(p.startsWith(serveRoot+path.sep));const s=await stat(p);assert(s.isFile());res.writeHead(200,{'Content-Type':mime[path.extname(p)]||'application/octet-stream','Content-Length':s.size});createReadStream(p).pipe(res);}catch{res.writeHead(404);res.end('Not found');}});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));audit.url=`http://127.0.0.1:${server.address().port}`;
 const executable=process.env.OPENSWING_CHROMIUM_EXECUTABLE||'/tmp/aswing-chromium/chrome-linux/chrome';
 const args=process.env.OPENSWING_WEBGL_DRIVER==='mesa'?['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native','--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'];
 audit.browser_environment=Object.fromEntries(['LD_LIBRARY_PATH','VK_ICD_FILENAMES','OPENSWING_WEBGL_DRIVER','LP_NUM_THREADS'].map(k=>[k,process.env[k]??null]));audit.browser_args=args;
 browser=await chromium.launch({headless:true,executablePath:executable,args});audit.chromium=browser.version();
 timer=setTimeout(()=>{audit.timeout=true;browser.close().catch(()=>{});},240000);
 const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});page=await context.newPage();page.setDefaultTimeout(60000);
 page.on('pageerror',e=>audit.page_errors.push(e.message));context.on('requestfailed',r=>audit.network_failures.push({url:r.url(),failure:r.failure()}));context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))audit.offline_requests.push(r.url());});
 await page.addInitScript(()=>{window.referenceRequests=[];const W=window.Worker;window.Worker=class extends W{postMessage(m,...r){window.referenceRequests.push(structuredClone(m));return super.postMessage(m,...r);}};});
 await page.goto(audit.url);await expect(page.locator('#solve')).toBeEnabled({timeout:180000});audit.startup_seconds=(performance.now()-started)/1000;
 await context.setOffline(true);offline=true;
 await page.locator('#file').setInputFiles({name:'SA_3.asw',mimeType:'text/plain',buffer:Buffer.from(inputs.source)});await expect(page.locator('#editor')).toHaveValue(inputs.source);await expect(page.locator('#solve')).toBeEnabled();
 await page.locator('#node-file').setInputFiles({name:'reference-mesh.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({format:'openswing-mesh',version:1,panels:inputs.panels}))});
 await page.waitForFunction(()=>!document.querySelector('#node-file').value);await expect(page.locator('#node-table tbody tr')).toHaveCount(native.panels+1);await expect(page.locator('#solve')).toBeEnabled();
 await page.locator('#mode').selectOption('rigid');await page.locator('details').evaluateAll(ns=>ns.forEach(n=>n.open=true));
 await page.locator('#density-mode').selectOption('custom');await page.locator('#gravity-mode').selectOption('custom');await page.locator('#mach-mode').selectOption('fixed');
 for(const [id,v] of Object.entries({speed:c.speed,alpha:c.alpha,beta:c.beta,density:c.density,'gravity-magnitude':c.gravity_magnitude,'pg-mach':c.mach,'load-factor':c.load_factor,'stall-factor':c.stall_factor,'stall-width':c.stall_width,'wake-core-ratio':c.wake_core_ratio,altitude:c.altitude_m}))await page.locator('#'+id).fill(String(v));
 for(const [id,v] of Object.entries({stall:c.stall,'aero-lag':c.aero_lag,'freeze-influences':c.freeze_influences,'derivatives-enable':false}))await page.locator('#'+id).setChecked(v);
 await page.locator('#ground-effect').selectOption('0');await page.locator('#gust-kind').selectOption('none');await page.locator('#circulation-modes input').fill('0');
 for(const axis of ['x','y','z']){await page.locator('#position-earth-'+axis).fill('0');for(const group of ['rates','acceleration','angular_acceleration'])await page.locator('#'+group+'-'+axis).fill('0');}
 for(const k of ['bank','elevation','heading'])await page.locator('#attitude-'+k).fill('0');
 const begin=performance.now();console.log('Starting sole offline rigid solve.');await page.locator('#solve').click();await expect(page.locator('#result-state')).toHaveText('Converged · rigid geometry',{timeout:90000});await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();audit.solve_seconds=(performance.now()-begin)/1000;
 async function download(id,name){const event=page.waitForEvent('download');await page.locator('#'+id).click();const bytes=await readFile(await(await event).path());await writeFile(path.join(output,name),bytes);return bytes;}
 const bytes=await download('export-json','result.json'),result=JSON.parse(bytes);
 assert.deepEqual(result.software_provenance.modules,audit.modules);assert.deepEqual(result.request.panels,inputs.panels);assert.equal(result.request.source,inputs.source);assert.equal(result.request.mode,'rigid');assert.deepEqual(normalized(result.request.condition),normalized(c));check('cold rigid solve',!result.request.initial_state);check('residual',result.converged&&result.residual<=1e-8);audit.parity=compare(native,result);
 const requests=await page.evaluate(()=>window.referenceRequests);check('one solve request',requests.filter(r=>r.request?.action==='solve').length===1);await writeFile(path.join(output,'requests.json'),JSON.stringify(requests,null,2)+'\n');
 await page.locator('#project-name').fill('ISAE SA-3 archived ASWING comparison');await page.locator('#project-rename').click();await page.locator('#project-case-name').fill('Original model, 10.0173913 deg, 400 intervals');await page.locator('#project-add').click();
 await page.locator('#project-solution-name').fill('Computed rigid reference case');await page.locator('#project-save-solution').click();await expect(page.locator('#project-load-solution')).toBeEnabled();
 const project=await download('project-export','project.json');
 await page.locator('#project-file').setInputFiles({name:'reference-project.json',mimeType:'application/json',buffer:project});await expect(page.locator('#project-load-solution')).toBeEnabled();await page.locator('#project-load-solution').click();await expect(page.locator('#export-json')).toBeEnabled();
 const reopened=await download('export-json','reopened-result.json');check('saved result restored byte-exactly',Buffer.compare(bytes,reopened)===0);check('no extra solve for restore',(await page.evaluate(()=>window.referenceRequests)).filter(r=>r.request?.action==='solve').length===1);
 await page.locator('details').evaluateAll(ns=>ns.forEach(n=>n.open=false));await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();await page.locator('#fit').click();
 check('mobile width',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(output,'mobile.png')});
 for(const p of [audit.inputs,audit.native,audit.native_report,audit.script,...audit.built_assets])check('unchanged '+p.path,(await pin(p.path)).sha256===p.sha256);
 check('offline HTTP absent',audit.offline_requests.length===0);check('page errors absent',audit.page_errors.length===0);check('network failures absent',audit.network_failures.length===0);audit.status='PASS_OFFLINE_RIGID_REFERENCE_AND_PROJECT_RESTORE';
}catch(e){audit.status='FAILURE_RETAINED';audit.error={message:e.message,stack:e.stack};process.exitCode=1;console.error(e.stack);try{if(page&&!page.isClosed())await page.screenshot({path:path.join(output,'failure.png')});}catch{}}
finally{clearTimeout(timer);try{await browser?.close();}finally{server?.closeAllConnections();if(server?.listening)await new Promise(resolve=>server.close(resolve));}audit.total_seconds=(performance.now()-started)/1000;await save();console.log(JSON.stringify({status:audit.status,startup_seconds:audit.startup_seconds,solve_seconds:audit.solve_seconds,parity:audit.parity,total_seconds:audit.total_seconds}));}
