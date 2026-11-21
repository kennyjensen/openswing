// One cold modal solve in the built offline worker, compared with a pinned native result.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createReadStream} from 'node:fs';
import {mkdir,readFile,readdir,stat,writeFile} from 'node:fs/promises';
import {createServer} from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
assert([4,5].includes(process.argv.length),'Supply a new output directory, a completed native modal case, and optionally a saved browser run to reassess.');
const output=path.resolve(process.argv[2]),nativePath=path.resolve(process.argv[3]);
const savedPath=process.argv[4]?path.resolve(process.argv[4]):null;
await mkdir(output,{recursive:false});
const read=async p=>JSON.parse(await readFile(p,'utf8'));
const hash=b=>createHash('sha256').update(b).digest('hex');
const save=(name,v)=>writeFile(path.join(output,name),JSON.stringify(v,null,2)+'\n');
const plan=await read(path.join(nativePath,'plan.json'));
const native=await read(path.join(nativePath,'result.json'));
const request=await read(path.join(nativePath,'request.json'));
assert.equal((await read(path.join(nativePath,'report.json'))).status,'PASS');
assert.equal(request.action,'modes');assert.equal(request.modes.matrices,true);
const modules=Object.fromEntries(Object.entries(plan.pins).filter(([name])=>name.startsWith('openswing/')).map(([name,h])=>[path.basename(name),h]));
assert.deepEqual((await readdir(path.join(root,'openswing'))).filter(n=>n.endsWith('.py')).sort(),Object.keys(modules).sort());
for(const [name,h] of Object.entries(modules))for(const folder of ['openswing','public/kernel','dist/kernel'])assert.equal(hash(await readFile(path.join(root,folder,name))),h,folder+'/'+name);
const assets=await readdir(path.join(root,'dist/assets')),workers=assets.filter(n=>/^worker-.*\.js$/.test(n));assert.equal(workers.length,1);
const worker='/assets/'+workers[0];
const audit={status:'PREPARING',scope:'One complete modal worker calculation; no whole-family or native ASWING validation claim.',
  modules,worker_path:worker,worker_sha256:hash(await readFile(path.join(root,'dist'+worker))),script_sha256:hash(await readFile(fileURLToPath(import.meta.url))),
  request_sha256:hash(await readFile(path.join(nativePath,'request.json'))),native_sha256:hash(await readFile(path.join(nativePath,'result.json'))),
  gates:{absolute:2e-8,relative:2e-8,backward:1e-8},page_errors:[],network_failures:[],external_requests:[],offline_requests:[],
  excluded:['base.evaluations'],comparisons:[]};
