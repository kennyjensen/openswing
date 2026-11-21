// Offline literal FFWT import/editor/project checks, with an explicitly gated UI solve.
// node scripts/test-ffwt-input-browser.mjs NEW_OUTPUT NATIVE_STAGE [--solve]
import {chromium} from 'playwright';
import {expect} from '@playwright/test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {createReadStream} from 'node:fs';
import {readFile,writeFile,readdir,mkdir,stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';


assert([4,5].includes(process.argv.length),'Supply new output, native stage and optional --solve.');
if(process.argv.length===5)assert.equal(process.argv[4],'--solve');
const solveEnabled=process.argv[4]==='--solve';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.resolve(process.argv[2]),nativeStage=path.resolve(process.argv[3]);
await mkdir(output,{recursive:false});
const sha=b=>createHash('sha256').update(b).digest('hex');
const pin=async p=>{const b=await readFile(p);return {path:p,bytes:b.length,sha256:sha(b)};};
const read=async p=>JSON.parse(await readFile(p));
const wire=value=>JSON.parse(JSON.stringify(value));
const audit={status:'PREPARING',checks:[],page_errors:[],offline_requests:[],network_failures:[],
 planned_solves:solveEnabled?1:0,additional_native_solves:0,case:'coarse',retries:0,
 scope:'Literal archived FFWT file import, constant rigid GJ preview on beam3, exact raw source export, canonical worker serialization followed by real UI reimport, and project roundtrip. Optional one cold mounted UI solve is gated by a successful native physical pilot. Browser/native agreement does not establish archived ASWING agreement.',
 canonical_scope:'canonical_asw is sent directly to the app worker because there is no canonical-format UI button. Its returned text is reimported using the ordinary file UI. No solve or result is injected through this helper.',
 gates:{absolute:2e-8,relative:2e-8,residual:1e-8},exclusions:['evaluations'],
 exclusion_reason:'Execution counter only; every native physical field and metadata key is compared.',
 caps:{startup_ms:180000,solve_ms:240000,internal_total_ms:435000,owner_seconds:450}};
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
 const {parseProject}=await import('../web/project-data.js');
 const plan=await read(path.join(nativeStage,'plan.json'));
 audit.plan=await pin(path.join(nativeStage,'plan.json'));audit.script=await pin(fileURLToPath(import.meta.url));audit.inputs=[];
 audit.historical_input_snapshots=[];
 for(const p of plan.pins){
  if(p.path===path.join(root,'scripts/verify-isae-ffwt-reference.py')){
   let resolved=p.path,bytes=await readFile(p.path);
   if(sha(bytes)!==p.sha256){resolved=path.join(nativeStage+'-completion','runner-v1-at-execution.py');bytes=await readFile(resolved);}
   check('frozen native input '+p.path,sha(bytes)===p.sha256);
   const saved=path.join(output,'native-driver-at-launch.py');await writeFile(saved,bytes);
   const retained=await pin(saved);assert.equal(retained.sha256,p.sha256);
   audit.historical_input_snapshots.push({original:p,retained,resolved_from:resolved,reason:'The completed native producer is pinned to these executed bytes; subsequent closure-only code does not change saved native results.'});
  }else check('frozen native input '+p.path,(await pin(p.path)).sha256===p.sha256);
 }
 const names=(await readdir(path.join(root,'openswing'))).filter(n=>n.endsWith('.py')).sort();
 assert.deepEqual(names,Object.keys(plan.kernel_pins).sort());audit.modules=plan.kernel_pins;
 for(const n of names)for(const folder of ['openswing','public/kernel','dist/kernel'])check(folder+'/'+n,sha(await readFile(path.join(root,folder,n)))===audit.modules[n]);
 audit.ui_sources=[];for(const n of (await readdir(path.join(root,'web'))).filter(n=>n.endsWith('.js')))audit.ui_sources.push(await pin(path.join(root,'web',n)));
 const folder=path.join(nativeStage,'cases','coarse');
 const request=await read(path.join(folder,'request.json')),inputBytes=await readFile(path.join(folder,'input-project.json'));
 const inputProject=parseProject(inputBytes.toString('utf8'));
 const sourcePath=path.join(root,'examples/isae-ffwt-flare10.asw'),sourceBytes=await readFile(sourcePath),source=sourceBytes.toString('utf8');
 for(const p of [sourcePath,path.join(folder,'request.json'),path.join(folder,'input-project.json')])audit.inputs.push(await pin(p));
 check('literal archived file hash',sha(sourceBytes)==='f73fe93bebb9419f0d38d94dc9a365baac7e3437e2996473c72c3c1f459fbf13');
 assert.equal(request.source,source);assert.equal(request.mode,'mounted');assert.equal(request.action,'solve');assert(!request.initial_state);
 assert.deepEqual(request.numerics,{beam_interpolation:'drela-segspl-v1',structural_operator:'drela-steady-coupled-v1'});
 const config=inputProject.cases.find(c=>c.id===inputProject.selected).configuration;
 assert.equal(inputProject.cases.length,1);assert.equal(inputProject.solutions.length,0);assert.equal(inputProject.selected_solution,null);
 assert.equal(config.source,source);assert.deepEqual(config.mesh,request.panels);assert.deepEqual(config.numerics,request.numerics);
 assert.deepEqual(config.controls,{'1':'0'});assert.deepEqual(config.powers,{});assert.deepEqual(config.circulation,{'1':'0','2':'0','3':'0'});
 for(const k of ['roll','pitch','yaw'])assert.equal(config.fields['trim-'+k],'1');assert.equal(config.fields['trim-engine'],'');
 assert.equal(config.fields.mode,'mounted');assert.deepEqual(config.constraints,[]);assert.deepEqual(config.equilibrium,{state:null,enabled:false,label:''});
 for(const [field,key] of [['speed','speed'],['alpha','alpha'],['beta','beta'],['density','density'],['gravity-magnitude','gravity_magnitude'],['pg-mach','mach'],['ground-effect','ground_effect']])assert.equal(Number(config.fields[field]),request.condition[key]);
 check('Node project parser and model-index/request preflight',true);
 let native=null;
 if(solveEnabled){
  const summary=await read(path.join(nativeStage,'summary.json')),physical=await read(path.join(folder,'report.json'));
  check('native pilot physical gates passed before browser solve',summary.status.startsWith('PASS')&&physical.status==='PASS'&&physical.checks.every(c=>c.passed));
  native=await read(path.join(folder,'result.json'));check('native converged finite residual',native.converged&&Number.isFinite(native.residual)&&native.residual<=audit.gates.residual);
  for(const p of [path.join(nativeStage,'summary.json'),path.join(folder,'report.json'),path.join(folder,'result.json')])audit.inputs.push(await pin(p));
  audit.native_summary=await pin(path.join(nativeStage,'summary.json'));audit.native_report=await pin(path.join(folder,'report.json'));
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
    window.referenceRequests=[];window.referenceEvents=[];window.referenceReplies={};const WorkerClass=window.Worker;
    window.Worker=class extends WorkerClass{
      constructor(...args){super(...args);window.ffwtWorker=this;this.addEventListener('message',e=>{
        if(e.data?.type==='progress')window.referenceEvents.push(structuredClone(e.data));
        else if(e.data?.id!==undefined)window.referenceReplies[e.data.id]=structuredClone(e.data);
      });}
      postMessage(message,...rest){window.referenceRequests.push(structuredClone(message));return super.postMessage(message,...rest);}
    };
    let specialId=1000000;
    window.ffwtCanonical=request=>new Promise((resolve,reject)=>{
      if(request.action!=='canonical_asw')throw new Error('This helper supports canonical serialization only.');
      const worker=window.ffwtWorker,id=++specialId,timeout=setTimeout(()=>{worker.removeEventListener('message',receive);reject(new Error('Canonical request timed out'));},60000);
      function receive(e){if(e.data?.id!==id||e.data?.type==='progress')return;clearTimeout(timeout);worker.removeEventListener('message',receive);e.data.error?reject(new Error(e.data.error)):resolve(e.data.result);}
      worker.addEventListener('message',receive);worker.postMessage({id,request});
    });
  });
  await page.goto(audit.url);await expect(page.locator('#solve')).toBeEnabled({timeout:audit.caps.startup_ms});audit.startup_seconds=(performance.now()-started)/1000;
  await context.setOffline(true);offline=true;
  async function openControls(){await page.locator('details').evaluateAll(nodes=>nodes.forEach(n=>n.open=true));}
  async function download(id,name){const event=page.waitForEvent('download');await page.locator('#'+id).click();const bytes=await readFile(await(await event).path());await writeFile(path.join(output,name),bytes);return bytes;}
  async function loadProject(bytes,solution=false){
    const project=JSON.parse(bytes);await openControls();await page.locator('#project-file').setInputFiles({name:'ffwt-project.json',mimeType:'application/json',buffer:bytes});
    await expect(page.locator('#project-name')).toHaveValue(project.name);await expect(page.locator('#project-cases')).toHaveValue(project.selected??'');
    const selector=solution?'#project-load-solution':'#project-load';await expect(page.locator(selector)).toBeEnabled();await page.locator(selector).click();
    await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();await openControls();
  }
  async function importFile(bytes,name){
    await page.locator('#file').setInputFiles({name,mimeType:'text/plain',buffer:bytes});
    await expect(page.locator('#editor')).toHaveValue(bytes.toString('utf8'));await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();
  }
  async function preview(label,expectedSource){
    await page.locator('#tab-distributions').click();await page.locator('#distribution-beam').selectOption('3');
    await expect(page.locator('#distribution-load')).toBeEnabled();await page.locator('#distribution-name').fill('GJ');
    const requestStart=await page.evaluate(()=>window.referenceRequests.length);
    await page.locator('#distribution-load').click();
    // Canonical and literal text can produce identical visible previews. Wait
    // for this click's worker reply, rather than accepting the previous plot.
    await page.waitForFunction(({source,start})=>{
      const m=window.referenceRequests.slice(start).filter(x=>x.request?.action==='distribution'&&x.request.beam===3&&x.request.name==='GJ'&&x.request.source===source).at(-1);
      return m&&window.referenceReplies[m.id];
    },{source:expectedSource,start:requestStart});
    await expect(page.locator('#distribution-plot-note')).toContainText('Rigid throughout the beam');await expect(page.locator('#distribution-table tbody tr')).toHaveCount(1);
    await expect(page.locator('#distribution-plot svg')).toHaveAttribute('aria-label',/rigid throughout the beam/);
    await expect(page.locator('#distribution-plot .distribution-point')).toHaveCount(1);
    const report=await page.evaluate(({source,start})=>{
      const m=window.referenceRequests.slice(start).filter(x=>x.request?.action==='distribution'&&x.request.beam===3&&x.request.name==='GJ'&&x.request.source===source).at(-1);
      const reply=window.referenceReplies[m.id];if(reply.error)throw new Error(reply.error);return reply.result;
    },{source:expectedSource,start:requestStart});
    assert(report.constant_rigid);assert.equal(report.mirrored,false);assert.deepEqual(report.points,[[.182,0]]);assert.deepEqual(report.domain,[-.5,-.364]);assert.equal(report.segments.length,1);
    const s=report.segments[0];assert.equal(s.extrapolated,false);assert(s.values.every(v=>v===0));assert.equal(s.t[0],-.5);assert.equal(s.t.at(-1),-.364);
    assert.deepEqual(report.software_provenance.modules,audit.modules);await writeFile(path.join(output,label+'-preview.json'),JSON.stringify(report,null,2)+'\n');
    check(label+' constant rigid preview preserves sample and actual domain',true);await page.locator('#pane-distributions').screenshot({path:path.join(output,label+'-preview.png')});
    return report;
  }
  await importFile(sourceBytes,'isae-ffwt-flare10.asw');
  check('raw file UI export is byte-exact',Buffer.compare(sourceBytes,await download('save','original-export.asw'))===0);
  await loadProject(inputBytes);await expect(page.locator('#structural-equations')).toHaveValue('aswing-coupled');
  await preview('original',source);
  await page.locator('#distribution-scale').fill('0');await page.locator('#distribution-preview').click();await expect(page.locator('#distribution-apply')).toBeEnabled();
  await expect(page.locator('#distribution-plot-note')).toContainText('Rigid throughout the beam');await page.locator('#distribution-apply').click();await expect(page.locator('#solve')).toBeEnabled();
  check('zero-only edit keeps original raw ASW bytes',Buffer.compare(sourceBytes,await download('save','zero-edit-export.asw'))===0);
  // Reload the exact original case before archiving its configuration and before any optional solve.
  await loadProject(inputBytes);
  const projectBytes=await download('project-export','input-project.json');assert.deepEqual(JSON.parse(projectBytes),inputProject);
  await loadProject(projectBytes);check('unsolved project roundtrip byte-exact',Buffer.compare(projectBytes,await download('project-export','input-project-reopened.json'))===0);
  const canonical=await page.evaluate(request=>window.ffwtCanonical(request),{action:'canonical_asw',source,panels:request.panels,numerics:request.numerics});
  assert.deepEqual(canonical.software_provenance.modules,audit.modules);await writeFile(path.join(output,'canonical.asw'),canonical.source);
  await importFile(Buffer.from(canonical.source),'ffwt-canonical.asw');
  check('canonical text reimports and exports exactly through UI',Buffer.compare(Buffer.from(canonical.source),await download('save','canonical-reexport.asw'))===0);
  const canonicalPreview=await preview('canonical',canonical.source);
  const canonicalAgain=await page.evaluate(request=>window.ffwtCanonical(request),{action:'canonical_asw',source:canonical.source,panels:request.panels,numerics:request.numerics});
  check('canonical serialization is idempotent',canonicalAgain.source===canonical.source);
  audit.canonical={source_sha256:sha(Buffer.from(canonical.source)),worker_only_requests:2,raw_source_unchanged:true,raw_singleton:canonicalPreview.points};
  await loadProject(inputBytes);check('literal source restored before optional solve',Buffer.compare(sourceBytes,await download('save','restored-original.asw'))===0);
  if(solveEnabled){
    console.log('Starting sole cold FFWT UI solve.');const begin=performance.now();await page.locator('#solve').click();
    await expect(page.locator('#result-state')).toHaveText('Converged · mounted equilibrium',{timeout:audit.caps.solve_ms});await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();audit.solve_seconds=(performance.now()-begin)/1000;
    const bytes=await download('export-json','result.json'),result=JSON.parse(bytes);assert.deepEqual(result.request,request);assert.deepEqual(result.software_provenance.modules,audit.modules);
    check('browser residual',result.converged&&result.residual<=audit.gates.residual);audit.parity=compare(native,result);check('full native parity',audit.parity.max_fraction<=1,audit.parity);
    check('version2 hinge charts retained without launch',result.equilibrium_state.version===2&&result.equilibrium_state.hinge_charts.length===2&&!Object.hasOwn(result.equilibrium_state,'launch'));
    await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText('SPRUNG HINGES');
    for(const h of result.hinges)await expect(page.locator('#pane-report')).toContainText(`hinge angle [deg] ${h.angle_deg.toPrecision(7)}`);
    await page.locator('#project-solution-name').fill('Literal FFWT conditional mounted result');await page.locator('#project-save-solution').click();await expect(page.locator('#project-load-solution')).toBeEnabled();
    const saved=await download('project-export','project.json');assert.equal(JSON.parse(saved).solutions.length,1);await loadProject(saved,true);
    check('solved result restores byte-exactly without solve',Buffer.compare(bytes,await download('export-json','result-reopened.json'))===0);
    check('solved project restores byte-exactly without solve',Buffer.compare(saved,await download('project-export','project-reopened.json'))===0);
    await page.locator('#fit').click();await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(output,'desktop.png')});
  }
  check('exactly one aircraft canvas',await page.locator('#viewport canvas').count()===1);audit.renderer=await page.locator('#viewport canvas').getAttribute('data-renderer');
  const requests=await page.evaluate(()=>window.referenceRequests),solves=requests.filter(r=>r.request?.action==='solve');
  check('exact planned solve count; none during restore',solves.length===audit.planned_solves);
  if(solveEnabled)assert.deepEqual(wire(solves[0].request),request);
  check('no injected solve',requests.filter(r=>r.id>=1000000).every(r=>r.request.action==='canonical_asw'));
  await writeFile(path.join(output,'requests.json'),JSON.stringify(requests,null,2)+'\n');await writeFile(path.join(output,'events.json'),JSON.stringify(await page.evaluate(()=>window.referenceEvents),null,2)+'\n');
  audit.request_counts=Object.fromEntries([...new Set(requests.map(r=>r.request?.action??'runtime'))].map(a=>[a,requests.filter(r=>(r.request?.action??'runtime')===a).length]));
  for(const p of [...plan.pins,audit.plan,audit.script,...audit.inputs,...audit.ui_sources,...audit.built_assets]){
    const historical=audit.historical_input_snapshots.find(s=>s.original.path===p.path);
    check('unchanged '+p.path,(await pin(historical?.retained.path??p.path)).sha256===p.sha256);
  }
  for(const n of names)for(const folder of ['openswing','public/kernel','dist/kernel'])check('unchanged '+folder+'/'+n,sha(await readFile(path.join(root,folder,n)))===audit.modules[n]);
  check('offline HTTP absent',audit.offline_requests.length===0);check('page errors absent',audit.page_errors.length===0);check('network failures absent',audit.network_failures.length===0);
  audit.status=solveEnabled?'PASS_FFWT_UI_IMPORT_PREVIEW_AND_ONE_COLD_NATIVE_PARITY':'PASS_FFWT_UI_IMPORT_PREVIEW_PROJECT_ZERO_SOLVES';
}catch(error){audit.status='FAILURE_RETAINED';audit.error={message:error.message,stack:error.stack};process.exitCode=1;console.error(error.stack);}
finally{
  if(page&&!page.isClosed())try{
    await writeFile(path.join(output,'requests-final.json'),JSON.stringify(await page.evaluate(()=>window.referenceRequests),null,2)+'\n');
    await writeFile(path.join(output,'events-final.json'),JSON.stringify(await page.evaluate(()=>window.referenceEvents),null,2)+'\n');
    if(audit.status==='FAILURE_RETAINED'){audit.visible_error=await page.locator('#error').textContent();await page.screenshot({path:path.join(output,'failure.png')});}
  }catch(error){audit.final_capture_error=error.message;}
  clearTimeout(timer);try{await browser?.close();}finally{server?.closeAllConnections();if(server?.listening)await new Promise(resolve=>server.close(resolve));}
  audit.total_seconds=(performance.now()-started)/1000;await writeFile(path.join(output,'report.json'),JSON.stringify(audit,null,2)+'\n');console.log(JSON.stringify({status:audit.status,planned_solves:audit.planned_solves,solve_seconds:audit.solve_seconds,parity:audit.parity,total_seconds:audit.total_seconds}));
}
