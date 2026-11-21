// Exercise metadata sharing through the real continuation handler with two retained segments.
// A Vite-only hook supplies the first segment and a worker replay supplies the next; no trajectory is
// recomputed. This bounds memory while checking full-app callback integration.
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {createServer} from 'vite';
import {chromium} from '@playwright/test';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const base=path.join(root,'artifacts/isae/ua2-history-storage-20261102');
const input='artifacts/isae/ua2-incidence-periodic-browser-20261101/production/part209/trajectory.json.gz';
const compressed=await readFile(path.join(root,input)),raw=gunzipSync(compressed),trajectory=JSON.parse(raw);
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const receipt=JSON.parse(await readFile(path.join(root,path.dirname(input),'receipt.json')));
assert.equal(hash(compressed),receipt.output_sha256['trajectory.json.gz']);
assert.equal(trajectory.snapshots.length,17);
const nextInput='artifacts/isae/ua2-incidence-periodic-browser-20261101/production/part210/trajectory.json.gz';
const nextCompressed=await readFile(path.join(root,nextInput)),nextRaw=gunzipSync(nextCompressed),nextTrajectory=JSON.parse(nextRaw);
const nextReceipt=JSON.parse(await readFile(path.join(root,path.dirname(nextInput),'receipt.json')));
assert.equal(hash(nextCompressed),nextReceipt.output_sha256['trajectory.json.gz']);
const plan=JSON.parse(await readFile(path.join(root,'artifacts/isae/ua2-incidence-periodic-browser-20261101/plan.json')));
let browser,server,timer;const errors=[];const started=performance.now();
// Only inspect/distribution are permitted. These small, serial parsing jobs
// avoid loading a second numerical runtime merely to replay saved UI results.
let inspectionQueue=Promise.resolve();
function inspect(request){
  assert.ok(['inspect','distribution'].includes(request.action));
  const job=inspectionQueue.then(()=>new Promise((resolve,reject)=>{
    const child=spawn('timeout',['30s',path.join(root,'.venv/bin/python'),'-c',
      'import sys\nfrom openswing.bridge import run_json\nsys.stdout.write(run_json(sys.stdin.read()))'],
      {cwd:root,env:{...process.env,OPENBLAS_NUM_THREADS:'1',OMP_NUM_THREADS:'1',MKL_NUM_THREADS:'1',PYTHONDONTWRITEBYTECODE:'1'}});
    const output=[],error=[];
    child.stdout.on('data',data=>output.push(data));child.stderr.on('data',data=>error.push(data));
    child.on('error',reject);child.on('exit',code=>code===0?resolve(Buffer.concat(output)):reject(Error(Buffer.concat(error).toString()||`Inspection exit ${code}`)));
    child.stdin.end(JSON.stringify(request));
  }));
  inspectionQueue=job.catch(()=>{});return job;
}
try{
  server=await createServer({root,server:{host:'127.0.0.1',port:0},plugins:[{
    name:'ua2-retained-result-replay',
    configureServer(server){
      server.middlewares.use('/ua2-retained-result.json',(_req,res)=>{res.setHeader('Content-Type','application/json');res.end(raw);});
      server.middlewares.use('/ua2-retained-next.json',(_req,res)=>{res.setHeader('Content-Type','application/json');res.end(nextRaw);});
      server.middlewares.use('/ua2-inspect',async(req,res)=>{try{
        const blocks=[];for await(const block of req)blocks.push(block);
        const result=await inspect(JSON.parse(Buffer.concat(blocks)));res.setHeader('Content-Type','application/json');res.end(result);
      }catch(error){res.writeHead(500);res.end(String(error));}});
    },
    transform(code,id){
      if(id.split('?')[0]!==path.join(root,'web/main.js'))return;
      return code+`\n// Test-only retained-result replay; production modules are unchanged.\n
globalThis.__ua2Replay=async()=>{
  const began=performance.now(),result=await(await fetch('/ua2-retained-result.json')).json();
  const loaded=performance.now();
  state.trajectory=shareTimeHistoryMetadata(result);globalThis.__ua2FirstContext=state.trajectory.restart_context;timeView.setTrajectory(state.trajectory);$('tab-time').click();
  return {load_ms:loaded-began,render_ms:performance.now()-loaded,snapshots:result.snapshots.length};
};
globalThis.__ua2ReadyForPolicy=()=>!state.busy&&!state.dirty&&!nodeView.hasDraft()&&!distributionView.hasDraft();
globalThis.__ua2Selected=()=>({index:timeView.selectedIndex(),time:state.result.time,CL:state.result.CL});
globalThis.__ua2Sharing=()=>({root_context_reused:state.trajectory.restart_context===globalThis.__ua2FirstContext,snapshots:state.trajectory.snapshots.length,selected:timeView.selectedIndex()});
`;
    },
  }]});await server.listen();
  browser=await chromium.launch({executablePath:path.join(root,'artifacts/isae/browser-libs-20261101/chromium/chrome-linux/chrome'),headless:true,timeout:45000,
    env:{...process.env,LP_NUM_THREADS:'1',LD_LIBRARY_PATH:[path.join(root,'artifacts/isae/browser-libs-20261101/lib'),process.env.LD_LIBRARY_PATH].filter(Boolean).join(':')},
    args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-webgl']});
  timer=setTimeout(()=>browser?.close().catch(()=>{}),160000);
  const page=await browser.newPage({viewport:{width:1280,height:900}});page.setDefaultTimeout(60000);
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(({numerics,source,endTime})=>{
    window.__ua2Requests=[];
    window.Worker=class {
      terminate(){}
      async postMessage(packet){try{
      const action=packet.request?.action;if(action)window.__ua2Requests.push(action);
      let result;
      if(action==='resume_time'){
        if(packet.request.source!==source||packet.request.checkpoint.state.time!==endTime||Object.entries(numerics).some(([key,value])=>packet.request.numerics?.[key]!==value))throw Error('Replay request does not match retained model and checkpoint');
        result=await(await fetch('/ua2-retained-next.json')).json();
      }else if(['inspect','distribution'].includes(action)){
        const response=await fetch('/ua2-inspect',{method:'POST',body:JSON.stringify(packet.request)});
        if(!response.ok)throw Error(await response.text());result=await response.json();
      }else if(action!=='discard_frequency')throw Error('Replay may not start a numerical solve');
      this.onmessage({data:{id:packet.id,result}});
    }catch(error){this.onmessage({data:{id:packet.id,error:String(error)}});}
    }
    };
  },{numerics:plan.full_request.numerics,source:plan.full_request.source,endTime:trajectory.end_time});
  console.log('Loading workbench with the application software renderer.');
  await page.goto(server.resolvedUrls.local[0]);
  await page.waitForFunction(()=>document.getElementById('solve')?.disabled===false);
  console.log('Workbench ready; inspecting the retained UA-2 model.');
  await page.locator('#file').setInputFiles({name:'ua2-replay.asw',mimeType:'text/plain',buffer:Buffer.from(plan.full_request.source)});
  await page.waitForFunction(()=>document.getElementById('solve')?.disabled===false);
  await page.locator('#mode').selectOption('time');
  await page.waitForFunction(()=>globalThis.__ua2ReadyForPolicy());
  await page.locator('#structural-equations').selectOption('aswing-airflow');
  await page.waitForFunction(()=>document.getElementById('solve')?.disabled===false);
  assert.equal(await page.locator('#error').isVisible(),false,await page.locator('#error p').textContent());
  console.log('Replaying the retained segment without integration.');
  const measurement=await page.evaluate(()=>globalThis.__ua2Replay());
  await page.waitForFunction(()=>document.querySelectorAll('#time-plot circle').length===17);
  const timings=[];
  for(const index of [0,4,8,12,16]){
    const value=await page.evaluate(index=>{
      const input=document.getElementById('time-scrub'),start=performance.now();
      input.value=index;input.dispatchEvent(new Event('input',{bubbles:true}));document.getElementById('time-plot').getBoundingClientRect();
      return {milliseconds:performance.now()-start,...globalThis.__ua2Selected()};
    },index);
    assert.equal(value.index,index);assert.equal(value.time,trajectory.snapshots[index].time);assert.equal(value.CL,trajectory.snapshots[index].CL);timings.push(value.milliseconds);
  }
  await page.locator('#time-view').selectOption('earth');
  await page.locator('#time-quantity').selectOption('node.displacement.2');
  assert.equal(await page.locator('#time-plot circle').count(),17);
  await page.locator('#time-quantity').selectOption('CL');
  console.log('Initial replay and scrub checks pass; requesting recorded continuation.');
  await page.locator('#time-checkpoint-settings').evaluate(e=>e.open=true);
  await page.locator('#time-checkpoint-use').click();
  await page.locator('#time-continue-duration').fill(String(nextTrajectory.end_time-trajectory.end_time));
  await page.locator('#time-continue').click();
  await page.waitForFunction(()=>document.getElementById('runtime-status').textContent==='Time continuation converged');
  console.log('Continuation rendered; verifying all exported values.');
  const sharing=await page.evaluate(()=>globalThis.__ua2Sharing());
  assert.equal(sharing.snapshots,33);assert.equal(sharing.root_context_reused,true);
  await page.locator('#time-scrub').fill('32');
  const last=await page.evaluate(()=>globalThis.__ua2Selected());
  assert.equal(last.time,nextTrajectory.snapshots.at(-1).time);assert.equal(last.CL,nextTrajectory.snapshots.at(-1).CL);
  const download=page.waitForEvent('download');await page.locator('#export-json').click();
  const file=await download;const exported=await readFile(await file.path());
  const exportedResult=JSON.parse(exported);
  const expectedSnapshots=[...trajectory.snapshots.map(s=>({...s,restart_context:s.restart_context??trajectory.restart_context})),...nextTrajectory.snapshots.slice(1)];
  assert.deepEqual(exportedResult.snapshots,expectedSnapshots,'Every retained and continued snapshot field must survive export');
  for(const [key,value]of Object.entries(nextTrajectory))if(!['snapshots','accepted_steps','start_time','duration'].includes(key))assert.deepEqual(exportedResult[key],value,'Retained result field '+key);
  assert.equal(exportedResult.accepted_steps,32);assert.equal(exportedResult.retained_steps,16);
  assert.equal(await page.locator('#error').isVisible(),false,await page.locator('#error p').textContent());
  console.log('All exported values match; capturing desktop/mobile plots.');
  await page.locator('#time-plot').screenshot({path:path.join(base,'app-continuation-desktop.png')});
  await page.setViewportSize({width:390,height:844});
  // Export focused the Output panel; mobile correctly preserves that focus.
  await page.locator('#workspace-tab-plots').click();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.locator('#time-plot').screenshot({path:path.join(base,'app-continuation-mobile.png')});
  const actions=await page.evaluate(()=>window.__ua2Requests);
  assert.ok(actions.length&&actions.every(action=>['inspect','distribution','discard_frequency','resume_time'].includes(action)));
  assert.equal(actions.filter(action=>action==='resume_time').length,1);
  assert.deepEqual(errors,[]);
  const renderer=await page.locator('#viewport canvas').getAttribute('data-renderer');assert.equal(renderer,'canvas2d');
  const result={passed:true,scope:'Actual development app with software renderer, two recorded segments through the real continuation handler, 33 complete snapshots. A test-only worker adapter uses serial CPython model-inspection replies and recorded browser continuation output. No integration is recalculated. This does not establish current WASM startup or full 5281-snapshot memory, archive saving or UI performance.',input,input_sha256:hash(compressed),next_input:nextInput,next_input_sha256:hash(nextCompressed),sharing,script_sha256:hash(await readFile(fileURLToPath(import.meta.url))),time_results_sha256:hash(await readFile(path.join(root,'web/time-results.js'))),metadata_source_sha256:hash(await readFile(path.join(root,'web/time-history-metadata.js'))),main_source_sha256:hash(await readFile(path.join(root,'web/main.js'))),browser:browser.version(),renderer,...measurement,scrub_ms:timings,export_bytes:exported.length,export_all_snapshot_and_inherited_fields_equal:true,mobile_width:390,no_horizontal_overflow:true,worker_actions:actions,browser_errors:errors,wall_seconds:(performance.now()-started)/1000,numerical_reexecution:false,full_history_UI_validation:false};
  await writeFile(path.join(base,'app-continuation.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({passed:true,snapshots:sharing.snapshots,load_ms:measurement.load_ms,render_ms:measurement.render_ms,scrub_ms:timings,export_all_snapshot_and_inherited_fields_equal:true}));
}finally{clearTimeout(timer);await browser?.close();await server?.close();}
