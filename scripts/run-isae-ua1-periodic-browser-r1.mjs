// Bounded, serial requests to the actual built app worker. No reference state
// initializes production. Every result and standalone checkpoint is retained.
import assert from 'node:assert/strict';
import {createReadStream} from 'node:fs';
import {readFile, writeFile, mkdir, stat, rename, open, unlink} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {gzip, gunzip} from 'node:zlib';
import {promisify} from 'node:util';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from '@playwright/test';
import {checkpointRecord} from '../web/saved-state-data.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const BASE = path.join(ROOT, 'artifacts/isae/ua1-incidence-periodic-browser-20261102-r1');
const zip = promisify(gzip), unzip = promisify(gunzip);
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const read = async name => JSON.parse(await readFile(name, 'utf8'));
const write = (name, value) => writeFile(name, JSON.stringify(value, null, 2)+'\n', {flag:'wx'});
async function exists(name) {try {await stat(name); return true;} catch(e) {if(e.code==='ENOENT')return false;throw e;}}
async function digest(name) {
  const h=createHash('sha256');for await(const block of createReadStream(name))h.update(block);return h.digest('hex');
}
async function live(value) {
  const name=path.join(BASE,'live-browser.json');await writeFile(name+'.tmp',JSON.stringify(value,null,2)+'\n');await rename(name+'.tmp',name);
}
const args=process.argv.slice(2);
if(args.length && !(args.length===2&&args[0]==='--max-new-jobs'&&/^[1-9]\d*$/.test(args[1])))
  throw Error('Usage: node scripts/run-isae-ua1-periodic-browser-r1.mjs [--max-new-jobs N]');
const limit=args.length?Number(args[1]):Infinity;
const planBytes=await readFile(path.join(BASE,'plan.json')),plan=JSON.parse(planBytes);
const planHash=hash(planBytes);
for(const [name,value] of Object.entries(plan.source_sha256))assert.equal(await digest(path.join(ROOT,name)),value,name);
assert.equal(plan.jobs.length,128);assert.equal(plan.max_steps_per_job,20);
assert.equal(plan.panels,4);assert.equal(plan.worker_request_timeout_seconds,45);
const completed=[];
for(const job of plan.jobs) {
  const folder=path.join(BASE,'production',`part${String(job.part).padStart(3,'0')}`);
  if(!await exists(folder))break;
  const receipt=await read(path.join(folder,'receipt.json'));
  assert.equal(receipt.outcome,'success','Inspect retained failed or interrupted browser job');
  assert.equal(receipt.plan_sha256,planHash);assert.deepEqual(receipt.job,job);
  for(const [name,value] of Object.entries(receipt.output_sha256))assert.equal(await digest(path.join(folder,name)),value,name);
  completed.push(job);
}
// Refuse holes or attempts beyond the contiguous completed prefix.
for(const job of plan.jobs.slice(completed.length))
  assert.equal(await exists(path.join(BASE,'production',`part${String(job.part).padStart(3,'0')}`)),false);
