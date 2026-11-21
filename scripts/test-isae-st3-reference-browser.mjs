// One real offline built-UI structural replay of the literal ST3 signed-weight case.
// node scripts/test-isae-st3-reference-browser.mjs NEW_OUTPUT_DIR NATIVE_RUN_DIR INTERVALS
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
assert.equal(process.argv.length,5,'Supply a new output directory, completed native run directory and interval count.');
const output=path.resolve(process.argv[2]),nativeRun=path.resolve(process.argv[3]),intervals=Number(process.argv[4]),nativeDir=path.join(nativeRun,`n${intervals}`);
assert(Number.isInteger(intervals)&&intervals>=4&&intervals<=512);
await mkdir(output,{recursive:false});
const sha=b=>createHash('sha256').update(b).digest('hex');
const pin=async p=>{const b=await readFile(p);return {path:p,bytes:b.length,sha256:sha(b)};};
const audit={status:'PREPARING',scope:'One current built UI/Pyodide structural solve of the unchanged literal signed-weight case, offline after startup, full native-result parity and saved-project restore.',checks:[],page_errors:[],offline_requests:[],network_failures:[],planned_solves:1,gates:{absolute:2e-8,relative:2e-8,residual:1e-8},exclusions:['evaluations'],exclusion_reason:'Only the execution counter may differ between native and WASM; no physical output is excluded.'};
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
let browser,server,page,timer;let offline=false;const started=performance.now();
try{
 const plan=JSON.parse(await readFile(path.join(nativeRun,'plan.json'))),summary=JSON.parse(await readFile(path.join(nativeRun,'summary.json'))),native=JSON.parse(await readFile(path.join(nativeDir,'result.json'))),report=JSON.parse(await readFile(path.join(nativeDir,'comparison.json')));
 const mesh=plan.meshes.find(m=>m.intervals===intervals);assert(mesh,'The requested mesh must be one of the frozen native cases.');
 const sourcePath=path.resolve(root,plan.source),source=await readFile(sourcePath,'utf8');
 assert.equal(sha(Buffer.from(source)),plan.source_sha256);
 const inputs={source,panels:mesh.panels};await writeFile(path.join(output,'inputs.json'),JSON.stringify(inputs,null,2)+'\n');
 audit.inputs=await pin(path.join(output,'inputs.json'));audit.source=await pin(sourcePath);audit.plan=await pin(path.join(nativeRun,'plan.json'));audit.summary=await pin(path.join(nativeRun,'summary.json'));audit.native=await pin(path.join(nativeDir,'result.json'));audit.native_report=await pin(path.join(nativeDir,'comparison.json'));audit.script=await pin(fileURLToPath(import.meta.url));
 check('native numerical checks passed',report.numerical_gates_pass&&report.checks.fresh_residual<=1e-8&&summary.all_numerical_gates_pass);
 assert.equal(native.analysis,'structural_static');assert.equal(native.structural_elements,intervals);assert.equal(native.structural_nodes,intervals+1);assert.equal(native.structural_only,true);assert.deepEqual(native.strips,[]);assert.deepEqual(native.gravity_body,[0,0,-9.81]);assert.equal(native.mass_properties.physical,false);assert(!Object.hasOwn(native.equilibrium_state,'launch'));
 audit.modules={};const names=(await readdir(path.join(root,'openswing'))).filter(n=>n.endsWith('.py')).sort();assert.deepEqual(names,Object.keys(plan.kernel_pins).map(n=>path.basename(n)).sort(),'all native kernel modules are present');
 for(const n of names){const expected=plan.kernel_pins['openswing/'+n];assert(expected,n);audit.modules[n]=expected;for(const folder of ['openswing','public/kernel','dist/kernel'])check(folder+'/'+n,sha(await readFile(path.join(root,folder,n)))===expected);}
 const serveRoot=path.join(root,'dist'),mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.css':'text/css','.svg':'image/svg+xml','.woff2':'font/woff2'};
 audit.built_assets=[];for(const n of ['index.html',...(await readdir(path.join(serveRoot,'assets'))).map(n=>'assets/'+n)])audit.built_assets.push(await pin(path.join(serveRoot,n)));
 server=createServer(async(req,res)=>{try{const rel=decodeURIComponent(new URL(req.url,'http://local').pathname),p=path.resolve(serveRoot,'.'+(rel==='/'?'/index.html':rel));assert(p.startsWith(serveRoot+path.sep));const s=await stat(p);assert(s.isFile());res.writeHead(200,{'Content-Type':mime[path.extname(p)]||'application/octet-stream','Content-Length':s.size});createReadStream(p).pipe(res);}catch{res.writeHead(404);res.end('Not found');}});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));audit.url=`http://127.0.0.1:${server.address().port}`;
 const executable=process.env.OPENSWING_CHROMIUM_EXECUTABLE||'/tmp/aswing-chromium/chrome-linux/chrome';
 const args=process.env.OPENSWING_WEBGL_DRIVER==='mesa'?['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native','--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'];
 audit.browser_environment=Object.fromEntries(['LD_LIBRARY_PATH','VK_ICD_FILENAMES','OPENSWING_WEBGL_DRIVER','LP_NUM_THREADS'].map(k=>[k,process.env[k]??null]));audit.browser_args=args;
 browser=await chromium.launch({headless:true,executablePath:executable,args});audit.chromium=browser.version();
 timer=setTimeout(()=>{audit.timeout=true;browser.close().catch(()=>{});},285000);
 const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});page=await context.newPage();page.setDefaultTimeout(60000);
 page.on('pageerror',e=>audit.page_errors.push(e.message));context.on('requestfailed',r=>audit.network_failures.push({url:r.url(),failure:r.failure()}));context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))audit.offline_requests.push(r.url());});
 await page.addInitScript(()=>{window.referenceRequests=[];window.referenceEvents=[];const W=window.Worker;window.Worker=class extends W{constructor(...a){super(...a);this.addEventListener('message',e=>{if(e.data?.type==='progress'||e.data?.progress||e.data?.stage)window.referenceEvents.push(structuredClone(e.data));});}postMessage(m,...r){window.referenceRequests.push(structuredClone(m));return super.postMessage(m,...r);}};});
 await page.goto(audit.url);await expect(page.locator('#solve')).toBeEnabled({timeout:180000});audit.startup_seconds=(performance.now()-started)/1000;
 await context.setOffline(true);offline=true;
 await page.locator('#file').setInputFiles({name:'isae-st3-static-m15_0.asw',mimeType:'text/plain',buffer:Buffer.from(inputs.source)});await expect(page.locator('#editor')).toHaveValue(inputs.source);await expect(page.locator('#solve')).toBeEnabled();
 await page.locator('#node-file').setInputFiles({name:'reference-mesh.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({format:'openswing-mesh',version:1,panels:inputs.panels}))});
 await page.waitForFunction(()=>!document.querySelector('#node-file').value);await expect(page.locator('#node-table tbody tr')).toHaveCount(native.structural_nodes);await expect(page.locator('#solve')).toBeEnabled();
 await page.locator('#mode').selectOption('structural');await page.locator('details').evaluateAll(ns=>ns.forEach(n=>n.open=true));await page.locator('#static-gravity-mode').selectOption('file');
 await expect(page.locator('#speed')).toBeHidden();await expect(page.locator('#atmosphere-settings')).toBeHidden();await expect(page.locator('#static-weight-note')).toBeVisible();
 const begin=performance.now();console.log('Starting sole offline structural solve.');await page.locator('#solve').click();await expect(page.locator('#result-state')).toHaveText('Converged · structural static',{timeout:90000});await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();audit.solve_seconds=(performance.now()-begin)/1000;
 async function download(id,name){const event=page.waitForEvent('download');await page.locator('#'+id).click();const bytes=await readFile(await(await event).path());await writeFile(path.join(output,name),bytes);return bytes;}
 const bytes=await download('export-json','result.json'),result=JSON.parse(bytes);
 assert.deepEqual(result.software_provenance.modules,audit.modules);assert.deepEqual(result.request.panels,inputs.panels);assert.equal(result.request.source,inputs.source);assert.equal(result.request.mode,'structural');assert.equal(result.request.condition,null);assert.equal(result.request.gravity,null);assert.equal(result.condition,null);assert.deepEqual(result.request.operating_constraints,[]);assert(!Object.hasOwn(result.request,'derivatives'));
 check('cold structural solve',!result.request.initial_state);check('residual',result.converged&&result.residual<=1e-8);check('signed static scope',result.structural_only&&result.mass_properties.physical===false&&!Object.hasOwn(result.equilibrium_state,'launch')&&result.strips.length===0);audit.parity=compare(native,result);check('full native result parity',audit.parity.max_fraction<=1,audit.parity);
 audit.counters={native:native.evaluations,browser:result.evaluations};
 const requests=await page.evaluate(()=>window.referenceRequests);check('one solve request',requests.filter(r=>r.request?.action==='solve').length===1);await writeFile(path.join(output,'requests.json'),JSON.stringify(requests,null,2)+'\n');
 await page.locator('#project-name').fill('ISAE ST-3 archived ASWING structural comparison');await page.locator('#project-rename').click();await page.locator('#project-case-name').fill(`Literal signed-weight couple, ${intervals} explicit intervals`);await page.locator('#project-add').click();
 await page.locator('#project-solution-name').fill('Computed structural reference case');await page.locator('#project-save-solution').click();await expect(page.locator('#project-load-solution')).toBeEnabled();
 const project=await download('project-export','project.json');
 await page.locator('#project-file').setInputFiles({name:'reference-project.json',mimeType:'application/json',buffer:project});await expect(page.locator('#project-load-solution')).toBeEnabled();await page.locator('#project-load-solution').click();await expect(page.locator('#export-json')).toBeEnabled();
 const reopened=await download('export-json','reopened-result.json');check('saved result restored byte-exactly',Buffer.compare(bytes,reopened)===0);const finalRequests=await page.evaluate(()=>window.referenceRequests);check('no extra solve for restore',finalRequests.filter(r=>r.request?.action==='solve').length===1);await writeFile(path.join(output,'requests-final.json'),JSON.stringify(finalRequests,null,2)+'\n');audit.request_counts=Object.fromEntries([...new Set(finalRequests.map(r=>r.request?.action??'runtime'))].map(a=>[a,finalRequests.filter(r=>(r.request?.action??'runtime')===a).length]));
 check('single visible canvas',await page.locator('#viewport canvas').count()===1);await expect(page.locator('#structure-plot svg')).toBeVisible();await expect(page.locator('#mass')).toHaveText('—');await page.screenshot({path:path.join(output,'desktop.png')});
 await page.locator('details').evaluateAll(ns=>ns.forEach(n=>n.open=false));await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();await page.locator('#fit').click();
 check('mobile width',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(output,'mobile.png')});
 audit.renderer=await page.locator('#viewport').evaluate(e=>({dataset:{...e.dataset},canvases:[...e.querySelectorAll('canvas')].map(c=>({width:c.width,height:c.height,attributes:[...c.attributes].map(a=>[a.name,a.value]),webgl:!!(c.getContext('webgl2')||c.getContext('webgl')),canvas2d:!!c.getContext('2d')}))}));
 await writeFile(path.join(output,'events.json'),JSON.stringify(await page.evaluate(()=>window.referenceEvents),null,2)+'\n');
 for(const p of [audit.inputs,audit.source,audit.plan,audit.summary,audit.native,audit.native_report,audit.script,...audit.built_assets])check('unchanged '+p.path,(await pin(p.path)).sha256===p.sha256);
 check('offline HTTP absent',audit.offline_requests.length===0);check('page errors absent',audit.page_errors.length===0);check('network failures absent',audit.network_failures.length===0);for(const n of names)for(const folder of ['openswing','public/kernel','dist/kernel'])check('unchanged '+folder+'/'+n,sha(await readFile(path.join(root,folder,n)))===audit.modules[n]);audit.status='PASS_OFFLINE_STRUCTURAL_REFERENCE_AND_PROJECT_RESTORE';
}catch(e){audit.status='FAILURE_RETAINED';audit.error={message:e.message,stack:e.stack};try{if(page&&!page.isClosed())await writeFile(path.join(output,'requests-at-failure.json'),JSON.stringify(await page.evaluate(()=>window.referenceRequests),null,2)+'\n');}catch{}process.exitCode=1;console.error(e.stack);try{if(page&&!page.isClosed())await page.screenshot({path:path.join(output,'failure.png')});}catch{}}
finally{clearTimeout(timer);try{await browser?.close();}finally{server?.closeAllConnections();if(server?.listening)await new Promise(resolve=>server.close(resolve));}audit.total_seconds=(performance.now()-started)/1000;await save();console.log(JSON.stringify({status:audit.status,startup_seconds:audit.startup_seconds,solve_seconds:audit.solve_seconds,parity:audit.parity,total_seconds:audit.total_seconds}));}
