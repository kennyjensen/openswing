// One offline source-coupled UI solve and native parity; four saved policy generations.
// node scripts/test-source-coupled-browser.mjs NEW_OUTPUT_DIR NATIVE_INTEGRATION_DIR
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
assert([4,5].includes(process.argv.length),'Supply new output, native baseline, and optionally a prior browser stage to resume without solving.');
const resume=process.argv[4]?path.resolve(process.argv[4]):null;
const output=path.resolve(process.argv[2]),nativeStage=path.resolve(process.argv[3]),nativeDir=path.join(nativeStage,'cases','source-160');
await mkdir(output,{recursive:false});
const sha=b=>createHash('sha256').update(b).digest('hex');
const pin=async p=>{const b=await readFile(p);return {path:p,bytes:b.length,sha256:sha(b)};};
const audit={status:'PREPARING',checks:[],page_errors:[],offline_requests:[],network_failures:[],planned_solves:resume?0:1,
  scope:'Unchanged AE-2 [03_90] model at the selected archived ASWING beta 5 / IAS 10 coordinate, using the declared frozen-influence PG0 operating candidate. Offline built UI, full native parity and four saved policy generations. Historical settings remain conditional; this is not experimental validation. Two additional input-only UI transitions perform no solves.',
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
  const plan=JSON.parse(await readFile(path.join(nativeStage,'plan.json'))),report=JSON.parse(await readFile(path.join(nativeStage,'summary.json'))),
    native=JSON.parse(await readFile(path.join(nativeDir,'result.json'))),input=JSON.parse(await readFile(path.join(nativeDir,'request.json')));
  let priorProject;
  if(resume){
    const prior=JSON.parse(await readFile(path.join(resume,'report.json'))),priorRequests=JSON.parse(await readFile(path.join(resume,'requests-at-failure.json')));
    priorProject=await readFile(path.join(resume,'project.json'));
    assert(prior.parity?.max_fraction<=1&&Number.isFinite(prior.solve_seconds));
    assert.equal(priorRequests.filter(r=>r.request?.action==='solve').length,1);
    audit.original_run={startup_seconds:prior.startup_seconds,solve_seconds:prior.solve_seconds,parity:prior.parity,solves:1};
    audit.resume_inputs=await Promise.all(['report.json','requests-at-failure.json','project.json','result.json'].map(n=>pin(path.join(resume,n))));
  }
  check('native integration passed',report.status.startsWith('PASS'));assert.equal(input.numerics.structural_operator,'drela-steady-coupled-v1');
  audit.plan=await pin(path.join(nativeStage,'plan.json'));audit.native=await pin(path.join(nativeDir,'result.json'));audit.script=await pin(fileURLToPath(import.meta.url));
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
  await page.locator('details').evaluateAll(ns=>ns.forEach(n=>n.open=true));
  const templatePath=path.join(root,'examples/isae-ae2-uncoupled-project.json');
  const template=JSON.parse(await readFile(templatePath));audit.configuration_template=await pin(templatePath);
  const config=structuredClone(template.cases[0].configuration);
  Object.assign(config,{source:input.source,filename:'[03_90].asw',mesh:input.panels,numerics:plan.policy,equilibrium:{state:null,enabled:false,label:''}});
  Object.assign(config.fields,{mode:'mounted','freeze-influences':true,'mach-mode':'fixed','pg-mach':'0'});
  const freshSeed={format:'openswing-project',version:2,name:'AE-2 source structure comparison',selected:'ae2-source',cases:[{id:'ae2-source',name:'Original AE-2 beta 5 / IAS 10',configuration:config}],solutions:[],selected_solution:null};
  const seed=resume?JSON.parse(priorProject):freshSeed;
  await writeFile(path.join(output,'input-project.json'),JSON.stringify(seed,null,2)+'\n');
  await page.locator('#project-file').setInputFiles({name:'ae2-source-input.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(seed))});
  const initialLoad=resume?'#project-load-solution':'#project-load';
  await expect(page.locator(initialLoad)).toBeEnabled();await page.locator(initialLoad).click();
  await expect(page.locator('#editor')).toHaveValue(input.source);await expect(page.locator('#solve')).toBeEnabled();
  await expect(page.locator('#mode')).toHaveValue('mounted');await expect(page.locator('#structural-equations')).toHaveValue('aswing-coupled');
  await page.locator('details').evaluateAll(ns=>ns.forEach(n=>n.open=true));
  await expect(page.locator('#error')).toBeHidden();
  const beforeSolve=await page.evaluate(()=>window.referenceRequests);const sourceInspect=beforeSolve.filter(r=>r.request?.action==='inspect').at(-1);
  check('policy used for inspected geometry',JSON.stringify(sourceInspect.request.numerics)===JSON.stringify(plan.policy));
  if(!resume){
    const begin=performance.now();console.log('Starting sole offline source-coupled solve.');await page.locator('#solve').click();
    await expect(page.locator('#result-state')).toHaveText('Converged · mounted equilibrium',{timeout:90000});await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();audit.solve_seconds=(performance.now()-begin)/1000;
  }else{audit.solve_seconds=null;console.log('Continuing UI checks from saved source-coupled result; zero solves.');}
  async function download(id,name){const event=page.waitForEvent('download');await page.locator('#'+id).click();const bytes=await readFile(await(await event).path());await writeFile(path.join(output,name),bytes);return bytes;}
  const bytes=await download('export-json','result.json'),result=JSON.parse(bytes);
  assert.deepEqual(result.software_provenance.modules,audit.modules);assert.deepEqual(result.request,input);assert.deepEqual(result.numerics,plan.policy);
  check('cold source coupled solve',!result.request.initial_state);check('residual',result.converged&&result.residual<=audit.gates.residual);
  check('mounted source coupled scope',result.analysis==='mounted_static'&&!result.structural_only&&result.mass_properties.dynamic_inertia_available===false&&result.mass_properties.spatial_matrix===null&&!Object.hasOwn(result.equilibrium_state,'launch')&&result.strips.length===plan.cases.find(c=>c.name==='source-160').expected_elements);check('nonzero coupled response',Math.abs(result.sensors[0].position_earth[1])>.01&&Number.isFinite(result.sensors[0].beta));
  check('authoritative source recovery',result.structure.strain_source==='source_discrete_constitutive'&&result.elements.every(e=>e.endpoint_traces.length===2));
  audit.parity=compare(native,result);check('full native result parity',audit.parity.max_fraction<=1,audit.parity);
  await page.locator('#tab-structure').click();
  await expect(page.locator('#structure-state')).toContainText('interval constitutive estimates');
  if(!resume){
  await page.locator('#project-name').fill('AE-2 source structure browser verification');await page.locator('#project-rename').click();
  await page.locator('#project-case-name').fill('Original AE-2 beta 5 / IAS 10');await page.locator('#project-update').click();
  await page.locator('#project-solution-name').fill('AE-2 source coupled result');await page.locator('#project-save-solution').click();await expect(page.locator('#project-load-solution')).toBeEnabled();
  }
  const projectBytes=await download('project-export','project.json'),project=JSON.parse(projectBytes);
  if(resume){
    check('resumed project byte-exact',Buffer.compare(projectBytes,priorProject)===0);
    check('resumed result byte-exact',Buffer.compare(bytes,await readFile(path.join(resume,'result.json')))===0);
  }
  const saved=project.solutions.find(s=>s.name==='AE-2 source coupled result');assert.deepEqual(saved.configuration.numerics,plan.policy);assert.deepEqual(saved.data.numerics,plan.policy);
  await page.locator('#project-file').setInputFiles({name:'source-project.json',mimeType:'application/json',buffer:projectBytes});await expect(page.locator('#project-load-solution')).toBeEnabled();
  await page.locator('#project-load-solution').click();await expect(page.locator('#export-json')).toBeEnabled();await expect(page.locator('#structural-equations')).toHaveValue('aswing-coupled');
  const reopened=await download('export-json','reopened-result.json');check('saved source result restored byte-exactly',Buffer.compare(bytes,reopened)===0);
  await page.locator('#tab-structure').click();
  await page.locator('#structure-quantity').selectOption('curvature_change.1');
  await expect(page.locator('#structure-plot svg')).toBeVisible();await expect(page.locator('#mass')).not.toHaveText('—');check('single aircraft canvas',await page.locator('#viewport canvas').count()===1);
  await page.screenshot({path:path.join(output,'desktop.png')});
  await page.locator('details').evaluateAll(ns=>ns.forEach(n=>n.open=false));await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();await page.locator('#fit').click();
  check('mobile width',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(output,'mobile.png')});
  await page.setViewportSize({width:1440,height:1000});await page.locator('details').evaluateAll(ns=>ns.forEach(n=>n.open=true));
  // Input-only regressions: a rejected mode change must retain the selected
  // seed, and a new model must not inherit a previous model's unapplied draft.
  await expect(page.locator('#equilibrium-use')).toBeEnabled();await page.locator('#equilibrium-use').click();
  await expect(page.locator('#equilibrium-enable')).toBeEnabled();await expect(page.locator('#equilibrium-enable')).toBeChecked();
  await page.locator('#tab-distributions').click();await expect(page.locator('#distribution-scale')).toBeEnabled();
  await page.locator('#distribution-scale').fill('1.01');
  await page.locator('#mode').selectOption('rigid');
  await expect(page.locator('#mode')).toHaveValue('mounted');await expect(page.locator('#structural-equations')).toHaveValue('aswing-coupled');
  await expect(page.locator('#equilibrium-enable')).toBeEnabled();await expect(page.locator('#equilibrium-enable')).toBeChecked();
  await expect(page.locator('#error')).toContainText('apply or reload model drafts');
  check('rejected mode change retains coupled mode and enabled loaded seed',true);
  const signedPath=path.join(root,'examples/isae-st3-static-0_3_90.asw'),signedBytes=await readFile(signedPath),signedSource=signedBytes.toString('utf8');
  audit.transition_fixture={...(await pin(signedPath)),scope:'Input-only signed-load import; no solve or numerical comparison.'};
  const beforeImport=(await page.evaluate(()=>window.referenceRequests)).length;
  await page.locator('#file').setInputFiles({name:'signed-static-transition.asw',mimeType:'text/plain',buffer:signedBytes});
  await expect(page.locator('#editor')).toHaveValue(signedSource);await expect(page.locator('#solve')).toBeEnabled();
  await expect(page.locator('#mode')).toHaveValue('structural');await expect(page.locator('#structural-equations')).toHaveValue('midpoint');await expect(page.locator('#error')).toBeHidden();
  const importRequests=(await page.evaluate(()=>window.referenceRequests)).slice(beforeImport).filter(r=>r.request?.action==='inspect');
  check('signed model import replaces old draft and reinspects once with default policy',importRequests.length===2&&importRequests.every(r=>r.request.source===signedSource)&&JSON.stringify(importRequests[0].request.numerics)===JSON.stringify(plan.policy)&&!importRequests[1].request.numerics);
  await expect(page.locator('#equilibrium-enable')).not.toBeChecked();
  await page.locator('#project-file').setInputFiles({name:'source-project-again.json',mimeType:'application/json',buffer:projectBytes});await expect(page.locator('#project-load-solution')).toBeEnabled();
  await page.locator('#project-load-solution').click();await expect(page.locator('#export-json')).toBeEnabled();await expect(page.locator('#structural-equations')).toHaveValue('aswing-coupled');
  check('coupled result remains byte-exact after input-only transitions',Buffer.compare(bytes,await download('export-json','after-transitions-result.json'))===0);
  await expect(page.locator('#distribution-scale')).toBeEnabled();
  await page.locator('#mode').selectOption('structural');await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#structural-equations')).toHaveValue('midpoint');
  await expect(page.locator('#export-json')).toBeDisabled();await expect(page.locator('#error')).toBeHidden();
  check('leaving mounted reinspects historical policy',!(await page.evaluate(()=>window.referenceRequests.filter(r=>r.request?.action==='inspect').at(-1))).request.numerics);
  const sectionPath=path.join(root,'examples/source-section-check-project.json'),sectionBytes=await readFile(sectionPath),section=JSON.parse(sectionBytes);
  audit.general_section_project=await pin(sectionPath);
  await page.locator('#project-file').setInputFiles({name:'general-section-project.json',mimeType:'application/json',buffer:sectionBytes});await expect(page.locator('#project-load-solution')).toBeEnabled();
  await page.locator('#project-load-solution').click();await expect(page.locator('#export-json')).toBeEnabled();await expect(page.locator('#structural-equations')).toHaveValue('aswing-section');
  assert.deepEqual(JSON.parse(await download('export-json','general-section-result.json')),section.solutions[0].data);
  assert.deepEqual(JSON.parse(await download('project-export','general-section-project.json')).solutions,section.solutions);
  check('prior general-section result and sealed solution unchanged',true);
  const zeroPath=path.join(root,'examples/isae-st5-source-static-project.json'),zeroBytes=await readFile(zeroPath),zero=JSON.parse(zeroBytes);
  audit.zero_offset_project=await pin(zeroPath);
  await page.locator('#project-file').setInputFiles({name:'zero-offset-project.json',mimeType:'application/json',buffer:zeroBytes});await expect(page.locator('#project-load-solution')).toBeEnabled();
  await page.locator('#project-load-solution').click();await expect(page.locator('#export-json')).toBeEnabled();await expect(page.locator('#structural-equations')).toHaveValue('aswing');
  const zeroResult=JSON.parse(await download('export-json','zero-offset-result.json'));assert.deepEqual(zeroResult,zero.solutions[0].data);check('prior zero-offset result restored without mutation',true);
  const zeroExport=JSON.parse(await download('project-export','zero-offset-project.json'));assert.deepEqual(zeroExport.solutions,zero.solutions);check('prior zero-offset sealed solutions unchanged',true);
  const legacyPath=path.join(root,'examples/isae-st5-reference-project.json'),legacyBytes=await readFile(legacyPath),legacy=JSON.parse(legacyBytes);
  audit.legacy_project=await pin(legacyPath);
  await page.locator('#project-file').setInputFiles({name:'legacy-project.json',mimeType:'application/json',buffer:legacyBytes});await expect(page.locator('#project-load-solution')).toBeEnabled();
  await page.locator('#project-load-solution').click();await expect(page.locator('#export-json')).toBeEnabled();await expect(page.locator('#structural-equations')).toHaveValue('midpoint');
  const oldResult=JSON.parse(await download('export-json','legacy-result.json'));assert.deepEqual(oldResult,legacy.solutions[0].data);check('historical result restored without mutation',true);
  const oldExport=JSON.parse(await download('project-export','legacy-project.json'));assert.deepEqual(oldExport.solutions,legacy.solutions);check('historical sealed solutions unchanged',true);
  const finalRequests=await page.evaluate(()=>window.referenceRequests);check('declared solve budget; restores did not solve',finalRequests.filter(r=>r.request?.action==='solve').length===audit.planned_solves);
  check('historical project inspect has no source override',!finalRequests.filter(r=>r.request?.action==='inspect').at(-1).request.numerics);
  await writeFile(path.join(output,'requests.json'),JSON.stringify(finalRequests,null,2)+'\n');await writeFile(path.join(output,'events.json'),JSON.stringify(await page.evaluate(()=>window.referenceEvents),null,2)+'\n');
  audit.request_counts=Object.fromEntries([...new Set(finalRequests.map(r=>r.request?.action??'runtime'))].map(a=>[a,finalRequests.filter(r=>(r.request?.action??'runtime')===a).length]));
  for(const p of [...plan.pins,audit.plan,audit.native,audit.script,audit.configuration_template,audit.transition_fixture,audit.general_section_project,audit.zero_offset_project,audit.legacy_project,...audit.built_assets,...(audit.resume_inputs??[])])check('unchanged '+p.path,(await pin(p.path)).sha256===p.sha256);
  for(const n of names)for(const folder of ['openswing','public/kernel','dist/kernel'])check('unchanged '+folder+'/'+n,sha(await readFile(path.join(root,folder,n)))===audit.modules[n]);
  check('offline HTTP absent',audit.offline_requests.length===0);check('page errors absent',audit.page_errors.length===0);check('network failures absent',audit.network_failures.length===0);
  audit.status='PASS_OFFLINE_SOURCE_COUPLED_UI_AND_FOUR_PROJECT_POLICIES';
}catch(e){audit.status='FAILURE_RETAINED';audit.error={message:e.message,stack:e.stack};process.exitCode=1;console.error(e.stack);
  try{if(page&&!page.isClosed()){await writeFile(path.join(output,'requests-at-failure.json'),JSON.stringify(await page.evaluate(()=>window.referenceRequests),null,2)+'\n');await page.screenshot({path:path.join(output,'failure.png')});}}catch{}
}finally{
  clearTimeout(timer);try{await browser?.close();}finally{server?.closeAllConnections();if(server?.listening)await new Promise(resolve=>server.close(resolve));}
  audit.total_seconds=(performance.now()-started)/1000;await writeFile(path.join(output,'report.json'),JSON.stringify(audit,null,2)+'\n');
  console.log(JSON.stringify({status:audit.status,startup_seconds:audit.startup_seconds,solve_seconds:audit.solve_seconds,parity:audit.parity,total_seconds:audit.total_seconds}));
}
