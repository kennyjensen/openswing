// Actual built-worker continuation, with one browser and no external requests.
import assert from 'node:assert/strict';
import {readFile,readdir,mkdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {preview} from 'vite';
import {chromium} from 'playwright';

const root=process.cwd(),output=path.resolve(process.argv[2]);
const request=JSON.parse(await readFile('artifacts/isae/ffwt4-continuation-20261106/mounted-request.json','utf8'));
await mkdir(output,{recursive:true});
const hash=data=>createHash('sha256').update(data).digest('hex');
const report={checks:[],modules:{},page_errors:[],external_requests:[],
  scope:'Synthetic source moving-airflow equilibrium: serial checkpoint jobs versus uninterrupted solve in the built browser worker. No ISAE match claim.'};
function check(name,value){report.checks.push({name,passed:!!value});assert(value,name);}
let server,browser;
try{
  await writeFile(path.join(output,'runner-at-execution.mjs'),await readFile(new URL(import.meta.url)));
  for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py'))){
    const digest=hash(await readFile('openswing/'+name));
    assert.equal(hash(await readFile('dist/kernel/'+name)),digest,name);
    report.modules[name]=digest;
  }
  server=await preview({preview:{host:'127.0.0.1',port:0},logLevel:'warn'});
  const origin=`http://127.0.0.1:${server.httpServer.address().port}`;
  browser=await chromium.launch({headless:true,timeout:30000,
    executablePath:path.join(root,'artifacts/isae/browser-libs-20261101/chromium/chrome-linux/chrome'),
    env:{...process.env,LP_NUM_THREADS:'1',LD_LIBRARY_PATH:[path.join(root,'artifacts/isae/browser-libs-20261101/lib'),process.env.LD_LIBRARY_PATH].filter(Boolean).join(':')},
    args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--js-flags=--max-old-space-size=192']});
  const page=await browser.newPage();page.setDefaultTimeout(60000);
  page.on('pageerror',error=>report.page_errors.push(error.message));
  await page.route(/^https?:/,route=>{
    if(new URL(route.request().url()).origin===origin)return route.continue();
    report.external_requests.push(route.request().url());return route.abort();
  });
  await page.addInitScript(()=>{
    const Original=window.Worker;
    window.Worker=class extends Original{constructor(...args){super(...args);window.kernel=this;}};
    window.callKernel=request=>new Promise((resolve,reject)=>{
      const worker=window.kernel,id=-100;
      const timer=setTimeout(()=>{worker.removeEventListener('message',listener);reject(Error('60 second job deadline'));},60000);
      function listener({data}){
        if(data.id!==id||(!data.result&&!data.error))return;
        clearTimeout(timer);worker.removeEventListener('message',listener);
        data.error?reject(Error(data.error)):resolve(data.result);
      }
      worker.addEventListener('message',listener);worker.postMessage({id,request});
    });
  });
  await page.goto(origin);
  await page.waitForFunction(()=>document.querySelector('#solve')?.disabled===false);
  const call=r=>page.evaluate(r=>window.callKernel(r),r);
  const reject=r=>page.evaluate(async r=>{try{await window.callKernel(r);return null;}catch(error){return error.message;}},r);
  console.log('Built browser ready');
  const ordinary=await call(request);await writeFile(path.join(output,'ordinary.json'),JSON.stringify(ordinary,null,2)+'\n');
  check('ordinary full-load equilibrium',ordinary.converged&&ordinary.residual<=1e-12);
  let checkpoint,final;const jobs=[];
  for(let i=0;i<10;i++){
    const jobRequest={...request,continuation:{max_load_steps:1,...(checkpoint?{checkpoint}:{})}};
    const result=await call(jobRequest);jobs.push(result);
    assert.deepEqual(result.software_provenance.modules,report.modules);
    await writeFile(path.join(output,`job-${i+1}.json`),JSON.stringify(result,null,2)+'\n');
    if(result.continuation_status==='complete'){final=result;break;}
    check(`job ${i+1} is an unfinished load state`,result.continuation_status==='pending'&&!result.converged&&!result.equilibrium_state);
    check(`job ${i+1} physical residual`,result.checkpoint.physical_residual<=1e-12);
    check(`job ${i+1} preserves accepted count`,result.accepted_load_steps===i+1);
    check(`job ${i+1} advances load`,result.load_fraction>(checkpoint?.load_fraction??0));
    checkpoint=result.checkpoint;
    if(i===0){
      const damaged=structuredClone(checkpoint);damaged.next_increment*=.9;
      check('changed checkpoint checksum rejected',/checksum/.test(await reject({...request,continuation:{max_load_steps:1,checkpoint:damaged}})));
      check('changed flight setting rejected',/do not match/.test(await reject({...request,condition:{...request.condition,alpha:request.condition.alpha+1},continuation:{max_load_steps:1,checkpoint}})));
      check('partial checkpoint cannot launch time',/identity/.test(await reject({action:'launch_time',source:request.source,numerics:request.numerics,
        equilibrium_state:checkpoint,time:{duration:.01,dt:.01,max_steps:1}})));
      // A process-local matrix/cache must not be required for resumption.
      await page.reload();
      await page.waitForFunction(()=>document.querySelector('#solve')?.disabled===false);
      check('checkpoint survives complete worker restart',true);
    }
    console.log(`Accepted job ${i+1}: load ${result.load_fraction}`);
  }
  check('bounded jobs complete full equilibrium',final?.converged&&final.residual<=1e-12);
  check('continuation count matches uninterrupted solve',final.continuation_steps===ordinary.continuation_steps);
  for(const key of ['positions','rotations','internal_force','internal_moment','reactions','circulation','hinge_charts']){
    assert.deepEqual(final.equilibrium_state[key],ordinary.equilibrium_state[key],key);
    check('identical final '+key,true);
  }
  const pm2=JSON.parse(await readFile('artifacts/isae/ffwt4-startup-20261106/flare20-full-n8/request.json','utf8'));
  const first=await call({...pm2,continuation:{max_load_steps:1}});
  await writeFile(path.join(output,'literal-flare20-first-job.json'),JSON.stringify(first,null,2)+'\n');
  assert.deepEqual(first.software_provenance.modules,report.modules);
  check('literal PM2 first step is saved unfinished',first.continuation_status==='pending'&&!first.converged&&first.accepted_load_steps===1);
  check('literal PM2 physical residual',first.checkpoint.physical_residual<=1e-12);
  check('literal PM2 retains both qualified pylons',first.checkpoint.context.identity.rigid_weight_attachments.length===2);
  check('literal PM2 retains beta 16',first.checkpoint.context.setup.condition.beta===16);
  check('no page errors',report.page_errors.length===0);
  check('no external requests',report.external_requests.length===0);
  report.status='PASS';report.jobs=jobs.length;report.request=request;
}catch(error){report.status='FAIL';report.error=error.stack;process.exitCode=1;}
finally{await browser?.close();await server?.httpServer.close();}
await writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({...report,modules:undefined,request:undefined}));
