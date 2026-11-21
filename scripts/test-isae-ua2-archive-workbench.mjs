// Real UI replay of audited states. No unsteady integration is recalculated.
import assert from 'node:assert/strict';
import {readFile,writeFile,appendFile} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createServer} from 'vite';
import {chromium} from '@playwright/test';
import {openTimeHistoryArchive} from '../web/time-history-archive.js';
import {distributionHistory,envelopeCSV,historyCSV,stripColumns} from '../web/distribution-history.js';
import {loadingQuantities,loadingValue} from '../web/loading-data.js';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const base=path.join(root,'artifacts/isae/ua2-archive-ui-20261102');
const attempt=process.argv[2]??'01',prefix=path.join(base,'browser-'+attempt);
const full=!process.argv.includes('--workflow-only');
const inputBase=path.join(root,'artifacts/isae/ua2-incidence-periodic-browser-20261101');
const plan=JSON.parse(await readFile(path.join(inputBase,'plan.json')));
const reference=JSON.parse(await readFile(path.join(base,'reference.json')));
const golden=JSON.parse(await readFile(path.join(root,'artifacts/isae/ua2-history-archive-20261102/archive.json')));
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const raw=[],result=[],inputHashes={};
for(const part of [209,210]){
  const folder=path.join(inputBase,'assessment/production','part'+part);
  const compressed=await readFile(path.join(folder,'trajectory.json.gz'));
  assert.equal(sha(compressed),JSON.parse(await readFile(path.join(folder,'receipt.json'))).output_sha256['trajectory.json.gz']);
  inputHashes[part]=sha(compressed);raw.push(gunzipSync(compressed));result.push(JSON.parse(raw.at(-1)));
}
const request={action:'resume_time',source:plan.full_request.source,numerics:plan.full_request.numerics,
  checkpoint:JSON.parse(await readFile(path.join(inputBase,'assessment/production/part208/checkpoint.json'))),
  time:{duration:result[0].end_time-result[0].start_time,dt:result[0].maximum_step,order:result[0].restart_context.method.order}};