function compare(expected,actual,label){
  let numeric=0,maximum=0,worst=null;
  function visit(a,b,p){
    if(audit.excluded.includes(p))return;
    if(typeof a==='number'){
      assert.equal(typeof b,'number',p);assert(Number.isFinite(a)&&Number.isFinite(b),p);
      const error=Math.abs(a-b)/(audit.gates.absolute+audit.gates.relative*Math.abs(a));
      numeric++;if(error>maximum){maximum=error;worst=p;}assert(error<=1,p+' exceeds parity gate');
    }else if(Array.isArray(a)){
      assert(Array.isArray(b)&&a.length===b.length,p);a.forEach((x,i)=>visit(x,b[i],p+'['+i+']'));
    }else if(a!==null&&typeof a==='object'){
      assert(b!==null&&typeof b==='object',p);for(const [k,v] of Object.entries(a)){assert(Object.hasOwn(b,k),p+'.'+k);visit(v,b[k],p+'.'+k);}
    }else assert.deepEqual(b,a,p);
  }
  visit(expected,actual,label);audit.comparisons.push({label,numeric,maximum,worst});
}
function normalize(value,[r,i]){
  const divisor=r*r+i*i;assert(divisor>0&&Number.isFinite(divisor));
  function parts(re,im){
    if(Array.isArray(re)){const pairs=re.map((v,k)=>parts(v,im[k]));return [pairs.map(v=>v[0]),pairs.map(v=>v[1])];}
    return [(re*r+im*i)/divisor,(im*r-re*i)/divisor];
  }
  if(Array.isArray(value))return value.map(v=>normalize(v,[r,i]));
  if(value!==null&&typeof value==='object'){
    if(Object.hasOwn(value,'real')&&Object.hasOwn(value,'imag')){const [real,imag]=parts(value.real,value.imag);return {...value,real,imag};}
    return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,normalize(v,[r,i])]));
  }
  return value;
}
function pencilChecks(result){
  const {A,M}=result.matrices,n=A.length;
  const norm=matrix=>Math.sqrt(matrix.reduce((s,row)=>s+row.reduce((t,x)=>t+x*x,0),0));
  const an=norm(A),mn=norm(M),checks=[];
  for(const mode of result.modes)for(const side of ['right','left']){
    const v=mode[side],[lr,li0]=mode.eigenvalue,li=side==='left'?-li0:li0;let squared=0,vn=0;
    for(let row=0;row<n;row++){
      let ar=0,ai=0,mr=0,mi=0;
      for(let col=0;col<n;col++){
        const a=side==='left'?A[col][row]:A[row][col],m=side==='left'?M[col][row]:M[row][col];
        ar+=a*v.real[col];ai+=a*v.imag[col];mr+=m*v.real[col];mi+=m*v.imag[col];
      }
      squared+=(ar-lr*mr+li*mi)**2+(ai-lr*mi-li*mr)**2;vn+=v.real[row]**2+v.imag[row]**2;
    }
    const error=Math.sqrt(squared)/((an+Math.hypot(lr,li)*mn)*Math.sqrt(vn));
    assert(Number.isFinite(error)&&error<=audit.gates.backward);checks.push({side,eigenvalue:mode.eigenvalue,error});
  }
  return checks;
}
let server,browser,actual,offline=false;const began=performance.now();
try{
  if(savedPath){
    const previous=await read(path.join(savedPath,'report.json'));
    assert.equal(previous.status,'FAILURE_RETAINED');assert.equal(previous.comparisons.length,0);
    const originalHarness=await readFile(path.join(savedPath,'original-harness.mjs'));
    assert.equal(hash(originalHarness),previous.script_sha256);
    // The original run saved the full reply before its mistaken request-echo
    // assertion. Its pinned harness supplies this exact request to postMessage.
    assert(originalHarness.toString().includes('page.evaluate(r=>window.runModalRequest(1,r),request)'));
    assert(originalHarness.toString().includes('worker.postMessage({id,request})'));
    assert(previous.error.message.includes('Expected values to be strictly deep-equal'));
    for(const key of ['modules','worker_path','worker_sha256','request_sha256','native_sha256','gates','excluded'])assert.deepEqual(previous[key],audit[key],key);
    for(const key of ['page_errors','network_failures','external_requests','offline_requests'])audit[key]=previous[key];
    actual=await read(path.join(savedPath,'result.json'));
    audit.solve_seconds=previous.solve_seconds;
    audit.original_run_seconds=previous.seconds;
    audit.reassessment={directory:path.relative(root,savedPath),report_sha256:hash(await readFile(path.join(savedPath,'report.json'))),
      result_sha256:hash(await readFile(path.join(savedPath,'result.json'))),harness_sha256:previous.script_sha256,
      request_provenance:'Exact request passed by the hash-verified original harness; worker replies do not echo requests.'};
  }else{
  const dist=path.join(root,'dist'),types={'.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm'};
  server=createServer(async(req,res)=>{try{
    const file=path.resolve(dist,'.'+decodeURIComponent(new URL(req.url,'http://local').pathname));
    assert(file.startsWith(dist+path.sep)&&(await stat(file)).isFile());
    res.writeHead(200,{'Content-Type':types[path.extname(file)]??'application/octet-stream'});createReadStream(file).pipe(res);
  }catch{res.writeHead(404);res.end();}});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const url=`http://127.0.0.1:${server.address().port}`;
  browser=await chromium.launch({headless:true,executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,
    args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--js-flags=--max-old-space-size=192']});
  const context=await browser.newContext();
  await context.route(/^https?:/,route=>{if(new URL(route.request().url()).origin===url)return route.continue();audit.external_requests.push(route.request().url());return route.abort();});
  context.on('requestfailed',r=>audit.network_failures.push(r.url()));
  context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))audit.offline_requests.push(r.url());});
  const page=await context.newPage();page.on('pageerror',e=>audit.page_errors.push(e.message));
  await page.goto(url+'/kernel/manifest.json');
  await page.evaluate(workerURL=>{
    const worker=new Worker(workerURL,{type:'module'});let pending=null;
    window.sentModalRequests=[];
    worker.onmessage=({data})=>{if(!pending||data.id!==pending.id)return;if(data.error||data.result){const p=pending;pending=null;clearTimeout(p.timer);data.error?p.reject(Error(data.error)):p.resolve(data.result);}};
    worker.onerror=e=>{if(pending){clearTimeout(pending.timer);pending.reject(Error(e.message));pending=null;}};
    window.runModalRequest=(id,request)=>new Promise((resolve,reject)=>{
      if(pending)return reject(Error('Concurrent worker request'));
      const timer=setTimeout(()=>{worker.terminate();pending=null;reject(Error('Worker deadline'));},180000);
      pending={id,resolve,reject,timer};window.sentModalRequests.push(structuredClone({id,request}));worker.postMessage({id,request});
    });
  },worker);
  const warm=await page.evaluate(r=>window.runModalRequest(0,r),{action:'inspect',source:request.source,panels:request.panels,numerics:request.numerics});
  assert.deepEqual(warm.software_provenance.modules,modules);
  await context.setOffline(true);offline=true;const start=performance.now();
  actual=await page.evaluate(r=>window.runModalRequest(1,r),request);audit.solve_seconds=(performance.now()-start)/1000;
  audit.sent_request=await page.evaluate(()=>window.sentModalRequests.find(r=>r.id===1));
  assert.deepEqual(audit.sent_request,{id:1,request});
  }
  await save('result.json',actual);assert.deepEqual(actual.software_provenance.modules,modules);
  assert(actual.converged&&actual.base.residual<=1e-9);
  for(const key of ['base','matrices','frame_mode','structural_operator','numerics'])compare(native[key],actual[key],key);
  const expectedColumns=native.diagnostics.state_linearization.direct_mechanical_columns;
  assert(expectedColumns>0);assert.equal(actual.diagnostics.state_linearization.direct_mechanical_columns,expectedColumns);
  const geometry=native.diagnostics.state_linearization;
  if(geometry.grouped_geometry_columns>0){
    assert.equal(actual.diagnostics.state_linearization.grouped_geometry_columns,geometry.grouped_geometry_columns);
    assert.equal(actual.diagnostics.state_linearization.geometry_column_groups,geometry.geometry_column_groups);
    assert.equal(actual.diagnostics.state_linearization.geometry_method,geometry.geometry_method);
    audit.grouped_geometry={columns:geometry.grouped_geometry_columns,groups:geometry.geometry_column_groups};
  }
  assert.equal(actual.modes.length,native.modes.length);const unused=new Set(actual.modes.map((_,i)=>i));
  for(const [index,expected] of native.modes.entries()){
    const j=[...unused].sort((a,b)=>Math.hypot(...actual.modes[a].eigenvalue.map((v,k)=>v-expected.eigenvalue[k]))-Math.hypot(...actual.modes[b].eigenvalue.map((v,k)=>v-expected.eigenvalue[k])))[0];unused.delete(j);
    const mode=actual.modes[j];compare(expected.eigenvalue,mode.eigenvalue,'mode'+index+'.pole');assert.equal(mode.stability,expected.stability);
    const width=native.diagnostics.state_layout.node_coordinates.width;
    const pivot=expected.right.real.slice(0,width).reduce((best,v,k)=>Math.hypot(v,expected.right.imag[k])>Math.hypot(expected.right.real[best],expected.right.imag[best])?k:best,0);
    const e=[expected.right.real[pivot],expected.right.imag[pivot]],a=[mode.right.real[pivot],mode.right.imag[pivot]];
    compare(normalize(expected.right,e),normalize(mode.right,a),'mode'+index+'.right');
    compare(normalize(expected.output,e),normalize(mode.output,a),'mode'+index+'.output');
    const lp=expected.left.real.reduce((best,v,k)=>Math.hypot(v,expected.left.imag[k])>Math.hypot(expected.left.real[best],expected.left.imag[best])?k:best,0);
    compare(normalize(expected.left,[expected.left.real[lp],expected.left.imag[lp]]),normalize(mode.left,[mode.left.real[lp],mode.left.imag[lp]]),'mode'+index+'.left');
  }
  audit.native_pencil_checks=pencilChecks(native);audit.browser_pencil_checks=pencilChecks(actual);
  for(const key of ['page_errors','network_failures','external_requests','offline_requests'])assert.equal(audit[key].length,0,key);
  for(const [name,h] of Object.entries(modules))for(const folder of ['openswing','public/kernel','dist/kernel'])assert.equal(hash(await readFile(path.join(root,folder,name))),h,folder+'/'+name+' after solve');
  assert.equal(hash(await readFile(path.join(root,'dist'+worker))),audit.worker_sha256);
  assert.equal(hash(await readFile(fileURLToPath(import.meta.url))),audit.script_sha256);
  assert.equal(hash(await readFile(path.join(nativePath,'request.json'))),audit.request_sha256);
  assert.equal(hash(await readFile(path.join(nativePath,'result.json'))),audit.native_sha256);
  audit.pins_rechecked_after_assessment=true;
  audit.status=savedPath?'PASS_REASSESSED_OFFLINE_MODAL_WORKER':'PASS_OFFLINE_MODAL_WORKER';
}catch(error){audit.status='FAILURE_RETAINED';audit.error={message:error.message,stack:error.stack};process.exitCode=1;console.error(error.stack);
}finally{
  await browser?.close();server?.closeAllConnections();if(server?.listening)await new Promise(resolve=>server.close(resolve));
  audit.seconds=(performance.now()-began)/1000;await save('report.json',audit);
  console.log(JSON.stringify({status:audit.status,solve_seconds:audit.solve_seconds,comparisons:audit.comparisons.length,seconds:audit.seconds}));
}
