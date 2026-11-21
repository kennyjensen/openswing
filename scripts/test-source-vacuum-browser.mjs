// One offline built-UI source vacuum/still-air/moving modal solve. No equilibrium/eigenvalue work is done in Node.
// node scripts/test-source-vacuum-browser.mjs NEW_OUTPUT_DIR COMPLETED_NATIVE_DIR
import {chromium} from 'playwright';
import {expect} from '@playwright/test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {createReadStream} from 'node:fs';
import {readFile,writeFile,readdir,mkdir,stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {numericalSelection} from '../web/numerical-policy.js';

// Scaled sum of squares avoids overflow/underflow and function-argument limits
// when a real aircraft's full descriptor matrix has hundreds of thousands of entries.
function euclideanNorm(rows){
  let scale=0,squares=1;
  for(const row of rows)for(const value of row){
    assert(Number.isFinite(value),'finite norm input');const x=Math.abs(value);
    if(x===0)continue;
    if(scale<x){squares=1+squares*(scale/x)**2;scale=x;}
    else squares+=(x/scale)**2;
  }
  return scale===0?0:scale*Math.sqrt(squares);
}
if(process.argv.length===3&&process.argv[2]==='--norm-self-test'){
  const ones=Array.from({length:1024},()=>Array(1024).fill(1));
  assert.equal(euclideanNorm(ones),1024);
  assert.equal(euclideanNorm([[0,0],[0,0]]),0);
  for(const scale of [1,1e200,1e-200])assert(Math.abs(euclideanNorm([[3*scale],[-4*scale]])/(5*scale)-1)<4*Number.EPSILON);
  console.log(JSON.stringify({status:'PASS_NORM_ONLY',checks:5,large_matrix_entries:1024**2,browser_runs:0,physics_calls:0}));
  process.exit(0);
}

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
assert.equal(process.argv.length,4,'Supply a new output directory and completed native baseline directory.');
const output=path.resolve(process.argv[2]),nativeStage=path.resolve(process.argv[3]);
await mkdir(output,{recursive:false});
const sha=b=>createHash('sha256').update(b).digest('hex');
const pin=async p=>{const b=await readFile(p);return {path:p,bytes:b.length,sha256:sha(b)};};
const wire=value=>JSON.parse(JSON.stringify(value)); // Worker messages can have undefined JS properties.
const audit={status:'PREPARING',planned_solves:1,checks:[],page_errors:[],offline_requests:[],external_requests:[],network_failures:[],
  scope:'Offline source-modal verification; case scope and returned spectrum coverage are read from the pinned native plan.',
  gates:{absolute:2e-8,relative:2e-8},
  exclusions:['base.evaluations'],
  exclusions_reason:'Execution counter only within base comparison. Eigenvectors and complex modal outputs have arbitrary phase/scale and are not compared componentwise; each full eigenvector is checked against its own full A/M pencil.',
  duration_cap_seconds:300};
const check=(name,ok,details={})=>{audit.checks.push({name,passed:!!ok,...details});assert(ok,name);};
function compare(expected,actual,start=''){
  const summary={numeric:0,leaves:0,max_absolute:0,max_fraction:0,worst:null};
  function visit(e,a,p){
    if(audit.exclusions.includes(p))return;
    if(typeof e==='number'){
      assert.equal(typeof a,'number',p);assert(Number.isFinite(a)&&Number.isFinite(e),p);
      const d=Math.abs(a-e),limit=audit.gates.absolute+audit.gates.relative*Math.abs(e);
      summary.numeric++;summary.leaves++;summary.max_absolute=Math.max(summary.max_absolute,d);
      if(d/limit>summary.max_fraction)Object.assign(summary,{max_fraction:d/limit,worst:p});
      assert(d<=limit,`${p}: numerical parity ${d} > ${limit}`);
    }else if(Array.isArray(e)){
      assert(Array.isArray(a)&&a.length===e.length,p);e.forEach((v,i)=>visit(v,a[i],`${p}[${i}]`));
    }else if(e!==null&&typeof e==='object'){
      assert(a!==null&&typeof a==='object',p);
      for(const [k,v] of Object.entries(e)){assert(Object.hasOwn(a,k),p+'.'+k);visit(v,a[k],p?p+'.'+k:k);}
    }else{summary.leaves++;assert.deepEqual(a,e,p);}
  }
  visit(expected,actual,start);return summary;
}

// Independent saved-array algebra: A v = lambda M v and A^T y = conjugate(lambda) M^T y.
// Frobenius matrix norms make the dimensionless backward bound explicit and reproducible.
function pencilResiduals(result,gate){
  const {A,M}=result.matrices,n=A.length;
  for(const matrix of [A,M])assert(matrix.length===n&&matrix.every(row=>Array.isArray(row)&&row.length===n&&row.every(Number.isFinite)),'finite square A/M');
  const anorm=euclideanNorm(A),mnorm=euclideanNorm(M);
  function residual(mode,side){
    const vector=mode[side],lambda=mode.eigenvalue;
    assert(Array.isArray(lambda)&&lambda.length===2&&lambda.every(Number.isFinite),'finite eigenvalue');
    for(const part of ['real','imag'])assert(vector[part].length===n&&vector[part].every(Number.isFinite),'full finite '+side+' eigenvector');
    const lr=lambda[0],li=side==='left'?-lambda[1]:lambda[1],r=[],i=[];
    for(let row=0;row<n;row++){
      let ar=0,ai=0,mr=0,mi=0;
      for(let col=0;col<n;col++){
        const a=side==='left'?A[col][row]:A[row][col],m=side==='left'?M[col][row]:M[row][col];
        ar+=a*vector.real[col];ai+=a*vector.imag[col];mr+=m*vector.real[col];mi+=m*vector.imag[col];
      }
      r.push(ar-lr*mr+li*mi);i.push(ai-lr*mi-li*mr);
    }
    const vectorNorm=euclideanNorm([vector.real,vector.imag]),residualNorm=euclideanNorm([r,i]);
    const denominator=(anorm+Math.hypot(...lambda)*mnorm)*vectorNorm;
    assert(Number.isFinite(denominator)&&denominator>0,'nonzero full-pencil normalization');
    const backward=residualNorm/denominator;assert(Number.isFinite(backward)&&backward<=gate,`${side} full-pencil backward error ${backward}`);
    return {backward_error:backward,residual_norm:residualNorm,vector_norm:vectorNorm,denominator};
  }
  return {dimension:n,matrix_norm:'Frobenius',A_norm:anorm,M_norm:mnorm,gate,
    modes:result.modes.map((mode,index)=>({index,eigenvalue:mode.eigenvalue,right:residual(mode,'right'),left:residual(mode,'left')}))};
}
function matchSpectrum(expected,actual,absolute,relative,label='returned spectrum'){
  assert.equal(actual.length,expected.length,label+' length');
  const candidates=expected.map((mode,index)=>{
    const lambda=mode.eigenvalue,limit=absolute+relative*Math.hypot(...lambda);
    const matches=actual.flatMap((candidate,j)=>{
      const distance=Math.hypot(candidate.eigenvalue[0]-lambda[0],candidate.eigenvalue[1]-lambda[1]);
      return distance<=limit?[{native_index:index,browser_index:j,native_eigenvalue:lambda,browser_eigenvalue:candidate.eigenvalue,distance,limit}]:[];
    });
    assert(matches.length>0,`eigenvalue candidate for native mode ${index}`);
    return matches.sort((a,b)=>a.distance-b.distance);
  });
  // Bipartite matching retains the multiplicity of repeated relaxation poles.
  // Their arbitrary eigenvectors are independently checked against each pencil.
  const owners=new Map();
  function assign(i,seen){
    for(const edge of candidates[i]){
      const j=edge.browser_index;if(seen.has(j))continue;seen.add(j);
      if(!owners.has(j)||assign(owners.get(j),seen)){owners.set(j,i);return true;}
    }
    return false;
  }
  expected.forEach((_,i)=>assert(assign(i,new Set()),'one-to-one '+label+' including multiplicity'));
  return [...owners.entries()].map(([j,i])=>candidates[i].find(e=>e.browser_index===j)).sort((a,b)=>a.native_index-b.native_index);
}

// This branch checks a local full-pencil search, not a finite-dimension census.
// Iteration counts and left-recovery choices may differ between native and WASM.
function localArnoldiDiagnostics(result,origin){
  const d=result.diagnostics,n=result.matrices.A.length,settings=d.arnoldi,deflation=d.integrator_deflation;
  assert.equal(d.method,'full_shift_invert');assert.equal(d.requested_method,'full_shift_invert');
  for(const key of ['finite_dimension','eliminated_dimension','finite_spectrum','rank_tolerance']){
    assert(Object.hasOwn(d,key),origin+' explicit '+key);assert.equal(d[key],null,origin+' unclassified '+key);
  }
  assert.deepEqual(d.right_reduction,[]);assert.equal(d.full_dimension,n);
  assert.equal(deflation.count,0);assert.deepEqual(deflation.operations,[]);
  const indices=Array.from({length:n},(_,i)=>i);
  assert.deepEqual(deflation.retained_rows,indices);assert.deepEqual(deflation.retained_columns,indices);
  assert.equal(deflation.original_A_nullity_estimate,null);assert.equal(deflation.quotient_finite_dimension,null);
  assert(result.modes.every(mode=>mode.exact_integrator===false),'local roots do not claim certified integrator factors');
  assert.equal(settings.retained_dimension,n);assert.equal(settings.mass_rank_reduction,false);
  assert.equal(settings.factorizations,1);assert.equal(settings.arpack_mode,1);assert.equal(settings.bmat,'I');assert.equal(settings.which,'LM');
  assert(Number.isInteger(settings.operator_applications)&&settings.operator_applications>0);
  assert(Number.isFinite(settings.solve_backward_gate)&&settings.solve_backward_gate>0&&settings.solve_backward_gate<=1e-10);
  assert(Number.isFinite(settings.maximum_solve_backward_error)&&settings.maximum_solve_backward_error>=0&&settings.maximum_solve_backward_error<=settings.solve_backward_gate);
  const records=d.inverse_iteration,counts=d.left_recovery_counts;
  assert(Array.isArray(records)&&records.length===result.modes.length,'one left-recovery record per returned root');
  for(const [i,record] of records.entries()){
    assert.deepEqual(record.eigenvalue,result.modes[i].eigenvalue);
    assert(['PASS','FAIL','NOT_ATTEMPTED'].includes(record.status));assert.equal(typeof record.reason,'string');
    if(record.status==='PASS'){
      assert.equal(record.factorizations,1);assert(Number.isInteger(record.iterations)&&record.iterations>0);
      assert.equal(record.linear_solves,record.iterations);
      assert(Number.isFinite(record.left_backward_error)&&record.left_backward_error<=record.backward_gate&&record.backward_gate<=1e-10);
      assert(Number.isFinite(record.mass_pairing_error)&&record.mass_pairing_error<=record.pairing_gate&&record.pairing_gate<=1e-10);
    }else if(record.status==='NOT_ATTEMPTED')assert.equal(record.reason,'repeated_selected_pole');
  }
  assert.equal(counts.inverse_iteration,records.filter(r=>r.status==='PASS').length);
  assert.equal(counts.inverse_iteration_failed,records.filter(r=>r.status==='FAIL').length);
  assert.equal(counts.repeated_pole_fallback,records.filter(r=>r.status==='NOT_ATTEMPTED').length);
  if(records.some(r=>r.status!=='PASS'))assert(counts.schur_pencils>0||counts.nullspace_fallback>0,'explicit original-pencil fallback');

  // Independently form the physical selected-space W^H M V. Repeated vectors
  // need not have the same arbitrary basis in the two runtimes.
  const mv=result.modes.map(({right:v})=>({
    real:result.matrices.M.map(row=>row.reduce((sum,x,j)=>sum+x*v.real[j],0)),
    imag:result.matrices.M.map(row=>row.reduce((sum,x,j)=>sum+x*v.imag[j],0))}));
  let diagonal=0,offDiagonal=0;
  for(const [i,{left:w}] of result.modes.entries())for(const [j,v] of mv.entries()){
    let re=0,im=0;
    for(let k=0;k<n;k++){re+=w.real[k]*v.real[k]+w.imag[k]*v.imag[k];im+=w.real[k]*v.imag[k]-w.imag[k]*v.real[k];}
    const defect=Math.hypot(re-(i===j?1:0),im);assert(Number.isFinite(defect));
    if(i===j)diagonal=Math.max(diagonal,defect);else offDiagonal=Math.max(offDiagonal,defect);
  }
  const pairing=d.biorthogonality;
  assert(pairing&&typeof pairing.verified==='boolean'&&Array.isArray(pairing.repeated_clusters));
  assert(Number.isFinite(pairing.gate)&&pairing.gate>0&&pairing.gate<=1e-8);
  for(const [key,actual] of [['diagonal_error',diagonal],['off_diagonal_error',offDiagonal]]){
    assert(Number.isFinite(pairing[key])&&pairing[key]>=0);
    assert(Math.abs(actual-pairing[key])<=1e-11+1e-8*Math.abs(pairing[key]),origin+' independent '+key);
  }
  if(pairing.verified){
    assert(result.modes.every(mode=>mode.biorthogonal_normalized));
    assert(Math.max(diagonal,offDiagonal)<=pairing.gate,origin+' independently verified selected-space pairing');
  }
  return {scope:d.spectrum_scope,arnoldi:settings,integrator_deflation:deflation,
    inverse_iteration:records,left_recovery_counts:counts,biorthogonality:pairing,
    independently_measured_pairing:{diagonal_error:diagonal,off_diagonal_error:offDiagonal}};
}

let browser,server,page,timer;let offline=false;const started=performance.now();
try{
  const planPath=path.join(nativeStage,'plan.json'),reportPath=path.join(nativeStage,'report.json'),requestPath=path.join(nativeStage,'request.json'),resultPath=path.join(nativeStage,'result.json');
  const plan=JSON.parse(await readFile(planPath)),nativeReport=JSON.parse(await readFile(reportPath)),input=JSON.parse(await readFile(requestPath)),native=JSON.parse(await readFile(resultPath));
  check('native baseline passed',nativeReport.status.startsWith('PASS'));
  const stillAir=input.numerics?.structural_operator==='drela-fixed-still-air-v1';
  const moving=input.numerics?.structural_operator==='drela-moving-vacuum-v1';
  const selection=moving?'aswing-moving-vacuum':stillAir?'aswing-still-air':'aswing-vacuum',medium=stillAir?'still air':moving?'moving vacuum':'vacuum';
  const method=input.modes.method,localSearch=method==='full_shift_invert';
  assert(['dense','full_shift_invert'].includes(method),'supported native modal method');
  const caseOptions=plan.browser_case??{},returnedCount=plan.expected_returned_count??(localSearch?input.modes.count:plan.expected_finite_dimension);
  const finiteDimension=Object.hasOwn(plan,'expected_finite_dimension')?plan.expected_finite_dimension:native.diagnostics.finite_dimension;
  assert(Number.isInteger(returnedCount)&&returnedCount>0,'positive declared returned root count');
  if(localSearch)assert.equal(finiteDimension,null,'local search must not declare a finite dimension');
  else assert(Number.isInteger(finiteDimension)&&finiteDimension>=returnedCount,'classified finite dimension contains returned roots');
  assert.equal(native.modes.length,returnedCount);assert.equal(native.diagnostics.finite_dimension,finiteDimension);
  const completeSpectrum=!localSearch&&returnedCount===finiteDimension,spectrumLabel=completeSpectrum?'complete finite spectrum':localSearch?'local returned spectrum':'selected returned spectrum';
  assert.equal(native.diagnostics.method,method);audit.modal_method=method;
  if(localSearch)audit.local_arnoldi={native:localArnoldiDiagnostics(native,'native')};
  const solveTimeoutMs=caseOptions.solve_timeout_ms??120000,totalTimeoutMs=caseOptions.total_timeout_ms??300000;
  assert(Number.isFinite(solveTimeoutMs)&&solveTimeoutMs>0&&Number.isFinite(totalTimeoutMs)&&totalTimeoutMs>15000&&solveTimeoutMs<totalTimeoutMs,'bounded browser timeouts');
  audit.duration_cap_seconds=totalTimeoutMs/1000;audit.solve_cap_seconds=solveTimeoutMs/1000;
  audit.expected_returned_count=returnedCount;audit.expected_finite_dimension=finiteDimension;
  audit.complete_spectrum_returned=completeSpectrum;
  assert.deepEqual(input.numerics,{beam_interpolation:'drela-segspl-v1',structural_operator:moving?'drela-moving-vacuum-v1':stillAir?'drela-fixed-still-air-v1':'drela-fixed-vacuum-v1'});
  assert.equal(input.action,'modes');assert.equal(input.mode,'modes');assert.equal(input.condition,null);
  if(moving)assert(['fixed','prescribed','free','mixed'].includes(input.modes.frame));
  else assert.equal(input.modes.frame,'fixed');
  assert.equal(input.modes.vacuum,!stillAir);
  assert.equal(input.modes.count,returnedCount);assert.equal(input.modes.matrices,true);
  for(const name of ['position','attitude','shift'])assert(Array.isArray(input.modes[name])&&input.modes[name].length===(name==='shift'?2:3)&&input.modes[name].every(Number.isFinite),'finite native modal '+name);
  assert(Number.isFinite(input.modes.gravity_magnitude)&&input.modes.gravity_magnitude>=0,'explicit native gravity magnitude');
  check('native cold modal request',!Object.hasOwn(input,'initial_state')&&!Object.hasOwn(input.modes,'initial_state'));
  for(const key of ['controller','derivatives','operating_constraints','strut_mode','gravity','equilibrium_state'])assert(!Object.hasOwn(input,key),'unexpected native request field '+key);
  if(stillAir){
    check('explicit positive native fluid density',typeof input.modes.quiescent_density==='number'&&Number.isFinite(input.modes.quiescent_density)&&input.modes.quiescent_density>0);
  }else assert(!Object.hasOwn(input.modes,'quiescent_density'));
  audit.scope=caseOptions.scope??plan.scope??`Synthetic fixed-frame source ${medium} modal case; not archived ASWING agreement.`;
  audit.scope+=` Browser verification compares the full native base and A/M matrices, ${spectrumLabel} including multiplicities, and each returned left/right full-pencil residual. Native/browser parity does not establish archived ASWING agreement.`;
  const meshBeams=native.base.mesh_discretization?.beams;
  const nodeCounts=meshBeams?Object.fromEntries(meshBeams.map(beam=>[String(beam.beam),beam.nodes.length])):
    Object.fromEntries(native.base.geometry.map(beam=>[String(beam.index),native.base.nodes.filter(node=>node.beam===beam.index).length]));
  assert(Object.keys(nodeCounts).length>0&&Object.values(nodeCounts).every(count=>Number.isInteger(count)&&count>0),'native per-beam applied node counts');
  audit.native_mesh={request:input.panels,structural_elements:native.base.structural_elements,structural_nodes:native.base.structural_nodes,node_counts:nodeCounts};
  if(plan.expected_structural_nodes!=null)assert.equal(native.base.structural_nodes,plan.expected_structural_nodes);
  if(plan.expected_structural_elements!=null)assert.equal(native.base.structural_elements,plan.expected_structural_elements);
  const sourceFile=path.resolve(root,plan.source_file??'examples/source-vacuum-check.asw');
  assert.equal(input.source,await readFile(sourceFile,'utf8'));
  if(plan.source_sha256)assert.equal(sha(Buffer.from(input.source)),plan.source_sha256);
  audit.policy=input.numerics;audit.gates.pencil=plan.pencil_backward_gate;audit.gates.base_residual=plan.base_residual_gate;
  audit.inputs=await Promise.all([planPath,reportPath,requestPath,resultPath,sourceFile,fileURLToPath(import.meta.url),path.join(root,'web/numerical-policy.js'),path.join(root,'web/saved-state-data.js')].map(pin));
  const compatibilityProjects=(stillAir||localSearch)?['examples/source-vacuum-check-project.json','examples/source-vacuum-damped-check-project.json','examples/pazy-isae-wall-half-project.json']:[];
  audit.inputs.push(...await Promise.all(compatibilityProjects.map(name=>pin(path.join(root,name)))));
  audit.native_report=nativeReport;audit.modules=plan.kernel_pins;
  const names=(await readdir(path.join(root,'openswing'))).filter(n=>n.endsWith('.py')).sort();
  assert.deepEqual(names,Object.keys(audit.modules).sort());audit.kernel_module_count=names.length;
  for(const name of names)for(const folder of ['openswing','public/kernel','dist/kernel'])check(folder+'/'+name,sha(await readFile(path.join(root,folder,name)))===audit.modules[name]);
  const serveRoot=path.join(root,'dist'),mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.css':'text/css','.svg':'image/svg+xml','.woff2':'font/woff2'};
  audit.built_assets=[];
  for(const name of ['index.html',...(await readdir(path.join(serveRoot,'assets'))).map(n=>'assets/'+n)])audit.built_assets.push(await pin(path.join(serveRoot,name)));
  server=createServer(async(req,res)=>{try{
    const rel=decodeURIComponent(new URL(req.url,'http://local').pathname),file=path.resolve(serveRoot,'.'+(rel==='/'?'/index.html':rel));
    assert(file.startsWith(serveRoot+path.sep));const s=await stat(file);assert(s.isFile());
    res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream','Content-Length':s.size});createReadStream(file).pipe(res);
  }catch{res.writeHead(404);res.end('Not found');}});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));audit.url=`http://127.0.0.1:${server.address().port}`;
  timer=setTimeout(()=>{audit.timeout=true;browser?.close().catch(()=>{});},Math.max(1,totalTimeoutMs-15000-(performance.now()-started)));
  const executable=process.env.OPENSWING_CHROMIUM_EXECUTABLE||'/tmp/aswing-chromium/chrome-linux/chrome';
  const args=process.env.OPENSWING_WEBGL_DRIVER==='mesa'?['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native','--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'];
  audit.browser_environment=Object.fromEntries(['LD_LIBRARY_PATH','VK_ICD_FILENAMES','OPENSWING_WEBGL_DRIVER','LP_NUM_THREADS'].map(k=>[k,process.env[k]??null]));
  browser=await chromium.launch({headless:true,executablePath:executable,args,timeout:30000});audit.chromium=browser.version();
  const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
  await context.route('**/*',async route=>{
    const url=route.request().url();if(/^https?:/.test(url)&&new URL(url).origin!==audit.url){audit.external_requests.push(url);await route.abort();}else await route.continue();
  });
  page=await context.newPage();page.setDefaultTimeout(45000);
  page.on('pageerror',e=>audit.page_errors.push(e.message));
  context.on('requestfailed',r=>audit.network_failures.push({url:r.url(),failure:r.failure()}));
  context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))audit.offline_requests.push(r.url());});
  await page.addInitScript(()=>{
    window.referenceRequests=[];window.referenceEvents=[];const W=window.Worker;
    window.Worker=class extends W{constructor(...a){super(...a);this.addEventListener('message',e=>{if(e.data?.type==='progress'||e.data?.progress||e.data?.stage)window.referenceEvents.push(structuredClone(e.data));});}postMessage(m,...rest){window.referenceRequests.push(structuredClone(m));return super.postMessage(m,...rest);}};
  });
  await page.goto(audit.url);await expect(page.locator('#solve')).toBeEnabled({timeout:180000});audit.startup_seconds=(performance.now()-started)/1000;
  if(localSearch){await expect(page.locator('#modal-method')).toHaveValue('full_shift_invert');check('fresh UI selects published shifted Arnoldi method',true);}
  await context.setOffline(true);offline=true;
  await page.locator('#file').setInputFiles({name:path.basename(sourceFile),mimeType:'text/plain',buffer:Buffer.from(input.source)});
  await expect(page.locator('#editor')).toHaveValue(input.source);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#node-file').setInputFiles({name:'source-modal-mesh.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({format:'openswing-mesh',version:1,panels:input.panels}))});
  await page.waitForFunction(()=>!document.querySelector('#node-file').value);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('modes');await page.locator('details').evaluateAll(nodes=>nodes.forEach(node=>node.open=true));
  // Fixed policy must still reject moving input before any worker solve.
  await page.locator('#rates-x').fill('1');const beforeGuard=await page.evaluate(()=>window.referenceRequests.length);
  await page.locator('#structural-equations').selectOption(moving?'aswing-vacuum':selection);
  await expect(page.locator('#structural-equations')).toHaveValue('midpoint');await expect(page.locator('#error')).toBeVisible();await expect(page.locator('#rates-x')).toHaveValue('1');
  check('unsafe source modal selection refused before worker request',(await page.evaluate(()=>window.referenceRequests.length))===beforeGuard);
  await page.locator('#rates-x').fill('0');
  if(stillAir){
    await page.locator('#modal-quiescent').check();
    await page.locator('#modal-quiescent-density').fill('0');
    const beforeDensityGuard=await page.evaluate(()=>window.referenceRequests.length);
    await page.locator('#structural-equations').selectOption(selection);
    await expect(page.locator('#structural-equations')).toHaveValue('midpoint');
    await expect(page.locator('#error')).toContainText('positive finite');
    check('invalid density selection refused before worker request',(await page.evaluate(()=>window.referenceRequests.length))===beforeDensityGuard);
    await page.locator('#modal-quiescent-density').fill(String(input.modes.quiescent_density));
  }
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill(String(input.modes.gravity_magnitude));
  for(const [group,key,axes] of [['position-earth','position',['x','y','z']],['attitude','attitude',['bank','elevation','heading']]])for(const [i,axis] of axes.entries())await page.locator('#'+group+'-'+axis).fill(String(input.modes[key][i]));
  await page.locator('#modal-count').fill(String(input.modes.count));await page.locator('#modal-method').selectOption(method);
  await page.locator('#modal-shift-real').fill(String(input.modes.shift[0]));await page.locator('#modal-shift-imag').fill(String(input.modes.shift[1]));
  await page.locator('#modal-step').fill(String(input.modes.step));await page.locator('#modal-rank').fill(String(input.modes.rank_tolerance));await page.locator('#modal-matrices').check();
  if(moving){
    await page.locator('#modal-frame').selectOption(input.modes.frame);
    await expect(page.locator('#modal-ordinary-frame')).toHaveValue(input.modes.frame);
    for(const [kind,values] of Object.entries(input.modes.motion))for(const [i,axis] of ['x','y','z'].entries())
      await page.locator('#'+kind+'-'+axis).fill(String(values[i]*(kind==='acceleration'?1:180/Math.PI)));
    for(const [quantity,target] of Object.entries(input.modes.load_targets??{})){
      const [group,axis]=quantity.split('.'),key=(group==='force'?'F':'M')+axis;
      await page.locator('#modal-load-'+key).selectOption('load');
      await page.locator('#modal-target-'+key).fill(String(target));
    }
  }
  await page.locator('#structural-equations').selectOption(selection);await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();
  if(moving)for(const [i,axis] of ['x','y','z'].entries())await page.locator('#moving-velocity-'+axis).fill(String(input.modes.velocity[i]));
  await expect(page.locator('#structural-equations')).toHaveValue(selection);await expect(page.locator('#modal-frame')).toHaveValue(input.modes.frame);
  await expect(page.locator('#modal-ordinary-frame')).toHaveValue(input.modes.frame);
  if(moving)await expect(page.locator('#modal-frame')).toBeEnabled();
  else await expect(page.locator('#modal-frame')).toBeDisabled();
  for(const id of ['modal-vacuum','modal-quiescent'])await expect(page.locator('#'+id)).toBeDisabled();
  await expect(page.locator('#modal-vacuum')).toBeChecked({checked:!stillAir});await expect(page.locator('#modal-quiescent')).toBeChecked({checked:stillAir});
  if(stillAir)await expect(page.locator('#modal-quiescent-density')).toHaveValue(String(input.modes.quiescent_density));
  await page.locator('#tab-nodes').click();
  for(const [beam,count] of Object.entries(nodeCounts)){
    await page.locator('#node-beam').selectOption(beam);await expect(page.locator('#node-table tbody tr')).toHaveCount(count);
    check('applied native node count on beam '+beam,true,{count});
  }
  const preSolve=await page.evaluate(()=>window.referenceRequests),inspected=preSolve.filter(r=>r.request?.action==='inspect').at(-1);
  assert.deepEqual(inspected.request.numerics,input.numerics);check('selected source policy inspected before solve',true);
  const physicalActions=['solve','modes','frequency','time','launch_time','resume_time','stability','rom','flow_survey'];
  check('no physical requests before sole modal solve',preSolve.every(r=>!physicalActions.includes(r.request?.action)));
  const begin=performance.now();console.log(`Starting sole offline source ${medium} modal solve.`);await page.locator('#solve').click();
  await expect(page.locator('#result-state')).toHaveText('Modal base equilibrium',{timeout:solveTimeoutMs});await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();audit.solve_seconds=(performance.now()-begin)/1000;
  async function download(id,name){const event=page.waitForEvent('download');await page.locator('#'+id).click();const bytes=await readFile(await(await event).path());await writeFile(path.join(output,name),bytes);return bytes;}
  const bytes=await download('export-json','result.json'),result=JSON.parse(bytes);
  assert.deepEqual(result.software_provenance.modules,audit.modules);assert.deepEqual(result.request,input);assert.deepEqual(result.numerics,input.numerics);
  check('exact native wire request and source policy',true);check('cold request without loaded seed',!Object.hasOwn(result.request,'initial_state')&&!Object.hasOwn(result.request.modes,'initial_state'));
  check(input.modes.frame+' '+medium+' returned roots and '+(localSearch?'unclassified':'classified')+' dimension',result.vacuum===!stillAir&&result.frame_mode===input.modes.frame&&result.modes.length===returnedCount&&result.diagnostics.finite_dimension===finiteDimension);
  assert.equal(result.diagnostics.method,method);
  if(localSearch){audit.local_arnoldi.browser=localArnoldiDiagnostics(result,'browser');check('native and browser retain full local Arnoldi scope and original-pencil diagnostics',true);}
  check('top and base operator match selected equations',result.structural_operator===input.numerics.structural_operator&&result.base.structural_operator===input.numerics.structural_operator);
  if(stillAir){
    const density=input.modes.quiescent_density,equilibrium=result.base.equilibrium_state;
    for(const [location,fluid] of [['top',result.fluid],['base',result.base.fluid]]){
      check(location+' explicit noncirculatory still-air density',fluid?.kind==='quiescent'&&fluid.density===density&&fluid.circulatory===false);
      assert.deepEqual(fluid.mean_velocity_body,[0,0,0]);assert.deepEqual(fluid.supported_analyses,['fixed_frame_modes']);
      assert.equal(fluid.structural_operator,input.numerics.structural_operator);
      check(location+' fluid is endpoint data, not an asserted aggregate tensor',fluid.apparent_properties.mass_tensor===null&&fluid.apparent_properties.spatial_matrix===null&&Array.isArray(fluid.apparent_properties.endpoint_coefficients));
    }
    check('base density identity and launch metadata retained without time permission',equilibrium.identity.quiescent_density===density&&equilibrium.launch.quiescent_density===density);
    for(const id of ['equilibrium-enable','equilibrium-use','equilibrium-open','equilibrium-save','rom-build','stability-build'])await expect(page.locator('#'+id)).toBeDisabled();
  }else check('vacuum result remains without fluid metadata',result.fluid==null&&result.base.fluid==null);
  check('base converged with unchanged gate',result.converged&&result.base.converged&&result.base.residual<=plan.base_residual_gate);
  check('exact native applied structural mesh counts',result.base.structural_elements===native.base.structural_elements&&result.base.structural_nodes===native.base.structural_nodes);
  audit.parity={base:compare(native.base,result.base,'base'),matrices:compare(native.matrices,result.matrices,'matrices')};
  const metadata=['analysis','converged','frame_mode','frame_load_targets','vacuum','limitations','controller','rom_output_catalog','numerics','structural_operator'];
  if(stillAir)metadata.push('fluid');
  audit.parity.metadata=compare(Object.fromEntries(metadata.map(k=>[k,native[k]])),result);
  for(const [name,summary] of Object.entries(audit.parity))check(name+' native parity',summary.max_fraction<=1,summary);
  audit.spectrum=matchSpectrum(native.modes,result.modes,audit.gates.absolute,audit.gates.relative,spectrumLabel);
  check('one-to-one '+spectrumLabel+' matching including multiplicity',audit.spectrum.length===returnedCount);
  const hasCensus=Object.hasOwn(native.diagnostics,'finite_spectrum');
  assert.equal(Object.hasOwn(result.diagnostics,'finite_spectrum'),hasCensus,'native/browser census availability');
  if(hasCensus){
    const expected=native.diagnostics.finite_spectrum,actual=result.diagnostics.finite_spectrum;
    if(expected===null){assert.equal(actual,null);audit.census=null;}
    else{
      assert(actual&&typeof actual==='object','browser finite census');
      assert.deepEqual(Object.keys(actual).sort(),Object.keys(expected).sort());assert.equal(actual.scope,expected.scope);
      for(const [origin,census] of [['native',expected],['browser',actual]]){
        assert(Array.isArray(census.eigenvalues)&&census.eigenvalues.length===finiteDimension,origin+' complete finite census dimension');
        assert(census.eigenvalues.every(value=>Array.isArray(value)&&value.length===2&&value.every(Number.isFinite)),origin+' finite census values');
      }
      audit.census={scope:expected.scope,units:'1/input T',finite_dimension:finiteDimension,
        matching:matchSpectrum(expected.eigenvalues.map(eigenvalue=>({eigenvalue})),actual.eigenvalues.map(eigenvalue=>({eigenvalue})),audit.gates.absolute,audit.gates.relative,'complete finite census')};
      check('complete finite census matching including multiplicity',audit.census.matching.length===finiteDimension);
    }
  }
  audit.pencil={native:pencilResiduals(native,plan.pencil_backward_gate),browser:pencilResiduals(result,plan.pencil_backward_gate)};
  for(const [origin,record] of Object.entries(audit.pencil))for(const mode of record.modes)for(const side of ['right','left'])check(`${origin} mode ${mode.index} ${side} full-pencil residual`,mode[side].backward_error<=plan.pencil_backward_gate,mode[side]);
  await writeFile(path.join(output,'spectrum-and-pencil.json'),JSON.stringify({matching:audit.spectrum,census:audit.census,pencil:audit.pencil,...(localSearch?{local_arnoldi:audit.local_arnoldi}:{})},null,2)+'\n');
  await page.locator('#tab-modes').click();await expect(page.locator('#modal-roots svg')).toBeVisible();await expect(page.locator('#modal-select option')).toHaveCount(returnedCount);
  const plotBeam=Number(caseOptions.plot_beam??native.base.geometry[0].index),plotQuantity=caseOptions.plot_quantity??'nodes.displacement.1';
  const [plotGroup,plotField,plotAxis]=plotQuantity.split('.');
  function plotValues(modalResult,index){
    return (modalResult.modes[index].output[plotGroup]??[]).flatMap(row=>{
      const station=plotGroup==='nodes'?modalResult.base.nodes.find(node=>node.index===row.index):row,value=row[plotField];
      if(station?.beam!==plotBeam||value==null)return [];
      const real=plotAxis==null?value.real:value.real[plotAxis],imag=plotAxis==null?value.imag:value.imag[plotAxis];
      assert(Number.isFinite(real)&&Number.isFinite(imag),'finite modal plot sample');return [Math.hypot(real,imag)];
    });
  }
  const availablePlots=native.modes.map((mode,index)=>{
    const values=plotValues(native,index);
    return {index,positive:mode.eigenvalue[1]>0,maximum:values.reduce((a,b)=>Math.max(a,b),0)};
  });
  // A display choice only: prefer a positive-frequency root with a visible
  // component over numerical leakage in an unrelated mode. No physical gate
  // or archive association depends on this arbitrary eigenvector amplitude.
  const preferredPlots=availablePlots.filter(entry=>entry.maximum>0).sort((a,b)=>Number(b.positive)-Number(a.positive)||b.maximum-a.maximum);
  const plotNativeIndex=caseOptions.plot_native_mode_index??preferredPlots[0]?.index??0;
  assert(Number.isInteger(plotNativeIndex)&&plotNativeIndex>=0&&plotNativeIndex<returnedCount,'declared modal plot index');
  const plotBrowserIndex=audit.spectrum.find(entry=>entry.native_index===plotNativeIndex).browser_index;
  const nativePlotValues=plotValues(native,plotNativeIndex),browserPlotValues=plotValues(result,plotBrowserIndex);
  check('selected modal plot has finite native and browser samples',nativePlotValues.length>0&&browserPlotValues.length===nativePlotValues.length);
  if(caseOptions.require_nonzero_plot??!completeSpectrum)check('selected modal plot is nonzero in both runtimes',nativePlotValues.some(value=>value>0)&&browserPlotValues.some(value=>value>0));
  audit.plot={beam:plotBeam,quantity:plotQuantity,native_mode_index:plotNativeIndex,browser_mode_index:plotBrowserIndex,native_eigenvalue:native.modes[plotNativeIndex].eigenvalue,browser_eigenvalue:result.modes[plotBrowserIndex].eigenvalue,nonzero_native:nativePlotValues.some(value=>value>0),nonzero_browser:browserPlotValues.some(value=>value>0)};
  await page.locator('#modal-select').selectOption(String(plotBrowserIndex));await page.locator('#modal-beam').selectOption(String(plotBeam));
  await page.locator('#modal-quantity').selectOption(plotQuantity);await expect(page.locator('#modal-plot svg')).toBeVisible();
  if(native.base.structure.strain_source==='source_discrete_damped_constitutive'){
    const strainQuantities=['sections.strain.1'];
    if((native.modes[plotNativeIndex].output.sensors??[]).some(sensor=>sensor.beam===plotBeam&&sensor.strain!=null))strainQuantities.push('sensors.strain.1');
    for(const quantity of strainQuantities){
      await page.locator('#modal-quantity').selectOption(quantity);await expect(page.locator('#modal-plot svg')).toBeVisible();
      check('damped modal strain renders '+quantity,true);
    }
    await page.locator('#tab-structure').click();await page.locator('#structure-quantity').selectOption('strain.1');
    await expect(page.locator('#structure-plot svg')).toBeVisible();
    await expect(page.locator('#structure-state')).toContainText('interval');
    check('damped interval structure plot renders with correct sampling description',true);
    await page.locator('#tab-modes').click();
  }
  await page.locator('#modal-quantity').selectOption(plotQuantity);
  await page.locator('#project-name').fill(caseOptions.project_name??`Source ${medium} modal verification`);await page.locator('#project-rename').click();
  await page.locator('#project-case-name').fill(caseOptions.case_name??`${native.base.structural_elements} applied intervals, ${input.modes.frame} ${medium}, gravity ${input.modes.gravity_magnitude}`);await page.locator('#project-add').click();
  const solutionName=caseOptions.solution_name??`Source ${medium} ${returnedCount}-root result`;
  await page.locator('#project-solution-name').fill(solutionName);await page.locator('#project-save-solution').click();await expect(page.locator('#project-load-solution')).toBeEnabled();
  const projectBytes=await download('project-export','project.json'),project=JSON.parse(projectBytes),saved=project.solutions.find(s=>s.name===solutionName);
  assert.deepEqual(saved.configuration.numerics,input.numerics);assert.deepEqual(saved.data.numerics,input.numerics);assert.deepEqual(saved.data,result);
  assert.equal(saved.configuration.fields['modal-method'],method);
  if(stillAir){
    assert.equal(saved.configuration.fields['modal-quiescent-density'],String(input.modes.quiescent_density));
    assert.equal(saved.configuration.fields['modal-quiescent'],true);assert.equal(saved.configuration.fields['modal-vacuum'],false);
    assert.deepEqual(saved.configuration.equilibrium,{state:null,enabled:false,label:''});
  }
  await page.locator('#project-file').setInputFiles({name:'source-modal-project.json',mimeType:'application/json',buffer:projectBytes});await expect(page.locator('#project-load-solution')).toBeEnabled();
  await expect(page.locator('#project-name')).toHaveValue(project.name);
  await page.locator('#project-load-solution').click();await expect(page.locator('#export-json')).toBeEnabled();await expect(page.locator('#structural-equations')).toHaveValue(selection);
  await expect(page.locator('#modal-method')).toHaveValue(method);
  await expect(page.locator('#project-status')).toContainText(`Opened ${solutionName}.`);
  const reopened=await download('export-json','reopened-result.json'),reopenedProject=await download('project-export','reopened-project.json');
  check('saved modal result restored byte-exactly',Buffer.compare(bytes,reopened)===0);check('saved project restored byte-exactly',Buffer.compare(projectBytes,reopenedProject)===0);
  await page.locator('#tab-modes').click();await page.locator('#fit').click();check('single aircraft canvas',await page.locator('#viewport canvas').count()===1);
  audit.canvas=await page.locator('#viewport canvas').evaluate(canvas=>({width:canvas.width,height:canvas.height,client_width:canvas.clientWidth,client_height:canvas.clientHeight,webgl:!!(canvas.getContext('webgl2')||canvas.getContext('webgl')),canvas2d:!!canvas.getContext('2d')}));
  await page.screenshot({path:path.join(output,'desktop.png')});
  await page.locator('details').evaluateAll(nodes=>nodes.forEach(node=>node.open=false));await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();await page.locator('#fit').click();
  check('mobile width',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(output,'mobile.png')});
  // Reopen prior policies from pinned projects, without asking the worker to solve.
  // Preserve their historical numerical provenance and exact saved records.
  if(compatibilityProjects.length){
    await page.setViewportSize({width:1440,height:1000});await page.locator('details').evaluateAll(nodes=>nodes.forEach(node=>node.open=true));
    audit.compatibility_projects=[];
    for(const relative of compatibilityProjects){
      const priorBytes=await readFile(path.join(root,relative)),prior=JSON.parse(priorBytes),name=path.basename(relative);
      const selected=prior.solutions.find(s=>s.id===prior.selected_solution)??prior.solutions[0];assert(selected,'prior saved solution');
      await page.locator('#project-file').setInputFiles({name,mimeType:'application/json',buffer:priorBytes});
      await expect(page.locator('#project-name')).toHaveValue(prior.name);
      await expect(page.locator('#project-load-solution')).toBeEnabled();
      await page.locator('#project-load-solution').click();await expect(page.locator('#export-json')).toBeEnabled();
      await expect(page.locator('#project-status')).toContainText(`Opened ${selected.name}.`);
      const priorSelection=numericalSelection(selected.configuration.numerics);
      await expect(page.locator('#structural-equations')).toHaveValue(priorSelection);
      await expect(page.locator('#modal-method')).toHaveValue(selected.configuration.fields['modal-method']);
      const oldResult=await download('export-json','retained-'+name.replace('-project','-result'));
      assert.deepEqual(JSON.parse(oldResult),selected.data);
      const oldProject=JSON.parse(await download('project-export','retained-'+name));
      assert.equal(JSON.stringify(oldProject.solutions),JSON.stringify(prior.solutions));
      check('retained prior-policy result and sealed solutions '+name,true);
      audit.compatibility_projects.push({path:relative,solutions:prior.solutions.length,selection:priorSelection,additional_solves:0});
    }
  }
  const finalRequests=wire(await page.evaluate(()=>window.referenceRequests));
  audit.request_counts=Object.fromEntries([...new Set(finalRequests.map(r=>r.request?.action??'runtime'))].map(action=>[action,finalRequests.filter(r=>(r.request?.action??'runtime')===action).length]));
  const physical=finalRequests.filter(r=>physicalActions.includes(r.request?.action));
  check('exactly one modal solve, none during guard or restore',physical.length===1&&physical[0].request.action==='modes');assert.deepEqual(physical[0].request,input);
  await writeFile(path.join(output,'requests.json'),JSON.stringify(finalRequests,null,2)+'\n');await writeFile(path.join(output,'events.json'),JSON.stringify(await page.evaluate(()=>window.referenceEvents),null,2)+'\n');
  for(const p of [...audit.inputs,...audit.built_assets])check('unchanged '+p.path,(await pin(p.path)).sha256===p.sha256);
  for(const name of names)for(const folder of ['openswing','public/kernel','dist/kernel'])check('unchanged '+folder+'/'+name,sha(await readFile(path.join(root,folder,name)))===audit.modules[name]);
  check('offline HTTP absent',audit.offline_requests.length===0);check('external HTTP absent',audit.external_requests.length===0);check('page errors absent',audit.page_errors.length===0);check('network failures absent',audit.network_failures.length===0);check('within duration cap',!audit.timeout&&(performance.now()-started)<totalTimeoutMs);
  audit.status=moving?'PASS_OFFLINE_SOURCE_MOVING_VACUUM_MODAL_UI':stillAir?'PASS_OFFLINE_SOURCE_STILL_AIR_MODAL_UI':'PASS_OFFLINE_SOURCE_VACUUM_MODAL_UI';
}catch(error){
  audit.status='FAILURE_RETAINED';audit.error={message:error.message,stack:error.stack};process.exitCode=1;console.error(error.stack);
  try{if(page&&!page.isClosed()){await writeFile(path.join(output,'requests-at-failure.json'),JSON.stringify(wire(await page.evaluate(()=>window.referenceRequests)),null,2)+'\n');await page.screenshot({path:path.join(output,'failure.png')});}}catch{}
}finally{
  clearTimeout(timer);try{await browser?.close();}finally{server?.closeAllConnections();if(server?.listening)await new Promise(resolve=>server.close(resolve));}
  audit.total_seconds=(performance.now()-started)/1000;audit.check_counts={passed:audit.checks.filter(c=>c.passed).length,total:audit.checks.length};
  audit.artifacts=[];for(const name of (await readdir(output)).sort())if((await stat(path.join(output,name))).isFile())audit.artifacts.push(await pin(path.join(output,name)));
  await writeFile(path.join(output,'report.json'),JSON.stringify(audit,null,2)+'\n');
  console.log(JSON.stringify({status:audit.status,checks:audit.check_counts,startup_seconds:audit.startup_seconds,solve_seconds:audit.solve_seconds,parity:audit.parity,total_seconds:audit.total_seconds}));
}
