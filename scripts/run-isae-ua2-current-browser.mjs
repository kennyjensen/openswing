// Four serial requests per mesh through the actual built browser worker.
import assert from 'node:assert/strict';
import {createReadStream} from 'node:fs';
import {readFile, writeFile, mkdir, stat, readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {gzip} from 'node:zlib';
import {promisify} from 'node:util';
import path from 'node:path';
import {chromium} from '@playwright/test';
import {checkpointRecord} from '../web/saved-state-data.js';

const ROOT=path.resolve('.'), BASE=path.join(ROOT,'artifacts/isae/ua2-displacement-time-20261103');
const panels=Number(process.argv[2]);assert.ok([20,40].includes(panels));
const read=async p=>JSON.parse(await readFile(p,'utf8'));
const write=(p,v)=>writeFile(p,JSON.stringify(v,null,2)+'\n',{flag:'wx'});
const hash=b=>createHash('sha256').update(b).digest('hex');
const digest=async p=>{const h=createHash('sha256');for await(const b of createReadStream(p))h.update(b);return h.digest('hex');};
const planPath=path.join(BASE,'browser-plan.json'),plan=await read(planPath),planHash=await digest(planPath);
for(const [name,value] of Object.entries(plan.source_sha256))assert.equal(await digest(path.join(ROOT,name)),value,name);
const folder=path.join(BASE,`browser-n${panels}`);await mkdir(folder);
let browser,server,failure=null;const errors=[],started=performance.now(),completed=[];
try {
  const dist=path.join(ROOT,'dist'),types={'.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm'};
  server=createServer(async(req,res)=>{
    try {const file=path.resolve(dist,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));
      if(!file.startsWith(dist+path.sep)||(await stat(file)).isDirectory())throw Error('Not a file');
      res.writeHead(200,{'Content-Type':types[path.extname(file)]??'application/octet-stream'});
      createReadStream(file).on('error',()=>res.destroy()).pipe(res);
    }catch{res.writeHead(404);res.end();}
  });
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  const executable=path.join(ROOT,'artifacts/isae/browser-libs-20261101/chromium/chrome-linux/chrome');
  browser=await chromium.launch({executablePath:executable,headless:true,timeout:45000,
    env:{...process.env,LD_LIBRARY_PATH:[path.join(ROOT,'artifacts/isae/browser-libs-20261101/lib'),process.env.LD_LIBRARY_PATH].filter(Boolean).join(':')},
    args:['--no-sandbox','--disable-dev-shm-usage']});
  const page=await browser.newPage();page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(`http://127.0.0.1:${server.address().port}/kernel/manifest.json`);
  await page.evaluate(url=>{
    const worker=new Worker(url,{type:'module'});let pending=null,broken=false;
    worker.onerror=e=>{broken=true;worker.terminate();if(pending){clearTimeout(pending.timer);pending.reject(Error(e.message));pending=null;}};
    worker.onmessage=({data})=>{
      if(!pending||data.id!==pending.id)return;
      if(data.type==='progress'){pending.progress=data;return;}
      if(data.error||data.result){const p=pending;pending=null;clearTimeout(p.timer);
        if(data.error){broken=true;worker.terminate();p.reject(Error(data.error));}else p.resolve(data.result);}
    };
    globalThis.ua2Request=(id,request)=>new Promise((resolve,reject)=>{
      if(pending||broken){reject(Error('Busy or failed worker'));return;}
      const timer=setTimeout(()=>{const progress=pending?.progress;pending=null;broken=true;worker.terminate();reject(Error('45-second request limit: '+JSON.stringify(progress)));},45000);
      pending={id,resolve,reject,timer};worker.postMessage({id,request});
    });
  },plan.worker_url);
  const jobs=plan.jobs.filter(j=>j.panels===panels);assert.equal(jobs.length,4);
  const warmup=await page.evaluate(request=>globalThis.ua2Request(0,request),
    {action:'inspect',source:jobs[0].full_request.source,panels,numerics:jobs[0].full_request.numerics});
  for(const [name,value] of Object.entries(warmup.software_provenance.modules))assert.equal(value,plan.source_sha256['openswing/'+name]);
  await write(path.join(folder,'warmup.json'),{software_provenance:warmup.software_provenance,browser:browser.version(),executable_sha256:await digest(executable)});
  let owned=null;
  for(const job of jobs){
    console.log(JSON.stringify({starting:job.id}));
    const out=path.join(folder,job.id);await mkdir(out);
    const full=job.full_request,end=plan.times[job.end_index];let request;
    if(job.kind==='cold')request={...full,time:{...full.time,duration:end}};
    else {
      let checkpoint=owned;
      if(job.kind==='legacy_replay'){
        const bytes=await readFile(path.join(ROOT,job.checkpoint));assert.equal(hash(bytes),job.checkpoint_sha256);checkpoint=JSON.parse(bytes);
      }
      assert.ok(checkpoint);assert.ok(Math.abs(checkpoint.state.time-plan.times[job.start_index])<1e-12);
      const {condition,time,...common}=full;
      request={...common,action:'resume_time',checkpoint,time:{duration:end-checkpoint.state.time,max_steps:128}};
    }
    await write(path.join(out,'request.json'),request);
    const t=performance.now();
    const raw=await page.evaluate(({id,request})=>globalThis.ua2Request(id,request),{id:job.part+1,request});
    await writeFile(path.join(out,'trajectory.json.gz'),await promisify(gzip)(Buffer.from(JSON.stringify(raw)),{level:1}),{flag:'wx'});
    assert.equal(raw.converged,true);assert.equal(raw.accepted_steps,16);assert.equal(raw.rejected_steps,0);
    assert.equal(raw.snapshots.length,17);assert.ok(Math.abs(raw.snapshots.at(-1).time-end)<1e-12);
    assert.equal(Object.keys(raw.software_provenance.modules).length,136);
    for(const [name,value] of Object.entries(raw.software_provenance.modules))assert.equal(value,plan.source_sha256['openswing/'+name],name);
    const sample=raw.snapshots.at(-1),checkpoint=checkpointRecord(sample.restart,sample.restart_context??raw.restart_context);
    if(job.kind==='cold')owned=checkpoint;
    await write(path.join(out,'checkpoint.json'),checkpoint);
    const outputs={};for(const name of ['request.json','trajectory.json.gz','checkpoint.json'])outputs[name]=await digest(path.join(out,name));
    const receipt={computed:true,accuracy_audit:'pending',job:job.id,kind:job.kind,plan_sha256:planHash,
      seconds:(performance.now()-t)/1000,output_sha256:outputs};
    await write(path.join(out,'receipt.json'),receipt);completed.push(job.id);
    console.log(JSON.stringify({completed:job.id,seconds:receipt.seconds}));
  }
  assert.deepEqual(errors,[]);
}catch(e){failure=String(e.stack??e);}
finally{
  if(browser)await browser.close();if(server)await new Promise(resolve=>server.close(resolve));
  await write(path.join(folder,'outcome.json'),{computed:failure===null,error:failure,completed,
    browser_errors:errors,wall_seconds:(performance.now()-started)/1000,plan_sha256:planHash});
}
if(failure){console.error(failure);process.exitCode=1;}
else console.log(JSON.stringify({computed:true,panels,jobs:completed.length,accuracy_audit:'pending'}));
