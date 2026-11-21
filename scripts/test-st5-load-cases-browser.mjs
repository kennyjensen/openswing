// Two offline built-UI structural solves on the original ST-5 level-0 grids.
// node scripts/test-st5-load-cases-browser.mjs NEW_OUTPUT_DIR COMPLETED_NATIVE_STAGE [--preflight]
// Run only after native physical gates and explicit execution authorization.
import {chromium} from 'playwright';
import {expect} from '@playwright/test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {createReadStream} from 'node:fs';
import {readFile,writeFile,readdir,mkdir,stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const scriptPath=fileURLToPath(import.meta.url),root=path.resolve(path.dirname(scriptPath),'..');
assert(process.argv.length===4||(process.argv.length===5&&process.argv[4]==='--preflight'),
  'Supply a new output directory, the completed native stage, and optional --preflight.');
const preflight=process.argv[4]==='--preflight';
const output=path.resolve(process.argv[2]),nativeStage=path.resolve(process.argv[3]);
const cases=['20lb_90_10','30lb_90_10'];
const policy={beam_interpolation:'drela-segspl-v1',structural_operator:'drela-steady-section-v1'};
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const wire=value=>JSON.parse(JSON.stringify(value)); // Worker messages can contain omitted undefined values.
const readJSON=async p=>JSON.parse(await readFile(p,'utf8'));
const pin=async p=>{const bytes=await readFile(p);return {path:p,bytes:bytes.length,sha256:sha(bytes)};};
const save=async(name,value)=>writeFile(path.join(output,name),JSON.stringify(value,null,2)+'\n');
await mkdir(output,{recursive:false});
const audit={status:'PREPARING',scope:'Two additional original ST-5 static load cases on their archived level-0 node grids. Actual offline built UI, full native parity, and saved-solution restoration. Reference agreement is assessed separately by the native all-output study; no experimental comparison.',
  planned_solves:preflight?0:2,prospective_browser_solves:2,data_only_preflight:preflight,retries:0,cases:[],checks:[],page_errors:[],network_failures:[],offline_requests:[],blocked_external_requests:[],
  gates:{absolute:2e-8,relative:2e-8,residual:1e-8},
  exclusions:['evaluations'],exclusion_reason:'Execution counter only; no physical result fields excluded.',
  caps_seconds:{process:450,internal:435,startup:180,solve:120},numerics:policy};
const check=(name,ok,details={})=>{audit.checks.push({name,passed:!!ok,...details});assert(ok,name);};
function compare(expected,actual){
  const out={numeric:0,leaves:0,max_absolute:0,max_fraction:0,worst:null};
  function visit(e,a,p){
    if(audit.exclusions.includes(p))return;
    if(typeof e==='number'){
      assert.equal(typeof a,'number',p);assert(Number.isFinite(e)&&Number.isFinite(a),p);
      const difference=Math.abs(a-e),limit=audit.gates.absolute+audit.gates.relative*Math.abs(e);
      out.numeric++;out.leaves++;out.max_absolute=Math.max(out.max_absolute,difference);
      if(difference/limit>out.max_fraction)Object.assign(out,{max_fraction:difference/limit,worst:p});
      assert(difference<=limit,p+' numerical parity');
    }else if(Array.isArray(e)){
      assert(Array.isArray(a)&&a.length===e.length,p);e.forEach((value,i)=>visit(value,a[i],`${p}[${i}]`));
    }else if(e!==null&&typeof e==='object'){
      assert(a!==null&&typeof a==='object'&&!Array.isArray(a),p);
      for(const [key,value] of Object.entries(e)){assert(Object.hasOwn(a,key),p+'.'+key);visit(value,a[key],p?p+'.'+key:key);}
    }else{out.leaves++;assert.deepEqual(a,e,p);}
  }
  visit(expected,actual,'');return out;
}
let browser,server,page,timer,offline=false;
const started=performance.now();
try{
  audit.script=await pin(scriptPath);await writeFile(path.join(output,'runner-at-execution.mjs'),await readFile(scriptPath));
  const planPath=path.join(nativeStage,'plan.json'),summaryPath=path.join(nativeStage,'summary.json');
  const plan=await readJSON(planPath),summary=await readJSON(summaryPath);
  audit.plan=await pin(planPath);audit.native_summary=await pin(summaryPath);
  check('native physical study completed',summary.status==='PASS_PHYSICAL_CHECKS_REFERENCE_COMPARISON_COMPLETE');
  assert.deepEqual(plan.numerics,policy);assert.deepEqual(summary.numerics,policy);
  assert.deepEqual(plan.cases.map(c=>c.name),cases);
  check('both native cases passed their physical gates',cases.every(c=>summary.cases[c].all_numerical_gates_pass));
  assert(Array.isArray(plan.source_pins)&&plan.source_pins.length>0);
  audit.native_source_pins=plan.source_pins;
  for(const p of plan.source_pins)check('frozen '+p.path,JSON.stringify(await pin(p.path))===JSON.stringify(p));
  const names=(await readdir(path.join(root,'openswing'))).filter(n=>n.endsWith('.py')).sort();
  const kernelPins=plan.source_pins.filter(p=>path.dirname(p.path)===path.join(root,'openswing')&&p.path.endsWith('.py'));
  assert.deepEqual(kernelPins.map(p=>path.basename(p.path)).sort(),names);
  audit.modules=Object.fromEntries(kernelPins.map(p=>[path.basename(p.path),p.sha256]));
  audit.kernel_count=names.length;
  for(const name of names)for(const folder of ['openswing','public/kernel','dist/kernel'])
    check(folder+'/'+name,sha(await readFile(path.join(root,folder,name)))===audit.modules[name]);
  audit.ui_source_pins=[];
  for(const name of (await readdir(path.join(root,'web'))).filter(n=>/\.(js|css)$/.test(n)).sort())
    audit.ui_source_pins.push(await pin(path.join(root,'web',name)));
  const nativeCases=[];
  for(const name of cases){
    const casePlanPath=path.join(nativeStage,name,'plan.json'),nativePath=path.join(nativeStage,name,'level0/result.json');
    const casePlan=await readJSON(casePlanPath),native=await readJSON(nativePath);
    const sourcePath=path.join(root,casePlan.source),source=await readFile(sourcePath);
    // dispatch() returns core fields; the native verifier did not append request metadata.
    // Reproduce its pinned call and explicit wrapper, then check the actual UI wire request.
    assert.deepEqual(casePlan.request,{action:'solve',mode:'structural'});
    const input={...casePlan.request,source:source.toString('utf8'),panels:casePlan.meshes[0].panels,
      condition:null,gravity:null,numerics:policy};
    assert(input&&input.action==='solve'&&input.mode==='structural');assert.deepEqual(input.numerics,policy);
    assert.equal(input.condition,null);assert.equal(input.gravity,null);assert(!Object.hasOwn(input,'initial_state'));
    assert.deepEqual(Object.keys(input).sort(),['action','condition','gravity','mode','numerics','panels','source']);
    assert.deepEqual(input.panels,casePlan.meshes[0].panels);
    assert.equal(sha(source),casePlan.source_sha256);assert.equal(input.source,source.toString('utf8'));
    assert.deepEqual(Object.keys(input.panels.beams).sort(),['1','2']);
    const intervals=Object.values(input.panels.beams).map(value=>{
      assert(Array.isArray(value.nodes)&&value.nodes.every(Number.isFinite));
      assert(value.nodes.every((t,i)=>i===0||t>value.nodes[i-1]));return value.nodes.length-1;
    });
    assert.deepEqual(intervals,[38,32]);
    check(name+' native residual gate',native.converged&&native.residual<=audit.gates.residual);
    const record={name,level:0,native:await pin(nativePath),case_plan:await pin(casePlanPath),source:await pin(sourcePath),
      panels:input.panels,request_sha256:sha(Buffer.from(JSON.stringify(input))),status:'PREPARED',
      request_provenance:'Pinned generated verifier plan and literal source; dispatch wrapper adds condition:null, gravity:null and the explicit section policy. Native core result has no request field.'};
    audit.cases.push(record);nativeCases.push({name,native,input,record});
    await mkdir(path.join(output,name));await save(name+'/expected-request.json',input);
  }
  if(preflight){
    check('preflight launched no browser and performed no solves',true);
    audit.status='PASS_DATA_ONLY_PREFLIGHT';
  }else{
  const serveRoot=path.join(root,'dist');
  const mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json',
    '.wasm':'application/wasm','.css':'text/css','.svg':'image/svg+xml','.woff2':'font/woff2'};
  audit.built_assets=[];
  for(const name of ['index.html',...(await readdir(path.join(serveRoot,'assets'))).map(n=>'assets/'+n)])
    audit.built_assets.push(await pin(path.join(serveRoot,name)));
  server=createServer(async(req,res)=>{
    try{
      const rel=decodeURIComponent(new URL(req.url,'http://local').pathname);
      const p=path.resolve(serveRoot,'.'+(rel==='/'?'/index.html':rel));assert(p.startsWith(serveRoot+path.sep));
      const s=await stat(p);assert(s.isFile());
      res.writeHead(200,{'Content-Type':mime[path.extname(p)]||'application/octet-stream','Content-Length':s.size});createReadStream(p).pipe(res);
    }catch{res.writeHead(404);res.end('Not found');}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));audit.url=`http://127.0.0.1:${server.address().port}`;
  const executable=process.env.OPENSWING_CHROMIUM_EXECUTABLE||'/tmp/aswing-chromium/chrome-linux/chrome';
  const args=process.env.OPENSWING_WEBGL_DRIVER==='mesa'
    ?['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native','--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']
    :['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'];
  audit.browser_environment=Object.fromEntries(['LD_LIBRARY_PATH','VK_ICD_FILENAMES','OPENSWING_WEBGL_DRIVER','LP_NUM_THREADS'].map(k=>[k,process.env[k]??null]));
  browser=await chromium.launch({headless:true,executablePath:executable,args});audit.chromium=browser.version();
  timer=setTimeout(()=>{audit.timeout=true;browser.close().catch(()=>{});},Math.max(1,435000-(performance.now()-started)));
  const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
  await context.route(/^https?:/,route=>{
    if(new URL(route.request().url()).origin===audit.url)return route.continue();
    audit.blocked_external_requests.push(route.request().url());return route.abort('blockedbyclient');
  });
  page=await context.newPage();page.setDefaultTimeout(60000);
  page.on('pageerror',error=>audit.page_errors.push(error.message));
  context.on('requestfailed',request=>audit.network_failures.push({url:request.url(),failure:request.failure()}));
  context.on('request',request=>{if(offline&&/^https?:/.test(request.url()))audit.offline_requests.push(request.url());});
  await page.addInitScript(()=>{
    window.referenceRequests=[];window.referenceEvents=[];const OriginalWorker=window.Worker;
    window.Worker=class extends OriginalWorker{
      constructor(...args){super(...args);this.addEventListener('message',event=>{
        if(event.data?.type==='progress'||event.data?.progress||event.data?.stage)window.referenceEvents.push(structuredClone(event.data));
      });}
      postMessage(message,...rest){window.referenceRequests.push(structuredClone(message));return super.postMessage(message,...rest);}
    };
  });
  await page.goto(audit.url);await expect(page.locator('#solve')).toBeEnabled({timeout:180000});
  audit.startup_seconds=(performance.now()-started)/1000;
  await context.setOffline(true);offline=true;
  async function download(id,name){
    const event=page.waitForEvent('download');await page.locator('#'+id).click();
    const bytes=await readFile(await(await event).path());await writeFile(path.join(output,name),bytes);return bytes;
  }
  for(const {name,native,input,record} of nativeCases){
    await page.locator('details').evaluateAll(nodes=>nodes.forEach(node=>node.open=true));
    // A genuine empty project import keeps each portable artifact independent.
    const projectName='Original ST-5 '+name+' · source section';
    const empty={format:'openswing-project',version:2,name:projectName,selected:null,cases:[],solutions:[],selected_solution:null};
    await page.locator('#project-file').setInputFiles({name:'empty-project.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(empty))});
    await expect(page.locator('#project-name')).toHaveValue(projectName);await expect(page.locator('#project-load-solution')).toBeDisabled();
    await page.locator('#file').setInputFiles({name:path.basename(record.source.path),mimeType:'text/plain',buffer:Buffer.from(input.source)});
    await expect(page.locator('#editor')).toHaveValue(input.source);await expect(page.locator('#solve')).toBeEnabled();
    await page.locator('#node-file').setInputFiles({name:'original-stations.json',mimeType:'application/json',
      buffer:Buffer.from(JSON.stringify({format:'openswing-mesh',version:1,panels:input.panels}))});
    await page.waitForFunction(()=>!document.querySelector('#node-file').value);await expect(page.locator('#solve')).toBeEnabled();
    await page.locator('#mode').selectOption('structural');await expect(page.locator('#solve')).toBeEnabled();
    await page.locator('#structural-equations').selectOption('aswing-section');await expect(page.locator('#solve')).toBeEnabled();
    await expect(page.locator('#error')).toBeHidden();await page.locator('#static-gravity-mode').selectOption('file');
    await page.locator('#tab-nodes').click();
    for(const [beam,value] of Object.entries(input.panels.beams)){
      await page.locator('#node-beam').selectOption(beam);await expect(page.locator('#node-table tbody tr')).toHaveCount(value.nodes.length);
    }
    const before=await page.evaluate(()=>window.referenceRequests),lastInspect=before.filter(r=>r.request?.action==='inspect').at(-1);
    assert.deepEqual(wire(lastInspect.request.numerics),policy);assert.equal(lastInspect.request.source,input.source);
    check(name+' source policy used by geometry inspection',true);
    const priorSolves=before.filter(r=>r.request?.action==='solve').length;
    console.log('BEGIN offline cold structural solve '+name);const began=performance.now();
    await page.locator('#solve').click();
    await expect(page.locator('#result-state')).toHaveText(/Converged.*ASWING static/,{timeout:120000});
    await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();
    record.solve_seconds=(performance.now()-began)/1000;
    const bytes=await download('export-json',name+'/result.json'),result=JSON.parse(bytes);
    assert.deepEqual(result.request,input);assert.deepEqual(result.numerics,policy);
    assert.deepEqual(result.software_provenance.modules,audit.modules);
    check(name+' cold solve has no initial state',!Object.hasOwn(result.request,'initial_state'));
    check(name+' converged at unchanged residual gate',result.converged&&result.residual<=audit.gates.residual);
    check(name+' source structural output',result.structural_only&&result.strips.length===0&&result.condition===null
      &&!Object.hasOwn(result.equilibrium_state,'launch')&&result.mass_properties.dynamic_inertia_available===false);
    for(const key of Object.keys(policy))assert.equal(result.equilibrium_state.identity[key],policy[key]);
    check(name+' authoritative source endpoint recovery',result.structure.strain_source==='source_discrete_constitutive'
      &&result.elements.every(element=>element.endpoint_traces.length===2));
    record.parity=compare(native,result);check(name+' full native output parity',record.parity.max_fraction<=1,record.parity);
    await expect(page.locator('#structure-state')).toContainText('interval constitutive estimates');
    await page.locator('#structure-quantity').selectOption('curvature_change.1');await expect(page.locator('#structure-plot svg')).toBeVisible();
    await page.locator('#project-case-name').fill(name+' original node grid');await page.locator('#project-add').click();
    await expect(page.locator('#project-status')).toContainText('New case saved.');
    const solutionName=name+' computed static result';
    await page.locator('#project-solution-name').fill(solutionName);await page.locator('#project-save-solution').click();
    await expect(page.locator('#project-status')).toContainText('Computed solution saved.');await expect(page.locator('#project-load-solution')).toBeEnabled();
    const projectBytes=await download('project-export',name+'/project.json'),project=JSON.parse(projectBytes);
    assert.equal(project.cases.length,1);assert.equal(project.solutions.length,1);
    const saved=project.solutions[0];assert.equal(saved.name,solutionName);assert.deepEqual(saved.data,result);
    assert.equal(saved.configuration.source,input.source);assert.deepEqual(saved.configuration.mesh,input.panels);
    assert.deepEqual(saved.configuration.numerics,policy);assert.deepEqual(saved.data.request,input);
    assert.equal(saved.configuration.fields.mode,'structural');assert.equal(saved.configuration.fields['static-gravity-mode'],'file');
    assert.equal(saved.configuration.equilibrium.enabled,false);
    await page.locator('#project-file').setInputFiles({name:'saved-st5-project.json',mimeType:'application/json',buffer:projectBytes});
    await expect(page.locator('#project-status')).toContainText('Project opened.');await expect(page.locator('#project-load-solution')).toBeEnabled();
    await page.locator('#project-load-solution').click();await expect(page.locator('#project-status')).toContainText('Opened '+solutionName+'.');
    await expect(page.locator('#export-json')).toBeEnabled();await expect(page.locator('#structural-equations')).toHaveValue('aswing-section');
    await expect(page.locator('#error')).toBeHidden();await expect(page.locator('#editor')).toHaveValue(input.source);
    const reopened=await download('export-json',name+'/reopened-result.json');
    check(name+' reopened result is byte-exact',Buffer.compare(bytes,reopened)===0);
    const reexport=await download('project-export',name+'/reopened-project.json');
    check(name+' reexported project is byte-exact',Buffer.compare(projectBytes,reexport)===0);
    const after=await page.evaluate(()=>window.referenceRequests),solves=after.filter(r=>r.request?.action==='solve');
    check(name+' exactly one solve and no restore solve',solves.length===priorSolves+1);
    assert.deepEqual(wire(solves.at(-1).request),input);
    await expect(page.locator('#structure-plot svg')).toBeVisible();
    check(name+' exactly one viewer canvas',await page.locator('#viewport canvas').count()===1);
    record.canvas=await page.locator('#viewport canvas').evaluate(canvas=>({backend:canvas.dataset.renderer??null,width:canvas.width,height:canvas.height,
      rect:{width:canvas.getBoundingClientRect().width,height:canvas.getBoundingClientRect().height}}));
    check(name+' nonempty canvas dimensions',record.canvas.width>0&&record.canvas.height>0);
    await page.screenshot({path:path.join(output,name,'desktop.png')});
    record.status='PASS';record.result=await pin(path.join(output,name,'result.json'));record.project=await pin(path.join(output,name,'project.json'));
    console.log(JSON.stringify({case:name,status:record.status,solve_seconds:record.solve_seconds,parity:record.parity}));
  }
  await page.locator('details').evaluateAll(nodes=>nodes.forEach(node=>node.open=false));
  await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();await page.locator('#fit').click();
  check('mobile viewport fits',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:path.join(output,'mobile.png')});
  const requests=await page.evaluate(()=>window.referenceRequests),solveRequests=requests.filter(r=>r.request?.action==='solve');
  check('exactly two cold solves; all restores saved-only',solveRequests.length===2);
  solveRequests.forEach((request,i)=>assert.deepEqual(wire(request.request),nativeCases[i].input));
  await save('requests.json',requests);await save('events.json',await page.evaluate(()=>window.referenceEvents));
  audit.request_counts=Object.fromEntries([...new Set(requests.map(r=>r.request?.action??'runtime'))]
    .map(action=>[action,requests.filter(r=>(r.request?.action??'runtime')===action).length]));
  audit.parity={numeric:audit.cases.reduce((n,c)=>n+c.parity.numeric,0),leaves:audit.cases.reduce((n,c)=>n+c.parity.leaves,0),
    max_absolute:Math.max(...audit.cases.map(c=>c.parity.max_absolute)),max_fraction:Math.max(...audit.cases.map(c=>c.parity.max_fraction))};
  const retained=[...plan.source_pins,audit.plan,audit.native_summary,audit.script,...audit.ui_source_pins,...audit.built_assets,
    ...audit.cases.flatMap(c=>[c.native,c.case_plan,c.source])];
  for(const p of retained)check('unchanged '+p.path,JSON.stringify(await pin(p.path))===JSON.stringify(p));
  for(const name of names)for(const folder of ['openswing','public/kernel','dist/kernel'])
    check('unchanged '+folder+'/'+name,sha(await readFile(path.join(root,folder,name)))===audit.modules[name]);
  check('no offline HTTP requests',audit.offline_requests.length===0);check('no external requests',audit.blocked_external_requests.length===0);
  check('no page errors',audit.page_errors.length===0);check('no network failures',audit.network_failures.length===0);
  audit.status='PASS_OFFLINE_ST5_TWO_LOAD_CASES_AND_SAVED_PROJECTS';
  }
}catch(error){
  audit.status='FAILURE_RETAINED';audit.error={message:error.message,stack:error.stack};process.exitCode=1;console.error(error.stack);
  try{if(page&&!page.isClosed()){
    await save('requests-at-failure.json',await page.evaluate(()=>window.referenceRequests));
    await save('events-at-failure.json',await page.evaluate(()=>window.referenceEvents));
    await writeFile(path.join(output,'failure.html'),await page.content());await page.screenshot({path:path.join(output,'failure.png')});
  }}catch{}
}finally{
  clearTimeout(timer);
  try{await browser?.close();}catch(error){audit.cleanup_error=error.message;process.exitCode=1;audit.status='FAILURE_RETAINED';}
  server?.closeAllConnections();if(server?.listening)await new Promise(resolve=>server.close(resolve));
  audit.total_seconds=(performance.now()-started)/1000;audit.checks_passed=audit.checks.filter(c=>c.passed).length;audit.checks_total=audit.checks.length;
  await save('report.json',audit);console.log(JSON.stringify({status:audit.status,checks_passed:audit.checks_passed,checks_total:audit.checks_total,
    startup_seconds:audit.startup_seconds,parity:audit.parity,total_seconds:audit.total_seconds}));
}
