// One offline built-UI source Euler-BDF cold trajectory + one checkpoint continuation.
// node scripts/test-source-time-browser.mjs NEW_OUTPUT_DIR COMPLETED_NATIVE_DIR
// Root owns the outer 300 s supervisor. No native solve is performed by this runner.
import {chromium} from 'playwright';
import {expect} from '@playwright/test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {createReadStream} from 'node:fs';
import {readFile,writeFile,readdir,mkdir,stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {movingVacuumFrame,movingVacuumTimeRequest,numericalRequest} from '../web/numerical-policy.js';

assert.equal(process.argv.length,4,'Supply a new output directory and completed native baseline directory.');
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.resolve(process.argv[2]),nativeStage=path.resolve(process.argv[3]);
await mkdir(output,{recursive:false});
const sha=b=>createHash('sha256').update(b).digest('hex');
const pin=async p=>{const b=await readFile(p);return {path:p,bytes:b.length,sha256:sha(b)};};
const wire=x=>JSON.parse(JSON.stringify(x));
const write=async(name,x)=>writeFile(path.join(output,name),JSON.stringify(x,null,2)+'\n');
const physicalActions=['solve','modes','frequency','time','launch_time','resume_time','stability','rom','flow_survey'];
const executionKeys=new Set(['evaluations','iterations','newton_iterations','jacobian_builds','residual_evaluations','factorizations','linear_solves']);
const audit={status:'PREPARING',checks:[],planned_cold_solves:1,planned_continuations:1,
  scope:'Synthetic rigid prescribed-frame source Euler-BDF time response and saved-history continuation; not archived ASWING agreement.',
  duration_cap_seconds:300,solve_cap_seconds:120,gates:{absolute:2e-8,relative:2e-8,residual:1e-8},
  exclusions:[],exclusions_reason:'Execution counters only. Every other native result field, including all snapshot/restart physical fields, is compared.',
  page_errors:[],offline_requests:[],external_requests:[],network_failures:[]};
function check(name,ok,details={}){audit.checks.push({name,passed:!!ok,...details});assert(ok,name);}
function compare(expected,actual,label){
  const s={numeric:0,leaves:0,max_absolute:0,max_fraction:0,worst:null};
  function visit(e,a,p){
    if(typeof e==='number'){
      assert.equal(typeof a,'number',p);assert(Number.isFinite(e)&&Number.isFinite(a),p);
      const d=Math.abs(a-e),limit=audit.gates.absolute+audit.gates.relative*Math.abs(e);
      s.numeric++;s.leaves++;s.max_absolute=Math.max(s.max_absolute,d);
      if(d/limit>s.max_fraction)Object.assign(s,{max_fraction:d/limit,worst:p});
      assert(d<=limit,`${p}: ${d} > ${limit}`);
    }else if(Array.isArray(e)){
      assert(Array.isArray(a)&&e.length===a.length,p);e.forEach((v,i)=>visit(v,a[i],`${p}[${i}]`));
    }else if(e!==null&&typeof e==='object'){
      assert(a!==null&&typeof a==='object'&&!Array.isArray(a),p);
      for(const [k,v] of Object.entries(e)){
        assert(Object.hasOwn(a,k),p+'.'+k);
        if(executionKeys.has(k)){audit.exclusions.push(p+'.'+k);continue;}
        visit(v,a[k],p+'.'+k);
      }
    }else{s.leaves++;assert.deepEqual(a,e,p);}
  }
  visit(expected,actual,label);return s;
}
function timeChecks(result,label){
  check(label+' converged',result.analysis==='time_response'&&result.converged);
  check(label+' source Euler method',result.temporal_policy==='drela-euler-bdf-v1');
  for(const [i,s] of result.snapshots.entries()){
    check(`${label} snapshot ${i} residual`,Number.isFinite(s.residual)&&s.residual<=audit.gates.residual);
    const h=s.restart.state;
    check(`${label} snapshot ${i} Euler histories`,Array.isArray(h.source_angles)&&h.source_angles.length===5
      &&h.source_angles.every(q=>q.length===3&&q.every(Number.isFinite))&&h.source_attitude.length===3&&h.source_attitude.every(Number.isFinite));
    const a=s.restart.accepted_method;
    if(a.kind==='bdf')check(`${label} snapshot ${i} accepted Euler method`,a.scheme==='drela-euler-bdf-v1');
  }
}

let server,browser,page,timer,offline=false;const began=performance.now();
try{
  const names=['plan.json','report.json','request.json','result.json','checkpoint.json','resume-request.json','resumed-result.json'];
  const data=Object.fromEntries(await Promise.all(names.map(async name=>[name,JSON.parse(await readFile(path.join(nativeStage,name)))])));
  const plan=data['plan.json'],report=data['report.json'],input=data['request.json'],native=data['result.json'];
  const expectedResume=data['resumed-result.json'],resumeInput=data['resume-request.json'];
  check('native baseline passed',report.status==='PASS_NATIVE_SOURCE_MOVING_TIME');
  check('native exactly one cold and one continuation',report.actual_cold_calls===1&&report.actual_resume_calls===1);
  assert.equal(input.action,'time');assert.equal(input.mode,'time');assert.equal(input.condition,null);
  assert.deepEqual(input.numerics,{beam_interpolation:'drela-segspl-v1',structural_operator:'drela-moving-vacuum-v1'});
  assert.equal(input.time.frame,'prescribed');assert.equal(input.time.order,2);assert.equal(input.time.duration,.08);assert.equal(input.time.dt,.02);
  assert.deepEqual(plan.continuation_options,{duration:.02,dt:.02,order:2,accuracy:null});
  const sourceFile=path.resolve(root,plan.source_file);assert.equal(await readFile(sourceFile,'utf8'),input.source);
  assert.equal(sha(Buffer.from(input.source)),plan.source_sha256);
  audit.inputs=await Promise.all([...names.map(n=>path.join(nativeStage,n)),sourceFile,fileURLToPath(import.meta.url),
    ...['web/numerical-policy.js','web/saved-state-data.js','web/time-checkpoint.js','web/time-results.js','web/solution-data.js'].map(p=>path.join(root,p))].map(pin));
  audit.modules=plan.kernel_pins;
  const moduleNames=(await readdir(path.join(root,'openswing'))).filter(n=>n.endsWith('.py')).sort();
  assert.deepEqual(moduleNames,Object.keys(audit.modules).sort());audit.kernel_module_count=moduleNames.length;
  for(const name of moduleNames)for(const folder of ['openswing','public/kernel','dist/kernel'])check(folder+'/'+name,sha(await readFile(path.join(root,folder,name)))===audit.modules[name]);
  const serveRoot=path.join(root,'dist');audit.built_assets=[];
  for(const name of ['index.html',...(await readdir(path.join(serveRoot,'assets'))).map(n=>'assets/'+n)])audit.built_assets.push(await pin(path.join(serveRoot,name)));
  // Preflight exact request construction using the same pure UI boundary.
  // Degree inputs are chosen by division by the actual radians-per-degree
  // factor; this reproduces the declared angular rates bit-for-bit.
  const fields={'gravity-mode':'custom','gravity-magnitude':String(input.time.gravity_magnitude)};
  for(const [group,values,axes] of [['position-earth',input.time.position,['x','y','z']],
    ['attitude',input.time.attitude,['bank','elevation','heading']],['moving-velocity',input.time.velocity,['x','y','z']]])
    axes.forEach((axis,i)=>fields[`${group}-${axis}`]=String(values[i]));
  for(const kind of ['rates','acceleration','angular_acceleration'])['x','y','z'].forEach((axis,i)=>fields[`${kind}-${axis}`]=String(input.time.motion[kind][i]/(kind==='acceleration'?1:Math.PI/180)));
  const uiTime={duration:.08,dt:.02,order:2,frame:'prescribed',forcing:'',accuracy:null,actuator_constraints:[]};
  const builtRequest=numericalRequest(movingVacuumTimeRequest({action:'time',mode:'time',source:input.source,panels:input.panels,
    condition:{},strut_mode:'bilateral',operating_constraints:[],derivatives:null,time:uiTime},movingVacuumFrame(fields)),input.numerics);
  assert.deepEqual(wire(builtRequest),input);check('pure UI request preflight exact',true);await write('ui-fields.json',fields);
  const mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.css':'text/css','.svg':'image/svg+xml','.woff2':'font/woff2'};
  server=createServer(async(req,res)=>{try{
    const rel=decodeURIComponent(new URL(req.url,'http://local').pathname),file=path.resolve(serveRoot,'.'+(rel==='/'?'/index.html':rel));
    assert(file.startsWith(serveRoot+path.sep));const s=await stat(file);assert(s.isFile());
    res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream','Content-Length':s.size});createReadStream(file).pipe(res);
  }catch{res.writeHead(404);res.end('Not found');}});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));audit.url=`http://127.0.0.1:${server.address().port}`;
  timer=setTimeout(()=>{audit.timeout=true;browser?.close().catch(()=>{});},Math.max(1,285000-(performance.now()-began)));
  const executable=process.env.OPENSWING_CHROMIUM_EXECUTABLE||'/tmp/aswing-chromium/chrome-linux/chrome';
  const args=process.env.OPENSWING_WEBGL_DRIVER==='mesa'?['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native','--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'];
  audit.browser_environment=Object.fromEntries(['LD_LIBRARY_PATH','VK_ICD_FILENAMES','OPENSWING_WEBGL_DRIVER','LP_NUM_THREADS'].map(k=>[k,process.env[k]??null]));
  browser=await chromium.launch({headless:true,executablePath:executable,args,timeout:30000});audit.chromium=browser.version();
  const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
  await context.route('**/*',async route=>{const url=route.request().url();if(/^https?:/.test(url)&&new URL(url).origin!==audit.url){audit.external_requests.push(url);await route.abort();}else await route.continue();});
  context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))audit.offline_requests.push(r.url());});
  context.on('requestfailed',r=>audit.network_failures.push({url:r.url(),failure:r.failure()}));
  page=await context.newPage();page.setDefaultTimeout(30000);page.on('pageerror',e=>audit.page_errors.push(e.message));
  await page.addInitScript(()=>{window.referenceRequests=[];window.referenceEvents=[];const W=window.Worker;
    window.Worker=class extends W{constructor(...args){super(...args);this.addEventListener('message',e=>{if(e.data?.type==='progress'||e.data?.progress||e.data?.stage)window.referenceEvents.push(structuredClone(e.data));});}
      postMessage(m,...rest){window.referenceRequests.push(structuredClone(m));return super.postMessage(m,...rest);}};});
  await page.goto(audit.url);await expect(page.locator('#solve')).toBeEnabled({timeout:180000});audit.startup_seconds=(performance.now()-began)/1000;
  await context.setOffline(true);offline=true;
  await page.locator('#file').setInputFiles({name:'source-moving-rigid-time.asw',mimeType:'text/plain',buffer:Buffer.from(input.source)});
  await expect(page.locator('#editor')).toHaveValue(input.source);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#node-file').setInputFiles({name:'source-time-mesh.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({format:'openswing-mesh',version:1,panels:input.panels}))});
  await page.waitForFunction(()=>!document.querySelector('#node-file').value);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('time');await page.locator('details').evaluateAll(nodes=>nodes.forEach(node=>node.open=true));
  await page.locator('#structural-equations').selectOption('aswing-moving-vacuum');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#gravity-mode').selectOption('custom');
  for(const [id,value] of Object.entries(fields))if(id!=='gravity-mode')await page.locator('#'+id).fill(value);
  await page.locator('#time-duration').fill('.08');await page.locator('#time-step').fill('.02');await page.locator('#time-order').selectOption('2');await page.locator('#time-frame').selectOption('prescribed');
  await page.locator('#time-accuracy-enabled').uncheck();await page.locator('#time-initial-enable').uncheck();await page.locator('#time-forcing').fill('');
  await expect(page.locator('#error')).toBeHidden();
  check('no solve during setup',(await page.evaluate(()=>window.referenceRequests)).every(r=>!physicalActions.includes(r.request?.action)));
  const t0=performance.now();console.log('Starting sole offline source Euler-BDF cold trajectory.');await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:120000});await expect(page.locator('#solve')).toBeEnabled();
  audit.solve_seconds=(performance.now()-t0)/1000;await expect(page.locator('#error')).toBeHidden();
  async function download(id,name){const event=page.waitForEvent('download');await page.locator('#'+id).click();const bytes=await readFile(await(await event).path());await writeFile(path.join(output,name),bytes);return bytes;}
  const bytes=await download('export-json','result.json'),result=JSON.parse(bytes);timeChecks(result,'cold');audit.parity={cold:compare(native,result,'cold')};
  assert.deepEqual(wire(result.request),input);check('cold exact worker request',true);
  check('heading crossing displayed continuously',result.snapshots.at(-1).frame.attitude[2]>180);
  await page.locator('#time-scrub').fill(String(result.snapshots.length-1));await page.locator('#tab-time').click();await page.locator('#time-checkpoint-settings').evaluate(e=>e.open=true);
  const checkpointBytes=await download('time-checkpoint-save','checkpoint.json'),checkpoint=JSON.parse(checkpointBytes);
  audit.parity.checkpoint=compare(data['checkpoint.json'],checkpoint,'checkpoint');
  await page.locator('#time-quantity').selectOption(plan.browser_case.plot_quantity);await expect(page.locator('#time-plot svg')).toBeVisible();
  await page.locator('details').evaluateAll(nodes=>nodes.forEach(node=>node.open=true));
  await page.locator('#project-name').fill(plan.browser_case.project_name);await page.locator('#project-rename').click();
  await page.locator('#project-case-name').fill(plan.browser_case.case_name);await page.locator('#project-add').click();
  await page.locator('#project-solution-name').fill(plan.browser_case.solution_name);await page.locator('#project-save-solution').click();
  const projectBytes=await download('project-export','project.json'),project=JSON.parse(projectBytes);
  const saved=project.solutions.find(s=>s.name===plan.browser_case.solution_name);assert(saved);
  assert.deepEqual(saved.data,result);assert.deepEqual(saved.configuration.numerics,input.numerics);
  await page.locator('#project-file').setInputFiles({name:'source-time-project.json',mimeType:'application/json',buffer:projectBytes});
  await expect(page.locator('#project-load-solution')).toBeEnabled();await page.locator('#project-load-solution').click();
  await expect(page.locator('#project-status')).toContainText(`Opened ${plan.browser_case.solution_name}.`);await expect(page.locator('#export-json')).toBeEnabled();
  const reopened=await download('export-json','reopened-result.json'),reopenedProject=await download('project-export','reopened-project.json');
  check('saved trajectory byte-exact restore',Buffer.compare(bytes,reopened)===0);check('project byte-exact restore',Buffer.compare(projectBytes,reopenedProject)===0);
  check('one cold solve before continuation',(await page.evaluate(()=>window.referenceRequests)).filter(r=>physicalActions.includes(r.request?.action)).length===1);
  // Import the standalone checkpoint: no prefix merge obscures the native
  // continuation segment, and the owned BDF2 predecessor remains binding.
  await page.locator('#tab-time').click();await page.locator('#time-checkpoint-settings').evaluate(e=>e.open=true);
  await page.locator('#time-checkpoint-file').setInputFiles({name:'source-time-checkpoint.json',mimeType:'application/json',buffer:checkpointBytes});
  await expect(page.locator('#time-continue')).toBeEnabled();await page.locator('#time-continue-duration').fill('.02');await page.locator('#time-continue-step').fill('.02');
  await page.locator('#time-continue-order').selectOption('2');await page.locator('#time-continue-replace').uncheck();await page.locator('#time-continue-accuracy-enabled').uncheck();
  const t1=performance.now();console.log('Starting sole offline checkpoint continuation.');await page.locator('#time-continue').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time continuation converged',{timeout:120000});audit.resume_seconds=(performance.now()-t1)/1000;await expect(page.locator('#error')).toBeHidden();
  const resumeBytes=await download('export-json','resumed-result.json'),resumed=JSON.parse(resumeBytes);timeChecks(resumed,'resume');
  audit.parity.resume=compare(expectedResume,resumed,'resume');assert.equal(resumed.snapshots[1].order,2);
  const expectedWireResume={...resumeInput,checkpoint};assert.deepEqual(wire(resumed.request),expectedWireResume);check('exact continuation options and browser-owned checkpoint',true);
  await page.locator('#time-quantity').selectOption(plan.browser_case.plot_quantity);await expect(page.locator('#time-plot svg')).toBeVisible();
  await page.locator('#fit').click();check('single aircraft canvas',await page.locator('#viewport canvas').count()===1);
  audit.canvas=await page.locator('#viewport canvas').evaluate(canvas=>({width:canvas.width,height:canvas.height,client_width:canvas.clientWidth,client_height:canvas.clientHeight,
    webgl:!!(canvas.getContext('webgl2')||canvas.getContext('webgl')),canvas2d:!!canvas.getContext('2d')}));
  await page.screenshot({path:path.join(output,'desktop.png')});
  await page.locator('details').evaluateAll(nodes=>nodes.forEach(node=>node.open=false));await page.setViewportSize({width:390,height:844});
  // Mobile Plots stacks the panels; the desktop tab bar is intentionally hidden.
  await page.locator('#workspace-tab-plots').click();await expect(page.locator('#time-plot svg')).toBeVisible();
  check('mobile width',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(output,'mobile.png')});
  await page.locator('#time-plot').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,'mobile-time.png')});
  const requests=wire(await page.evaluate(()=>window.referenceRequests)),physical=requests.filter(r=>physicalActions.includes(r.request?.action));
  check('exactly cold time plus checkpoint continuation',physical.length===2&&physical[0].request.action==='time'&&physical[1].request.action==='resume_time');
  assert.deepEqual(physical[0].request,input);assert.deepEqual(physical[1].request,expectedWireResume);
  audit.request_counts=Object.fromEntries([...new Set(requests.map(r=>r.request?.action??'runtime'))].map(action=>[action,requests.filter(r=>(r.request?.action??'runtime')===action).length]));
  await write('requests.json',requests);await write('events.json',await page.evaluate(()=>window.referenceEvents));
  for(const p of [...audit.inputs,...audit.built_assets])check('unchanged '+p.path,(await pin(p.path)).sha256===p.sha256);
  for(const name of moduleNames)for(const folder of ['openswing','public/kernel','dist/kernel'])check('unchanged '+folder+'/'+name,sha(await readFile(path.join(root,folder,name)))===audit.modules[name]);
  check('offline HTTP absent',audit.offline_requests.length===0);check('external HTTP absent',audit.external_requests.length===0);
  check('page errors absent',audit.page_errors.length===0);check('network failures absent',audit.network_failures.length===0);
  check('within cap',!audit.timeout&&performance.now()-began<300000);audit.status='PASS_OFFLINE_SOURCE_MOVING_TIME_UI';
}catch(error){
  audit.status='FAILURE_RETAINED';audit.error={message:error.message,stack:error.stack};process.exitCode=1;console.error(error.stack);
  try{if(page&&!page.isClosed()){await write('requests-at-failure.json',wire(await page.evaluate(()=>window.referenceRequests)));await writeFile(path.join(output,'failure.html'),await page.content());await page.screenshot({path:path.join(output,'failure.png')});}}catch{}
}finally{
  clearTimeout(timer);try{await browser?.close();}finally{server?.closeAllConnections();if(server?.listening)await new Promise(resolve=>server.close(resolve));}
  audit.total_seconds=(performance.now()-began)/1000;audit.check_counts={passed:audit.checks.filter(c=>c.passed).length,total:audit.checks.length};
  audit.exclusions=[...new Set(audit.exclusions)];audit.artifacts=[];
  for(const name of (await readdir(output)).sort())if((await stat(path.join(output,name))).isFile())audit.artifacts.push(await pin(path.join(output,name)));
  await write('report.json',audit);console.log(JSON.stringify({status:audit.status,checks:audit.check_counts,startup_seconds:audit.startup_seconds,
    solve_seconds:audit.solve_seconds,resume_seconds:audit.resume_seconds,parity:audit.parity,total_seconds:audit.total_seconds}));
}
