// Exercise the real app renderers with one retained, unmodified browser segment.
// A Vite-only test hook hands it to the normal time renderer; no trajectory is
// recomputed. This bounds memory while checking full-app callback integration.
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {createServer} from 'vite';
import {chromium} from '@playwright/test';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const base=path.join(root,'artifacts/isae/ua2-time-ui-20261101');
const input='artifacts/isae/ua2-incidence-periodic-browser-20261101/production/part209/trajectory.json.gz';
const compressed=await readFile(path.join(root,input)),raw=gunzipSync(compressed),trajectory=JSON.parse(raw);
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const receipt=JSON.parse(await readFile(path.join(root,path.dirname(input),'receipt.json')));
assert.equal(hash(compressed),receipt.output_sha256['trajectory.json.gz']);
assert.equal(trajectory.snapshots.length,17);
const plan=JSON.parse(await readFile(path.join(root,'artifacts/isae/ua2-incidence-periodic-browser-20261101/plan.json')));
let browser,server,timer;const errors=[];const started=performance.now();
try{
  server=await createServer({root,server:{host:'127.0.0.1',port:0},plugins:[{
    name:'ua2-retained-result-replay',
    configureServer(server){server.middlewares.use('/ua2-retained-result.json',(_req,res)=>{res.setHeader('Content-Type','application/json');res.end(raw);});},
    transform(code,id){
      if(id.split('?')[0]!==path.join(root,'web/main.js'))return;
      return code+`\n// Test-only retained-result replay; production modules are unchanged.\n
globalThis.__ua2Replay=async()=>{
  const began=performance.now(),result=await(await fetch('/ua2-retained-result.json')).json();
  const loaded=performance.now();
  state.trajectory=result;timeView.setTrajectory(result);$('tab-time').click();
  return {load_ms:loaded-began,render_ms:performance.now()-loaded,snapshots:result.snapshots.length};
};
globalThis.__ua2Selected=()=>({index:timeView.selectedIndex(),time:state.result.time,CL:state.result.CL});
`;
    },
  }]});await server.listen();
  browser=await chromium.launch({executablePath:path.join(root,'artifacts/isae/browser-libs-20261101/chromium/chrome-linux/chrome'),headless:true,timeout:45000,
    env:{...process.env,LP_NUM_THREADS:'1',LD_LIBRARY_PATH:[path.join(root,'artifacts/isae/browser-libs-20261101/lib'),process.env.LD_LIBRARY_PATH].filter(Boolean).join(':')},
    args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-webgl']});
  timer=setTimeout(()=>browser?.close().catch(()=>{}),80000);
  const page=await browser.newPage({viewport:{width:1280,height:900}});page.setDefaultTimeout(60000);
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
    window.__ua2Requests=[];const send=Worker.prototype.postMessage;
    Worker.prototype.postMessage=function(packet,...rest){
      const action=packet.request?.action;if(action)window.__ua2Requests.push(action);
      if(action&&!['inspect','distribution','discard_frequency'].includes(action))throw Error('Replay may not start a numerical solve');
      return send.call(this,packet,...rest);
    };
  });
  console.log('Loading workbench with the application software renderer.');
  await page.goto(server.resolvedUrls.local[0]);
  await page.waitForFunction(()=>document.getElementById('solve')?.disabled===false);
  console.log('Workbench ready; inspecting the retained UA-2 model.');
  await page.locator('#file').setInputFiles({name:'ua2-replay.asw',mimeType:'text/plain',buffer:Buffer.from(plan.full_request.source)});
  await page.waitForFunction(()=>document.getElementById('solve')?.disabled===false);
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
  const download=page.waitForEvent('download');await page.locator('#export-json').click();
  const file=await download;const exported=await readFile(await file.path());
  assert.deepEqual(JSON.parse(exported),trajectory,'Full app export must preserve every retained value');
  assert.equal(await page.locator('#error').isVisible(),false);
  await page.locator('#time-plot').screenshot({path:path.join(base,'app-segment-desktop.png')});
  await page.setViewportSize({width:390,height:844});
  // Export focused the Output panel; mobile correctly preserves that focus.
  await page.locator('#workspace-tab-plots').click();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.locator('#time-plot').screenshot({path:path.join(base,'app-segment-mobile.png')});
  const actions=await page.evaluate(()=>window.__ua2Requests);
  assert.ok(actions.length&&actions.every(action=>['inspect','distribution','discard_frequency'].includes(action)));
  assert.deepEqual(errors,[]);
  const renderer=await page.locator('#viewport canvas').getAttribute('data-renderer');assert.equal(renderer,'canvas2d');
  const result={passed:true,scope:'Actual development app with software renderer, one complete 17-snapshot segment, all physical fields preserved. This does not establish full 5281-snapshot memory, archive saving or UI performance.',input,input_sha256:hash(compressed),script_sha256:hash(await readFile(fileURLToPath(import.meta.url))),time_results_sha256:hash(await readFile(path.join(root,'web/time-results.js'))),browser:browser.version(),renderer,...measurement,scrub_ms:timings,export_bytes:exported.length,export_all_values_equal:true,mobile_width:390,no_horizontal_overflow:true,worker_actions:actions,browser_errors:errors,wall_seconds:(performance.now()-started)/1000,numerical_reexecution:false,full_history_UI_validation:false};
  await writeFile(path.join(base,'app-segment.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({passed:true,snapshots:measurement.snapshots,load_ms:measurement.load_ms,render_ms:measurement.render_ms,scrub_ms:timings,export_all_values_equal:true}));
}finally{clearTimeout(timer);await browser?.close();await server?.close();}
