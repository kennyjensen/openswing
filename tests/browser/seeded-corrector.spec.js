import {test, expect} from '@playwright/test';
import {readFile, readdir, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const fixturePath=fileURLToPath(new URL('../data/seeded-corrector-flexible.asw',import.meta.url));
const referencePath=fileURLToPath(new URL('../data/seeded-corrector-reference.json',import.meta.url));
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const exclusions=new Set(['result.evaluations','result.circulation_solver.evaluations']);
const envelope=['continuation_steps','equilibrium_state','equilibrium_initialization','software_provenance',
  'request','requested_operating_constraints','condition','model'];

async function download(page,selector){
  const pending=page.waitForEvent('download');await page.locator(selector).click();
  const bytes=await readFile(await(await pending).path());return {bytes,value:JSON.parse(bytes.toString('utf8'))};
}

test('offline mounted warm equilibrium uses and releases its sparse corrector with full physical export parity',async({page,context},info)=>{
  test.setTimeout(300000);
  const reference=JSON.parse(await readFile(referencePath,'utf8'));
  const audit={status:'RUNNING',checks:[],comparisons:{},exclusions:[...exclusions],
    setup_differences:reference.setup_differences,limits:{cold_startup:false,webgl_rendering:false,
      independent_fresh_browser_residual:false,whole_application_suite:false,performance_claim:false}};
  const check=(name,pass_,details={})=>{audit.checks.push({name,pass_:!!pass_,...details});if(!pass_)throw new Error(name);};
  const errors=[],offlineRequests=[];let offline=false;
  page.on('pageerror',error=>errors.push(error.message));
  context.on('request',request=>{if(offline&&/^https?:/.test(request.url()))offlineRequests.push(request.url());});
  function compare(name,expected,actual,start){
    const stats={numeric_values:0,leaf_values:0,maximum_fraction:0,worst_path:null};
    const visit=(a,b,p)=>{
      if(exclusions.has(p))return;
      if(typeof a==='number'){
        if(typeof b!=='number'||!Number.isFinite(a)||!Number.isFinite(b))throw new Error(`${name}: nonfinite numeric field ${p}`);
        const difference=Math.abs(a-b),limit=reference.gates.absolute+reference.gates.relative*Math.abs(a),fraction=difference/limit;
        stats.numeric_values++;stats.leaf_values++;
        if(fraction>stats.maximum_fraction)Object.assign(stats,{maximum_fraction:fraction,worst_path:p,difference,limit});
        if(fraction>1)throw new Error(`${name}: ${p}: ${difference} > ${limit}`);
      }else if(Array.isArray(a)){
        if(!Array.isArray(b)||a.length!==b.length)throw new Error(`${name}: array shape ${p}`);
        a.forEach((value,i)=>visit(value,b[i],`${p}[${i}]`));
      }else if(a!==null&&typeof a==='object'){
        if(b===null||typeof b!=='object'||Array.isArray(b)||JSON.stringify(Object.keys(a).sort())!==JSON.stringify(Object.keys(b).sort()))throw new Error(`${name}: object keys ${p}`);
        for(const key of Object.keys(a))visit(a[key],b[key],`${p}.${key}`);
      }else{
        stats.leaf_values++;if(a!==b)throw new Error(`${name}: metadata ${p}`);
      }
    };
    audit.comparisons[name]=stats;visit(expected,actual,start);check(name,true,stats);
  }
  // Exact expected-copy transformations for zero gravity and omitted/zero
  // pointwise mode configuration; no physical fields are removed.
  // The raw baseline and actual exports are never modified or overwritten.
  function uiExpected(saved){
    const copy=structuredClone(saved);
    check('reference gravity representation is the declared body override',copy.result.gravity_source==='body_vector_override'
      &&copy.result.atmosphere.gravity_magnitude===9.80665&&copy.state.launch.condition.gravity_magnitude===null
      &&JSON.stringify(copy.state.launch.gravity)==='[0,0,0]');
    copy.result.gravity_source='Earth_magnitude';copy.result.atmosphere.gravity_magnitude=0;
    copy.state.launch.gravity=null;copy.state.launch.condition.gravity_magnitude=0;
    check('reference omitted modes select the pointwise basis',JSON.stringify(copy.state.launch.condition.circulation_modes)==='{}'
      &&copy.result.circulation_discretization.beams.every(beam=>beam.representation==='pointwise'));
    copy.state.launch.condition.circulation_modes={'1':0};
    return copy;
  }
  function verifyPhysical(label,result,savedState,expected){
    check(label+' full export field inventory',JSON.stringify(Object.keys(result).sort())===JSON.stringify([...Object.keys(expected.result),...envelope].sort()));
    const physical=Object.fromEntries(Object.keys(expected.result).map(key=>[key,result[key]]));
    compare(label+' complete physical output',expected.result,physical,'result');
    compare(label+' complete saved physical state',expected.state,result.equilibrium_state,'state');
    check(label+' separate equilibrium download equals JSON-export state',JSON.stringify(savedState)===JSON.stringify(result.equilibrium_state));
    check(label+' converged full residual gates',result.converged===true&&Number.isFinite(result.residual)
      &&result.residual<=reference.gates.full_residual&&Number.isFinite(savedState.residual)&&savedState.residual<=reference.gates.full_residual);
    check(label+' exact loaded kernel',JSON.stringify(Object.entries(result.software_provenance.modules).sort())===JSON.stringify(Object.entries(audit.expected_kernel).sort()));
    check(label+' physical zero gravity',result.gravity_body.every(value=>value===0));
    check(label+' requested mounted current-influence fixture',result.request.action==='solve'&&result.request.mode==='mounted'
      &&result.request.panels===4&&result.request.controller===null&&!result.request.derivatives
      &&result.request.operating_constraints.length===0&&result.request.strut_mode==='bilateral'
      &&result.condition.speed===20&&result.condition.beta===0&&result.condition.mach===.1
      &&result.condition.freeze_influences===false&&result.condition.gravity_magnitude===0);
  }
  try{
    check('fixture bytes equal prior WASM fixture',sha(await readFile(fixturePath))===reference.model.sha256);
    const sourceRoot=process.env.OPENSWING_SOURCE_ROOT||path.resolve('openswing');
    audit.expected_kernel=Object.fromEntries(await Promise.all((await readdir(sourceRoot)).filter(name=>name.endsWith('.py')).sort()
      .map(async name=>[name,sha(await readFile(path.join(sourceRoot,name)))])));
    check('expected source contains seeded corrector',Object.hasOwn(audit.expected_kernel,'seeded_corrector.py'));
    if(process.env.OPENSWING_EXPECTED_KERNEL_PINS){
      const frozen=JSON.parse(await readFile(process.env.OPENSWING_EXPECTED_KERNEL_PINS,'utf8'));
      check('study exact frozen candidate source',JSON.stringify(Object.entries(audit.expected_kernel).sort())===JSON.stringify(Object.entries(frozen).sort()));
    }
    await page.addInitScript(()=>{
      const get=HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:get.call(this,type,...args);};
      // Passive request recording: forward every original message unchanged.
      const NativeWorker=window.Worker;window.seededCorrectorRequests=[];
      window.seededCorrectorProgress=[];window.seededCorrectorRenderedProgress=[];
      window.Worker=class extends NativeWorker{
        constructor(...args){
          super(...args);
          // Listen without replacing, modifying or suppressing incoming messages.
          this.addEventListener('message',({data})=>{
            if(data?.type==='progress')window.seededCorrectorProgress.push(structuredClone(data));
          });
        }
        postMessage(message,...rest){window.seededCorrectorRequests.push(structuredClone(message));return super.postMessage(message,...rest);}
      };
      window.addEventListener('DOMContentLoaded',()=>{
        const node=document.getElementById('runtime-status');
        if(!node)return;
        new MutationObserver(()=>{
          const index=window.seededCorrectorProgress.length-1;
          window.seededCorrectorRenderedProgress.push({progress_index:index,
            progress:index<0?null:structuredClone(window.seededCorrectorProgress[index]),
            message:node.textContent,detail:document.getElementById('runtime-detail')?.textContent??''});
        }).observe(node,{childList:true,characterData:true,subtree:true});
      },{once:true});
    });
    await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
    await page.locator('#file').setInputFiles(fixturePath);
    await expect(page.locator('#model-name')).toHaveText(reference.model.name);
    await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
    await expect(page.locator('#solve')).toBeEnabled();
    await page.locator('#mode').selectOption('mounted');
    await page.locator('#speed').fill('20');await page.locator('#alpha').fill('2');await page.locator('#beta').fill('0');
    await page.locator('#stall').check();
    await page.locator('#atmosphere-settings').evaluate(element=>element.open=true);
    await page.locator('#density-mode').selectOption('standard');await page.locator('#altitude').fill('0');
    await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('.1');
    await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
    await page.locator('#load-factor').fill('1');
    await page.locator('#circulation-settings').evaluate(element=>element.open=true);
    await page.locator('#freeze-influences').uncheck();await page.locator('#aero-lag').check();
    await page.locator('#circulation-modes input').fill('0');
    await page.locator('#wake-core-ratio').fill('.25');
    await page.locator('#derivative-settings').evaluate(element=>element.open=true);await page.locator('#derivatives-enable').uncheck();
    await context.setOffline(true);offline=true;
    await page.locator('#solve').click();
    await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:120000});
    await page.locator('#equilibrium-settings').evaluate(element=>element.open=true);
    const initial=await download(page,'#export-json'),seed=await download(page,'#equilibrium-save');
    await writeFile(info.outputPath('initial-result.json'),initial.bytes);await writeFile(info.outputPath('initial-state.json'),seed.bytes);
    verifyPhysical('initial',initial.value,seed.value,uiExpected(reference.seed));
    check('initial request is cold',!initial.value.request.initial_state);
    await page.locator('#equilibrium-use').click();await expect(page.locator('#equilibrium-enable')).toBeChecked();
    await page.locator('#alpha').fill('2.05');await page.locator('#solve').click();
    await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:120000});
    const warm=await download(page,'#export-json'),state=await download(page,'#equilibrium-save');
    await writeFile(info.outputPath('warm-result.json'),warm.bytes);await writeFile(info.outputPath('warm-state.json'),state.bytes);
    verifyPhysical('warm',warm.value,state.value,uiExpected(reference.target));
    check('warm target alpha',warm.value.condition.alpha===2.05);
    check('warm request uses exact preceding UI seed',JSON.stringify(warm.value.request.initial_state)===JSON.stringify(seed.value));
    const initialization=warm.value.equilibrium_initialization,corrector=initialization.seeded_corrector;
    check('saved equilibrium path',initialization.initialization==='saved physical equilibrium'&&warm.value.continuation_steps===1);
    check('sparse final rank certificate at unchanged acceptance threshold',initialization.rank_check==='sparse inverse-norm certificate'
      &&initialization.column_scaled_reciprocal_condition===null
      &&Number.isFinite(initialization.column_scaled_reciprocal_condition_lower_bound)
      &&initialization.column_scaled_reciprocal_condition_lower_bound>reference.gates.dense_column_scaled_rcond);
    check('corrector full residual gate',Number.isFinite(initialization.residual)&&initialization.residual<=reference.gates.full_residual);
    check('eligible sparse corrector enabled',corrector.eligible===true&&corrector.enabled===true&&corrector.decline_reasons.length===0);
    check('successful sparse factor build and solve',corrector.builds.some(build=>build.status==='BUILT'&&build.solve_completions>0)&&corrector.dense_tangent_builds===0);
    check('factor wrappers released before fresh final tangent',corrector.factor_wrappers_alive_before_final_tangent===0&&corrector.builder_detached===true);
    check('fresh final sparse matrix and original rank threshold declared',corrector.final_tangent_values_unchanged===true
      &&corrector.rank_acceptance_threshold_unchanged===true&&corrector.final_tangent_storage==='sparse'
      &&corrector.final_rank_strategy==='conservative certificate with full SVD fallback');
    check('temporary owners restored',corrector.builds.every(build=>build.tangent_owner_restored===true&&build.iteration_fields_unchanged===true&&build.tangent_load_owner_restored===true));
    check('full final tangent and rank phases completed',corrector.phases.final_tangent.status==='COMPLETED'&&corrector.phases.final_rank.status==='COMPLETED');
    const requests=await page.evaluate(()=>window.seededCorrectorRequests.filter(message=>message.request?.action==='solve'));
    check('exactly two actual worker solves',requests.length===2&&requests[0].request.condition.alpha===2&&requests[1].request.condition.alpha===2.05);
    check('worker warm message retains exact UI seed',JSON.stringify(requests[1].request.initial_state)===JSON.stringify(seed.value));
    const captured=await page.evaluate(()=>({events:window.seededCorrectorProgress,rendered:window.seededCorrectorRenderedProgress}));
    const warmProgress=captured.events.filter(event=>event.id===requests[1].id);
    const warmRendered=captured.rendered.filter(row=>row.progress?.id===requests[1].id);
    for(const [stage,label] of [['equilibrium_tangent','Preparing final equilibrium check'],['equilibrium_rank','Checking equilibrium equations']]){
      const events=warmProgress.filter(event=>event.stage===stage);
      check('warm worker '+stage+' boundaries and column counters',events.length>=2&&events[0].time===0
        &&events.at(-1).time===events.at(-1).steps&&events.every((event,i)=>event.action==='solve'
          &&Number.isInteger(event.time)&&Number.isInteger(event.steps)&&event.steps>0
          &&event.time>=0&&event.time<=event.steps&&event.steps===events[0].steps
          &&(i===0||event.time>=events[i-1].time)),{events});
      const rendered=warmRendered.filter(row=>row.progress.stage===stage&&row.message.startsWith(label));
      check('actual mounted '+stage+' label rendered',rendered.length>0&&rendered.every(row=>
        row.message===`${label} · ${row.progress.time}/${row.progress.steps} columns…`
        &&row.detail.includes('not overall solve completion')),{rendered});
    }
    check('sparse fixture does not fall back to a full SVD',!warmProgress.some(event=>event.stage==='equilibrium_rank_svd'));
    check('mounted final progress never renders a time-integration fallback',warmRendered.length>0
      &&warmRendered.every(row=>!row.message.startsWith('Integrating')),{rendered_count:warmRendered.length});
    check('offline operation issued no HTTP requests',offlineRequests.length===0,{requests:offlineRequests});
    check('no page errors',errors.length===0,{errors});
    audit.status='PASS_OFFLINE_BROWSER_SEEDED_CORRECTOR';
  }catch(error){audit.status='FAIL_RETAINED';audit.error={message:error.message,stack:error.stack};throw error;}
  finally{
    audit.offline_requests=offlineRequests;audit.page_errors=errors;
    audit.counts={passed:audit.checks.filter(row=>row.pass_).length,total:audit.checks.length};
    await writeFile(info.outputPath('comparison.json'),JSON.stringify(audit,null,2));
    try{
      if(!page.isClosed()){
        await writeFile(info.outputPath('worker-requests.json'),JSON.stringify(await page.evaluate(()=>window.seededCorrectorRequests??[]),null,2));
        await writeFile(info.outputPath('worker-progress.json'),JSON.stringify(await page.evaluate(()=>window.seededCorrectorProgress??[]),null,2));
        await writeFile(info.outputPath('rendered-progress.json'),JSON.stringify(await page.evaluate(()=>window.seededCorrectorRenderedProgress??[]),null,2));
      }
    }catch(error){await writeFile(info.outputPath('request-capture-failure.json'),JSON.stringify({message:error.message}));}
  }
});
