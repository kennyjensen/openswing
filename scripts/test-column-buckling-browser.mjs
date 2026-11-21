// Serial offline modal calculations; optional trailing arguments select case folders.
// Node performs saved-array comparisons only; all physical solving uses the real worker.
import {chromium} from 'playwright';
import {expect} from '@playwright/test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {createReadStream} from 'node:fs';
import {readFile,writeFile,mkdir,readdir,stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
assert(process.argv.length>=4,'Supply a new output directory, completed native study, and optional case names.');
const output=path.resolve(process.argv[2]),study=path.resolve(process.argv[3]);
const caseNames=process.argv.length>4?process.argv.slice(4):['n32-half','n64-over'];
await mkdir(output,{recursive:false});
const readJSON=async p=>JSON.parse(await readFile(p,'utf8'));
const sha=b=>createHash('sha256').update(b).digest('hex');
const pin=async p=>({path:p,sha256:sha(await readFile(p))});
const save=(name,value)=>writeFile(path.join(output,name),JSON.stringify(value,null,2)+'\n');
const wire=v=>JSON.parse(JSON.stringify(v));
const audit={status:'PREPARING',scope:'Synthetic column supplement, not native ASWING validation. Selected native cases in the actual offline browser. Full physical base, phase-normalized modal outputs and eigenvectors, pole/stability checks and saved-project restoration.',
  planned_solves:caseNames.length,gates:{absolute:2e-8,relative:2e-8,backward:1e-8,base:1e-9},
  exclusions:['base.evaluations'],checks:[],cases:[],page_errors:[],network_failures:[],external_requests:[],offline_requests:[],
  matrix_output:'Native matrices remain in evidence; the browser uses its normal output setting (matrices:false). This flag only appends diagnostic A/M arrays after solving and output recovery; no physical equation or solve setting changes.'};
const check=(name,ok,details={})=>{audit.checks.push({name,passed:!!ok,...details});assert(ok,name);};
function compare(expected,actual,start=''){
  const result={numeric:0,maximum_fraction:0,worst:null};
  function visit(e,a,p){
    if(audit.exclusions.includes(p))return;
    if(typeof e==='number'){
      assert.equal(typeof a,'number',p);assert(Number.isFinite(e)&&Number.isFinite(a),p);
      const fraction=Math.abs(e-a)/(audit.gates.absolute+audit.gates.relative*Math.abs(e));
      result.numeric++;if(fraction>result.maximum_fraction)Object.assign(result,{maximum_fraction:fraction,worst:p});
      assert(fraction<=1,p+' exceeds unchanged parity allowance');
    }else if(Array.isArray(e)){
      assert(Array.isArray(a)&&a.length===e.length,p);e.forEach((v,i)=>visit(v,a[i],p+'['+i+']'));
    }else if(e!==null&&typeof e==='object'){
      assert(a!==null&&typeof a==='object',p);
      for(const [k,v] of Object.entries(e)){assert(Object.hasOwn(a,k),p+'.'+k);visit(v,a[k],p+'.'+k);}
    }else assert.deepEqual(a,e,p);
  }
  visit(expected,actual,start);return result;
}
function normalized(value,denominator){
  const [dr,di]=denominator,d=dr*dr+di*di;assert(Number.isFinite(d)&&d>0);
  function parts(re,im){
    if(Array.isArray(re)){assert(Array.isArray(im)&&re.length===im.length);const pairs=re.map((v,i)=>parts(v,im[i]));return [pairs.map(p=>p[0]),pairs.map(p=>p[1])];}
    assert(Number.isFinite(re)&&Number.isFinite(im));return [(re*dr+im*di)/d,(im*dr-re*di)/d];
  }
  function walk(v){
    if(Array.isArray(v))return v.map(walk);
    if(v!==null&&typeof v==='object'){
      if(Object.hasOwn(v,'real')&&Object.hasOwn(v,'imag')){const [real,imag]=parts(v.real,v.imag);return {...v,real,imag};}
      return Object.fromEntries(Object.entries(v).map(([k,x])=>[k,walk(x)]));
    }
    return v;
  }
  return walk(value);
}
// A constrained last node can have zero displacement. Normalize both results
// at the same nonzero physical component selected from the reference mode.
function physicalPivot(mode){
  let pivot=null,magnitude=0;
  for(const [node,n] of mode.output.nodes.entries())for(const quantity of ['displacement','rotation'])for(let axis=0;axis<3;axis++){
    const value=Math.hypot(n[quantity].real[axis],n[quantity].imag[axis]);
    if(value>magnitude){magnitude=value;pivot={node,quantity,axis};}
  }
  assert(pivot&&magnitude>0,'Mode needs a nonzero physical displacement or rotation.');return pivot;
}
function component(mode,{node,quantity,axis}){const v=mode.output.nodes[node][quantity];return [v.real[axis],v.imag[axis]];}
let browser,server,page,timer,offline=false;
const began=performance.now();
try{
  audit.script=await pin(fileURLToPath(import.meta.url));await writeFile(path.join(output,'runner-at-execution.mjs'),await readFile(fileURLToPath(import.meta.url)));
  const studyPlan=await readJSON(path.join(study,'plan.json'));
  audit.modules=Object.fromEntries(Object.entries(studyPlan.pins).filter(([p])=>p.startsWith('openswing/')).map(([p,h])=>[path.basename(p),h]));
  const names=(await readdir(path.join(root,'openswing'))).filter(n=>n.endsWith('.py')).sort();assert.deepEqual(names,Object.keys(audit.modules).sort());
  for(const name of names)for(const dir of ['openswing','public/kernel','dist/kernel'])check(dir+'/'+name,sha(await readFile(path.join(root,dir,name)))===audit.modules[name]);
  const solver=await readFile(path.join(root,'openswing/linear_dynamics.py'),'utf8');
  assert(solver.includes("    if matrices:\n        result['matrices'] = dict(A=(a.toarray() if issparse(a) else a).tolist(),\n                                  M=(m.toarray() if issparse(m) else m).tolist())\n    return result"));
  const cases=[];
  for(const name of caseNames){
    const folder=path.join(study,name==='n64-over'?'streamed':'',name),plan=await readJSON(path.join(folder,'plan.json')),report=await readJSON(path.join(folder,'report.json'));
    assert(['PASS','PASS_DISCRETE_ANALYTICAL_CHECK'].includes(report.status));
    const native=await readJSON(path.join(folder,'result.json')),original=await readJSON(path.join(folder,'request.json'));
    assert.equal(Boolean(native.matrices?.A&&native.matrices?.M),original.modes.matrices);
    // The independent native audit checks the retained full pencils. Release
    // these diagnostic arrays before launching Chromium; this browser request
    // explicitly asks for physical results without the optional matrix export.
    delete native.matrices;
    const input=structuredClone(original);input.modes.matrices=false;
    if(!Object.hasOwn(input,'strut_mode')){
      const bridge=await readFile(path.join(root,'openswing/bridge.py'),'utf8');
      assert(bridge.includes("strut_mode=request.get('strut_mode', 'bilateral')"));
      input.strut_mode='bilateral';
    }
    assert.deepEqual(input,{...original,strut_mode:original.strut_mode??'bilateral',modes:{...original.modes,matrices:false}});
    const record={name,native_pins:await Promise.all(['plan.json','report.json','request.json','result.json'].map(p=>pin(path.join(folder,p)))),
      expected_unstable:plan.reference?plan.reference.grid_stiffness<0:plan.load>plan.discrete_critical_load,
      explicit_default_strut_mode:!Object.hasOwn(original,'strut_mode')};
    await mkdir(path.join(output,name));await save(name+'/expected-request.json',input);
    audit.cases.push(record);cases.push({name,native,input,record});
  }
  const serveRoot=path.join(root,'dist'),mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.css':'text/css','.svg':'image/svg+xml','.woff2':'font/woff2'};
  audit.built_assets=await Promise.all(['index.html',...(await readdir(path.join(serveRoot,'assets'))).map(n=>'assets/'+n)].map(n=>pin(path.join(serveRoot,n))));
  server=createServer(async(req,res)=>{try{
    const rel=decodeURIComponent(new URL(req.url,'http://local').pathname),file=path.resolve(serveRoot,'.'+(rel==='/'?'/index.html':rel));assert(file.startsWith(serveRoot+path.sep));
    const s=await stat(file);assert(s.isFile());res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream','Content-Length':s.size});createReadStream(file).pipe(res);
  }catch{res.writeHead(404);res.end('Not found');}});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));audit.url=`http://127.0.0.1:${server.address().port}`;
  browser=await chromium.launch({headless:true,executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE||path.join(root,'artifacts/isae/browser-libs-20261101/chromium/chrome-linux/chrome'),
    args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-webgl','--js-flags=--max-old-space-size=192']});
  timer=setTimeout(()=>{audit.timeout=true;browser.close().catch(()=>{});},570000);
  const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
  await context.route(/^https?:/,route=>{if(new URL(route.request().url()).origin===audit.url)return route.continue();audit.external_requests.push(route.request().url());return route.abort();});
  context.on('requestfailed',r=>audit.network_failures.push({url:r.url(),failure:r.failure()}));
  context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))audit.offline_requests.push(r.url());});
  page=await context.newPage();page.setDefaultTimeout(60000);page.on('pageerror',e=>audit.page_errors.push(e.message));
  await page.addInitScript(()=>{window.referenceRequests=[];const W=window.Worker;window.Worker=class extends W{postMessage(m,...rest){window.referenceRequests.push(structuredClone(m));return super.postMessage(m,...rest);}};});
  await page.goto(audit.url);await expect(page.locator('#solve')).toBeEnabled({timeout:180000});
  // CSS font faces are lazy: a weight first used by a result can otherwise
  // request its bundled file after disconnection. Complete resource loading
  // before testing offline execution, without exempting any later requests.
  audit.fonts=await page.evaluate(async()=>{
    const faces=[...document.fonts];await Promise.all(faces.map(face=>face.load()));
    await document.fonts.ready;
    return faces.map(face=>({family:face.family,weight:face.weight,status:face.status}));
  });
  check('bundled fonts ready before disconnect',audit.fonts.length>0&&audit.fonts.every(face=>face.status==='loaded'));
  audit.startup_seconds=(performance.now()-began)/1000;
  await context.setOffline(true);offline=true;
  const download=async(id,name)=>{const event=page.waitForEvent('download');await page.locator('#'+id).click();const bytes=await readFile(await(await event).path());await writeFile(path.join(output,name),bytes);return bytes;};
  await page.locator('details').evaluateAll(nodes=>nodes.forEach(n=>n.open=true));
  const empty={format:'openswing-project',version:2,name:'Euler column analytical verification',selected:null,cases:[],solutions:[],selected_solution:null};
  await page.locator('#project-file').setInputFiles({name:'empty.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(empty))});
  await expect(page.locator('#project-status')).toContainText('Project opened.');
  for(const {name,native,input,record} of cases){
    await page.locator('details').evaluateAll(nodes=>nodes.forEach(n=>n.open=true));
    await page.locator('#file').setInputFiles({name:'euler-column.asw',mimeType:'text/plain',buffer:Buffer.from(input.source)});
    await expect(page.locator('#editor')).toHaveValue(input.source);await expect(page.locator('#solve')).toBeEnabled();
    await page.locator('#node-file').setInputFiles({name:'mesh.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({format:'openswing-mesh',version:1,panels:input.panels}))});
    await page.waitForFunction(()=>!document.querySelector('#node-file').value);await expect(page.locator('#solve')).toBeEnabled();
    await page.locator('#mode').selectOption('modes');
    await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill(String(input.modes.gravity_magnitude));
    for(const [key,axes] of [['position',['x','y','z']],['attitude',['bank','elevation','heading']]])for(const [i,axis] of axes.entries())await page.locator('#'+(key==='position'?'position-earth':key)+'-'+axis).fill(String(input.modes[key][i]));
    for(const [id,value] of Object.entries({'modal-count':input.modes.count,'modal-shift-real':input.modes.shift[0],'modal-shift-imag':input.modes.shift[1],'modal-step':input.modes.step,'modal-rank':input.modes.rank_tolerance}))await page.locator('#'+id).fill(String(value));
    await page.locator('#modal-method').selectOption('full_shift_invert');await page.locator('#modal-matrices').uncheck();
    await page.locator('#structural-equations').selectOption('aswing-vacuum');await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();
    const countBefore=await page.evaluate(()=>window.referenceRequests.filter(r=>r.request?.action==='modes').length);
    console.log('BEGIN offline column solve '+name);const start=performance.now();await page.locator('#solve').click();
    await expect(page.locator('#result-state')).toHaveText('Modal base equilibrium',{timeout:180000});await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();
    record.solve_seconds=(performance.now()-start)/1000;
    const bytes=await download('export-json',name+'/result.json'),result=JSON.parse(bytes);
    assert.deepEqual(result.request,input);assert.deepEqual(result.software_provenance.modules,audit.modules);assert(!Object.hasOwn(result,'matrices'));
    check(name+' converged base',result.converged&&result.base.converged&&result.base.residual<=audit.gates.base);
    record.base_parity=compare(native.base,result.base,'base');check(name+' complete base parity',true,record.base_parity);
    for(const key of ['analysis','frame_mode','vacuum','numerics','structural_operator','limitations','controller','rom_output_catalog'])compare(native[key],result[key],key);
    assert.equal(result.diagnostics.method,'full_shift_invert');assert.equal(result.diagnostics.arnoldi.factorizations,1);assert.equal(result.diagnostics.finite_dimension,null);
    assert.equal(result.modes.length,native.modes.length);const unused=new Set(native.modes.map((_,i)=>i));record.modes=[];
    for(const [index,expected] of native.modes.entries()){
      const j=[...unused].sort((a,b)=>Math.hypot(...result.modes[a].eigenvalue.map((v,k)=>v-expected.eigenvalue[k]))-Math.hypot(...result.modes[b].eigenvalue.map((v,k)=>v-expected.eigenvalue[k])))[0];unused.delete(j);
      const actual=result.modes[j];compare(expected.eigenvalue,actual.eigenvalue,'pole');
      for(const key of ['stability','frequency','damping_ratio','exact_integrator','constitutive_relaxation'])compare(expected[key],actual[key],key);
      for(const side of ['right','left'])assert(actual[side+'_backward_error']<=audit.gates.backward);
      const physical=physicalPivot(expected),eTip=component(expected,physical),aTip=component(actual,physical),outputParity=compare(normalized(expected.output,eTip),normalized(actual.output,aTip),'modal.output');
      const rightParity=compare(normalized(expected.right,eTip),normalized(actual.right,aTip),'modal.right');
      const pivot=expected.left.real.reduce((best,v,k)=>Math.hypot(v,expected.left.imag[k])>Math.hypot(expected.left.real[best],expected.left.imag[best])?k:best,0);
      const leftParity=compare(normalized(expected.left,[expected.left.real[pivot],expected.left.imag[pivot]]),normalized(actual.left,[actual.left.real[pivot],actual.left.imag[pivot]]),'modal.left');
      record.modes.push({native_index:index,browser_index:j,normalization_component:physical,eigenvalue:actual.eigenvalue,stability:actual.stability,output_parity:outputParity,right_parity:rightParity,left_parity:leftParity});
    }
    check(name+' all physical modal outputs and vectors agree after arbitrary phase normalization',true);
    check(name+' expected growing-mode classification',result.modes.some(m=>m.stability==='unstable')===record.expected_unstable);
    await page.locator('#tab-modes').click();await expect(page.locator('#modal-roots svg')).toBeVisible();await page.locator('#modal-quantity').selectOption('nodes.displacement.2');await expect(page.locator('#modal-plot svg')).toBeVisible();
    await page.locator('#project-case-name').fill(name+' analytical column');await page.locator('#project-add').click();await expect(page.locator('#project-status')).toContainText('New case saved.');
    const solutionName=name+' computed column modes';await page.locator('#project-solution-name').fill(solutionName);await page.locator('#project-save-solution').click();await expect(page.locator('#project-status')).toContainText('Computed solution saved.');
    const projectBytes=await download('project-export',name+'/project.json'),project=JSON.parse(projectBytes);assert.deepEqual(project.solutions.at(-1).data,result);
    await page.locator('#project-file').setInputFiles({name:'column-project.json',mimeType:'application/json',buffer:projectBytes});await expect(page.locator('#project-status')).toContainText('Project opened.');await page.locator('#project-load-solution').click();await expect(page.locator('#project-status')).toContainText('Opened '+solutionName+'.');
    check(name+' result restores byte-exactly',Buffer.compare(bytes,await download('export-json',name+'/reopened-result.json'))===0);
    check(name+' project restores byte-exactly',Buffer.compare(projectBytes,await download('project-export',name+'/reopened-project.json'))===0);
    assert.equal(await page.evaluate(()=>window.referenceRequests.filter(r=>r.request?.action==='modes').length),countBefore+1);
    record.result=await pin(path.join(output,name,'result.json'));record.project=await pin(path.join(output,name,'project.json'));record.status='PASS';
    await page.screenshot({path:path.join(output,name,'desktop.png')});console.log(JSON.stringify({case:name,status:'PASS',solve_seconds:record.solve_seconds,base_parity:record.base_parity}));
  }
  await page.locator('details').evaluateAll(nodes=>nodes.forEach(n=>n.open=false));await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
  check('mobile width',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(output,'mobile.png')});
  const requests=wire(await page.evaluate(()=>window.referenceRequests));await save('requests.json',requests);
  const physical=requests.filter(r=>['solve','modes','frequency','time','launch_time','resume_time','rom','stability'].includes(r.request?.action));
  check('exactly '+cases.length+' cold modal requests; no restore solves',physical.length===cases.length&&physical.every(r=>r.request.action==='modes'));
  physical.forEach((r,i)=>assert.deepEqual(r.request,cases[i].input));
  for(const p of [audit.script,...audit.built_assets,...audit.cases.flatMap(c=>c.native_pins)])assert.equal((await pin(p.path)).sha256,p.sha256);
  for(const key of ['page_errors','network_failures','external_requests','offline_requests'])check(key+' absent',audit[key].length===0);
  audit.status='PASS_OFFLINE_COLUMN_BUCKLING_AND_PROJECTS';
}catch(error){
  audit.status='FAILURE_RETAINED';audit.error={message:error.message,stack:error.stack};process.exitCode=1;console.error(error.stack);
  try{if(page&&!page.isClosed()){await save('requests-at-failure.json',wire(await page.evaluate(()=>window.referenceRequests)));await page.screenshot({path:path.join(output,'failure.png')});}}catch{}
}finally{
  clearTimeout(timer);await browser?.close();server?.closeAllConnections();if(server?.listening)await new Promise(resolve=>server.close(resolve));
  audit.total_seconds=(performance.now()-began)/1000;audit.check_counts={passed:audit.checks.filter(c=>c.passed).length,total:audit.checks.length};
  await save('report.json',audit);console.log(JSON.stringify({status:audit.status,checks:audit.check_counts,total_seconds:audit.total_seconds}));
}