if(completed.length===plan.jobs.length)throw Error('All browser segments already complete; run the raw-history audit.');
const lock=await open(path.join(BASE,'runner.lock'),'wx');
await lock.writeFile(JSON.stringify({pid:process.pid,plan_sha256:planHash})+'\n');await lock.close();
const runId=`run-${Date.now()}-${process.pid}`;
const runFolder=path.join(BASE,'runs',runId);await mkdir(runFolder,{recursive:true});
let browser,server,checkpoint=null,previous=null,runError=null,newJobs=0,provenanceFingerprint=null;
const runStarted=performance.now(),browserErrors=[];
try {
  if(completed.length) {
    const folder=path.join(BASE,'production',`part${String(completed.at(-1).part).padStart(3,'0')}`);
    checkpoint=await read(path.join(folder,'checkpoint.json'));
    const raw=JSON.parse(await unzip(await readFile(path.join(folder,'trajectory.json.gz'))));
    previous=raw.snapshots.at(-1);
    provenanceFingerprint=raw.software_provenance.fingerprint;
    assert.deepEqual(checkpoint,checkpointRecord(previous.restart,previous.restart_context??raw.restart_context));
  }
  const dist=path.join(ROOT,'dist');
  const types={'.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.html':'text/html'};
  server=createServer(async (req,res)=>{
    try {
      const file=path.resolve(dist,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));
      if(!file.startsWith(dist+path.sep)||(await stat(file)).isDirectory()) {res.writeHead(404);res.end();return;}
      res.writeHead(200,{'Content-Type':types[path.extname(file)]??'application/octet-stream'});
      createReadStream(file).on('error',()=>res.destroy()).pipe(res);
    } catch {res.writeHead(404);res.end();}
  });
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  const executable=process.env.OPENSWING_CHROMIUM??path.join(ROOT,'artifacts/isae/browser-libs-20261101/chromium/chrome-linux/chrome');
  const libraries=path.join(ROOT,'artifacts/isae/browser-libs-20261101/lib');
  browser=await chromium.launch({executablePath:executable,headless:true,timeout:45000,
    env:{...process.env,LD_LIBRARY_PATH:[libraries,process.env.LD_LIBRARY_PATH].filter(Boolean).join(':')},
    args:['--no-sandbox','--disable-dev-shm-usage']});
  await write(path.join(runFolder,'browser.json'),{version:browser.version(),executable,executable_sha256:await digest(executable),plan_sha256:planHash});
  const page=await browser.newPage();page.on('pageerror',e=>browserErrors.push(String(e)));
  await page.goto(`http://127.0.0.1:${server.address().port}/kernel/manifest.json`);
  await page.evaluate(({workerURL,timeout})=>{
    const worker=new Worker(workerURL,{type:'module'});let pending=null,broken=false;
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
    globalThis.ua1Request=(id,request)=>new Promise((resolve,reject)=>{
      if(pending||broken){reject(Error('Browser worker is busy or has failed'));return;}
      const timer=setTimeout(()=>{const diagnostic={statuses,lastProgress:pending?.lastProgress};broken=true;pending=null;worker.terminate();reject(Error(`Worker request exceeded ${timeout/1000} seconds: ${JSON.stringify(diagnostic)}`));},timeout);
      pending={id,resolve,reject,timer,lastProgress:null};worker.postMessage({id,request});
    });
  },{workerURL:plan.worker_url,timeout:plan.worker_request_timeout_seconds*1000});
  // Runtime loading is a separate bounded request, not part of a solve's budget.
  const warmupStarted=performance.now();
  console.log(JSON.stringify({starting:'runtime-and-model-inspection'}));
  const warmup=await page.evaluate(request=>globalThis.ua1Request(0,request),
    {action:'inspect',source:plan.full_request.source,panels:plan.panels,numerics:plan.full_request.numerics});
  const warmupSeconds=(performance.now()-warmupStarted)/1000;
  for(const [name,value] of Object.entries(warmup.result.software_provenance.modules))assert.equal(value,plan.source_sha256['openswing/'+name]);
  await write(path.join(runFolder,'warmup.json'),{seconds:warmupSeconds,status_messages:warmup.statuses,software_provenance:warmup.result.software_provenance});
  console.log(JSON.stringify({completed:'runtime-and-model-inspection',seconds:warmupSeconds}));
  for(const job of plan.jobs.slice(completed.length)) {
    const id=`part${String(job.part).padStart(3,'0')}`,folder=path.join(BASE,'production',id);
    await mkdir(folder,{recursive:true});
    const started=performance.now();
    await live({status:'running',runner_pid:process.pid,run_id:runId,job:id,plan_sha256:planHash});
    console.log(JSON.stringify({starting:id}));
    try {
      const {condition,time,...common}=plan.full_request;
      const end=plan.times[job.end_index];
      const request=checkpoint?{...common,action:'resume_time',checkpoint,time:{duration:end-checkpoint.state.time,max_steps:160}}
        :{...plan.full_request,time:{...time,duration:end,max_steps:160}};
      if(checkpoint)assert.ok(Math.abs(checkpoint.state.time-plan.times[job.start_index])<1e-12);
      const response=await page.evaluate(({id,request})=>globalThis.ua1Request(id,request),{id:job.part+1,request});
      const workerSeconds=(performance.now()-started)/1000;
      const raw=response.result;
      // Retain the actual result before enforcing comparison gates.
      const rawPath=path.join(folder,'trajectory.json.gz');
      await writeFile(rawPath+'.partial',await zip(Buffer.from(JSON.stringify(raw)),{level:1}),{flag:'wx'});
      await rename(rawPath+'.partial',rawPath);
      assert.equal(raw.converged,true);assert.equal(raw.accepted_steps,20);assert.equal(raw.rejected_steps,0);
      assert.equal(raw.snapshots.length,21);assert.ok(Math.abs(raw.snapshots.at(-1).time-end)<1e-12);
      const provenance=raw.software_provenance;assert.equal(Object.keys(provenance.modules).length,136);
      for(const [name,value] of Object.entries(provenance.modules))assert.equal(value,plan.source_sha256['openswing/'+name],name);
      if(provenanceFingerprint!==null)assert.equal(provenance.fingerprint,provenanceFingerprint,'Worker runtime/source fingerprint changed');
      provenanceFingerprint=provenance.fingerprint;
      if(previous) {
        for(const key of ['force','circulation_rate','frame'])assert.equal(JSON.stringify(raw.snapshots[0][key]),JSON.stringify(previous[key]),'Checkpoint join: '+key);
        assert.equal(JSON.stringify(raw.snapshots[0].strips.map(s=>s.circulation)),JSON.stringify(previous.strips.map(s=>s.circulation)));
      }
      const targetPath=path.join(BASE,plan.targets[job.part].path);
      const targetBytes=await readFile(targetPath);assert.equal(hash(targetBytes),plan.targets[job.part].sha256);
      const target=JSON.parse(targetBytes);assert.deepEqual(target.job,job);
      const angle=9*Math.PI/180,heave=[-Math.sin(angle),0,Math.cos(angle)],wind=[Math.cos(angle),0,Math.sin(angle)];
      const dynamicPressureArea=.5*1.225*100*200000;
      const dot=(a,b)=>a.reduce((sum,v,i)=>sum+v*b[i],0);
      let largestDifference=0,largestResidual=0;
      const rows=raw.snapshots.map((s,i)=>{
        assert.ok(Math.abs(s.time-plan.times[job.start_index+i])<1e-12);assert.equal(s.strips.length,4);
        assert.ok(Number.isFinite(s.residual)&&s.residual<plan.gates.normalized_residual);
        if(i)assert.equal(s.order,job.start_index+i===1?1:2);
        assert.ok(s.frame.attitude.concat(s.frame.rates_body).every(v=>Math.abs(v)<1e-12));
        assert.ok(Math.abs(dot(s.frame.velocity_origin_body,wind)+10)<1e-10);
        const row={time:s.time,CL:dot(s.force,heave)/dynamicPressureArea,force_coefficient:s.force.map(v=>v/dynamicPressureArea),
          circulation:s.strips.map(v=>v.circulation),circulation_rate:s.circulation_rate,
          heave_velocity:dot(s.frame.velocity_origin_body,heave),heave_position:dot(s.frame.position_earth,heave),
          heave_acceleration:dot(s.frame.acceleration_reference_body,heave),residual:s.residual,order:s.order};
        for(const key of ['CL','force_coefficient','circulation','circulation_rate','heave_velocity','heave_position','heave_acceleration']) {
          const a=[row[key]].flat(Infinity),b=[target.rows[i][key]].flat(Infinity);assert.equal(a.length,b.length);
          assert.ok(a.every(Number.isFinite)&&b.every(Number.isFinite),`Nonfinite physical field: ${key}`);
          for(let j=0;j<a.length;j++) {
            const difference=Math.abs(a[j]-b[j])/Math.max(1,Math.abs(b[j]));
            assert.ok(Number.isFinite(difference)&&difference<plan.gates.CPython_scaled_difference,`${id} ${key}: ${difference}`);
            largestDifference=Math.max(largestDifference,difference);
          }
        }
        largestResidual=Math.max(largestResidual,s.residual);return row;
      });
      previous=raw.snapshots.at(-1);
      checkpoint=checkpointRecord(previous.restart,previous.restart_context??raw.restart_context);
      const final=job.part===plan.jobs.length-1;
      const accepted=checkpoint.accepted_method;
      assert.equal(accepted.effective_order,2);assert.equal(accepted.scheme,'drela-euler-bdf-v1');
      assert.deepEqual(accepted.endpoint.state,checkpoint.state);
      assert.deepEqual(accepted.previous,raw.snapshots.at(-2).restart.state);
      assert.deepEqual(accepted.previous2,raw.snapshots.at(-3).restart.state);
      assert.equal(checkpoint.forcing_side,final?'left':'right');
      if(final)assert.equal(checkpoint.older,null);
      else assert.deepEqual(checkpoint.older,raw.snapshots.at(-2).restart.state);
      assert.ok(Math.abs(checkpoint.state.time-end)<1e-12);
      await write(path.join(folder,'checkpoint.json'),checkpoint);
      await write(path.join(folder,'report.json'),{segment_passed:true,job,rows,accepted_steps:20,rejected_steps:0,
        worker_seconds:workerSeconds,maximum_CPython_scaled_difference:largestDifference,maximum_residual:largestResidual,
        status_messages:response.statuses,last_progress:response.lastProgress,software_provenance:provenance,
        target_sha256:plan.targets[job.part].sha256,plan_sha256:planHash,full_periodic_audit:'pending'});
      const outputs={};for(const name of ['trajectory.json.gz','checkpoint.json','report.json'])outputs[name]=await digest(path.join(folder,name));
      const receipt={outcome:'success',job,plan_sha256:planHash,output_sha256:outputs,
        wall_seconds:(performance.now()-started)/1000,run_id:runId};
      await write(path.join(folder,'receipt.json'),receipt);newJobs++;
      await live({status:'between_jobs',runner_pid:process.pid,run_id:runId,completed_job:id,new_jobs:newJobs});
      console.log(JSON.stringify({completed:id,worker_seconds:workerSeconds,maximum_CPython_scaled_difference:largestDifference}));
      if(newJobs>=limit)break;
    } catch(error) {
      await write(path.join(folder,'receipt.json'),{outcome:'failed',job,plan_sha256:planHash,run_id:runId,error:String(error),wall_seconds:(performance.now()-started)/1000});throw error;
    }
  }
  assert.deepEqual(browserErrors,[]);
  for(const [name,value] of Object.entries(plan.source_sha256))assert.equal(await digest(path.join(ROOT,name)),value,name);
  if(completed.length+newJobs===plan.jobs.length)
    await write(path.join(BASE,'production-complete.json'),{computed_jobs:128,physical_steps:2560,audit_status:'pending',native_ASWING_comparison:false,full_goal_complete:false});
} catch(error) {runError=String(error);process.exitCode=1;console.error(runError);}
finally {
  if(browser)await browser.close();
  if(server){server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
  const outcome={status:'terminal',success:runError===null,error:runError,new_jobs:newJobs,prior_completed_jobs:completed.length,
    runner_pid:process.pid,run_id:runId,plan_sha256:planHash,wall_seconds:(performance.now()-runStarted)/1000,browser_errors:browserErrors};
  await write(path.join(runFolder,'outcome.json'),outcome);await live(outcome);await unlink(path.join(BASE,'runner.lock'));
  console.log(JSON.stringify(outcome));
}
