// Actual locally served Chromium UI -> Pyodide worker -> mounted equilibrium.
// Usage: node scripts/test-isae-ae1-browser.mjs NEW_OUTPUT_DIR [RETAINED_VACUUM_ATTEMPT]
import {chromium} from 'playwright';
import {expect} from '@playwright/test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {createReadStream} from 'node:fs';
import {readFile, readdir, writeFile, mkdir, stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output=path.resolve(process.argv[2] || '');
const priorVacuum=process.argv[3]?path.resolve(process.argv[3]):null;
assert(process.argv[2], 'Provide a new output directory.');
await mkdir(output, {recursive:false});
const sha=b=>createHash('sha256').update(b).digest('hex');
const pin=async p=>{const b=await readFile(p);return {path:p,bytes:b.length,sha256:sha(b)};};
const reportPath=path.join(root,'docs/validation/isae-ae1-pilot.json');
const nativeBytes=await readFile(reportPath), native=JSON.parse(nativeBytes);
const selected=[0,5,7].map((i,j)=>native.states[j===0?4:i]);
assert.deepEqual(selected.map(s=>[s.specification.refinement,s.specification.alpha_deg,s.specification.speed_m_s]),[[4,0,0],[4,5,30],[4,7,30]]);
const audit={status:'PREPARING',cases:[],checks:[],page_errors:[],network_failures:[],offline_requests:[],
  native_report:{path:reportPath,sha256:sha(nativeBytes)},script:await pin(fileURLToPath(import.meta.url)),
  gates:{absolute:2e-8,relative:2e-8,full_residual:1e-8},
  scope:'Existing local built app, real Chromium UI and Pyodide worker, offline after startup. Three cold starts: vacuum and two coupled cases. No hosted release or full browser suite assertion.',
  tolerance_basis:'Same discretization and equations across native BLAS and WASM; 2e-8 absolute+relative is far tighter than 0.7% pilot mesh differences. All native physical fields are compared, with only work counters and the explicitly equal-zero gravity-source label excluded.',
  exclusions:['evaluations','circulation_solver.evaluations','gravity_source'],
  declared_equivalences:['Native mounted run prescribes zero body gravity; UI derives zero Earth gravity from magnitude0 and attitude0.','UI circulation_modes={1:0} and native empty mapping both use pointwise circulation.','The structural bridge labels its no-flow result structural_static; the direct native network_result baseline labels the same physical output mounted_static. The baseline comparison explicitly changes only that label.'],
  serving:{root:path.join(root,'dist'),rebuilt:false,source_override:false},events:[]};
const save=()=>writeFile(path.join(output,'report.json'),JSON.stringify(audit,null,2)+'\n');
function check(name,value,details={}){audit.checks.push({name,passed:!!value,...details});assert(value,name);}
function compare(expected,actual,label){
  const stats={scalars:0,leaves:0,maximum_fraction:0,maximum_absolute:0,worst:null};
  const visit=(e,a,p)=>{
    if(audit.exclusions.includes(p))return;
    if(typeof e==='number'){
      assert(typeof a==='number'&&Number.isFinite(a)&&Number.isFinite(e),`${label}:${p} finite`);
      const d=Math.abs(a-e),limit=audit.gates.absolute+audit.gates.relative*Math.abs(e),fraction=d/limit;
      stats.scalars++;stats.leaves++;stats.maximum_absolute=Math.max(stats.maximum_absolute,d);
      if(fraction>stats.maximum_fraction)Object.assign(stats,{maximum_fraction:fraction,worst:p,difference:d,limit});
      assert(fraction<=1,`${label}:${p} difference ${d} > ${limit}`);
    }else if(Array.isArray(e)){
      assert(Array.isArray(a)&&a.length===e.length,`${label}:${p} array shape`);
      e.forEach((v,i)=>visit(v,a[i],`${p}[${i}]`));
    }else if(e!==null&&typeof e==='object'){
      assert(a!==null&&typeof a==='object',`${label}:${p} object`);
      for(const [key,value] of Object.entries(e)){assert(Object.hasOwn(a,key),`${label}:${p}.${key} present`);visit(value,a[key],p?`${p}.${key}`:key);}
    }else{stats.leaves++;assert.deepEqual(a,e,`${label}:${p}`);}
  };
  visit(expected,actual,'');return stats;
}
const nodeObservable=node=>{
  const c=node.rotation.map(row=>row[0]),p=node.position;
  return {midchord_m:p.map((v,i)=>v+.0059*c[i]),twist_deg:Math.atan2(-c[2],c[0])*180/Math.PI};
};
let browser,server,page,timer;let offline=false;const started=performance.now();
try{
  const names=(await readdir(path.join(root,'openswing'))).filter(n=>n.endsWith('.py')).sort();
  audit.modules={};audit.serving.asset_pins=[];
  for(const name of names){
    const digest=sha(await readFile(path.join(root,'openswing',name)));audit.modules[name]=digest;
    for(const folder of ['public/kernel','dist/kernel'])check(`${folder}/${name} current source`,sha(await readFile(path.join(root,folder,name)))===digest);
    check(`native kernel ${name}`,native.plan.source_sha256['openswing/'+name]===digest);
  }
  check('110 kernel modules',names.length===110);
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
  const executable=process.env.OPENSWING_CHROMIUM_EXECUTABLE || '/tmp/aswing-chromium/chrome-linux/chrome';
  audit.chromium={executable,arguments:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']};
  browser=await chromium.launch({headless:true,executablePath:executable,args:audit.chromium.arguments});
  audit.chromium.version=browser.version();
  timer=setTimeout(()=>{audit.timeout=true;browser.close().catch(()=>{});},1200000);
  const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
  page=await context.newPage();page.setDefaultTimeout(90000);
  page.on('pageerror',e=>audit.page_errors.push(e.message));
  context.on('requestfailed',r=>audit.network_failures.push({url:r.url(),failure:r.failure()}));
  context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))audit.offline_requests.push(r.url());});
  await page.addInitScript(()=>{
    window.ae1Observed={requests:[],progress:[],rendered:[]};
    const Original=window.Worker;
    window.Worker=class extends Original{
      constructor(...args){super(...args);this.addEventListener('message',({data})=>{if(data?.type==='progress')window.ae1Observed.progress.push(structuredClone(data));});}
      postMessage(message,...rest){window.ae1Observed.requests.push(structuredClone(message));return super.postMessage(message,...rest);}
    };
    window.addEventListener('DOMContentLoaded',()=>{
      const watch=()=>{
        const node=document.querySelector('#runtime-status');if(!node){setTimeout(watch,50);return;}
        new MutationObserver(()=>window.ae1Observed.rendered.push({message:node.textContent,
          detail:document.querySelector('#runtime-detail')?.textContent??'',progress:structuredClone(window.ae1Observed.progress.at(-1)??null)}))
          .observe(node,{childList:true,characterData:true,subtree:true});
      };watch();
    },{once:true});
  });
  await page.goto(audit.serving.url);await expect(page.locator('#solve')).toBeEnabled({timeout:240000});
  await expect(page.locator('#error')).toBeHidden();
  audit.runtime_ready_seconds=(performance.now()-started)/1000;
  await context.setOffline(true);offline=true;audit.offline_after_ready=true;
  console.log('Browser ready; current kernel verified on disk, HTTP disabled.');
  let browserBaseline;
  for(const old of selected){
    const spec=old.specification,id=spec.speed_m_s?`alpha${spec.alpha_deg}-u${spec.speed_m_s}`:'vacuum';
    const entry={id,specification:spec,status:'PREPARING'};audit.cases.push(entry);await save();
    if(priorVacuum&&!spec.speed_m_s){
      const priorReport=JSON.parse(await readFile(path.join(priorVacuum,'report.json'),'utf8'));
      assert.equal(priorReport.status,'FAIL_RETAINED');assert(priorReport.error.message.includes('vacuum:analysis'));
      assert.equal(priorReport.cases.length,1);
      const bytes=await readFile(path.join(priorVacuum,'vacuum.json')),result=JSON.parse(bytes);
      assert.equal(sha(bytes),priorReport.cases[0].result_sha256);
      assert.equal(old.result.analysis,'mounted_static');assert.equal(result.analysis,'structural_static');
      assert.deepEqual(result.software_provenance.modules,audit.modules);
      assert.equal(result.request.source,old.source);assert.deepEqual(result.request.panels,old.panels);
      assert.equal(result.request.condition,null);assert.deepEqual(result.request.gravity,[0,0,0]);
      entry.physical_comparison=compare({...old.result,analysis:'structural_static'},result,'retained vacuum');
      browserBaseline=nodeObservable(result.nodes.at(-1));entry.observable=browserBaseline;
      entry.observable_comparison=compare(nodeObservable(old.result.nodes.at(-1)),browserBaseline,'retained vacuum tip');
      const observed=JSON.parse(await readFile(path.join(priorVacuum,'observed.json'),'utf8'));
      const requests=observed.requests.filter(r=>r.request?.action==='solve');assert.equal(requests.length,1);
      const progress=observed.progress.filter(p=>p.id===requests[0].id),rendered=observed.rendered.filter(p=>p.progress?.id===requests[0].id);
      check('retained vacuum load stages',[.25,.5,.75,1].every(f=>progress.some(p=>p.stage==='static_load'&&p.time/p.steps===f)));
      check('retained vacuum residual',result.converged&&result.residual<=audit.gates.full_residual);
      entry.progress={events:progress,rendered};entry.seconds=priorReport.cases[0].seconds;entry.runtime=result.software_provenance.runtime;
      entry.result_sha256=sha(bytes);entry.reused_saved_only=true;entry.status='PASS';
      audit.reused_vacuum={report:await pin(path.join(priorVacuum,'report.json')),result:await pin(path.join(priorVacuum,'vacuum.json')),observed:await pin(path.join(priorVacuum,'observed.json'))};
      await writeFile(path.join(output,'vacuum.json'),bytes);await save();console.log('PASS retained vacuum; no repeated solve.');continue;
    }
    await page.setViewportSize({width:1440,height:1000});
    await page.locator('#file').setInputFiles({name:`ae1-${id}.asw`,mimeType:'text/plain',buffer:Buffer.from(old.source)});
    await expect(page.locator('#filename')).toHaveText(`ae1-${id}.asw`);
    await expect(page.locator('#editor')).toHaveValue(old.source);
    await expect(page.locator('#solve')).toBeEnabled();
    await page.locator('#node-file').setInputFiles({name:'ae1-60-half.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({format:'openswing-mesh',version:1,panels:old.panels}))});
    await expect(page.locator('#node-table tbody tr')).toHaveCount(121);
    await page.waitForFunction(()=>!document.querySelector('#node-file').value);
    await expect(page.locator('#solve')).toBeEnabled();
    await page.locator('#mode').selectOption(spec.speed_m_s?'mounted':'structural');
    await page.locator('details').evaluateAll(nodes=>nodes.forEach(n=>n.open=true));
    if(!spec.speed_m_s){
      await page.locator('#static-gravity-mode').selectOption('custom');
      for(const axis of ['x','y','z'])await page.locator('#static-gravity-'+axis).fill('0');
    }else{
      for(const [key,value] of [['speed',30],['alpha',spec.alpha_deg],['beta',0],['stall-factor',40],['stall-width',.05],['density',1.23],['gravity-magnitude',0],['pg-mach',0],['load-factor',1],['wake-core-ratio',.25]]){
        if(key==='density')await page.locator('#density-mode').selectOption('custom');
        if(key==='gravity-magnitude')await page.locator('#gravity-mode').selectOption('custom');
        if(key==='pg-mach')await page.locator('#mach-mode').selectOption('fixed');
        await page.locator('#'+key).fill(String(value));
      }
      await page.locator('#stall').check();await page.locator('#aero-lag').check();await page.locator('#freeze-influences').uncheck();
      await page.locator('#derivatives-enable').uncheck();await page.locator('#ground-effect').selectOption('0');
      for(const axis of ['x','y','z']){
        await page.locator('#position-earth-'+axis).fill('0');
        await page.locator('#ground-normal-'+axis).fill(axis==='y'?'1':'0');
        for(const group of ['rates','acceleration','angular_acceleration'])await page.locator('#'+group+'-'+axis).fill('0');
      }
      for(const key of ['bank','elevation','heading'])await page.locator('#attitude-'+key).fill('0');
      await page.locator('#circulation-modes input').fill('0');
    }
    const begin=performance.now();entry.status='SOLVING';await save();console.log('Starting',id);
    await page.locator('#solve').click();
    await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:600000});
    await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();
    entry.seconds=(performance.now()-begin)/1000;
    const download=page.waitForEvent('download');await page.locator('#export-json').click();
    const bytes=await readFile(await(await download).path());await writeFile(path.join(output,id+'.json'),bytes);
    const result=JSON.parse(bytes);entry.result_sha256=sha(bytes);entry.runtime=result.software_provenance.runtime;
    assert.deepEqual(result.software_provenance.modules,audit.modules);check(id+' exact loaded current kernel',true);
    assert.equal(result.request.source,old.source);assert.deepEqual(result.request.panels,old.panels);
    check(id+' cold start',!result.request.initial_state);
    check(id+' normalized residual',result.converged&&result.residual<=audit.gates.full_residual,{residual:result.residual});
    assert.deepEqual(result.gravity_body,[0,0,0]);
    if(spec.speed_m_s){
      assert.equal(result.request.mode,'mounted');assert.equal(result.request.controller,null);
      assert.deepEqual(result.request.operating_constraints,[]);
      const c=result.request.condition;
      for(const [key,value] of Object.entries({speed:30,alpha:spec.alpha_deg,beta:0,density:1.23,mach:0,gravity_magnitude:0,ground_effect:0,freeze_influences:false,stall:true,stall_factor:40,stall_width:.05,aero_lag:true,wake_core_ratio:.25}))assert.equal(c[key],value,'condition '+key);
      for(const key of ['rates','acceleration','angular_acceleration','position_earth','attitude'])assert.deepEqual(c[key],[0,0,0]);
      assert.deepEqual(c.ground_normal,[0,1,0]);assert.deepEqual(c.controls,{});assert.deepEqual(c.powers,{});
      assert.deepEqual(c.circulation_modes,{'1':0});assert.equal(result.gravity_source,'Earth_magnitude');
    }else{assert.equal(result.request.condition,null);assert.deepEqual(result.request.gravity,[0,0,0]);}
    if(!spec.speed_m_s){assert.equal(old.result.analysis,'mounted_static');assert.equal(result.analysis,'structural_static');}
    entry.physical_comparison=compare(spec.speed_m_s?old.result:{...old.result,analysis:'structural_static'},result,id);
    const tip=result.nodes.reduce((a,b)=>a.t>b.t?a:b),before=old.result.nodes.reduce((a,b)=>a.t>b.t?a:b);
    const actual=nodeObservable(tip),expected=nodeObservable(before);
    entry.observable_comparison=compare(expected,actual,id+' tip');entry.observable=actual;
    if(!spec.speed_m_s)browserBaseline=actual;
    else{
      const nativeBase=nodeObservable(selected[0].result.nodes.at(-1));
      const alpha=spec.alpha_deg*Math.PI/180;
      const recover=(a,b)=>{const d=a.midchord_m.map((v,i)=>v-b.midchord_m[i]);return {root_normal_percent:100*d[2]/.55,wind_normal_percent:100*(-Math.sin(alpha)*d[0]+Math.cos(alpha)*d[2])/.55,twist_deg:a.twist_deg-b.twist_deg};};
      entry.baseline_subtracted=recover(actual,browserBaseline);
      entry.baseline_comparison=compare(recover(expected,nativeBase),entry.baseline_subtracted,id+' baseline');
    }
    const observed=await page.evaluate(()=>window.ae1Observed);
    const requests=observed.requests.filter(m=>m.request?.action==='solve');
    const request=requests.at(-1);assert.equal(request.request.mode,spec.speed_m_s?'mounted':'structural');
    entry.worker_request_id=request.id;
    const progress=observed.progress.filter(p=>p.id===request.id),rendered=observed.rendered.filter(p=>p.progress?.id===request.id);
    entry.progress={events:progress,rendered};
    const loads=progress.filter(p=>p.stage==='static_load');
    check(id+' worker load continuation stages',loads.length>=4&&[.25,.5,.75,1].every(f=>loads.some(p=>p.time/p.steps===f)));
    if(spec.speed_m_s){
      check(id+' structured assembly progress',progress.some(p=>p.stage==='static_tangent'&&p.time===0)&&progress.some(p=>p.stage==='static_tangent'&&p.time===p.steps));
      check(id+' mounted progress rendered',rendered.some(p=>p.message.startsWith('Balancing forces · applied load')&&p.detail.includes('not overall completion')));
      check(id+' no time-integration labels',rendered.every(p=>!p.message.startsWith('Integrating')));
    }
    await page.screenshot({path:path.join(output,id+'-desktop.png'),fullPage:true});
    entry.status='PASS';await save();console.log('PASS',id,entry.seconds.toFixed(2)+'s',JSON.stringify(entry.physical_comparison));
  }
  await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
  check('mobile plots fit viewport',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));
  await page.screenshot({path:path.join(output,'ae1-mobile.png'),fullPage:true});
  const observed=await page.evaluate(()=>window.ae1Observed);
  check('exact planned actual worker solve count',observed.requests.filter(m=>m.request?.action==='solve').length===(priorVacuum?2:3));
  await writeFile(path.join(output,'observed.json'),JSON.stringify(observed,null,2)+'\n');
  check('offline HTTP requests absent',audit.offline_requests.length===0);
  check('page errors absent',audit.page_errors.length===0);
  check('network failures absent',audit.network_failures.length===0);
  for(const [name,digest] of Object.entries(audit.modules))check('unchanged source '+name,sha(await readFile(path.join(root,'openswing',name)))===digest);
  check('native report unchanged',sha(await readFile(reportPath))===audit.native_report.sha256);
  check('test source unchanged',sha(await readFile(fileURLToPath(import.meta.url)))===audit.script.sha256);
  audit.status='PASS_OFFLINE_CHROMIUM_UI_AND_WORKER';
}catch(error){audit.status='FAIL_RETAINED';audit.error={message:error.message,stack:error.stack};process.exitCode=1;console.error(error.stack);
  try{if(page&&!page.isClosed()){await page.screenshot({path:path.join(output,'failure.png'),fullPage:true});await writeFile(path.join(output,'observed.json'),JSON.stringify(await page.evaluate(()=>window.ae1Observed??{}),null,2)+'\n');}}catch{}
}finally{
  clearTimeout(timer);await browser?.close();server?.closeAllConnections();if(server)await new Promise(resolve=>server.close(resolve));
  audit.total_seconds=(performance.now()-started)/1000;audit.counts={passed:audit.checks.filter(c=>c.passed).length,total:audit.checks.length,completed_cases:audit.cases.filter(c=>c.status==='PASS').length,planned_new_worker_solves:priorVacuum?2:3,cumulative_planned_worker_solves:3};
  await save();console.log(JSON.stringify({status:audit.status,counts:audit.counts,total_seconds:audit.total_seconds}));
}