const started=performance.now(),errors=[],log=[];let server,browser,page,timer;
const pins={};
for(const name of ['main.js','time-results.js','time-history-source.js','time-history-selection.js','time-history-index.js','time-history-archive.js','time-history-export.js','time-history-project.js','time-history-continuation.js','time-checkpoint.js','distribution-history.js','project-settings.js'])pins['web/'+name]=sha(await readFile(path.join(root,'web',name)));
pins['scripts/test-isae-ua2-archive-workbench.mjs']=sha(await readFile(fileURLToPath(import.meta.url)));
await writeFile(prefix+'-progress.jsonl','',{flag:'wx'});
async function progress(stage,data={}){const row={stage,elapsed_seconds:(performance.now()-started)/1000,...data};log.push(row);console.log(JSON.stringify(row));await appendFile(prefix+'-progress.jsonl',JSON.stringify(row)+'\n');}
let queue=Promise.resolve();
function inspect(request){
  assert.ok(['inspect','distribution'].includes(request.action));
  const job=queue.then(()=>new Promise((resolve,reject)=>{
    const child=spawn('timeout',['30s',path.join(root,'.venv/bin/python'),'-c','import sys\nfrom openswing.bridge import run_json\nsys.stdout.write(run_json(sys.stdin.read()))'],
      {cwd:root,env:{...process.env,OPENBLAS_NUM_THREADS:'1',OMP_NUM_THREADS:'1',MKL_NUM_THREADS:'1',PYTHONDONTWRITEBYTECODE:'1'}});
    const output=[],error=[];child.stdout.on('data',x=>output.push(x));child.stderr.on('data',x=>error.push(x));
    child.on('error',reject);child.on('exit',code=>code===0?resolve(Buffer.concat(output)):reject(Error(Buffer.concat(error).toString()||'Inspection exit '+code)));
    child.stdin.end(JSON.stringify(request));
  }));queue=job.catch(()=>{});return job;
}
try{
  server=await createServer({root,server:{host:'127.0.0.1',port:0},plugins:[{
    name:'ua2-archive-ui-replay',
    configureServer(server){
      server.middlewares.use('/ua2-first',(_req,res)=>{res.setHeader('Content-Type','application/json');res.end(raw[0]);});
      server.middlewares.use('/ua2-next',(_req,res)=>{res.setHeader('Content-Type','application/json');res.end(raw[1]);});
      server.middlewares.use('/ua2-request',(_req,res)=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify(request));});
      server.middlewares.use('/ua2-inspect',async(req,res)=>{try{const pieces=[];for await(const p of req)pieces.push(p);res.setHeader('Content-Type','application/json');res.end(await inspect(JSON.parse(Buffer.concat(pieces))));}catch(e){res.writeHead(500);res.end(String(e));}});
    },
    transform(code,id){if(id.split('?')[0]!==path.join(root,'web/main.js'))return;
      return code+`\n// Test-only access to the application's normal history consumers.\n
const fixtureInput=document.createElement('input');fixtureInput.type='file';fixtureInput.id='ua2-fixture';fixtureInput.hidden=true;document.body.append(fixtureInput);
globalThis.__ua2={
  ready:()=>!state.busy&&!state.dirty&&!nodeView.hasDraft()&&!distributionView.hasDraft(),
  viewReady:()=>timeView.ready(),
  async full(){
    const began=performance.now(),reader=await openTimeHistoryArchive(fixtureInput.files[0]),data=archiveTrajectory(reader);
    data.condition=data.restart_context.setup.condition;data.model=state.model.name;
    data.start_time=0;data.duration=data.end_time;data.accepted_steps=5280;data.retained_steps=5264;
    this.reader=reader;state.trajectory=data;$('tab-time').click();await timeView.setTrajectory(data);
    return {open_ms:performance.now()-began,statistics:reader.statistics,count:timeHistory(data).count,heap:performance.memory?.usedJSHeapSize};
  },
  async small(){
    const data=await(await fetch('/ua2-first')).json();data.condition=data.restart_context.setup.condition;data.model=state.model.name;
    data.request=await(await fetch('/ua2-request')).json();state.trajectory=shareTimeHistoryMetadata(data);
    $('tab-time').click();await timeView.setTrajectory(state.trajectory);projectView.refresh();
  },
  info:()=>({index:timeView.selectedIndex(),count:timeHistory(state.trajectory).count,archived:archivedTimeHistory(state.trajectory),time:state.result.time,CL:state.result.CL}),
  async hashes(){
    const {encodeHistoryJSON}=await import('/web/time-history-codec.js'),{checkpointRecord}=await import('/web/saved-state-data.js');
    const hash=async x=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',encodeHistoryJSON(x))),n=>n.toString(16).padStart(2,'0')).join('');
    const s=timeHistory(state.trajectory).peek(timeView.selectedIndex());
    return {index:timeView.selectedIndex(),time:s.time,snapshot_sha256:await hash(s),checkpoint_sha256:await hash(checkpointRecord(s.restart,s.restart_context??state.trajectory.restart_context))};
  },
  async series(key){
    const source=timeHistory(state.trajectory),values=await source.series(key,s=>key.split('.').reduce((v,k)=>v?.[k],s));
    const bytes=new Uint8Array(values.length*8),view=new DataView(bytes.buffer);values.forEach((v,i)=>view.setFloat64(i*8,v,true));
    return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),n=>n.toString(16).padStart(2,'0')).join('');
  },
  stats:()=>({...globalThis.__ua2.reader.statistics,heap:performance.memory?.usedJSHeapSize}),
};`;
    },
  }]});await server.listen();
  browser=await chromium.launch({executablePath:path.join(root,'artifacts/isae/browser-libs-20261101/chromium/chrome-linux/chrome'),headless:true,timeout:45000,
    env:{...process.env,LP_NUM_THREADS:'1',LD_LIBRARY_PATH:[path.join(root,'artifacts/isae/browser-libs-20261101/lib'),process.env.LD_LIBRARY_PATH].filter(Boolean).join(':')},
    args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-webgl','--enable-precise-memory-info','--js-flags=--max-old-space-size=192']});
  timer=setTimeout(()=>browser?.close().catch(()=>{}),450000);
  page=await browser.newPage({viewport:{width:1280,height:900}});page.setDefaultTimeout(60000);page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(({source,numerics,endTime,duration})=>{
    window.__ua2Requests=[];window.showSaveFilePicker=undefined;
    window.Worker=class{terminate(){}async postMessage(packet){try{
      const action=packet.request?.action;window.__ua2Requests.push(action);let result;
      if(action==='resume_time'){
        if(packet.request.source!==source||packet.request.checkpoint.state.time!==endTime||Math.abs(packet.request.time.duration-duration)>1e-12||Object.entries(numerics).some(([k,v])=>packet.request.numerics?.[k]!==v))throw Error('Replay request differs from retained continuation');
        result=await(await fetch('/ua2-next')).json();
      }else if(['inspect','distribution'].includes(action)){
        const response=await fetch('/ua2-inspect',{method:'POST',body:JSON.stringify(packet.request)});if(!response.ok)throw Error(await response.text());result=await response.json();
      }else if(action!=='discard_frequency')throw Error('Unexpected numerical solve in retained-output replay: '+action);
      this.onmessage({data:{id:packet.id,result}});
    }catch(error){this.onmessage({data:{id:packet.id,error:String(error)}});}}};
  },{source:plan.full_request.source,numerics:plan.full_request.numerics,endTime:result[0].end_time,duration:result[1].end_time-result[0].end_time});
  await progress('startup');await page.goto(server.resolvedUrls.local[0]);
  await page.waitForFunction(()=>document.getElementById('solve')?.disabled===false);
  await page.locator('#file').setInputFiles({name:'ua2-replay.asw',mimeType:'text/plain',buffer:Buffer.from(plan.full_request.source)});
  await page.waitForFunction(()=>globalThis.__ua2.ready());
  await page.locator('#mode').selectOption('time');await page.waitForFunction(()=>globalThis.__ua2.ready());
  await page.locator('#structural-equations').selectOption('aswing-airflow');await page.waitForFunction(()=>globalThis.__ua2.ready());
  assert.equal(await page.locator('#error').isVisible(),false,await page.locator('#error p').textContent());
  let opened=null,rapid=null,scanned=null;const scrub=[];
  if(full){
  await progress('opening_full_history');
  await page.locator('#ua2-fixture').setInputFiles(path.join(base,'history.oswh'));
  opened=await page.evaluate(()=>globalThis.__ua2.full());
  assert.equal(opened.count,5281);assert.equal(opened.statistics.recordsRead,2);
  assert.equal(await page.locator('#time-plot circle').count(),5281);
  assert.equal(await page.evaluate(()=>globalThis.__ua2.series('CL')),reference.float64_little_endian_sha256.CL);
  assert.deepEqual(await page.locator('#time-plot circle title').allTextContents(),reference.rows.map(row=>`t=${row[0].toPrecision(7)}; value=${row[1].toPrecision(7)}`));
  await progress('indexed_plot_exact',opened);
  for(const expected of golden.browser_samples){
    const began=performance.now();await page.locator('#time-scrub').fill(String(expected.index));await page.evaluate(()=>globalThis.__ua2.viewReady());
    assert.deepEqual(await page.evaluate(()=>globalThis.__ua2.hashes()),expected);scrub.push(performance.now()-began);
  }
  rapid=await page.evaluate(async()=>{
    const before=globalThis.__ua2.stats().recordsRead,input=document.getElementById('time-scrub');
    for(const i of [64,512,1600,2400,4400,5279]){input.value=i;input.dispatchEvent(new Event('input'));}
    await globalThis.__ua2.viewReady();return {reads:globalThis.__ua2.stats().recordsRead-before,...globalThis.__ua2.info()};
  });assert.equal(rapid.index,5279);assert.ok(rapid.reads<=2);
  await page.locator('#time-play-speed').selectOption('10');await page.locator('#time-play').click();
  await page.waitForFunction(()=>globalThis.__ua2.info().index===5280&&document.getElementById('time-play').textContent==='Play');
  await progress('selection_and_playback_exact',{samples:scrub.length,scrub_ms:scrub,rapid});
  await page.locator('#time-quantity').selectOption('frame.position_earth.2');
  const scanBegan=performance.now();await page.waitForFunction(()=>document.querySelectorAll('#time-plot circle').length===5281,null,{timeout:180000});
  assert.equal(await page.evaluate(()=>globalThis.__ua2.series('frame.position_earth.2')),reference.float64_little_endian_sha256['frame.position_earth.2']);
  assert.deepEqual(await page.locator('#time-plot circle title').allTextContents(),reference.rows.map(row=>`t=${row[0].toPrecision(7)}; value=${row[2].toPrecision(7)}`));
  scanned={seconds:(performance.now()-scanBegan)/1000,...await page.evaluate(()=>globalThis.__ua2.stats())};
  await progress('full_physical_scan_exact',scanned);
  await page.locator('#time-quantity').selectOption('CL');await page.evaluate(()=>globalThis.__ua2.viewReady());
  await page.locator('#time-plot').screenshot({path:prefix+'-desktop.png'});
  await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.locator('#time-plot').screenshot({path:prefix+'-mobile.png'});
  await page.setViewportSize({width:1280,height:900});
  }
  await page.evaluate(()=>globalThis.__ua2.small());await progress('small_file_workflow');
  async function saveArchive(label){
    await page.waitForFunction(()=>globalThis.__ua2.ready());
    const event=page.waitForEvent('download');await page.locator('#time-archive-save').click();const download=await event;
    const file=prefix+'-'+label+'.oswh';await download.saveAs(file);const bytes=await readFile(file);
    return {file,bytes:bytes.length,reader:await openTimeHistoryArchive(new Blob([bytes]))};
  }
  const saved=await saveArchive('saved');assert.equal(saved.reader.snapshotCount,17);
  for(let i=0;i<17;i++)assert.deepEqual(await saved.reader.readSnapshot(i),result[0].snapshots[i]);
  assert.equal(saved.reader.metadata().openswing_workbench.format,'openswing-workbench-history');
  await page.locator('#time-archive-file').setInputFiles(saved.file);
  await page.waitForFunction(()=>document.getElementById('runtime-status').textContent==='Complete history opened · 17 snapshots');
  await page.waitForFunction(()=>globalThis.__ua2.ready());
  assert.equal((await page.evaluate(()=>globalThis.__ua2.info())).archived,true);
  await page.locator('#time-scrub').fill('16');await page.evaluate(()=>globalThis.__ua2.viewReady());
  await page.locator('#time-checkpoint-settings').evaluate(e=>e.open=true);await page.locator('#time-checkpoint-use').click();
  await page.locator('#time-continue-duration').fill(String(result[1].end_time-result[0].end_time));
  await page.locator('#time-continue').click();
  await page.waitForFunction(()=>document.getElementById('runtime-status').textContent==='Time continuation converged');
  assert.deepEqual(await page.evaluate(()=>({count:globalThis.__ua2.info().count,archived:globalThis.__ua2.info().archived})),{count:33,archived:true});
  await page.locator('#time-scrub').fill('32');await page.evaluate(()=>globalThis.__ua2.viewReady());
  const continued=await saveArchive('continued');
  const expected=[...result[0].snapshots.map(s=>({...s,restart_context:s.restart_context??result[0].restart_context})),...result[1].snapshots.slice(1)];
  assert.equal(continued.reader.snapshotCount,33);
  for(let i=0;i<33;i++)assert.deepEqual(await continued.reader.readSnapshot(i),expected[i]);
  await progress('file_open_and_continuation_exact',{saved_bytes:saved.bytes,continued_bytes:continued.bytes,complete_states:33});
  await page.locator('#tab-loading').click();await page.locator('#plot-quantity').selectOption('cl');
  await page.locator('#plot-scope').selectOption('overlay');
  await page.waitForFunction(()=>document.querySelectorAll('#plot .distribution-trace').length===33);
  await page.locator('#plot-scope').selectOption('envelope');
  await page.waitForFunction(()=>!!document.querySelector('#plot circle.distribution-min'));
  const beam=Number(await page.locator('#plot-beam').inputValue());
  const expectedEnvelope=envelopeCSV(distributionHistory(expected,'strips',beam,row=>loadingValue(row,'cl')),beam,'cl',loadingQuantities.cl.unit);
  for(const [id,expectedCSV]of [['plot-envelope-csv',expectedEnvelope],['plot-history-csv',historyCSV(expected,'strips',stripColumns)]]){
    const event=page.waitForEvent('download');await page.locator('#'+id).click();const download=await event;
    assert.equal(await readFile(await download.path(),'utf8'),expectedCSV);
  }
  await page.locator('#plot-scope').selectOption('current');await page.locator('#tab-time').click();
  await progress('distribution_overlay_envelope_and_csv_exact',{snapshots:33});
  await page.waitForFunction(()=>globalThis.__ua2.ready());
  await page.locator('#project-settings').evaluate(e=>e.open=true);await page.locator('#project-solution-name').fill('UA-2 archive continuation');
  await page.locator('#project-save-solution').click();
  await page.waitForFunction(()=>document.getElementById('project-status').textContent.startsWith('Computed solution saved.')||!document.getElementById('error').hidden);
  assert.equal(await page.locator('#error').isVisible(),false,await page.locator('#error p').textContent());
  await page.locator('#time-scrub').fill('7');await page.evaluate(()=>globalThis.__ua2.viewReady());
  await page.locator('#project-load-solution').click();
  await page.waitForFunction(()=>document.getElementById('project-status').textContent.startsWith('Opened UA-2 archive continuation'));
  assert.equal((await page.evaluate(()=>globalThis.__ua2.info())).index,32);
  await page.waitForFunction(()=>globalThis.__ua2.ready());
  await page.locator('#project-undo-load').click();
  await page.waitForFunction(()=>document.getElementById('project-status').textContent==='Previous workbench inputs restored.');
  const undone=await page.evaluate(()=>globalThis.__ua2.info());assert.equal(undone.index,7);assert.equal(undone.archived,true);assert.equal(undone.count,33);
  await progress('small_project_and_undo_exact',undone);
  await page.waitForFunction(()=>globalThis.__ua2.ready());
  const truncated=prefix+'-truncated.oswh';await writeFile(truncated,(await readFile(saved.file)).subarray(0,100));
  await page.locator('#time-archive-file').setInputFiles(truncated);
  await page.waitForFunction(()=>!document.getElementById('error').hidden);
  assert.match(await page.locator('#error p').textContent(),/Invalid or incomplete time-history archive/);
  assert.deepEqual(await page.evaluate(()=>globalThis.__ua2.info()),undone);
  await progress('invalid_archive_preserves_workspace');
  assert.deepEqual(errors,[]);const actions=await page.evaluate(()=>window.__ua2Requests);
  assert.equal(actions.filter(x=>x==='resume_time').length,1);
  const renderer=await page.locator('#viewport canvas').getAttribute('data-renderer');assert.equal(renderer,'canvas2d');
  for(const [p,digest]of Object.entries(pins))assert.equal(sha(await readFile(path.join(root,p))),digest);
  const report={passed:true,full_history:full,scope:'Actual development workbench with software renderer. Full history only when full_history=true; small archive save/open, 17+16-state recorded continuation, JSON project and Undo load. Test-only root display metadata is assembled from retained records; worker adapter replays the recorded continuation and uses serial CPython inspection. No numerical reexecution or current WASM startup claim.',opened,scrub_ms:scrub,rapid,scanned,saved_bytes:saved.bytes,continued_bytes:continued.bytes,complete_exported_states:33,undo:undone,source_sha256:pins,input_sha256:inputHashes,browser:browser.version(),renderer,worker_actions:actions,errors,numerical_reexecution:false,native_ASWING_comparison:false,large_JSON_project_support:false,incremental_durable_continuation:false,wall_seconds:(performance.now()-started)/1000};
  await writeFile(prefix+'.json',JSON.stringify(report,null,2)+'\n',{flag:'wx'});await progress('passed');
}catch(error){
  await writeFile(prefix+'-failure.json',JSON.stringify({passed:false,error:String(error),stack:error.stack,errors,source_sha256:pins,log,runtime:await page?.locator('#runtime-status').textContent().catch(()=>null),message:await page?.locator('#error p').textContent().catch(()=>null)},null,2)+'\n',{flag:'wx'});throw error;
}finally{clearTimeout(timer);await browser?.close();await server?.close();await queue;}
