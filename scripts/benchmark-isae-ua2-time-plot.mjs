// Replay audited scalar samples through the production time-plot component.
// This deliberately measures plotting, not full physical-history storage or
// the application's geometry/loads callback. No solver is started.
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile,writeFile,stat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from '@playwright/test';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const base=path.join(root,'artifacts/isae/ua2-time-ui-20261101');
const variant=process.argv[2];
assert.ok(['before','after'].includes(variant),'Usage: node scripts/benchmark-isae-ua2-time-plot.mjs before|after');
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const fixtureBytes=await readFile(path.join(base,'plot-fixture.json'));
const manifest=JSON.parse(await readFile(path.join(base,'fixture-manifest.json')));
assert.equal(hash(fixtureBytes),manifest.fixture_sha256);
const source=await readFile(variant==='before'?path.join(base,'time-results-before.js'):path.join(root,'web/time-results.js'));
if(variant==='before')assert.equal(hash(source),manifest.baseline_source_sha256);
const errors=[];
const server=createServer(async(req,res)=>{
  try{
    const pathname=new URL(req.url,'http://localhost').pathname;
    if(pathname==='/'){res.setHeader('Content-Type','text/html');res.end('<!doctype html><title>UA-2 time plot measurement</title><style>body{font-family:sans-serif;margin:20px}.plot-grid{stroke:#ddd}.plot-line{fill:none;stroke:#007fb0}.section-point{fill:#007fb0}.time-cursor{stroke:#e25b28}#time-plot{width:770px}svg{width:100%}</style>');return;}
    if(pathname==='/fixture.json'){res.setHeader('Content-Type','application/json');res.end(fixtureBytes);return;}
    if(pathname==='/web/time-results.js'){res.setHeader('Content-Type','text/javascript');res.end(source);return;}
    const file=path.resolve(root,'.'+decodeURIComponent(pathname));
    assert.ok(file.startsWith(path.join(root,'web')+path.sep));
    assert.ok((await stat(file)).isFile());res.setHeader('Content-Type','text/javascript');res.end(await readFile(file));
  }catch{res.writeHead(404);res.end();}
});
let browser;
const started=performance.now();
try{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  browser=await chromium.launch({executablePath:path.join(root,'artifacts/isae/browser-libs-20261101/chromium/chrome-linux/chrome'),headless:true,timeout:45000,
    env:{...process.env,LD_LIBRARY_PATH:[path.join(root,'artifacts/isae/browser-libs-20261101/lib'),process.env.LD_LIBRARY_PATH].filter(Boolean).join(':')},
    args:['--no-sandbox','--disable-dev-shm-usage','--js-flags=--max-old-space-size=384']});
  const page=await browser.newPage({viewport:{width:1000,height:800}});
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  const result=await page.evaluate(async()=>{
    const {createTimeResults,timeSettings,timeTransport,timePane}=await import('/web/time-results.js');
    document.body.innerHTML=timeSettings+timeTransport+timePane;
    document.getElementById('pane-time').hidden=false;
    const $=id=>document.getElementById(id),fixture=await(await fetch('/fixture.json')).json();
    const clone=JSON.stringify(fixture);let selected=null,downloads=[];
    const view=createTimeResults(()=>({revision:0}),s=>{selected=s;},(...args)=>downloads.push(args),()=>{},()=>{},e=>{throw e;});
    const frame=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    const t=performance.now();view.setTrajectory(fixture);$('time-plot').getBoundingClientRect();
    const initial_ms=performance.now()-t;await frame();
    const normalizedSVG=()=>{const svg=$('time-plot').firstElementChild.cloneNode(true);svg.querySelector('.time-cursor')?.remove();return svg.outerHTML;};
    const originalSVG=normalizedSVG(),originalElement=$('time-plot').firstElementChild;
    let plotReplacements=0,lastElement=originalElement;
    const timings=[];
    const indices=[0,17,66,128,640,1280,2111,2640,3300,4000,5000,5280];
    for(const index of indices){
      const start=performance.now();$('time-scrub').value=index;$('time-scrub').dispatchEvent(new Event('input'));
      $('time-plot').getBoundingClientRect();timings.push(performance.now()-start);
      if($('time-plot').firstElementChild!==lastElement)plotReplacements++;
      lastElement=$('time-plot').firstElementChild;
      if(selected!==fixture.snapshots[index]||view.selectedIndex()!==index)throw Error('Wrong selected physical sample');
      if(normalizedSVG()!==originalSVG)throw Error('Scrubbing changed plotted values');
    }
    if($('time-plot').querySelectorAll('circle').length!==5281)throw Error('A plotted sample was lost');
    const endCursor=$('time-plot').querySelector('.time-cursor');
    // Compare actual cursor x to the last retained dot, not a copied formula.
    const lastDot=$('time-plot').querySelector('circle:last-of-type');
    if(Math.abs(Number(endCursor.getAttribute('d').match(/^M([^ ]+)/)[1])-Number(lastDot.getAttribute('cx')))>1e-9)throw Error('Cursor not on last sample');
    $('time-csv').click();
    const csv=downloads.pop()[1];if(csv.trimEnd().split('\n').length!==5282)throw Error('Incomplete CSV');
    const csv_sha256=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(csv))),x=>x.toString(16).padStart(2,'0')).join('');
    // Playback must still select computed states and reach the endpoint.
    view.select(5000);const played=[];let previous=view.selectedIndex();
    $('time-play-speed').value='10';$('time-play').click();
    const playStart=performance.now();
    while($('time-play').textContent!=='Play'){
      await frame();if(view.selectedIndex()!==previous){previous=view.selectedIndex();played.push(previous);}
      if(performance.now()-playStart>3000)throw Error('Playback did not finish');
    }
    if(view.selectedIndex()!==5280||!played.length)throw Error('Playback missed final sample');
    $('time-plot').style.width='350px';await frame();await frame();
    const resizedSVG=$('time-plot').firstElementChild;
    if(resizedSVG===lastElement||resizedSVG.viewBox.baseVal.width!==350)throw Error('Width change did not redraw');
    $('time-quantity').value='residual';$('time-quantity').dispatchEvent(new Event('change'));
    if(!$('time-unit').textContent.includes('Normalized nonlinear residual')||$('time-plot').firstElementChild===resizedSVG)throw Error('Quantity change did not redraw');
    if(JSON.stringify(fixture)!==clone)throw Error('Plotting mutated the trajectory');
    // Independent small fixture checks gaps, coincident left/right states,
    // selectable nodes/sensors and cache invalidation when data is replaced.
    const small={...fixture,accepted_steps:3,forcing:{channels:[],breaks:[1]},snapshots:[
      {time:0,step:0,CL:1,residual:0},
      {time:1,step:1,CL:2,residual:0,forcing_side:'left'},
      {time:1,step:0,CL:4,residual:0,input_transition:true,forcing_side:'right'},
      {time:2,step:1,CL:null,residual:0},
      {time:3,step:1,CL:5,residual:0},
    ].map((s,i)=>({...s,atmosphere:{},nodes:[{index:0,beam:1,t:0,position:[i,0,0],jig_position:[0,0,0]},{index:1,beam:1,t:1,position:[2*i,0,0],jig_position:[0,0,0]}],local_velocity:[[i,0,0],[2*i,0,0]],sensors:[{index:1,beam:1,displacement_body:[i,0,0]},{index:2,beam:1,displacement_body:[3*i,0,0]}]}))};
    view.setTrajectory(small);
    const segments=[...$('time-plot').querySelectorAll('polyline')].map(e=>e.getAttribute('points').split(' ').length);
    if(JSON.stringify(segments)!=='[2,1,1]'||$('time-plot').querySelectorAll('circle').length!==4)throw Error('Plot crossed a missing value or input jump');
    view.select(1);const left=$('time-plot').querySelector('.time-cursor').getAttribute('d');view.select(2);
    if($('time-plot').querySelector('.time-cursor').getAttribute('d')!==left||!$('time-current').textContent.includes('After input change'))throw Error('Coincident states lost their phase');
    $('time-quantity').value='node.displacement.0';$('time-quantity').dispatchEvent(new Event('change'));
    let prev=normalizedSVG();$('time-node').value='1';$('time-node').dispatchEvent(new Event('change'));
    if($('time-node-field').hidden||normalizedSVG()===prev)throw Error('Node change did not redraw');
    $('time-quantity').value='sensor.displacement_body.0';$('time-quantity').dispatchEvent(new Event('change'));
    prev=normalizedSVG();$('time-sensor').value='2';$('time-sensor').dispatchEvent(new Event('change'));
    if($('time-sensor-field').hidden||normalizedSVG()===prev)throw Error('Sensor change did not redraw');
    view.setTrajectory(null);if($('time-plot').children.length||!$('time-transport').hidden)throw Error('Old plot survives clearing');
    view.setTrajectory(fixture);view.select(2640);await frame();
    const sorted=[...timings].sort((a,b)=>a-b);
    return {initial_ms,scrub_ms:timings,scrub_median_ms:(sorted[5]+sorted[6])/2,scrub_max_ms:sorted.at(-1),plot_replacements:plotReplacements,samples:fixture.snapshots.length,csv_sha256,playback_selected_indices:played,checks:{unchanged_curve:true,all_samples:true,correct_cursor:true,CSV_complete:true,playback:true,resize:true,quantity_change:true,node_change:true,sensor_change:true,input_break_and_missing_values:true,duplicate_time_phase:true,clear_and_replace:true,trajectory_unchanged:true},used_JS_heap_bytes:performance.memory?.usedJSHeapSize??null};
  });
  await page.locator('#time-plot').screenshot({path:path.join(base,`${variant}.png`)});
  assert.deepEqual(errors,[]);
  if(variant==='after'){
    assert.equal(result.plot_replacements,0,'Scrubbing must reuse the retained curve');
    const before=JSON.parse(await readFile(path.join(base,'before.json')));
    assert.equal(result.csv_sha256,before.csv_sha256,'History CSV must be byte-identical');
    result.median_scrub_speedup=before.scrub_median_ms/result.scrub_median_ms;
  }
  const report={passed:true,variant,scope:manifest.scope,browser:browser.version(),source_sha256:hash(source),fixture_sha256:hash(fixtureBytes),script_sha256:hash(await readFile(fileURLToPath(import.meta.url))),...result,browser_errors:errors,wall_seconds:(performance.now()-started)/1000,numerical_reexecution:false,full_history_UI_validation:false};
  await writeFile(path.join(base,`${variant}.json`),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({variant,passed:true,samples:result.samples,scrub_median_ms:result.scrub_median_ms,plot_replacements:result.plot_replacements,speedup:result.median_scrub_speedup}));
}finally{
  await browser?.close();await new Promise(resolve=>server.close(resolve));
}
