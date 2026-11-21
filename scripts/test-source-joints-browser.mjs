// Two offline built-UI cold solves; native parity, v2 hinge charts and four old projects.
// node scripts/test-source-joints-browser.mjs NEW_OUTPUT_DIR NATIVE_INTEGRATION_DIR
import {chromium} from 'playwright';
import {expect} from '@playwright/test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {createReadStream} from 'node:fs';
import {readFile,writeFile,readdir,mkdir,stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

assert.equal(process.argv.length,4,'Supply a new output directory and the native integration directory.');
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.resolve(process.argv[2]),nativeStage=path.resolve(process.argv[3]);
await mkdir(output,{recursive:false});
const sha=b=>createHash('sha256').update(b).digest('hex');
const pin=async p=>{const b=await readFile(p);return {path:p,bytes:b.length,sha256:sha(b)};};
const read=async p=>JSON.parse(await readFile(p));
const policy={structural:'aswing-section',mounted:'aswing-coupled'};
const oldProjects=[
  ['midpoint','examples/isae-st5-reference-project.json'],
  ['aswing','examples/isae-st5-source-static-project.json'],
  ['aswing-section','examples/source-section-check-project.json'],
  ['aswing-coupled','examples/isae-ae2-source-coupled-project.json'],
];
const audit={status:'PREPARING',checks:[],cases:[],page_errors:[],offline_requests:[],network_failures:[],planned_solves:2,
  scope:'Existing OpenSwing articulated.asw fixture, one source-section structural static and one source-coupled mounted cold solve. Full saved-native parity, version-2 hinge chart and project restoration, shared Solver report, curvature plots and four prior policy projects. This is implementation integration, not archived ASWING agreement or experimental validation.',
  gates:{absolute:2e-8,relative:2e-8,residual:1e-8},exclusions:['evaluations'],
  exclusion_reason:'Execution counter only; all native physical outputs and their metadata are compared.',
  caps:{startup_ms:180000,each_solve_ms:90000,internal_total_ms:435000,planned_owner_ms:450000},retries:0};
const check=(name,passed,evidence={})=>{audit.checks.push({name,passed:!!passed,...evidence});assert(passed,name);};
function compare(expected,actual){
  const s={numeric:0,leaves:0,max_absolute:0,max_fraction:0,worst:null};
  function visit(e,a,p){
    if(audit.exclusions.includes(p))return;
    if(typeof e==='number'){
      assert.equal(typeof a,'number',p);assert(Number.isFinite(e)&&Number.isFinite(a),p);
      const d=Math.abs(a-e),limit=audit.gates.absolute+audit.gates.relative*Math.abs(e);
      s.numeric++;s.leaves++;s.max_absolute=Math.max(s.max_absolute,d);
      if(d/limit>s.max_fraction)Object.assign(s,{max_fraction:d/limit,worst:p});
      assert(d<=limit,p+' numerical parity');
    }else if(Array.isArray(e)){
      assert(Array.isArray(a)&&a.length===e.length,p);e.forEach((v,i)=>visit(v,a[i],`${p}[${i}]`));
    }else if(e!==null&&typeof e==='object'){
      assert(a!==null&&typeof a==='object',p);
      for(const [k,v] of Object.entries(e)){assert(Object.hasOwn(a,k),p+'.'+k);visit(v,a[k],p?p+'.'+k:k);}
    }else{s.leaves++;assert.deepEqual(a,e,p);}
  }
  visit(expected,actual,'');return s;
}
let browser,server,page,timer;let offline=false;
const started=performance.now();
try{
  const plan=await read(path.join(nativeStage,'plan.json')),summary=await read(path.join(nativeStage,'summary.json'));
  check('native integration passed',summary.status.startsWith('PASS'));
  audit.plan=await pin(path.join(nativeStage,'plan.json'));audit.native_summary=await pin(path.join(nativeStage,'summary.json'));
  audit.script=await pin(fileURLToPath(import.meta.url));audit.inputs=[];
  for(const p of plan.pins)check('frozen native input '+p.path,(await pin(p.path)).sha256===p.sha256);
  const names=(await readdir(path.join(root,'openswing'))).filter(n=>n.endsWith('.py')).sort();
  assert.deepEqual(names,Object.keys(plan.kernel_pins).sort());audit.modules=plan.kernel_pins;
  for(const n of names)for(const folder of ['openswing','public/kernel','dist/kernel'])check(folder+'/'+n,sha(await readFile(path.join(root,folder,n)))===audit.modules[n]);
  const cases=[];
  for(const name of ['structural','mounted']){
    const directory=path.join(nativeStage,'cases',name);
    const [request,inputProject,native]=await Promise.all(['request.json','input-project.json','result.json'].map(n=>read(path.join(directory,n))));
    for(const n of ['request.json','input-project.json','result.json'])audit.inputs.push(await pin(path.join(directory,n)));
    assert.equal(request.mode,name);assert.equal(request.action,'solve');assert(!request.initial_state);
    assert.equal(request.source,await readFile(path.join(root,'examples/articulated.asw'),'utf8'));
    assert.equal(request.numerics.structural_operator,name==='structural'?'drela-steady-section-v1':'drela-steady-coupled-v1');
    assert.equal(native.equilibrium_state.version,2);assert(native.hinges.length>0);
    assert.equal(inputProject.solutions.length,0);
    cases.push({name,request,inputProject,native});
  }
  audit.inputs.push(await pin(path.join(root,'examples/articulated.asw')));
  audit.prior_projects=[];const priorInputs=[];
  for(const [selection,relative] of oldProjects){
    const file=path.join(root,relative),bytes=await readFile(file);
    audit.prior_projects.push(await pin(file));priorInputs.push({selection,bytes,project:JSON.parse(bytes)});
  }
  const serveRoot=path.join(root,'dist'),mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.css':'text/css','.svg':'image/svg+xml','.woff2':'font/woff2'};
  audit.built_assets=[];
  for(const n of ['index.html',...(await readdir(path.join(serveRoot,'assets'))).map(n=>'assets/'+n)])audit.built_assets.push(await pin(path.join(serveRoot,n)));
  server=createServer(async(req,res)=>{
    try{
      const rel=decodeURIComponent(new URL(req.url,'http://local').pathname),p=path.resolve(serveRoot,'.'+(rel==='/'?'/index.html':rel));
      assert(p.startsWith(serveRoot+path.sep));const st=await stat(p);assert(st.isFile());
      res.writeHead(200,{'Content-Type':mime[path.extname(p)]||'application/octet-stream','Content-Length':st.size});createReadStream(p).pipe(res);
    }catch{res.writeHead(404);res.end('Not found');}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));audit.url=`http://127.0.0.1:${server.address().port}`;
  const executable=process.env.OPENSWING_CHROMIUM_EXECUTABLE||'/tmp/aswing-chromium/chrome-linux/chrome';
  const args=process.env.OPENSWING_WEBGL_DRIVER==='mesa'?['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native','--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'];
  audit.browser_environment=Object.fromEntries(['LD_LIBRARY_PATH','VK_ICD_FILENAMES','OPENSWING_WEBGL_DRIVER','LP_NUM_THREADS'].map(k=>[k,process.env[k]??null]));
  browser=await chromium.launch({headless:true,executablePath:executable,args});audit.chromium=browser.version();
  timer=setTimeout(()=>{audit.timeout=true;browser.close().catch(()=>{});},Math.max(1,audit.caps.internal_total_ms-(performance.now()-started)));
  const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});page=await context.newPage();page.setDefaultTimeout(60000);
  page.on('pageerror',e=>audit.page_errors.push(e.message));
  context.on('requestfailed',r=>audit.network_failures.push({url:r.url(),failure:r.failure()}));
  context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))audit.offline_requests.push(r.url());});
  await page.addInitScript(()=>{
    window.referenceRequests=[];window.referenceEvents=[];const WorkerClass=window.Worker;
    window.Worker=class extends WorkerClass{
      constructor(...args){super(...args);this.addEventListener('message',e=>{if(e.data?.type==='progress'||e.data?.progress||e.data?.stage)window.referenceEvents.push(structuredClone(e.data));});}
      postMessage(message,...rest){window.referenceRequests.push(structuredClone(message));return super.postMessage(message,...rest);}
    };
  });
  await page.goto(audit.url);await expect(page.locator('#solve')).toBeEnabled({timeout:audit.caps.startup_ms});audit.startup_seconds=(performance.now()-started)/1000;
  await context.setOffline(true);offline=true;
  async function openControls(){await page.locator('details').evaluateAll(nodes=>nodes.forEach(n=>n.open=true));}
  async function download(id,name){
    const event=page.waitForEvent('download');await page.locator('#'+id).click();
    const bytes=await readFile(await(await event).path());await writeFile(path.join(output,name),bytes);return bytes;
  }
  async function loadProject(bytes,solution){
    const project=JSON.parse(bytes);
    await openControls();await page.locator('#project-file').setInputFiles({name:'joint-check-project.json',mimeType:'application/json',buffer:bytes});
    await expect(page.locator('#project-name')).toHaveValue(project.name);
    await expect(page.locator('#project-cases')).toHaveValue(project.selected??'');
    const selector=solution?'#project-load-solution':'#project-load';
    await expect(page.locator(selector)).toBeEnabled();await page.locator(selector).click();
    await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();
    await openControls();
  }
  for(const {name,request,inputProject,native} of cases){
    const caseAudit={name};audit.cases.push(caseAudit);
    const inputBytes=Buffer.from(JSON.stringify(inputProject));await writeFile(path.join(output,name+'-input-project.json'),inputBytes);
    await loadProject(inputBytes,false);
    await expect(page.locator('#editor')).toHaveValue(request.source);await expect(page.locator('#mode')).toHaveValue(name);
    await expect(page.locator('#structural-equations')).toHaveValue(policy[name]);await expect(page.locator('#hinge-note')).toBeVisible();
    await expect(page.locator('#hinge-note')).toContainText('structural static');
    const inspect=(await page.evaluate(()=>window.referenceRequests)).filter(r=>r.request?.action==='inspect').at(-1);
    assert.deepEqual(inspect.request.numerics,request.numerics);
    console.log('Starting sole '+name+' cold UI solve.');const begin=performance.now();await page.locator('#solve').click();
    await expect(page.locator('#result-state')).toHaveText(name==='structural'?'Converged · ASWING static · experimental':'Converged · mounted equilibrium',{timeout:audit.caps.each_solve_ms});
    await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();caseAudit.solve_seconds=(performance.now()-begin)/1000;
    const bytes=await download('export-json',name+'-result.json'),result=JSON.parse(bytes);
    assert.deepEqual(result.request,request);assert.deepEqual(result.numerics,request.numerics);assert.deepEqual(result.software_provenance.modules,audit.modules);
    check(name+' fresh full residual',result.converged&&result.residual<=audit.gates.residual);
    const equilibrium=result.equilibrium_state;
    check(name+' source v2 hinge state without dynamic launch',equilibrium.version===2&&equilibrium.hinge_charts.length===result.hinges.length&&!Object.hasOwn(equilibrium,'launch'));
    result.hinges.forEach((h,i)=>{
      assert.equal(equilibrium.hinge_charts[i].joint,h.joint);
      check(name+' chart equals full solved Jangle angle '+h.joint,Math.abs(equilibrium.hinge_charts[i].angle_rad-h.angle_deg*Math.PI/180)<=2e-8);
    });
    check(name+' nonzero sprung response',result.hinges.some(h=>Math.abs(h.angle_deg)>1e-6));
    check(name+' source recovery available',result.structure.strain_source==='source_discrete_constitutive'&&result.elements.every(e=>e.endpoint_traces.length===2));
    caseAudit.parity=compare(native,result);check(name+' all native result fields',caseAudit.parity.max_fraction<=1,caseAudit.parity);
    await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText('SPRUNG HINGES');
    for(const h of result.hinges){
      await expect(page.locator('#pane-report')).toContainText(`hinge angle [deg] ${h.angle_deg.toPrecision(7)}`);
      await expect(page.locator('#pane-report')).toContainText(`beam-1 structural moment [F·L] ${h.structural_moment.toPrecision(7)} (${h.moment_trace} trace)`);
    }
    check(name+' Solver report displays each saved hinge angle and moment',true);
    await page.locator('#project-solution-name').fill('Articulated '+name+' source result');await page.locator('#project-save-solution').click();
    await expect(page.locator('#project-load-solution')).toBeEnabled();
    const projectBytes=await download('project-export',name+'-project.json'),project=JSON.parse(projectBytes);
    assert.equal(project.solutions.length,1);assert.deepEqual(project.solutions[0].data.equilibrium_state.hinge_charts,equilibrium.hinge_charts);
    await loadProject(projectBytes,true);await expect(page.locator('#export-json')).toBeEnabled();
    check(name+' saved result restored byte-exactly',Buffer.compare(bytes,await download('export-json',name+'-reopened-result.json'))===0);
    check(name+' saved project restored byte-exactly',Buffer.compare(projectBytes,await download('project-export',name+'-reopened-project.json'))===0);
    await page.locator('#tab-structure').click();await page.locator('#structure-quantity').selectOption('curvature_change.1');
    await expect(page.locator('#structure-plot svg')).toBeVisible();await expect(page.locator('#structure-state')).toContainText('interval constitutive estimates');
    check(name+' exactly one aircraft canvas',await page.locator('#viewport canvas').count()===1);
    caseAudit.renderer=await page.locator('#viewport canvas').getAttribute('data-renderer');
    await page.screenshot({path:path.join(output,name+'-desktop.png')});
    console.log(name+' parity PASS '+caseAudit.parity.numeric+' numerical values.');
  }
  await page.locator('details').evaluateAll(nodes=>nodes.forEach(n=>n.open=false));await page.setViewportSize({width:390,height:844});
  await page.locator('#workspace-tab-plots').click();await page.locator('#fit').click();
  check('mobile width',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(output,'mounted-mobile.png')});
  await page.setViewportSize({width:1440,height:1000});
  for(const {selection,bytes,project} of priorInputs){
    await loadProject(bytes,true);
    await expect(page.locator('#export-json')).toBeEnabled();await expect(page.locator('#structural-equations')).toHaveValue(selection);
    const selected=project.solutions.find(s=>s.id===project.selected_solution)??project.solutions[0];
    assert.deepEqual(JSON.parse(await download('export-json',selection+'-prior-result.json')),selected.data);
    const exported=JSON.parse(await download('project-export',selection+'-prior-project.json'));
    check(selection+' all prior sealed solution bytes unchanged',JSON.stringify(exported.solutions)===JSON.stringify(project.solutions));
  }
  const requests=await page.evaluate(()=>window.referenceRequests),solves=requests.filter(r=>r.request?.action==='solve');
  check('exactly two cold solves and no restore solves',solves.length===2);
  // Worker transport serializes requests as JSON; undefined optional fields are omitted.
  assert.deepEqual(JSON.parse(JSON.stringify(solves.map(s=>s.request))),cases.map(c=>c.request));
  await writeFile(path.join(output,'requests.json'),JSON.stringify(requests,null,2)+'\n');
  await writeFile(path.join(output,'events.json'),JSON.stringify(await page.evaluate(()=>window.referenceEvents),null,2)+'\n');
  audit.request_counts=Object.fromEntries([...new Set(requests.map(r=>r.request?.action??'runtime'))].map(a=>[a,requests.filter(r=>(r.request?.action??'runtime')===a).length]));
  audit.parity_totals={numeric:audit.cases.reduce((n,c)=>n+c.parity.numeric,0),
    leaves:audit.cases.reduce((n,c)=>n+c.parity.leaves,0),
    max_absolute:Math.max(...audit.cases.map(c=>c.parity.max_absolute)),
    max_fraction:Math.max(...audit.cases.map(c=>c.parity.max_fraction))};
  for(const p of [...plan.pins,audit.plan,audit.native_summary,audit.script,...audit.inputs,...audit.prior_projects,...audit.built_assets])check('unchanged '+p.path,(await pin(p.path)).sha256===p.sha256);
  for(const n of names)for(const folder of ['openswing','public/kernel','dist/kernel'])check('unchanged '+folder+'/'+n,sha(await readFile(path.join(root,folder,n)))===audit.modules[n]);
  check('offline HTTP absent',audit.offline_requests.length===0);check('page errors absent',audit.page_errors.length===0);check('network failures absent',audit.network_failures.length===0);
  audit.status='PASS_OFFLINE_SOURCE_JOINTS_TWO_MODES_AND_FOUR_PRIOR_PROJECTS';
}catch(error){
  audit.status='FAILURE_RETAINED';audit.error={message:error.message,stack:error.stack};process.exitCode=1;console.error(error.stack);
  try{if(page&&!page.isClosed()){
    await writeFile(path.join(output,'requests-at-failure.json'),JSON.stringify(await page.evaluate(()=>window.referenceRequests),null,2)+'\n');
    await page.screenshot({path:path.join(output,'failure.png')});
  }}catch{}
}finally{
  clearTimeout(timer);try{await browser?.close();}finally{server?.closeAllConnections();if(server?.listening)await new Promise(resolve=>server.close(resolve));}
  audit.total_seconds=(performance.now()-started)/1000;await writeFile(path.join(output,'report.json'),JSON.stringify(audit,null,2)+'\n');
  console.log(JSON.stringify({status:audit.status,startup_seconds:audit.startup_seconds,cases:audit.cases,total_seconds:audit.total_seconds}));
}
