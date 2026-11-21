// Resume the real 419-node boundary immediately before the former memory failure.
import assert from 'node:assert/strict';
import {readFile,readdir,mkdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {preview} from 'vite';
import {chromium} from 'playwright';

const root=process.cwd(),study='artifacts/isae/circulation-finish-memory-20261107';
const output=path.resolve(process.argv[2]);await mkdir(output,{recursive:false});
const read=async p=>JSON.parse(await readFile(p,'utf8'));
const hash=b=>createHash('sha256').update(b).digest('hex');
const report={checks:[],modules:{},jobs:[],page_errors:[],external_requests:[],
  scope:'Built browser continuation through the former 419-node circulation-finish memory failure, followed by a complete page/worker reload. No native-ASWING pass implied.'};
function check(name,value){report.checks.push({name,passed:!!value});assert(value,name);}
let server,browser;
try{
  await writeFile(path.join(output,'runner-at-execution.mjs'),await readFile(new URL(import.meta.url)));
  for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py'))){
    const bytes=await readFile('openswing/'+name);assert.equal(hash(await readFile('dist/kernel/'+name)),hash(bytes),name);
    report.modules[name]=hash(bytes);
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
      const worker=window.kernel,id=-419,progress=[];
      const timer=setTimeout(()=>{worker.removeEventListener('message',listener);reject(Error('120 second job deadline'));},120000);
      function listener({data}){
        if(data.id!==id)return;
        if(data.type==='progress')progress.push(data);
        if(!data.result&&!data.error)return;
        clearTimeout(timer);worker.removeEventListener('message',listener);
        data.error?reject(Error(data.error)):resolve({result:data.result,progress});
      }
      worker.addEventListener('message',listener);worker.postMessage({id,request});
    });
  });
  await page.goto(origin);await page.waitForFunction(()=>document.querySelector('#solve')?.disabled===false);
  console.log('Built browser ready');
  const base=await read(study+'/nodes-419/job-016/request.json');
  let checkpoint=base.continuation.checkpoint;
  for(const index of [16,17]){
    const started=performance.now();
    const {result,progress}=await page.evaluate(r=>window.callKernel(r),{...base,continuation:{max_load_steps:1,checkpoint}});
    const seconds=(performance.now()-started)/1000;
    assert.deepEqual(result.software_provenance.modules,report.modules);
    await writeFile(path.join(output,`job-${index}.json`),JSON.stringify(result,null,2)+'\n');
    await writeFile(path.join(output,`job-${index}-progress.json`),JSON.stringify(progress,null,2)+'\n');
    const native=await read(study+`/nodes-419/job-0${index}/result.json`);
    check(`job ${index} remains pending`,result.continuation_status==='pending'&&!result.converged&&!result.equilibrium_state);
    check(`job ${index} full physical residual`,result.checkpoint.physical_residual<=1e-12);
    check(`job ${index} accepted step count`,result.accepted_load_steps===index);
    check(`job ${index} kernel identity`,result.checkpoint.context.kernel_sha256===native.checkpoint.context.kernel_sha256);
    check(`job ${index} preserves 419 nodes and both pylons`,result.checkpoint.context.coordinates.nodes===419&&result.checkpoint.context.identity.rigid_weight_attachments.length===2);
    let delta=0;const actual=result.checkpoint.coordinates,expected=native.checkpoint.coordinates;
    assert.equal(actual.length,expected.length);
    actual.forEach((value,i)=>{delta=Math.max(delta,Math.abs(value-expected[i])/(1+Math.abs(expected[i])));});
    check(`job ${index} native state agreement`,delta<=2e-8);
    check(`job ${index} native load agreement`,Math.abs(result.load_fraction/native.load_fraction-1)<=2e-8);
    check(`job ${index} advances load`,result.load_fraction>checkpoint.load_fraction);
    report.jobs.push({index,seconds,load_fraction:result.load_fraction,residual:result.checkpoint.physical_residual,
      normalized_state_difference:delta,circulation_finish:result.continuation_log.filter(r=>r.circulation_polish).map(r=>r.circulation_polish)});
    checkpoint=result.checkpoint;
    if(index===16){await page.reload();await page.waitForFunction(()=>document.querySelector('#solve')?.disabled===false);}
    console.log(JSON.stringify(report.jobs.at(-1)));
  }
  check('worker reload preserves continuation',report.jobs.length===2);
  check('no page errors',report.page_errors.length===0);check('no external requests',report.external_requests.length===0);
  report.status='PASS';
}catch(error){report.status='FAIL';report.error=error.stack;process.exitCode=1;}
finally{await browser?.close();await server?.httpServer.close();}
await writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({...report,modules:undefined}));
