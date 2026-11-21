// One browser worker, three literal PM2 imports, and a bounded mechanical solve.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {preview} from 'vite';
import {chromium} from 'playwright';
import {checkpointRecord} from '../web/saved-state-data.js';

const root=process.cwd();
const output=path.resolve(process.argv[2]??'artifacts/isae/rigid-attachment-production-20261106/browser');
await mkdir(output,{recursive:true});
const reference=path.join(root,'.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865',
  '4 - Aeroelasticity/FFWT - Flared Folding Wingtips Cases/FFWT-4-U - Gust Alleviation of a Wing with and wo FFWT - Quantitative');
const hash=data=>createHash('sha256').update(data).digest('hex');
const audit={checks:[],page_errors:[],external_requests:[],sources:[],modules:{},
  scope:'Literal source loading and qualified rigid-pylon mechanics in the built local browser app; no native validation counts.'};
function check(name,value){audit.checks.push({name,passed:!!value});assert(value,name);}
let server,browser;
try{
  await writeFile(path.join(output,'runner-at-execution.mjs'),await readFile(new URL(import.meta.url)));
  for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py'))){
    const sha=hash(await readFile('openswing/'+name));
    assert.equal(hash(await readFile('dist/kernel/'+name)),sha,'built kernel '+name);
    audit.modules[name]=sha;
  }
  server=await preview({preview:{host:'127.0.0.1',port:0},logLevel:'warn'});
  const origin=`http://127.0.0.1:${server.httpServer.address().port}`;
  browser=await chromium.launch({headless:true,timeout:30000,
    executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE??path.join(root,'artifacts/isae/browser-libs-20261101/chromium/chrome-linux/chrome'),
    env:{...process.env,LP_NUM_THREADS:'1',LD_LIBRARY_PATH:[path.join(root,'artifacts/isae/browser-libs-20261101/lib'),process.env.LD_LIBRARY_PATH].filter(Boolean).join(':')},
    args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--js-flags=--max-old-space-size=192']});
  const page=await browser.newPage({viewport:{width:1200,height:900}});
  page.setDefaultTimeout(60000);
  page.on('pageerror',e=>audit.page_errors.push(e.message));
  await page.route(/^https?:/,route=>{
    if(new URL(route.request().url()).origin===origin)return route.continue();
    audit.external_requests.push(route.request().url());return route.abort();
  });
  await page.addInitScript(()=>{
    window.kernelResults=[];window.kernelRequests=[];
    const OriginalWorker=window.Worker;
    window.Worker=class extends OriginalWorker{
      constructor(...args){super(...args);window.testWorker=this;
        this.addEventListener('message',({data})=>{if(data.result||data.error)window.kernelResults.push(data);});}
      postMessage(message,...args){window.kernelRequests.push(structuredClone(message));return super.postMessage(message,...args);}
    };
    window.callKernel=request=>new Promise((resolve,reject)=>{
      const id=-1;const worker=window.testWorker;
      const timer=setTimeout(()=>{worker.removeEventListener('message',listener);reject(Error('60 second worker deadline'));},60000);
      function listener({data}){if(data.id!==id||(!data.result&&!data.error))return;
        clearTimeout(timer);worker.removeEventListener('message',listener);
        data.error?reject(Error(data.error)):resolve(data.result);}
      worker.addEventListener('message',listener);worker.postMessage({id,request});
    });
  });
  await page.goto(origin);
  await page.waitForFunction(()=>document.querySelector('#solve')?.disabled===false);
  console.log('Browser runtime ready');
  for(const flare of [10,20,30]){
    const filename=`FFWT_Flare${flare}_PM2.asw`,file=path.join(reference,filename);
    const bytes=await readFile(file);audit.sources.push({filename,sha256:hash(bytes)});
    // Avoid a blur-triggered reinspection racing the following file import.
    await page.locator('#panels').evaluate(input=>{input.value='4';});
    const count=await page.evaluate(()=>window.kernelResults.length);
    await page.locator('#file').setInputFiles(file);
    await page.waitForFunction(({filename,source,count})=>{
      const request=window.kernelRequests.findLast(r=>r.request?.action==='inspect'&&r.request.source===source);
      const response=window.kernelResults.find(r=>r.id===request?.id);
      return window.kernelResults.length>count&&response?.result&&
        document.querySelector('#filename')?.textContent===filename&&
        document.querySelector('#runtime-status')?.textContent.includes('Configuration ready')&&
        !document.querySelector('#solve').disabled;
    },{filename,source:bytes.toString('utf8'),count});
    const result=await page.evaluate(source=>{
      const request=window.kernelRequests.findLast(r=>r.request?.action==='inspect'&&r.request.source===source);
      return window.kernelResults.find(r=>r.id===request.id).result;
    },bytes.toString('utf8'));
    assert.deepEqual(result.software_provenance.modules,audit.modules);
    check(filename+' qualified endpoint anchors',JSON.stringify(result.rigid_weight_attachments.map(a=>[a.record,a.effective_t]))===JSON.stringify([[52,.364],[57,-.364]]));
    check(filename+' editor source preserved',await page.locator('#editor').inputValue()===bytes.toString('utf8'));
    await page.locator('#input-compatibility').evaluate(e=>{e.open=true;});
    check(filename+' visible compatibility note',await page.locator('#input-compatibility-list').isVisible()&&
      (await page.locator('#input-compatibility-list').innerText()).includes('native ASWING out-of-range input semantics are unverified'));
    check(filename+' no load error',await page.locator('#error').isHidden());
    await writeFile(path.join(output,filename+'.inspect.json'),JSON.stringify(result,null,2)+'\n');
    console.log(filename+' loaded with original point positions');
  }
  await page.screenshot({path:path.join(output,'pm2-loaded.png'),fullPage:true});
  const source='Name\nBrowser rigid pylon\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n10 1.2 340\nEnd\nReference\n1 .2 1\n0 0 0\nEnd\nGround\n1 2 0\nEnd\nWeight\n1 .8 .17 -.09 .11 7 0 0 .6 -.4 .2 2 3 4 .1 -.2 .3\nEnd\nBeam 1\nRigid beam\nt x y z chord\n1 0 0 0 .2\n2 0 1 0 .2\nEnd\n';
  const request={action:'solve',mode:'structural',source,panels:4,gravity:[.3,-.5,-9],tolerance:1e-9,
    numerics:{beam_interpolation:'natural-v1',structural_operator:'midpoint-v1'}};
  await writeFile(path.join(output,'mechanical-request.json'),JSON.stringify(request,null,2)+'\n');
  const solved=await page.evaluate(request=>window.callKernel(request),request);
  await writeFile(path.join(output,'mechanical-result.json'),JSON.stringify(solved,null,2)+'\n');
  check('mechanical residual',solved.converged&&solved.residual<1e-9);
  const expectedForce=[.21,-.35,-6.3],expectedMoment=[.6055,1.0941,-.0406];
  check('independent point force',solved.applied_force.every((v,i)=>Math.abs(v-expectedForce[i])<1e-10));
  check('independent moment at unchanged physical point',solved.applied_moment.every((v,i)=>Math.abs(v-expectedMoment[i])<1e-10));
  check('saved state records reduction',solved.equilibrium_state.identity.rigid_weight_attachments[0].effective_t===1);
  const timeRequest={action:'time',source,panels:4,
    numerics:{beam_interpolation:'drela-segspl-v1',structural_operator:'drela-moving-vacuum-v1'},
    time:{duration:.02,dt:.01,tolerance:1e-9,max_steps:2,frame:'prescribed',gravity_magnitude:0}};
  const history=await page.evaluate(request=>window.callKernel(request),timeRequest);
  check('bounded source time integration',history.accepted_steps===2&&history.rejected_steps===0);
  const saved=checkpointRecord(history.snapshots[1].restart,history.snapshots[1].restart_context??history.restart_context);
  const resumed=await page.evaluate(request=>window.callKernel(request),
    {action:'resume_time',source,numerics:timeRequest.numerics,checkpoint:saved,time:{duration:.01,max_steps:1}});
  check('source time checkpoint resumes',resumed.accepted_steps===1&&resumed.rejected_steps===0);
  assert.deepEqual(resumed.snapshots.at(-1).nodes,history.snapshots.at(-1).nodes);
  const damaged=structuredClone(saved);delete damaged.context.identity.rigid_weight_attachments;
  const rejection=await page.evaluate(async request=>{
    try{await window.callKernel(request);return null;}catch(e){return e.message;}
  },{action:'resume_time',source,numerics:timeRequest.numerics,checkpoint:damaged,time:{duration:.01,max_steps:1}});
  check('missing attachment metadata rejected in WASM',rejection?.includes('do not match'));
  await writeFile(path.join(output,'time-checkpoints.json'),JSON.stringify({timeRequest,history,resumed,rejection},null,2)+'\n');
  check('no page errors',audit.page_errors.length===0);
  check('no external requests',audit.external_requests.length===0);
  audit.status='PASS';
}catch(error){audit.status='FAIL';audit.error=error.stack;process.exitCode=1;}
finally{
  await browser?.close();
  if(server)await new Promise(resolve=>server.httpServer.close(resolve));
  await writeFile(path.join(output,'report.json'),JSON.stringify(audit,null,2)+'\n');
  console.log(JSON.stringify({status:audit.status,checks:audit.checks,error:audit.error}));
}
