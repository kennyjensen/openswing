// Real built UI -> Pyodide worker; one cold mounted equilibrium and one rejected crossing.
// Run only after the native source snapshot and local build are frozen:
// node scripts/test-wall-root-browser.mjs NEW_OUTPUT_DIR FINAL_NATIVE_JSON
import {chromium} from 'playwright';
import {expect} from '@playwright/test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {createReadStream} from 'node:fs';
import {readFile, readdir, writeFile, mkdir, stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const scriptPath=fileURLToPath(import.meta.url);
const root=path.resolve(path.dirname(scriptPath),'..');
assert(process.argv.length===4,'Usage: node scripts/test-wall-root-browser.mjs NEW_OUTPUT_DIR FINAL_NATIVE_JSON');
const output=path.resolve(process.argv[2]),nativePath=path.resolve(process.argv[3]);
await mkdir(output,{recursive:false}); // Never overwrite a retained attempt.
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const pin=async name=>{const bytes=await readFile(name);return {path:name,bytes:bytes.length,sha256:sha(bytes)};};
const audit={status:'PREPARING',cases:[],checks:[],page_errors:[],network_failures:[],offline_requests:[],
  scope:'Current locally built UI and real Chromium/Pyodide worker, offline after startup. One cold mounted steady wall-root equilibrium and one physical-crossing rejection; no dynamics, eigenmodes, time integration or hosted release.',
  planned:{equilibria:1,invalid_crossing_requests:1,worker_solve_requests:2},
  gates:{absolute:2e-8,relative:2e-8,full_residual:1e-8,root_pose:1e-10},
  tolerance_basis:'Same source, explicit mesh and physical conditions across native and WASM. Compare every native result field except the named counters and equivalent zero-gravity source label.',
  exclusions:['evaluations','circulation_solver.evaluations','gravity_source'],
  declared_equivalences:['Native zero body gravity and UI zero Earth gravity at identity attitude are equal physical loads.','Empty circulation_modes and an explicit zero per lifting beam both select pointwise circulation.'],
  serving:{root:path.join(root,'dist'),rebuilt:false,source_override:false,asset_pins:[]},events:[]};
const save=()=>writeFile(path.join(output,'report.json'),JSON.stringify(audit,null,2)+'\n');
function check(name,value,details={}){
  audit.checks.push({name,passed:!!value,...details});assert(value,name);
}
function compare(expected,actual,label){
  const stats={scalars:0,leaves:0,maximum_fraction:0,maximum_absolute:0,worst:null};
  function visit(e,a,p){
    if(audit.exclusions.includes(p))return;
    if(typeof e==='number'){
      assert(typeof a==='number'&&Number.isFinite(a)&&Number.isFinite(e),`${label}:${p} finite`);
      const difference=Math.abs(a-e),limit=audit.gates.absolute+audit.gates.relative*Math.abs(e),fraction=difference/limit;
      stats.scalars++;stats.leaves++;stats.maximum_absolute=Math.max(stats.maximum_absolute,difference);
      if(fraction>stats.maximum_fraction)Object.assign(stats,{maximum_fraction:fraction,worst:p,difference,limit});
      assert(fraction<=1,`${label}:${p}: difference ${difference} > ${limit}`);
    }else if(Array.isArray(e)){
      assert(Array.isArray(a)&&a.length===e.length,`${label}:${p} array shape`);
      e.forEach((value,i)=>visit(value,a[i],`${p}[${i}]`));
    }else if(e!==null&&typeof e==='object'){
      assert(a!==null&&typeof a==='object'&&!Array.isArray(a),`${label}:${p} object`);
      for(const [key,value] of Object.entries(e)){
        assert(Object.hasOwn(a,key),`${label}:${p}.${key} present`);
        visit(value,a[key],p?`${p}.${key}`:key);
      }
    }else{stats.leaves++;assert.deepEqual(a,e,`${label}:${p}`);}
  }
  visit(expected,actual,'');return stats;
}
const normalizedCondition=value=>({...value,
  circulation_modes:Object.fromEntries(Object.entries(value.circulation_modes).filter(([,n])=>n!==0))});
let browser,server,page,timer,native,nativeBytes;let offline=false;
const started=performance.now();
try{
  audit.script=await pin(scriptPath);
  nativeBytes=await readFile(nativePath);native=JSON.parse(nativeBytes);
  audit.native_report={path:nativePath,bytes:nativeBytes.length,sha256:sha(nativeBytes)};
  await save();
  check('native record completed',native.status==='completed');
  check('exact native source digest',sha(Buffer.from(native.source))===native.source_sha256);
  check('native fresh residual',Number.isFinite(native.fresh_residual)&&native.fresh_residual<=audit.gates.full_residual);
  const c=native.condition_kwargs;
  assert(c&&typeof c==='object','Final native record must include complete dataclasses.asdict(condition) as condition_kwargs.');
  audit.condition=c;audit.source_sha256=native.source_sha256;audit.panels=native.panels;
  assert.equal(c.ground_effect,1);assert.deepEqual(c.ground_normal,[0,1,0]);
  assert.equal(c.beta,0);assert.equal(c.gravity_magnitude,0);assert.equal(c.time,0);assert.equal(c.gust,null);
  for(const key of ['rates','acceleration','angular_acceleration','position_earth','attitude'])assert.deepEqual(c[key],[0,0,0],key);
  for(const key of ['controls','powers'])assert.deepEqual(c[key],{},key);
  assert.equal(c.body_added_mass_factor,1);assert.equal(c.sensor_flow,'full');assert.equal(c.altitude_m,0);
  assert.deepEqual(normalizedCondition(c).circulation_modes,{});
  const beamKeys=Object.keys(native.panels.beams);assert.deepEqual(beamKeys,['1']);
  assert(Array.isArray(native.panels.beams['1'].nodes));
  audit.expected_node_count=native.panels.beams['1'].nodes.length;
  const names=(await readdir(path.join(root,'openswing'))).filter(name=>name.endsWith('.py')).sort();
  audit.modules={};audit.module_count=names.length;
  check('wall-root module included',names.includes('wall_root.py'));
  assert.deepEqual(Object.keys(native.source_pins).sort(),names.map(name=>'openswing/'+name));
  for(const name of names){
    const digest=sha(await readFile(path.join(root,'openswing',name)));audit.modules[name]=digest;
    check('native source '+name,native.source_pins['openswing/'+name]===digest);
    for(const folder of ['public/kernel','dist/kernel'])check(folder+'/'+name+' current source',sha(await readFile(path.join(root,folder,name)))===digest);
  }
  const manifest=JSON.parse(await readFile(path.join(root,'dist/kernel/manifest.json'),'utf8'));
  assert.deepEqual(manifest.slice().sort(),names);
  audit.serving.asset_pins.push(await pin(path.join(root,'dist/index.html')),await pin(path.join(root,'dist/kernel/manifest.json')));
  for(const name of (await readdir(path.join(root,'dist/assets'))).sort())audit.serving.asset_pins.push(await pin(path.join(root,'dist/assets',name)));
  await save();
  const mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.css':'text/css','.svg':'image/svg+xml','.woff2':'font/woff2'};
  server=createServer(async(req,res)=>{
    try{
      const relative=decodeURIComponent(new URL(req.url,'http://local').pathname);
      const target=path.resolve(audit.serving.root,'.'+(relative==='/'?'/index.html':relative));
      assert(target.startsWith(audit.serving.root+path.sep));
      const info=await stat(target);assert(info.isFile());
      res.writeHead(200,{'Content-Type':mime[path.extname(target)]||'application/octet-stream','Content-Length':info.size,'Cache-Control':'no-store'});
      createReadStream(target).pipe(res);
    }catch{res.writeHead(404);res.end('Not found');}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  audit.serving.url=`http://127.0.0.1:${server.address().port}`;
  const executable=process.env.OPENSWING_CHROMIUM_EXECUTABLE||'/tmp/aswing-chromium/chrome-linux/chrome';
  audit.chromium={executable,arguments:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']};
  browser=await chromium.launch({headless:true,executablePath:executable,args:audit.chromium.arguments});
  audit.chromium.version=browser.version();
  timer=setTimeout(()=>{audit.timeout=true;browser.close().catch(()=>{});},900000);
  const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
  page=await context.newPage();page.setDefaultTimeout(90000);
  page.on('pageerror',error=>audit.page_errors.push(error.message));
  context.on('requestfailed',request=>audit.network_failures.push({url:request.url(),failure:request.failure()}));
  context.on('request',request=>{if(offline&&/^https?:/.test(request.url()))audit.offline_requests.push(request.url());});
  await page.addInitScript(()=>{
    window.wallRootObserved={requests:[],progress:[],responses:[],rendered:[]};
    const Original=window.Worker;
    window.Worker=class extends Original{
      constructor(...args){
        super(...args);this.addEventListener('message',({data})=>{
          if(data?.type==='progress')window.wallRootObserved.progress.push(structuredClone(data));
          if(data?.id&&(data.error||data.result))window.wallRootObserved.responses.push({id:data.id,error:data.error??null,
            result:data.result?{analysis:data.result.analysis??null,converged:data.result.converged??null,residual:data.result.residual??null}:null});
        });
      }
      postMessage(message,...rest){window.wallRootObserved.requests.push(structuredClone(message));return super.postMessage(message,...rest);}
    };
    window.addEventListener('DOMContentLoaded',()=>{
      const watch=()=>{
        const node=document.querySelector('#runtime-status');if(!node){setTimeout(watch,50);return;}
        new MutationObserver(()=>window.wallRootObserved.rendered.push({message:node.textContent,
          detail:document.querySelector('#runtime-detail')?.textContent??'',progress:structuredClone(window.wallRootObserved.progress.at(-1)??null)}))
          .observe(node,{childList:true,characterData:true,subtree:true});
      };watch();
    },{once:true});
  });
  await page.goto(audit.serving.url);await expect(page.locator('#solve')).toBeEnabled({timeout:240000});
  await expect(page.locator('#error')).toBeHidden();
  audit.runtime_ready_seconds=(performance.now()-started)/1000;
  await context.setOffline(true);offline=true;audit.offline_after_ready=true;
  console.log('Browser ready; source matched native/build, HTTP disabled.');
  await page.locator('#file').setInputFiles({name:'wall-root-half.asw',mimeType:'text/plain',buffer:Buffer.from(native.source)});
  await expect(page.locator('#filename')).toHaveText('wall-root-half.asw');
  await expect(page.locator('#editor')).toHaveValue(native.source);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#node-file').setInputFiles({name:'wall-root-explicit-mesh.json',mimeType:'application/json',
    buffer:Buffer.from(JSON.stringify({format:'openswing-mesh',version:1,panels:native.panels}))});
  await expect(page.locator('#node-table tbody tr')).toHaveCount(audit.expected_node_count);
  await page.waitForFunction(()=>!document.querySelector('#node-file').value);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('mounted');
  await page.locator('details').evaluateAll(nodes=>nodes.forEach(node=>node.open=true));
  await page.locator('#density-mode').selectOption('custom');await page.locator('#gravity-mode').selectOption('custom');
  await page.locator('#mach-mode').selectOption('fixed');
  for(const [id,value] of [['speed',c.speed],['alpha',c.alpha],['beta',c.beta],['density',c.density],
    ['gravity-magnitude',c.gravity_magnitude],['pg-mach',c.mach],['load-factor',c.load_factor],
    ['stall-factor',c.stall_factor],['stall-width',c.stall_width],['wake-core-ratio',c.wake_core_ratio],['altitude',0]])
    await page.locator('#'+id).fill(String(value));
  await page.locator('#stall').setChecked(c.stall);await page.locator('#aero-lag').setChecked(c.aero_lag);
  await page.locator('#freeze-influences').setChecked(c.freeze_influences);await page.locator('#derivatives-enable').uncheck();
  await page.locator('#ground-effect').selectOption('1');await page.locator('#gust-kind').selectOption('none');
  for(const [i,axis] of ['x','y','z'].entries()){
    await page.locator('#position-earth-'+axis).fill(String(c.position_earth[i]));
    await page.locator('#ground-normal-'+axis).fill(String(c.ground_normal[i]));
    for(const group of ['rates','acceleration','angular_acceleration'])await page.locator('#'+group+'-'+axis).fill('0');
  }
  for(const key of ['bank','elevation','heading'])await page.locator('#attitude-'+key).fill('0');
  await page.locator('#circulation-modes input').fill('0');
  const entry={id:'mounted-half',status:'SOLVING'};audit.cases.push(entry);await save();
  const begin=performance.now();console.log('Starting the sole cold mounted equilibrium.');
  await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:600000});
  await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();
  entry.seconds=(performance.now()-begin)/1000;
  const download=page.waitForEvent('download');await page.locator('#export-json').click();
  const bytes=await readFile(await(await download).path());await writeFile(path.join(output,'mounted-half.json'),bytes);
  const result=JSON.parse(bytes);entry.result_sha256=sha(bytes);entry.runtime=result.software_provenance.runtime;
  assert.deepEqual(result.software_provenance.modules,audit.modules);
  assert.equal(result.request.source,native.source);assert.deepEqual(result.request.panels,native.panels);
  assert.equal(result.request.mode,'mounted');assert.equal(result.request.controller,null);
  assert.deepEqual(result.request.operating_constraints,[]);
  assert.deepEqual(normalizedCondition(result.request.condition),normalizedCondition(c));
  check('cold start',!result.request.initial_state);
  check('normalized full residual',result.converged&&result.residual<=audit.gates.full_residual,{residual:result.residual});
  assert.deepEqual(result.gravity_body,[0,0,0]);assert.equal(result.gravity_source,'Earth_magnitude');
  check('physical result, not derivative probe',result.ground_plane.wall_root_derivative_probe===false);
  assert.equal(result.ground_plane.wall_roots.length,1);
  const mount=result.ground_plane.wall_roots[0],rootNodes=result.nodes.filter(node=>node.beam===mount.beam&&node.t===mount.t);
  assert.equal(rootNodes.length,1);
  entry.root_pose_error=Math.max(...rootNodes[0].position.map(Math.abs),...rootNodes[0].rotation.flatMap((row,i)=>row.map((v,j)=>Math.abs(v-(i===j?1:0)))));
  check('exact mounted root within roundoff',entry.root_pose_error<=audit.gates.root_pose,{error:entry.root_pose_error});
  entry.physical_comparison=compare(native.result,result,'mounted half');
  let observed=await page.evaluate(()=>window.wallRootObserved);
  let requests=observed.requests.filter(message=>message.request?.action==='solve');assert.equal(requests.length,1);
  const request=requests[0];entry.worker_request_id=request.id;
  const progress=observed.progress.filter(p=>p.id===request.id),rendered=observed.rendered.filter(p=>p.progress?.id===request.id);
  entry.progress={events:progress,rendered};
  check('four continuation load stages',[.25,.5,.75,1].every(f=>progress.some(p=>p.stage==='static_load'&&p.time/p.steps===f)));
  check('structured assembly progress',progress.some(p=>p.stage==='static_tangent'&&p.time===0)&&progress.some(p=>p.stage==='static_tangent'&&p.time===p.steps));
  check('mounted progress rendered',rendered.some(p=>p.message.startsWith('Balancing forces · applied load')&&p.detail.includes('not overall completion')));
  check('no time-integration labels',rendered.every(p=>!p.message.startsWith('Integrating')));
  await page.screenshot({path:path.join(output,'mounted-half-desktop.png'),fullPage:true});
  entry.status='PASS';await save();console.log('PASS mounted half',entry.seconds.toFixed(2)+'s',JSON.stringify(entry.physical_comparison));

  const invalid={id:'physical-crossing',status:'REQUESTING',position_earth:[0,-.001,0]};audit.cases.push(invalid);await save();
  await page.locator('#position-earth-y').fill('-.001');
  const invalidStart=performance.now();await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis stopped',{timeout:90000});
  await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeVisible();
  await expect(page.locator('#export-json')).toBeDisabled();
  invalid.seconds=(performance.now()-invalidStart)/1000;invalid.visible_error=await page.locator('#error').innerText();
  check('crossing visible error',/touches or crosses the ground image plane/.test(invalid.visible_error));
  observed=await page.evaluate(()=>window.wallRootObserved);
  requests=observed.requests.filter(message=>message.request?.action==='solve');assert.equal(requests.length,2);
  const rejected=requests[1];invalid.worker_request_id=rejected.id;
  assert.equal(rejected.request.source,native.source);assert.deepEqual(rejected.request.panels,native.panels);
  assert.deepEqual(normalizedCondition(rejected.request.condition),normalizedCondition({...c,position_earth:invalid.position_earth}));
  assert.equal(rejected.request.mode,'mounted');assert(!rejected.request.initial_state);
  const response=observed.responses.filter(message=>message.id===rejected.id);assert.equal(response.length,1);
  invalid.worker_error=response[0].error;
  check('worker collision rejected without result',response[0].result===null&&/touches or crosses the ground image plane/.test(response[0].error));
  invalid.progress=observed.progress.filter(p=>p.id===rejected.id);
  check('crossing rejected before positive load continuation',invalid.progress.every(p=>p.stage!=='static_tangent'&&!(p.stage==='static_load'&&p.time>0)));
  await page.screenshot({path:path.join(output,'physical-crossing-desktop.png'),fullPage:true});
  invalid.status='PASS_REJECTED';await writeFile(path.join(output,'observed.json'),JSON.stringify(observed,null,2)+'\n');
  check('exact planned worker solve requests',requests.length===audit.planned.worker_solve_requests);
  check('offline HTTP requests absent',audit.offline_requests.length===0);
  check('page errors absent',audit.page_errors.length===0);check('network failures absent',audit.network_failures.length===0);
  for(const [name,digest] of Object.entries(audit.modules)){
    for(const folder of ['openswing','public/kernel','dist/kernel'])check('unchanged '+folder+'/'+name,sha(await readFile(path.join(root,folder,name)))===digest);
  }
  for(const item of audit.serving.asset_pins)check('unchanged built asset '+path.relative(root,item.path),sha(await readFile(item.path))===item.sha256);
  check('native record unchanged',sha(await readFile(nativePath))===audit.native_report.sha256);
  check('browser driver unchanged',sha(await readFile(scriptPath))===audit.script.sha256);
  audit.status='PASS_OFFLINE_CHROMIUM_WALL_ROOT';
}catch(error){
  audit.status='FAIL_RETAINED';audit.error={message:error.message,stack:error.stack};process.exitCode=1;console.error(error.stack);
  try{if(page&&!page.isClosed()){
    await page.screenshot({path:path.join(output,'failure.png'),fullPage:true});
    await writeFile(path.join(output,'observed.json'),JSON.stringify(await page.evaluate(()=>window.wallRootObserved??{}),null,2)+'\n');
  }}catch(captureError){audit.failure_capture_error=captureError.message;}
}finally{
  clearTimeout(timer);
  try{await browser?.close();}catch(error){audit.cleanup_error=error.message;process.exitCode=1;audit.status='FAIL_RETAINED';}
  server?.closeAllConnections();if(server?.listening)await new Promise(resolve=>server.close(resolve));
  audit.total_seconds=(performance.now()-started)/1000;
  audit.counts={passed:audit.checks.filter(c=>c.passed).length,total:audit.checks.length,
    completed_equilibria:audit.cases.filter(c=>c.status==='PASS').length,
    expected_rejections:audit.cases.filter(c=>c.status==='PASS_REJECTED').length};
  await save();console.log(JSON.stringify({status:audit.status,counts:audit.counts,total_seconds:audit.total_seconds}));
}
