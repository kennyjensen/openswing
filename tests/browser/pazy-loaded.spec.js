import {test,expect} from '@playwright/test';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {cases,sha} from '../../scripts/pazy-loaded-runtime-cases.mjs';
const ready=async p=>{await expect(p.locator('#solve')).toBeEnabled();await expect(p.locator('#error')).toBeHidden();};
async function exported(p){const event=p.waitForEvent('download');await p.locator('#export-json').click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}
test('CONM2-audited Pazy gravity and static cases match native results in the offline served app',async({page,context},info)=>{
 test.setTimeout(1200000);page.setDefaultTimeout(60000);const selected=await cases(),modules={},errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py')))modules[n]=sha(await readFile('openswing/'+n));
 expect(selected.modules).toEqual(modules);await page.goto('/');await ready(page);await context.setOffline(true);const statics=[],modes=[];
 for(const old of selected.runs){
  const spec=old.specification;await page.locator('#file').setInputFiles({name:'pazy-conm2-audited.asw',mimeType:'text/plain',buffer:Buffer.from(old.source)});
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
  const start=performance.now();await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:240000});await ready(page);
  const seconds=(performance.now()-start)/1000,result=await exported(page);expect(result.request.source).toBe(old.source);expect(result.request.panels).toEqual(old.panels);
  expect(result.software_provenance.modules).toEqual(modules);
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
   expect(result.vacuum).toBe(true);expect(result.base.gravity_body).toEqual([0,0,spec.gravity?-spec.gravity:0]);
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
 await page.screenshot({path:info.outputPath('pazy-loaded-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
 await page.screenshot({path:info.outputPath('pazy-loaded-mobile.png'),fullPage:true});expect(errors).toEqual([]);expect(statics.length).toBe(4);expect(modes.length).toBe(6);
 await writeFile(info.outputPath('pazy-loaded-browser.json'),JSON.stringify({status:'PASS_EXPECTED_OUTCOMES',offline:true,served_build:true,modules,
  native_report_sha256:selected.reports,selector_sha256:selected.selector_sha256,test_sha256:sha(await readFile(import.meta.filename)),statics,modes,full_family_validated:false},null,2)+'\n');
});
