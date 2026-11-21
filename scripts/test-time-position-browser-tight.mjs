// Paired built-worker diagnostics for nodal displacement differentiation.
// The original failed periodic study remains failed; these are short replays.
import assert from 'node:assert/strict';
import {createReadStream} from 'node:fs';
import {readFile,writeFile,mkdir,stat,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {gzipSync,gunzipSync} from 'node:zlib';
import path from 'node:path';
import {chromium} from '@playwright/test';
import {checkpointRecord} from '../web/saved-state-data.js';
import {equalPhysical} from './isae_time_browser_compare.mjs';

const root=process.cwd(),study=path.join(root,'artifacts/isae/ua-time-position-20261102');
const base=path.join(study,'browser-tight');
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const read=async name=>JSON.parse(await readFile(name,'utf8'));
const write=(name,value)=>writeFile(name,JSON.stringify(value,null,2)+'\n',{flag:'wx'});
const frozen=await read(path.join(study,'plan.json'));
const original=await read(path.join(study,'requested/request.json'));
const modules=await read(path.join(root,'dist/kernel/manifest.json'));
const pins={};
for(const name of modules){
  const bytes=await readFile(path.join(root,'openswing',name));
  assert.equal(hash(bytes),frozen.source_sha256['openswing/'+name]);
  assert.equal(hash(await readFile(path.join(root,'dist/kernel',name))),hash(bytes));
  pins[name]=hash(bytes);
}
const workers=(await readdir('dist/assets')).filter(name=>/^worker-.*\.js$/.test(name));
assert.equal(workers.length,1);
const plan={module_sha256:pins,worker_url:'/assets/'+workers[0],
  worker_sha256:hash(await readFile('dist/assets/'+workers[0])),
  request_timeout_seconds:45,steps_per_request:8,requests:1,physical_difference_limit:2e-8,
  paired_plan_sha256:hash(await readFile(path.join(study,'plan.json'))),
  driver_sha256:hash(await readFile('scripts/test-time-position-browser-tight.mjs')),
  scope:'Independent tighter-tolerance replay from the same retained checkpoint; original-tolerance browser failure is preserved. Not a new full case.'};
await mkdir(base);await write(path.join(base,'plan.json'),plan);
let browser,server;
try{
  const dist=path.join(root,'dist');
  const types={'.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.html':'text/html'};
  server=createServer(async(req,res)=>{
    try{
      const file=path.resolve(dist,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));
      if(!file.startsWith(dist+path.sep)||(await stat(file)).isDirectory()){res.writeHead(404);res.end();return;}
      res.writeHead(200,{'Content-Type':types[path.extname(file)]??'application/octet-stream'});
      createReadStream(file).on('error',()=>res.destroy()).pipe(res);
    }catch{res.writeHead(404);res.end();}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const executable=path.join(root,'artifacts/isae/browser-libs-20261101/chromium/chrome-linux/chrome');
  const libraries=path.join(root,'artifacts/isae/browser-libs-20261101/lib');
  browser=await chromium.launch({executablePath:executable,headless:true,timeout:45000,
    env:{...process.env,LD_LIBRARY_PATH:[libraries,process.env.LD_LIBRARY_PATH].filter(Boolean).join(':')},
    args:['--no-sandbox','--disable-dev-shm-usage']});
  const page=await browser.newPage();
  await page.goto(`http://127.0.0.1:${server.address().port}/kernel/manifest.json`);
  await page.evaluate(({url,timeout})=>{
    const worker=new Worker(url,{type:'module'});let pending=null,broken=false;
    const statuses=[];
    worker.onerror=event=>{broken=true;if(pending){clearTimeout(pending.timer);pending.reject(Error(event.message));pending=null;}worker.terminate();};
    worker.onmessage=({data})=>{
      if(data.type==='status')statuses.push(data.message);
      if(!pending||data.id!==pending.id)return;
      if(data.type==='progress'){pending.lastProgress=data;return;}
      if(data.error||data.result){
        const current=pending;pending=null;clearTimeout(current.timer);
        if(data.error){broken=true;worker.terminate();current.reject(Error(data.error));}
        else current.resolve({result:data.result,statuses:[...statuses],lastProgress:current.lastProgress});
      }
    };
    globalThis.requestKernel=(id,request)=>new Promise((resolve,reject)=>{
      if(pending||broken){reject(Error('Worker unavailable'));return;}
      const timer=setTimeout(()=>{const progress=pending?.lastProgress;broken=true;pending=null;worker.terminate();reject(Error('Worker deadline: '+JSON.stringify({statuses,progress})));},timeout);
      pending={id,resolve,reject,timer};worker.postMessage({id,request});
    });
  },{url:plan.worker_url,timeout:45000});
  console.log(JSON.stringify({starting:'runtime-inspection'}));
  const warmup=await page.evaluate(request=>globalThis.requestKernel(0,request),
    {action:'inspect',source:original.source,panels:original.panels,numerics:original.numerics});
  assert.deepEqual(warmup.result.software_provenance.modules,pins);
  await write(path.join(base,'warmup.json'),warmup);
  const reports=[];
  const angle=9*Math.PI/180,heave=[-Math.sin(angle),0,Math.cos(angle)],qs=.5*1.225*100*200000;
  const dot=(a,b)=>a.reduce((sum,v,i)=>sum+v*b[i],0);
  const fields=s=>({CL:dot(s.force,heave)/qs,force_coefficient:s.force.map(v=>v/qs),
    CDp_fixed:s.CDp*(s.operating_values.speed/10)**2,section_cl:s.strips.map(s=>s.cl),
    circulation:s.strips.map(s=>s.circulation),circulation_rate:s.circulation_rate,
    velocity:dot(s.frame.velocity_origin_body,heave),position:dot(s.frame.position_earth,heave),
    acceleration:dot(s.frame.acceleration_reference_body,heave)});
  for(let part=1;part<2;part++){
    const entry=frozen.cases[part],folder=path.join(study,entry.name);
    const request=await read(path.join(folder,'request.json'));
    assert.equal(hash(await readFile(path.join(folder,'request.json'))),entry.request_sha256);
    const receipt=await read(path.join(folder,'completed.json'));
    const targetPath=path.join(folder,'trajectory.json.gz'),targetBytes=await readFile(targetPath);
    assert.equal(hash(targetBytes),receipt.output_sha256[path.relative(root,targetPath)]);
    const target=JSON.parse(gunzipSync(targetBytes)).snapshots;
    assert.equal(target.length,9);
    console.log(JSON.stringify({starting:entry.name}));
    const start=performance.now();
    const response=await page.evaluate(({id,request})=>globalThis.requestKernel(id,request),{id:part+1,request});
    const seconds=(performance.now()-start)/1000,raw=response.result;
    await writeFile(path.join(base,entry.name+'.json.gz'),gzipSync(Buffer.from(JSON.stringify(raw)),{level:1}),{flag:'wx'});
    assert.equal(raw.converged,true);assert.equal(raw.accepted_steps,8);assert.equal(raw.rejected_steps,0);
    assert.equal(raw.snapshots.length,9);assert.deepEqual(raw.software_provenance.modules,pins);
    let maxDifference=0,maxResidual=0;
    const rows=[];
    for(let i=0;i<9;i++){
      const actual=raw.snapshots[i],expected=target[i];
      assert.ok(Math.abs(actual.time-expected.time)<1e-12);assert.equal(actual.strips.length,4);
      if(i){assert.equal(actual.order,2);assert.ok(actual.residual<=entry.tolerance);maxResidual=Math.max(maxResidual,actual.residual);}
      const a=fields(actual),b=fields(expected),differences={};
      for(const key of Object.keys(a)){
        const x=[a[key]].flat(),y=[b[key]].flat();assert.equal(x.length,y.length);
        assert.ok(x.every(Number.isFinite)&&y.every(Number.isFinite));
        differences[key]=Math.max(...x.map((v,j)=>Math.abs(v-y[j])/Math.max(1,Math.abs(y[j]))));
        maxDifference=Math.max(maxDifference,differences[key]);
      }
      rows.push({time:actual.time,residual:actual.residual,differences});
    }
    const last=raw.snapshots.at(-1),saved=checkpointRecord(last.restart,last.restart_context??raw.restart_context);
    equalPhysical(saved.accepted_method.previous,raw.snapshots.at(-2).restart.state);
    equalPhysical(saved.accepted_method.previous2,raw.snapshots.at(-3).restart.state);
    assert.equal(saved.accepted_method.effective_order,2);
    await write(path.join(base,entry.name+'-checkpoint.json'),saved);
    const report={case:entry,seconds,maxDifference,maxResidual,rows,target_sha256:hash(targetBytes),
      passed:maxDifference<plan.physical_difference_limit,software_provenance:raw.software_provenance};
    await write(path.join(base,entry.name+'-report.json'),report);
    assert.ok(report.passed,'Preserve failed physical comparison: '+maxDifference);
    reports.push(report);console.log(JSON.stringify({case:entry.name,seconds,maxDifference,maxResidual}));
  }
  const report={passed:true,replayed_steps:8,distinct_physical_times:9,reports,
    browser:browser.version(),module_count:modules.length,registered_pass_count_change:0,
    complete_periodic_validation:false,native_ASWING_comparison:false};
  await write(path.join(base,'report.json'),report);console.log(JSON.stringify({passed:true,cases:1,replayed_steps:8}));
}catch(error){
  await write(path.join(base,'failure.json'),{message:String(error),stack:error.stack});throw error;
}finally{
  if(browser)await browser.close();if(server)await new Promise(resolve=>server.close(resolve));
}
