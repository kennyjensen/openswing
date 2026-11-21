import {test,expect} from '@playwright/test';
import {sealSolution} from '../../web/solution-data.js';
test.use({launchOptions:{executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,args:['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native','--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']}});
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {cases,sha} from '../../scripts/pazy-loaded-runtime-cases.mjs';
const ready=async p=>{await expect(p.locator('#solve')).toBeEnabled();await expect(p.locator('#error')).toBeHidden();};
async function exported(p){const event=p.waitForEvent('download');await p.locator('#export-json').click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}
test('Saved Pazy modal result renders on the host Vulkan backend without recomputation',async({page,context},info)=>{
 test.setTimeout(1200000);page.setDefaultTimeout(60000);const selected=await cases(),modules={},errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py')))modules[n]=sha(await readFile('openswing/'+n));
 expect(Object.keys(modules)).toEqual(Object.keys(selected.modules));expect(Object.keys(modules).filter(n=>modules[n]!==selected.modules[n])).toEqual(['linear_dynamics.py']);await page.goto('/');await ready(page);await context.setOffline(true);const statics=[],modes=[];
 for(const old of selected.runs.filter(r=>r.specification.analysis==='modes'&&r.specification.skin===1)){
  const spec=old.specification;if(spec.refinement!==4||spec.orientation!=='upright')continue;await page.locator('#file').setInputFiles({name:'pazy-conm2-audited.asw',mimeType:'text/plain',buffer:Buffer.from(old.source)});
  await expect(page.locator('#editor')).toHaveValue(old.source);await ready(page);
  await page.locator('#node-file').setInputFiles({name:'pazy-mesh.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({format:'openswing-mesh',version:1,panels:old.panels}))});
  await expect(page.locator('#node-table tbody tr')).toHaveCount(old.panels.beams['1'].nodes.length);await ready(page);
  await page.locator('#mode').selectOption(spec.analysis==='static'?'structural':'modes');
  if(spec.analysis==='modes'){
   await page.locator('#modal-vacuum').check();await page.locator('#modal-frame').selectOption('fixed');await page.locator('#modal-count').fill('16');
   await page.locator('#modal-method').selectOption('dense');await page.locator('#modal-shift-real').fill('-.1');await page.locator('#modal-shift-imag').fill('0');
  }
  if(spec.analysis==='static'){
   await page.locator('#static-gravity-mode').selectOption('custom');
   for(const [axis,value] of [['x',0],['y',0],['z',-spec.gravity]])await page.locator('#static-gravity-'+axis).fill(String(value));
  }else{
   await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill(String(spec.gravity));
  }
  const retained=JSON.parse(await readFile(process.env.OPENSWING_MODAL_BROWSER_RESULT,'utf8')).modes.find(r=>r.specification.refinement===4&&r.specification.orientation==='upright').result;
  await page.locator('#project-settings').evaluate(e=>e.open=true);
  const pending=page.waitForEvent('download');await page.locator('#project-export-current').click();const project=JSON.parse(await readFile(await(await pending).path(),'utf8'));
  const solution=await sealSolution({id:'retained-modal',name:'Retained verified Pazy mode',created_at:'2026-10-15T00:00:00Z',kind:'modes',configuration:project.cases[0].configuration,data:retained,auxiliary:{},view:{},provenance:retained.software_provenance});
  project.solutions=[solution];project.selected_solution=solution.id;
  await page.locator('#project-file').setInputFiles({name:'retained-modal.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});
  await expect(page.locator('#project-status')).toContainText('Project opened.');await page.locator('#project-load-solution').click();
  await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');await ready(page);
  const result=await exported(page),seconds=0;expect(result.software_provenance.modules).toEqual(modules);
  const canvas=page.locator('canvas[data-renderer="webgl"]');await expect(canvas).toBeVisible();
  const rendering=await canvas.evaluate(e=>{const gl=e.getContext('webgl2');return {lost:gl.isContextLost(),width:gl.drawingBufferWidth,height:gl.drawingBufferHeight,error:gl.getError()};});
  expect(rendering.lost).toBe(false);expect(rendering.width).toBeGreaterThan(0);expect(rendering.error).toBe(0);
  if(spec.analysis==='static'){
   expect(result.analysis).toBe('structural_static');expect(result.request.condition).toBeNull();expect(result.request.gravity).toEqual([0,0,-spec.gravity]);expect(result.gravity_body).toEqual([0,0,-spec.gravity]);expect(result.residual).toBeLessThan(1e-8);const differences={};
   for(const field of ['applied_force','applied_moment','support_force','support_moment','force_balance','moment_balance']){
    differences[field]=Math.max(...old.result[field].map((v,i)=>Math.abs(v-result[field][i])));expect(differences[field]).toBeLessThan(2e-8);
   }
   for(const [group,fields] of [['nodes',['position','rotation']],['elements',['force','moment','strain','curvature_change']]])for(const field of fields){
    expect(result[group].length).toBe(old.result[group].length);let maximum=0;
    for(let j=0;j<result[group].length;j++){
     const a=result[group][j][field].flat(Infinity),b=old.result[group][j][field].flat(Infinity);expect(a.length).toBe(b.length);
     for(let k=0;k<a.length;k++)maximum=Math.max(maximum,Math.abs(a[k]-b[k]));
    }
    differences[group+'.'+field]=maximum;expect(maximum).toBeLessThan(2e-8);
   }
   statics.push({specification:spec,seconds,differences,result});
  }else{
   expect(result.diagnostics.left_recovery_counts).toMatchObject({sparse_adjoint:8,conjugate_reuse:8,sparse_rejected:0,schur_pencils:0});expect(result.vacuum).toBe(true);expect(result.base.gravity_body).toEqual([0,0,spec.gravity?-spec.gravity:0]);
   expect(result.diagnostics.base_residual).toBeLessThan(1e-8);expect(result.diagnostics.finite_dimension).toBe(old.diagnostics.finite_dimension);const matches=[];
   for(const before of old.modes){
    const after=result.modes.filter(m=>m.eigenvalue[1]>0).sort((a,b)=>Math.abs(a.frequency-before.frequency_Hz)-Math.abs(b.frequency-before.frequency_Hz))[0];
    const difference=Math.abs(after.frequency-before.frequency_Hz);expect(difference).toBeLessThan(2e-6);
    expect(after.left_backward_error).toBeLessThan(1e-9);expect(after.right_backward_error).toBeLessThan(1e-9);
    let real=0,imag=0,aa=0,bb=0;
    for(let j=0;j<after.output.nodes.length;j++)for(let k=0;k<6;k++){
     const f=k<3?after.output.nodes[j].displacement:after.output.nodes[j].rotation,x=[f.real[k%3],f.imag[k%3]],y=[before.shape.real[j][k],before.shape.imag[j][k]];
     real+=x[0]*y[0]+x[1]*y[1];imag+=x[0]*y[1]-x[1]*y[0];aa+=x[0]**2+x[1]**2;bb+=y[0]**2+y[1]**2;
    }
    const score=(real*real+imag*imag)/(aa*bb);expect(score).toBeGreaterThan(1-2e-8);matches.push({frequency_difference_Hz:difference,shape_assurance:score});
   }
   modes.push({specification:spec,seconds,matches,result});
  }
  console.log('Browser',spec,seconds.toFixed(2)+'s','PASS');
 }
 await page.screenshot({path:info.outputPath('modal-adjoint-display-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
 await page.screenshot({path:info.outputPath('modal-adjoint-display-mobile.png'),fullPage:true});expect(errors).toEqual([]);expect(statics.length).toBe(0);expect(modes.length).toBe(1);
 await writeFile(info.outputPath('modal-adjoint-display.json'),JSON.stringify({status:'PASS_SAVED_MODAL_DISPLAY_WITHOUT_RECOMPUTATION',backend:'Vulkan',fresh_solve:false,offline:true,served_build:true,modules,baseline_modules:selected.modules,
  native_report_sha256:selected.reports,selector_sha256:selected.selector_sha256,test_sha256:sha(await readFile(import.meta.filename)),statics,modes,full_family_validated:false},null,2)+'\n');
});
