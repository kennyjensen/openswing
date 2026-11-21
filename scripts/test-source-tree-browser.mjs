// Built browser: source-tree startup, physical-state parity, restart and negative controls.
import assert from 'node:assert/strict';
import {readFile,readdir,mkdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {preview} from 'vite';
import {chromium} from 'playwright';

const root=process.cwd(),study='artifacts/isae/source-tree-production-20261107';
const output=path.resolve(process.argv[2]);await mkdir(output,{recursive:false});
const hash=data=>createHash('sha256').update(data).digest('hex');
const read=async p=>JSON.parse(await readFile(p,'utf8'));
const report={checks:[],modules:{},jobs:[],page_errors:[],external_requests:[],
  scope:'Two accepted literal frozen-matrix Flare20 211-node load steps using the source-tree proof, with complete browser reload and current native-kernel comparison; not full equilibrium or native-ASWING validation.'};
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
      const worker=window.kernel,id=-100,progress=[];
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
  const reject=r=>page.evaluate(async r=>{try{await window.callKernel(r);return null;}catch(error){return error.message;}},r);
  const tiny=await read('artifacts/isae/ffwt4-continuation-20261106/mounted-request.json');
  assert(tiny.source.includes('Ground\n1 1 0\n'));
  for(const [name,ground] of [['released ground rotations','1 1 1'],['redundant ground reactions','1 1 0\n1 1 0']]){
    const request={...tiny,source:tiny.source.replace('Ground\n1 1 0\n',`Ground\n${ground}\n`),continuation:{max_load_steps:1}};
    check(name+' rejected',/mechanism|redundant/.test(await reject(request)));
  }
  const base=await read(study+'/native/job-001/request.json');let checkpoint;
  for(let index=1;index<=2;index++){
    const request={...base,continuation:{max_load_steps:1,checkpoint:checkpoint??null}};
    const started=performance.now();
    const {result,progress}=await page.evaluate(r=>window.callKernel(r),request);
    const seconds=(performance.now()-started)/1000;
    assert.deepEqual(result.software_provenance.modules,report.modules);
    await writeFile(path.join(output,`job-${index}.json`),JSON.stringify(result,null,2)+'\n');
    await writeFile(path.join(output,`job-${index}-progress.json`),JSON.stringify(progress,null,2)+'\n');
    const native=await read(study+`/native/job-00${index}/result.json`),rank=result.rank_check;
    check(`job ${index} retains 211 nodes`,result.checkpoint.context.coordinates.nodes===211);
    check(`job ${index} is an accepted unfinished state`,result.continuation_status==='pending'&&!result.converged&&!result.equilibrium_state&&result.accepted_load_steps===index);
    check(`job ${index} full saved-load residual`,result.checkpoint.physical_residual<=1e-12);
    check(`job ${index} source-tree mechanical proof`,rank.method==='source flexible-tree rank certificate'&&rank.physical_certificate.certified);
    check(`job ${index} unchanged circulation rank threshold`,rank.circulation_rank.threshold===1e-10&&rank.circulation_rank.singular_ratio>=1e-10);
    check(`job ${index} reports algebraic scope without claiming conditioning`,rank.physical_certificate.numerical_condition_bound===false&&rank.physical_certificate.loaded_stability_claim===false&&!rank.mechanical_svd);
    check(`job ${index} preserves both pylons and beta`,result.checkpoint.context.identity.rigid_weight_attachments.length===2&&result.checkpoint.context.setup.condition.beta===16);
    check(`job ${index} load increases`,result.load_fraction>(checkpoint?.load_fraction??0));
    const actual=result.checkpoint.coordinates,expected=native.checkpoint.coordinates;
    assert.equal(actual.length,expected.length);let delta=0;
    actual.forEach((value,i)=>{delta=Math.max(delta,Math.abs(value-expected[i])/(1+Math.abs(expected[i])));});
    check(`job ${index} native state agreement`,delta<=2e-8);
    check(`job ${index} native load agreement`,Math.abs(result.load_fraction/native.load_fraction-1)<=2e-8);
    check(`job ${index} same kernel identity`,result.checkpoint.context.kernel_sha256===native.checkpoint.context.kernel_sha256);
    report.jobs.push({index,seconds,load_fraction:result.load_fraction,physical_residual:result.checkpoint.physical_residual,normalized_state_difference:delta,circulation_rank_ratio:rank.circulation_rank.singular_ratio});
    checkpoint=result.checkpoint;
    if(index===1){
      const damaged=structuredClone(checkpoint);damaged.next_increment*=.9;
      check('changed checkpoint checksum rejected',/checksum/.test(await reject({...base,continuation:{max_load_steps:1,checkpoint:damaged}})));
      check('changed flight condition rejected',/do not match/.test(await reject({...base,condition:{...base.condition,beta:15},continuation:{max_load_steps:1,checkpoint}})));
      await page.reload();await page.waitForFunction(()=>document.querySelector('#solve')?.disabled===false);
    }
    console.log(JSON.stringify(report.jobs.at(-1)));
  }
  check('complete worker restart preserves continuation',report.jobs.length===2);
  check('no page errors',report.page_errors.length===0);check('no external requests',report.external_requests.length===0);
  report.status='PASS';
}catch(error){report.status='FAIL';report.error=error.stack;process.exitCode=1;}
finally{await browser?.close();await server?.httpServer.close();}
await writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({...report,modules:undefined}));
