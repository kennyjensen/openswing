// One exact native request through the built application's offline WASM worker.
// This checks the worker and full descriptor result, not UI control selection.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createReadStream} from 'node:fs';
import {readFile, writeFile, mkdir, readdir, stat} from 'node:fs/promises';
import {createServer} from 'node:http';
import path from 'node:path';
import {chromium} from 'playwright';
import {expect} from '@playwright/test';

assert.equal(process.argv.length, 4, 'Supply new output folder and native case folder.');
const output=path.resolve(process.argv[2]), nativeFolder=path.resolve(process.argv[3]);
const heapMb=Number(process.env.OPENSWING_BROWSER_HEAP_MB||256);
assert(Number.isInteger(heapMb)&&heapMb>=256&&heapMb<=1024,'Browser verification heap must be 256–1024 MiB.');
await mkdir(output, {recursive:false});
const read=async name=>JSON.parse(await readFile(name,'utf8'));
const save=(name,value)=>writeFile(path.join(output,name),JSON.stringify(value,null,2)+'\n');
const sha=data=>createHash('sha256').update(data).digest('hex');
const request=await read(path.join(nativeFolder,'request.json'));
const native=await read(path.join(nativeFolder,'result.json'));
const baseline=await read(path.join(nativeFolder,'report.json'));
assert.equal(baseline.status,'computed');
const audit={status:'RUNNING',scope:'Built offline worker, exact AE-4 request; not UI controls or native-ASWING validation.',
  checks:[],modules:{},page_errors:[],external_requests:[],offline_requests:[],
  absolute:2e-8,relative:2e-8,pencil_gate:1e-8,numeric_comparisons:0,maximum_fraction:0};
