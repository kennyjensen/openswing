// Actual built-worker check of 16 continuous steps from a retained checkpoint.
// This checks the new Newton assembly in WASM, not a new full UA-1 case.
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

const root=process.cwd(),base=path.join(root,'artifacts/isae/ua-time-source-mechanics-20261102/browser');
const prior=path.join(root,'artifacts/isae/ua1-stall-20261102-r1');
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const read=async name=>JSON.parse(await readFile(name,'utf8'));
const write=(name,value)=>writeFile(name,JSON.stringify(value,null,2)+'\n',{flag:'wx'});
await mkdir(base);
const original=await read(path.join(prior,'n160-part001/request.json'));
const targetBytes=await readFile(path.join(prior,'n160-part001/trajectory.json.gz'));
const target=JSON.parse(gunzipSync(targetBytes)).snapshots.slice(0,17);
const modules=await read(path.join(root,'dist/kernel/manifest.json'));
const pins={};
for(const name of modules){
  const bytes=await readFile(path.join(root,'openswing',name));
  assert.equal(hash(await readFile(path.join(root,'dist/kernel',name))),hash(bytes));
  pins[name]=hash(bytes);
}
const workers=(await readdir('dist/assets')).filter(name=>/^worker-.*\.js$/.test(name));
assert.equal(workers.length,1);
const plan={module_sha256:pins,worker_url:'/assets/'+workers[0],
  worker_sha256:hash(await readFile('dist/assets/'+workers[0])),target_sha256:hash(targetBytes),
  request_timeout_seconds:45,steps_per_request:8,requests:2,physical_difference_limit:2e-8,
  scope:'Built-worker continuation from retained CPython checkpoint; no new complete-case validation count.'};
await write(path.join(base,'plan.json'),plan);
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
  let saved=original.checkpoint,previous=null,maxDifference=0,maxResidual=0;
  const reports=[];
  for(let part=0;part<2;part++){
    const end=target[(part+1)*8].time;
    const request={...original,checkpoint:saved,time:{duration:end-saved.state.time,max_steps:32}};
    console.log(JSON.stringify({starting:part}));
    const start=performance.now();
    const response=await page.evaluate(({id,request})=>globalThis.requestKernel(id,request),{id:part+1,request});
    const seconds=(performance.now()-start)/1000,raw=response.result;
    await writeFile(path.join(base,`part${part}.json.gz`),gzipSync(Buffer.from(JSON.stringify(raw)),{level:1}),{flag:'wx'});
    assert.equal(raw.converged,true);assert.equal(raw.accepted_steps,8);assert.equal(raw.rejected_steps,0);
    assert.equal(raw.snapshots.length,9);assert.deepEqual(raw.software_provenance.modules,pins);
    if(previous)for(const key of ['force','circulation_rate','frame'])equalPhysical(raw.snapshots[0][key],previous[key],key);
    const flatten=v=>Array.isArray(v)?v.flat(Infinity):[v];
    const scales={force:.5*1.225*100*200000,moment:.5*1.225*100*200000**2,
      CL:1,CDp:1,circulation_rate:10,local_velocity:10,local_rates:10,time:1};
    for(let i=0;i<raw.snapshots.length;i++){
      const actual=raw.snapshots[i],expected=target[part*8+i];
      assert.ok(Math.abs(actual.time-expected.time)<1e-12);
      assert.ok(actual.residual<1e-10);maxResidual=Math.max(maxResidual,actual.residual);
      for(const [key,scale] of Object.entries(scales)){
        const a=flatten(actual[key]),b=flatten(expected[key]);assert.equal(a.length,b.length);
        for(let j=0;j<a.length;j++)maxDifference=Math.max(maxDifference,Math.abs(a[j]-b[j])/scale);
      }
      for(let j=0;j<actual.strips.length;j++)maxDifference=Math.max(maxDifference,
        Math.abs(actual.strips[j].circulation-expected.strips[j].circulation)/10);
    }
    previous=raw.snapshots.at(-1);
    saved=checkpointRecord(previous.restart,previous.restart_context??raw.restart_context);
    await write(path.join(base,`checkpoint${part}.json`),saved);
    reports.push({part,seconds,maxDifference});console.log(JSON.stringify(reports.at(-1)));
  }
  assert.ok(maxDifference<plan.physical_difference_limit);
  const report={passed:true,steps:16,unique_states:17,maxDifference,maxResidual,reports,
    browser:browser.version(),module_count:modules.length,registered_pass_count_change:0};
  await write(path.join(base,'report.json'),report);console.log(JSON.stringify(report));
}catch(error){
  await write(path.join(base,'failure.json'),{message:String(error),stack:error.stack});throw error;
}finally{
  if(browser)await browser.close();if(server)await new Promise(resolve=>server.close(resolve));
}
