// Exact native AP-1 request through the real UI worker, then a project-import UI
// solve with explicit defaults, full native parity, and saved-project restore.
// node scripts/test-source-engines-browser.mjs NEW_OUTPUT_DIR NATIVE_PROBE_DIR [COMPLETED_BROWSER_DIR]
// The optional prior stage resumes completed results without another solve.
import {chromium} from 'playwright';
import {expect} from '@playwright/test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {createReadStream} from 'node:fs';
import {readFile,writeFile,readdir,mkdir,stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {sealSolution} from '../web/solution-data.js';

assert([4,5].includes(process.argv.length),'Supply a new output directory, native AP-1 probe directory, and optionally a completed browser stage.');
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.resolve(process.argv[2]),nativeStage=path.resolve(process.argv[3]);
const resume=process.argv[4]?path.resolve(process.argv[4]):null;
const nativeDir=path.join(nativeStage,'n150-a4');
await mkdir(output,{recursive:false});
const read=async file=>JSON.parse(await readFile(file,'utf8'));
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const pin=async file=>{const bytes=await readFile(file);return {path:file,bytes:bytes.length,sha256:sha(bytes)};};
const save=async(name,value)=>writeFile(path.join(output,name),JSON.stringify(value,null,2)+'\n');
const audit={status:'PREPARING',checks:[],page_errors:[],offline_requests:[],network_failures:[],
  planned_solves:{exact_worker:resume?0:1,project_ui:resume?0:1,restore:0},
  scope:'Literal original AP-1 PROWIM, n150 alpha 4, shared E1=500 W per engine, current influences and PG Mach zero. Offline built UI/Pyodide integration and native parity; no archived ASWING agreement or experimental validation claimed.',
  gates:{absolute:2e-8,relative:2e-8,residual:1e-8},exclusions:['evaluations'],
  exclusion_reason:'Execution counter only; every native physical result and metadata field is compared.',
  caps:{startup_ms:180000,each_solve_ms:90000,internal_total_ms:405000},retries:0};
const check=(name,passed,evidence={})=>{audit.checks.push({name,passed:!!passed,...evidence});assert(passed,name);};
function compare(expected,actual){
  const result={numeric:0,leaves:0,max_absolute:0,max_fraction:0,worst:null};
  function visit(e,a,p){
    if(audit.exclusions.includes(p))return;
    if(typeof e==='number'){
      assert.equal(typeof a,'number',p);assert(Number.isFinite(e)&&Number.isFinite(a),p);
      const difference=Math.abs(a-e),limit=audit.gates.absolute+audit.gates.relative*Math.abs(e);
      result.numeric++;result.leaves++;result.max_absolute=Math.max(result.max_absolute,difference);
      if(difference/limit>result.max_fraction)Object.assign(result,{max_fraction:difference/limit,worst:p});
      assert(difference<=limit,p+' numerical parity');
    }else if(Array.isArray(e)){
      assert(Array.isArray(a)&&e.length===a.length,p);e.forEach((v,i)=>visit(v,a[i],`${p}[${i}]`));
    }else if(e!==null&&typeof e==='object'){
      assert(a!==null&&typeof a==='object'&&!Array.isArray(a),p);
      if(p)assert.deepEqual(Object.keys(a).sort(),Object.keys(e).sort(),p+' fields');
      for(const [key,value] of Object.entries(e)){
        assert(Object.hasOwn(a,key),p+'.'+key);visit(value,a[key],p?p+'.'+key:key);
      }
    }else{result.leaves++;assert.deepEqual(a,e,p);}
  }
  visit(expected,actual,'');return result;
}
let browser,server,page,timer,offline=false;
const started=performance.now();
try{
  // Retain the native outcome verbatim even when the native case is incomplete
  // or failed. A missing successful result never triggers a substitute solve.
  audit.native_evidence=[];
  for(const name of ['request.json','checks.json','result.json','stderr.txt','stdout.txt','error.json']){
    try{const file=path.join(nativeDir,name),bytes=await readFile(file);await writeFile(path.join(output,'native-'+name),bytes);audit.native_evidence.push(await pin(file));}
    catch(error){if(error.code!=='ENOENT')throw error;}
  }
  const plan=await read(path.join(nativeStage,'plan.json')),request=await read(path.join(nativeDir,'request.json'));
  const native=await read(path.join(nativeDir,'result.json')),checks=await read(path.join(nativeDir,'checks.json'));
  check('native n150-a4 physical checks passed',checks.status==='PASS_PHYSICAL_CHECKS'&&Object.values(checks.checks).every(v=>v===true));
  assert.equal(request.action,'solve');assert.equal(request.mode,'mounted');assert.equal(request.panels,150);
  assert.equal(request.condition.alpha,4);assert.equal(request.condition.speed,50);
  assert.deepEqual(request.condition.powers,{'1':500});assert.equal(request.condition.freeze_influences,false);
  assert.equal(request.condition.mach,0);assert(!request.initial_state);
  assert.equal(request.numerics.structural_operator,'drela-steady-coupled-v1');
  check('literal original source bytes',request.source===await readFile(plan.source,'utf8'));
  audit.inputs=[await pin(path.join(nativeStage,'plan.json')),await pin(fileURLToPath(import.meta.url))];
  let previousRequests;
  if(resume){
    const previous=await read(path.join(resume,'report.json'));
    previousRequests=await read(path.join(resume,'requests-at-failure.json'));
    assert.equal(previousRequests.filter(item=>item.request?.action==='solve').length,2);
    assert(previous.exact_worker_parity?.max_fraction<=1&&Number.isFinite(previous.ui_solve_seconds));
    const previousScript=await pin(path.join(resume,'first-run-script.mjs'));
    assert.equal(previousScript.sha256,previous.inputs.find(input=>input.path===fileURLToPath(import.meta.url)).sha256);
    audit.resumed_run={directory:resume,status:previous.status,startup_seconds:previous.startup_seconds,
      exact_worker_seconds:previous.exact_worker_seconds,ui_solve_seconds:previous.ui_solve_seconds,
      original_script:previousScript,original_error:previous.error,
      assertion_correction:'The UI represents no gust as null. Corrected the harness expectation from {type:"none"} to null; source, numerical modules, results and physical gates are unchanged.'};
    for(const name of ['report.json','requests-at-failure.json','input-project.json','exact-worker-result.json','result.json','first-run-script.mjs'])audit.inputs.push(await pin(path.join(resume,name)));
  }
  const names=(await readdir(path.join(root,'openswing'))).filter(name=>name.endsWith('.py')).sort();
  audit.modules=Object.fromEntries(Object.entries(plan.pins).filter(([name])=>name.startsWith('openswing/')).map(([name,hash])=>[path.basename(name),hash]));
  assert.deepEqual(names,Object.keys(audit.modules).sort());
  for(const [relative,hash] of Object.entries(plan.pins))check('frozen native input '+relative,sha(await readFile(path.resolve(root,relative)))===hash);
  async function verifyModules(prefix){
    for(const folder of ['openswing','public/kernel','dist/kernel']){
      assert.deepEqual((await readdir(path.join(root,folder))).filter(name=>name.endsWith('.py')).sort(),names,folder+' module list');
      for(const name of names)check(prefix+folder+'/'+name,sha(await readFile(path.join(root,folder,name)))===audit.modules[name]);
    }
    for(const folder of ['public/kernel','dist/kernel'])assert.deepEqual((await read(path.join(root,folder,'manifest.json'))).sort(),names,folder+' manifest');
  }
  await verifyModules('');
  const serveRoot=path.join(root,'dist'),mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.css':'text/css','.svg':'image/svg+xml','.woff2':'font/woff2'};
  audit.built_assets=[];
  for(const name of ['index.html','kernel/manifest.json',...(await readdir(path.join(serveRoot,'assets'))).map(name=>'assets/'+name)])audit.built_assets.push(await pin(path.join(serveRoot,name)));
  server=createServer(async(req,res)=>{
    try{
      const relative=decodeURIComponent(new URL(req.url,'http://local').pathname),file=path.resolve(serveRoot,'.'+(relative==='/'?'/index.html':relative));
      assert(file.startsWith(serveRoot+path.sep));const info=await stat(file);assert(info.isFile());
      res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream','Content-Length':info.size});createReadStream(file).pipe(res);
    }catch{res.writeHead(404);res.end('Not found');}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));audit.url=`http://127.0.0.1:${server.address().port}`;
  const executable=process.env.OPENSWING_CHROMIUM_EXECUTABLE||'/tmp/aswing-chromium/chrome-linux/chrome';
  const args=process.env.OPENSWING_WEBGL_DRIVER==='mesa'?['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native','--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'];
  audit.browser_environment=Object.fromEntries(['LD_LIBRARY_PATH','VK_ICD_FILENAMES','OPENSWING_WEBGL_DRIVER','LP_NUM_THREADS'].map(key=>[key,process.env[key]??null]));
  browser=await chromium.launch({headless:true,executablePath:executable,args});audit.chromium=browser.version();
  timer=setTimeout(()=>{audit.timeout=true;browser.close().catch(()=>{});},Math.max(1,audit.caps.internal_total_ms-(performance.now()-started)));
  const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});page=await context.newPage();page.setDefaultTimeout(60000);
  page.on('pageerror',error=>audit.page_errors.push(error.message));
  context.on('requestfailed',r=>audit.network_failures.push({url:r.url(),failure:r.failure()}));
  context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))audit.offline_requests.push(r.url());});
  await page.addInitScript(()=>{
    window.referenceRequests=[];window.referenceEvents=[];window.referenceWorkers=[];
    const WorkerClass=window.Worker;
    window.Worker=class extends WorkerClass{
      constructor(...args){
        super(...args);window.referenceWorkers.push(this);
        this.addEventListener('message',event=>{if(event.data?.type==='progress'||event.data?.error)window.referenceEvents.push(structuredClone(event.data));});
      }
      postMessage(message,...rest){window.referenceRequests.push(structuredClone(message));return super.postMessage(message,...rest);}
    };
  });
  await page.goto(audit.url);await expect(page.locator('#solve')).toBeEnabled({timeout:audit.caps.startup_ms});audit.startup_seconds=(performance.now()-started)/1000;
  await context.setOffline(true);offline=true;
  const exactStart=performance.now();console.log(resume?'Resuming completed browser results; zero new solves.':'Starting exact native request through the offline UI worker.');
  const exact=resume?await read(path.join(resume,'exact-worker-result.json')):await page.evaluate(({request,timeout})=>new Promise((resolve,reject)=>{
    const worker=window.referenceWorkers[0],id='source-engines-exact-native';
    const timeoutId=setTimeout(()=>{worker.removeEventListener('message',receive);reject(new Error('Exact worker solve exceeded its time cap.'));},timeout);
    function receive(event){
      if(event.data.id!==id||event.data.type==='progress')return;
      clearTimeout(timeoutId);worker.removeEventListener('message',receive);
      if(event.data.error)reject(new Error(event.data.error));else resolve(event.data.result);
    }
    worker.addEventListener('message',receive);worker.postMessage({id,request});
  }),{request,timeout:audit.caps.each_solve_ms});
  audit.exact_worker_seconds=resume?null:(performance.now()-exactStart)/1000;await save('exact-worker-result.json',exact);
  assert.deepEqual(exact.software_provenance.modules,audit.modules);
  assert.deepEqual(Object.keys(exact).filter(key=>key!=='software_provenance').sort(),Object.keys(native).sort());
  audit.exact_worker_parity=compare(native,exact);check('exact worker all native fields',true,audit.exact_worker_parity);
  async function openControls(){await page.locator('details').evaluateAll(nodes=>nodes.forEach(node=>node.open=true));}
  async function download(id,name){
    const event=page.waitForEvent('download');await page.locator('#'+id).click();
    const bytes=await readFile(await(await event).path());await writeFile(path.join(output,name),bytes);return bytes;
  }
  await openControls();
  const bootstrap=JSON.parse(await download('project-export-current','bootstrap-project.json'));
  const config=structuredClone(bootstrap.cases[0].configuration);
  Object.assign(config,{source:request.source,filename:'PROWIM.asw',mesh:request.panels,numerics:request.numerics,
    controls:{'1':'0'},powers:{'1':'500'},circulation:{'1':'0'},derivative_parameters:[],constraints:[],equilibrium:{state:null,enabled:false,label:''}});
  Object.assign(config.fields,{mode:'mounted',speed:'50',alpha:'4',beta:'0','density-mode':'custom',density:'1.2256',
    'mach-mode':'fixed','pg-mach':'0','freeze-influences':false,'gravity-mode':'file','ground-effect':'0',
    'feedback-enabled':false,'derivatives-enable':false,'gust-kind':'none','trim-roll':'1','trim-pitch':'1','trim-yaw':'1','trim-engine':'1'});
  const inputProject=resume?await read(path.join(resume,'input-project.json')):{format:'openswing-project',version:2,name:'Original AP-1 source engine integration',selected:'ap1-n150-a4',
    cases:[{id:'ap1-n150-a4',name:'Original PROWIM n150 alpha 4',configuration:config}],solutions:[],selected_solution:null};
  await save('input-project.json',inputProject);
  async function loadProject(bytes,solution){
    const project=JSON.parse(bytes);await openControls();
    await page.locator('#project-file').setInputFiles({name:'ap1-source-engine-project.json',mimeType:'application/json',buffer:bytes});
    await expect(page.locator('#project-name')).toHaveValue(project.name);
    await expect(page.locator('#project-cases')).toHaveValue(project.selected);
    const selector=solution?'#project-load-solution':'#project-load';
    await expect(page.locator(selector)).toBeEnabled();await page.locator(selector).click();
    await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();await openControls();
  }
  await loadProject(Buffer.from(JSON.stringify(inputProject)),false);
  await expect(page.locator('#editor')).toHaveValue(request.source);await expect(page.locator('#mode')).toHaveValue('mounted');
  await expect(page.locator('#structural-equations')).toHaveValue('aswing-coupled');
  await expect(page.locator('[data-power="1"]')).toHaveValue('500');await expect(page.locator('#freeze-influences')).not.toBeChecked();
  if(resume){
    const data=await read(path.join(resume,'result.json'));
    const saved=await sealSolution({id:'completed-ui-result',name:'Completed original UI solve',created_at:new Date().toISOString(),
      kind:'mounted',configuration:inputProject.cases[0].configuration,data,auxiliary:{},view:{},provenance:data.software_provenance});
    const retained={...inputProject,solutions:[saved],selected_solution:saved.id};await save('retained-completed-project.json',retained);
    await loadProject(Buffer.from(JSON.stringify(retained)),true);
    // Remove the temporary record, retaining the displayed result so the normal
    // UI save path below independently seals it with the restored workbench.
    await page.locator('#project-delete-solution').click();await expect(page.locator('#project-solutions option')).toHaveCount(0);
    audit.ui_solve_seconds=null;
  }else{
    const uiStart=performance.now();console.log('Starting project-import offline UI solve.');await page.locator('#solve').click();
    await expect(page.locator('#result-state')).toHaveText('Converged · mounted equilibrium',{timeout:audit.caps.each_solve_ms});
    await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();audit.ui_solve_seconds=(performance.now()-uiStart)/1000;
  }
  const resultBytes=await download('export-json','result.json'),result=JSON.parse(resultBytes);
  if(resume)check('completed UI output bytes retained',Buffer.compare(resultBytes,await readFile(path.join(resume,'result.json')))===0);
  assert.deepEqual(result.software_provenance.modules,audit.modules);assert.deepEqual(result.numerics,request.numerics);
  for(const key of ['action','mode','source','panels','numerics'])assert.deepEqual(result.request[key],request[key]);
  for(const [key,value] of Object.entries(request.condition))assert.deepEqual(result.request.condition[key],value);
  assert(!result.request.initial_state);assert.deepEqual(result.request.operating_constraints,[]);
  assert.equal(result.request.controller,null);assert.equal(result.request.strut_mode,'bilateral');
  audit.explicit_ui_defaults=Object.fromEntries(Object.entries(result.request.condition).filter(([key])=>!Object.hasOwn(request.condition,key)));
  assert.deepEqual(audit.explicit_ui_defaults,{stall:true,stall_factor:40,stall_width:.05,sensor_flow:'full',aero_lag:true,
    wake_core_ratio:.25,circulation_modes:{'1':0},body_added_mass_factor:1,altitude_m:0,gravity_magnitude:null,
    load_factor:1,ground_effect:0,position_earth:[0,0,0],attitude:[0,0,0],ground_normal:[0,0,1],
    rates:[0,0,0],acceleration:[0,0,0],angular_acceleration:[0,0,0],gust:null,time:0});
  audit.ui_parity=compare(native,result);check('project UI all native fields',true,audit.ui_parity);
  check('full mounted source residual',result.converged&&result.residual<=audit.gates.residual);
  check('two engines share active control and retain jets',result.engines.length===2&&result.engines.every(engine=>engine.index===1&&engine.type===1&&engine.requested_power===500&&engine.jet_enabled&&engine.delta_velocity>0));
  check('static source recovery and identity',result.structure.strain_source==='source_discrete_constitutive'&&result.elements.every(element=>element.endpoint_traces.length===2)&&result.mass_properties.dynamic_inertia_available===false&&!Object.hasOwn(result.equilibrium_state,'launch'));
  await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText('ENGINES');
  for(const engine of result.engines)await expect(page.locator('#pane-report')).toContainText(`thrust [F] ${engine.thrust.toPrecision(7)}`);
  await page.locator('#project-solution-name').fill('Original PROWIM source engine result');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-load-solution')).toBeEnabled();
  const projectBytes=await download('project-export','project.json'),project=JSON.parse(projectBytes);
  assert.equal(project.solutions.length,1);assert.deepEqual(project.solutions[0].data,result);
  await loadProject(projectBytes,true);await expect(page.locator('#export-json')).toBeEnabled();
  check('saved result restored byte-exactly',Buffer.compare(resultBytes,await download('export-json','reopened-result.json'))===0);
  check('saved project restored byte-exactly',Buffer.compare(projectBytes,await download('project-export','reopened-project.json'))===0);
  await expect(page.locator('[data-power="1"]')).toHaveValue('500');await expect(page.locator('#freeze-influences')).not.toBeChecked();
  await page.locator('#tab-structure').click();await page.locator('#structure-quantity').selectOption('curvature_change.1');
  await expect(page.locator('#structure-plot svg')).toBeVisible();await expect(page.locator('#structure-state')).toContainText('interval constitutive estimates');
  check('single aircraft canvas',await page.locator('#viewport canvas').count()===1);
  audit.renderer=await page.locator('#viewport canvas').getAttribute('data-renderer');await page.screenshot({path:path.join(output,'desktop.png')});
  await page.locator('details').evaluateAll(nodes=>nodes.forEach(node=>node.open=false));await page.setViewportSize({width:390,height:844});
  await page.locator('#workspace-tab-plots').click();await page.locator('#fit').click();
  check('mobile width',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(output,'mobile.png')});
  const requests=await page.evaluate(()=>window.referenceRequests),solves=requests.filter(item=>item.request?.action==='solve');
  check(resume?'zero new solves while restoring completed outputs':'exactly two cold solves with no restore solve',solves.length===(resume?0:2));
  const completedSolves=resume?previousRequests.filter(item=>item.request?.action==='solve'):solves;
  assert.deepEqual(JSON.parse(JSON.stringify(completedSolves[0].request)),request);assert.deepEqual(JSON.parse(JSON.stringify(completedSolves[1].request)),result.request);
  await save('requests.json',requests);await save('events.json',await page.evaluate(()=>window.referenceEvents));
  audit.request_counts=Object.fromEntries([...new Set(requests.map(item=>item.request?.action??'runtime'))].map(action=>[action,requests.filter(item=>(item.request?.action??'runtime')===action).length]));
  for(const input of [...audit.inputs,...audit.native_evidence,...audit.built_assets])check('unchanged '+input.path,(await pin(input.path)).sha256===input.sha256);
  for(const [relative,hash] of Object.entries(plan.pins))check('unchanged native input '+relative,sha(await readFile(path.resolve(root,relative)))===hash);
  await verifyModules('unchanged ');
  check('offline HTTP absent',audit.offline_requests.length===0);check('page errors absent',audit.page_errors.length===0);check('network failures absent',audit.network_failures.length===0);
  audit.status='PASS_OFFLINE_SOURCE_ENGINES_EXACT_WORKER_UI_AND_RESTORE';
}catch(error){
  audit.status='FAILURE_RETAINED';audit.error={message:error.message,stack:error.stack};process.exitCode=1;console.error(error.stack);
  try{if(page&&!page.isClosed()){
    await save('requests-at-failure.json',await page.evaluate(()=>window.referenceRequests));
    await save('events-at-failure.json',await page.evaluate(()=>window.referenceEvents));
    await page.screenshot({path:path.join(output,'failure.png')});
  }}catch{}
}finally{
  clearTimeout(timer);try{await browser?.close();}finally{server?.closeAllConnections();if(server?.listening)await new Promise(resolve=>server.close(resolve));}
  audit.total_seconds=(performance.now()-started)/1000;await save('report.json',audit);
  console.log(JSON.stringify({status:audit.status,startup_seconds:audit.startup_seconds,exact_worker_seconds:audit.exact_worker_seconds,
    ui_solve_seconds:audit.ui_solve_seconds,exact_worker_parity:audit.exact_worker_parity,ui_parity:audit.ui_parity,total_seconds:audit.total_seconds}));
}