const check=(name,ok,details={})=>{audit.checks.push({name,passed:!!ok,...details});assert(ok,name);};
function compare(a,b,label){
  if(typeof a==='number'){
    assert.equal(typeof b,'number',label);assert(Number.isFinite(a)&&Number.isFinite(b),label);
    const fraction=Math.abs(a-b)/(audit.absolute+audit.relative*Math.abs(a));
    audit.numeric_comparisons++;audit.maximum_fraction=Math.max(audit.maximum_fraction,fraction);assert(fraction<=1,label);
  }else if(Array.isArray(a)){
    assert(Array.isArray(b)&&a.length===b.length,label);a.forEach((v,i)=>compare(v,b[i],`${label}[${i}]`));
  }else if(a!==null&&typeof a==='object'){
    for(const [k,v] of Object.entries(a)){
      if(k==='evaluations')continue; // Execution count, not a physical output.
      assert(Object.hasOwn(b,k),label+'.'+k);compare(v,b[k],label+'.'+k);
    }
  }else assert.deepEqual(b,a,label);
}
function pencil(result){
  const {A,M}=result.matrices,n=A.length;
  assert(n>0&&M.length===n&&A.every(r=>r.length===n)&&M.every(r=>r.length===n));
  const norm=x=>Math.sqrt(x.flat().reduce((s,v)=>s+v*v,0));
  const an=norm(A),mn=norm(M),rows=[];
  for(const mode of result.modes)for(const side of ['right','left']){
    const v=mode[side],lr=mode.eigenvalue[0],li=mode.eigenvalue[1]*(side==='left'?-1:1);
    let squared=0;
    for(let i=0;i<n;i++){
      let ar=0,ai=0,mr=0,mi=0;
      for(let j=0;j<n;j++){
        const a=side==='left'?A[j][i]:A[i][j],m=side==='left'?M[j][i]:M[i][j];
        ar+=a*v.real[j];ai+=a*v.imag[j];mr+=m*v.real[j];mi+=m*v.imag[j];
      }
      squared+=(ar-lr*mr+li*mi)**2+(ai-lr*mi-li*mr)**2;
    }
    const error=Math.sqrt(squared)/((an+Math.hypot(lr,li)*mn)*norm([v.real,v.imag]));
    assert(Number.isFinite(error)&&error<=audit.pencil_gate,side+' full pencil');rows.push({side,eigenvalue:mode.eigenvalue,error});
  }
  return rows;
}
let browser,server,timer,offline=false;
const began=performance.now();
try{
  for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py'))){
    const digest=sha(await readFile('openswing/'+name));audit.modules[name]=digest;
    for(const folder of ['public/kernel','dist/kernel'])assert.equal(sha(await readFile(folder+'/'+name)),digest);
  }
  const dist=path.resolve('dist');
  const mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.css':'text/css','.svg':'image/svg+xml','.woff2':'font/woff2'};
  server=createServer(async(req,res)=>{try{
    const name=decodeURIComponent(new URL(req.url,'http://local').pathname),file=path.resolve(dist,'.'+(name==='/'?'/index.html':name));
    assert(file.startsWith(dist+path.sep)&&(await stat(file)).isFile());
    res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream'});createReadStream(file).pipe(res);
  }catch{res.writeHead(404);res.end();}});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const url=`http://127.0.0.1:${server.address().port}`;
  browser=await chromium.launch({headless:true,executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,
    args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-webgl',`--js-flags=--max-old-space-size=${heapMb}`]});
  timer=setTimeout(()=>browser.close().catch(()=>{}),210000);
  const context=await browser.newContext();
  await context.route(/^https?:/,route=>{
    if(new URL(route.request().url()).origin===url)return route.continue();
    audit.external_requests.push(route.request().url());return route.abort();
  });
  context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))audit.offline_requests.push(r.url());});
  const page=await context.newPage();page.on('pageerror',e=>audit.page_errors.push(e.message));
  await page.addInitScript(()=>{window.testWorkers=[];const W=window.Worker;window.Worker=class extends W{
    constructor(...args){super(...args);window.testWorkers.push(this);}
  };});
  await page.goto(url);await expect(page.locator('#solve')).toBeEnabled({timeout:120000});
  await page.evaluate(async()=>{await Promise.all([...document.fonts].map(f=>f.load()));await document.fonts.ready;});
  await context.setOffline(true);offline=true;
  const started=performance.now();
  const result=await page.evaluate(request=>new Promise((resolve,reject)=>{
    const worker=window.testWorkers[0],id=-7001;
    const listener=({data})=>{
      if(data.id!==id||data.type==='progress')return;
      worker.removeEventListener('message',listener);
      if(data.error)reject(new Error(data.error));else resolve(data.result);
    };
    worker.addEventListener('message',listener);worker.postMessage({id,request});
  }),request);
  audit.solve_seconds=(performance.now()-started)/1000;await save('result.json',result);
  assert.deepEqual(result.software_provenance.modules,audit.modules);check('exact shipped kernel',true);
  compare(native.base,result.base,'base');check('complete physical base parity',true);
  compare(native.matrices,result.matrices,'matrices');check('complete A and M parity',true);
  assert.equal(result.modes.length,native.modes.length);
  const used=new Set();
  for(const mode of native.modes){
    const candidates=result.modes.map((r,i)=>({i,d:Math.hypot(...r.eigenvalue.map((v,k)=>v-mode.eigenvalue[k]))}))
      .filter(r=>!used.has(r.i)).sort((a,b)=>a.d-b.d);
    const index=candidates[0].i;used.add(index);compare(mode.eigenvalue,result.modes[index].eigenvalue,'eigenvalue');
  }
  check('all selected eigenvalues and multiplicities',true);
  audit.pencil=pencil(result);check('all full left and right eigenvectors',true);
  check('fresh base residual',result.diagnostics.base_residual<=1e-7);
  check('solid wall retained',result.base.ground_plane.flag===1&&result.base.ground_plane.wall_roots.length>0);
  check('documented shift retained',JSON.stringify(result.diagnostics.shift)==='[0,200]');
  check('offline execution',!audit.offline_requests.length&&!audit.external_requests.length);
  check('no page errors',!audit.page_errors.length);audit.status='PASS';
}catch(error){
  audit.status='FAILURE_RETAINED';audit.error={message:error.message,stack:error.stack};process.exitCode=1;
}finally{
  clearTimeout(timer);await browser?.close();await new Promise(resolve=>server?server.close(resolve):resolve());
  audit.seconds=(performance.now()-began)/1000;await save('report.json',audit);
  console.log(JSON.stringify({status:audit.status,checks:audit.checks.length,numeric:audit.numeric_comparisons,seconds:audit.seconds}));
}
