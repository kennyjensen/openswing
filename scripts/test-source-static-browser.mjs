// One offline UI solve, native parity, new/legacy project restore and policy switching.
// node scripts/test-source-static-browser.mjs NEW_OUTPUT_DIR NATIVE_BASELINE_DIR
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
assert.equal(process.argv.length,4,'Supply new output and completed native baseline directories.');
const output=path.resolve(process.argv[2]),nativeDir=path.resolve(process.argv[3]);
await mkdir(output,{recursive:false});
const sha=b=>createHash('sha256').update(b).digest('hex');
const pin=async p=>{const b=await readFile(p);return {path:p,bytes:b.length,sha256:sha(b)};};
const audit={status:'PREPARING',checks:[],page_errors:[],offline_requests:[],network_failures:[],planned_solves:1,
  scope:'Unchanged ST5 original case, source static policy; offline built UI, full native parity, saved source and historical projects.',
  gates:{absolute:2e-8,relative:2e-8,residual:1e-8},exclusions:['evaluations'],exclusion_reason:'Execution counter only; no physical outputs excluded.'};
const check=(name,ok,details={})=>{audit.checks.push({name,passed:!!ok,...details});assert(ok,name);};
function compare(expected,actual){
  const s={numeric:0,leaves:0,max_absolute:0,max_fraction:0,worst:null};
  function visit(e,a,p){
    if(audit.exclusions.includes(p))return;
    if(typeof e==='number'){
      assert.equal(typeof a,'number',p);assert(Number.isFinite(a)&&Number.isFinite(e),p);
      const d=Math.abs(a-e),limit=audit.gates.absolute+audit.gates.relative*Math.abs(e);s.numeric++;s.leaves++;s.max_absolute=Math.max(s.max_absolute,d);
      if(d/limit>s.max_fraction)Object.assign(s,{max_fraction:d/limit,worst:p});assert(d<=limit,p+' numerical parity');
    }else if(Array.isArray(e)){assert(Array.isArray(a)&&a.length===e.length,p);e.forEach((v,i)=>visit(v,a[i],`${p}[${i}]`));}
    else if(e!==null&&typeof e==='object'){assert(a!==null&&typeof a==='object',p);for(const [k,v] of Object.entries(e)){assert(Object.hasOwn(a,k),p+'.'+k);visit(v,a[k],p?p+'.'+k:k);}}
    else{s.leaves++;assert.deepEqual(a,e,p);}
  }
  visit(expected,actual,'');return s;
}
let browser,server,page,timer;let offline=false;const started=performance.now();
try{
  const plan=JSON.parse(await readFile(path.join(nativeDir,'plan.json'))),report=JSON.parse(await readFile(path.join(nativeDir,'report.json'))),
    native=JSON.parse(await readFile(path.join(nativeDir,'result.json'))),input=JSON.parse(await readFile(path.join(nativeDir,'request.json')));
  check('native baseline passed',report.status==='PASS_NATIVE_BRIDGE_BASELINE');
  audit.plan=await pin(path.join(nativeDir,'plan.json'));audit.native=await pin(path.join(nativeDir,'result.json'));audit.script=await pin(fileURLToPath(import.meta.url));
  for(const p of plan.pins)check('frozen '+p.path,(await pin(p.path)).sha256===p.sha256);
  const names=(await readdir(path.join(root,'openswing'))).filter(n=>n.endsWith('.py')).sort();
  assert.deepEqual(names,Object.keys(plan.kernel_pins).sort());audit.modules=plan.kernel_pins;
  for(const n of names)for(const folder of ['openswing','public/kernel','dist/kernel'])check(folder+'/'+n,sha(await readFile(path.join(root,folder,n)))===audit.modules[n]);
  const serveRoot=path.join(root,'dist'),mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.css':'text/css','.svg':'image/svg+xml','.woff2':'font/woff2'};
  audit.built_assets=[];for(const n of ['index.html',...(await readdir(path.join(serveRoot,'assets'))).map(n=>'assets/'+n)])audit.built_assets.push(await pin(path.join(serveRoot,n)));
  server=createServer(async(req,res)=>{try{const rel=decodeURIComponent(new URL(req.url,'http://local').pathname),p=path.resolve(serveRoot,'.'+(rel==='/'?'/index.html':rel));assert(p.startsWith(serveRoot+path.sep));const s=await stat(p);assert(s.isFile());res.writeHead(200,{'Content-Type':mime[path.extname(p)]||'application/octet-stream','Content-Length':s.size});createReadStream(p).pipe(res);}catch{res.writeHead(404);res.end('Not found');}});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));audit.url=`http://127.0.0.1:${server.address().port}`;
  const executable=process.env.OPENSWING_CHROMIUM_EXECUTABLE||'/tmp/aswing-chromium/chrome-linux/chrome';
  const args=process.env.OPENSWING_WEBGL_DRIVER==='mesa'?['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native','--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'];
  audit.browser_environment=Object.fromEntries(['LD_LIBRARY_PATH','VK_ICD_FILENAMES','OPENSWING_WEBGL_DRIVER','LP_NUM_THREADS'].map(k=>[k,process.env[k]??null]));
  browser=await chromium.launch({headless:true,executablePath:executable,args});audit.chromium=browser.version();
  timer=setTimeout(()=>{audit.timeout=true;browser.close().catch(()=>{});},285000);
  const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});page=await context.newPage();page.setDefaultTimeout(60000);
  page.on('pageerror',e=>audit.page_errors.push(e.message));context.on('requestfailed',r=>audit.network_failures.push({url:r.url(),failure:r.failure()}));context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))audit.offline_requests.push(r.url());});
  await page.addInitScript(()=>{window.referenceRequests=[];window.referenceEvents=[];const W=window.Worker;window.Worker=class extends W{constructor(...a){super(...a);this.addEventListener('message',e=>{if(e.data?.type==='progress'||e.data?.progress||e.data?.stage)window.referenceEvents.push(structuredClone(e.data));});}postMessage(m,...r){window.referenceRequests.push(structuredClone(m));return super.postMessage(m,...r);}};});
  await page.goto(audit.url);await expect(page.locator('#solve')).toBeEnabled({timeout:180000});audit.startup_seconds=(performance.now()-started)/1000;
  await context.setOffline(true);offline=true;
  await page.locator('#file').setInputFiles({name:'isae-st5-static-20lb_80_20.asw',mimeType:'text/plain',buffer:Buffer.from(input.source)});
  await expect(page.locator('#editor')).toHaveValue(input.source);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#node-file').setInputFiles({name:'reference-mesh.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({format:'openswing-mesh',version:1,panels:input.panels}))});
  await page.waitForFunction(()=>!document.querySelector('#node-file').value);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('structural');await page.locator('details').evaluateAll(ns=>ns.forEach(n=>n.open=true));
  await page.locator('#structural-equations').selectOption('aswing');await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();
  await expect(page.locator('#structural-equations')).toHaveValue('aswing');await page.locator('#static-gravity-mode').selectOption('file');
  await page.locator('#tab-nodes').click();
  for(const [beam,count] of Object.entries(plan.mesh.intervals_by_beam)){await page.locator('#node-beam').selectOption(beam);await expect(page.locator('#node-table tbody tr')).toHaveCount(count+1);}
  const beforeSolve=await page.evaluate(()=>window.referenceRequests);const sourceInspect=beforeSolve.filter(r=>r.request?.action==='inspect').at(-1);
  check('policy used for inspected geometry',JSON.stringify(sourceInspect.request.numerics)===JSON.stringify(plan.policy));
  const begin=performance.now();console.log('Starting sole offline source static solve.');await page.locator('#solve').click();
  await expect(page.locator('#result-state')).toHaveText('Converged · ASWING static · experimental',{timeout:90000});await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();audit.solve_seconds=(performance.now()-begin)/1000;
  async function download(id,name){const event=page.waitForEvent('download');await page.locator('#'+id).click();const bytes=await readFile(await(await event).path());await writeFile(path.join(output,name),bytes);return bytes;}
  const bytes=await download('export-json','result.json'),result=JSON.parse(bytes);
  assert.deepEqual(result.software_provenance.modules,audit.modules);assert.deepEqual(result.request,input);assert.deepEqual(result.numerics,plan.policy);
  check('cold source static solve',!result.request.initial_state);check('residual',result.converged&&result.residual<=audit.gates.residual);
  check('signed static scope',result.structural_only&&result.mass_properties.physical===false&&!Object.hasOwn(result.equilibrium_state,'launch')&&result.strips.length===0);
  check('authoritative source recovery',result.structure.strain_source==='source_discrete_constitutive'&&result.elements.every(e=>e.endpoint_traces.length===2));
  audit.parity=compare(native,result);check('full native result parity',audit.parity.max_fraction<=1,audit.parity);
  await expect(page.locator('#structure-state')).toContainText('interval constitutive estimates');
  await page.locator('#project-name').fill('ASWING source static policy browser verification');await page.locator('#project-rename').click();
  await page.locator('#project-case-name').fill('Literal ST5, 70 intervals, source static equations');await page.locator('#project-add').click();
  await page.locator('#project-solution-name').fill('Source static result');await page.locator('#project-save-solution').click();await expect(page.locator('#project-load-solution')).toBeEnabled();
  const projectBytes=await download('project-export','project.json'),project=JSON.parse(projectBytes);
  const saved=project.solutions.find(s=>s.name==='Source static result');assert.deepEqual(saved.configuration.numerics,plan.policy);assert.deepEqual(saved.data.numerics,plan.policy);
  await page.locator('#project-file').setInputFiles({name:'source-project.json',mimeType:'application/json',buffer:projectBytes});await expect(page.locator('#project-load-solution')).toBeEnabled();
  await page.locator('#project-load-solution').click();await expect(page.locator('#export-json')).toBeEnabled();await expect(page.locator('#structural-equations')).toHaveValue('aswing');
  const reopened=await download('export-json','reopened-result.json');check('saved source result restored byte-exactly',Buffer.compare(bytes,reopened)===0);
  await expect(page.locator('#structure-plot svg')).toBeVisible();await expect(page.locator('#mass')).toHaveText('—');check('single aircraft canvas',await page.locator('#viewport canvas').count()===1);
  await page.screenshot({path:path.join(output,'desktop.png')});
  await page.locator('details').evaluateAll(ns=>ns.forEach(n=>n.open=false));await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();await page.locator('#fit').click();
  check('mobile width',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(output,'mobile.png')});
  await page.setViewportSize({width:1440,height:1000});await page.locator('details').evaluateAll(ns=>ns.forEach(n=>n.open=true));
  await page.locator('#mode').selectOption('mounted');await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#structural-equations')).toHaveValue('midpoint');
  await expect(page.locator('#export-json')).toBeDisabled();await expect(page.locator('#error')).toBeHidden();
  check('leaving structural reinspects historical policy',!(await page.evaluate(()=>window.referenceRequests.filter(r=>r.request?.action==='inspect').at(-1))).request.numerics);
  const legacyPath=path.join(root,'examples/isae-st5-reference-project.json'),legacyBytes=await readFile(legacyPath),legacy=JSON.parse(legacyBytes);
  audit.legacy_project=await pin(legacyPath);
  await page.locator('#project-file').setInputFiles({name:'legacy-project.json',mimeType:'application/json',buffer:legacyBytes});await expect(page.locator('#project-load-solution')).toBeEnabled();
  await page.locator('#project-load-solution').click();await expect(page.locator('#export-json')).toBeEnabled();await expect(page.locator('#structural-equations')).toHaveValue('midpoint');
  const oldResult=JSON.parse(await download('export-json','legacy-result.json'));assert.deepEqual(oldResult,legacy.solutions[0].data);check('historical result restored without mutation',true);
  const oldExport=JSON.parse(await download('project-export','legacy-project.json'));assert.deepEqual(oldExport.solutions,legacy.solutions);check('historical sealed solutions unchanged',true);
  const finalRequests=await page.evaluate(()=>window.referenceRequests);check('only one solve; restores did not solve',finalRequests.filter(r=>r.request?.action==='solve').length===1);
  check('historical project inspect has no source override',!finalRequests.filter(r=>r.request?.action==='inspect').at(-1).request.numerics);
  await writeFile(path.join(output,'requests.json'),JSON.stringify(finalRequests,null,2)+'\n');await writeFile(path.join(output,'events.json'),JSON.stringify(await page.evaluate(()=>window.referenceEvents),null,2)+'\n');
  audit.request_counts=Object.fromEntries([...new Set(finalRequests.map(r=>r.request?.action??'runtime'))].map(a=>[a,finalRequests.filter(r=>(r.request?.action??'runtime')===a).length]));
  for(const p of [...plan.pins,audit.plan,audit.native,audit.script,...audit.built_assets])check('unchanged '+p.path,(await pin(p.path)).sha256===p.sha256);
  for(const n of names)for(const folder of ['openswing','public/kernel','dist/kernel'])check('unchanged '+folder+'/'+n,sha(await readFile(path.join(root,folder,n)))===audit.modules[n]);
  check('offline HTTP absent',audit.offline_requests.length===0);check('page errors absent',audit.page_errors.length===0);check('network failures absent',audit.network_failures.length===0);
  audit.status='PASS_OFFLINE_SOURCE_STATIC_UI_AND_PROJECTS';
}catch(e){audit.status='FAILURE_RETAINED';audit.error={message:e.message,stack:e.stack};process.exitCode=1;console.error(e.stack);
  try{if(page&&!page.isClosed()){await writeFile(path.join(output,'requests-at-failure.json'),JSON.stringify(await page.evaluate(()=>window.referenceRequests),null,2)+'\n');await page.screenshot({path:path.join(output,'failure.png')});}}catch{}
}finally{
  clearTimeout(timer);try{await browser?.close();}finally{server?.closeAllConnections();if(server?.listening)await new Promise(resolve=>server.close(resolve));}
  audit.total_seconds=(performance.now()-started)/1000;await writeFile(path.join(output,'report.json'),JSON.stringify(audit,null,2)+'\n');
  console.log(JSON.stringify({status:audit.status,startup_seconds:audit.startup_seconds,solve_seconds:audit.solve_seconds,parity:audit.parity,total_seconds:audit.total_seconds}));
}
