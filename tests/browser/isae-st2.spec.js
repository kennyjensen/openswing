import {test,expect} from '@playwright/test';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const sha=b=>createHash('sha256').update(b).digest('hex');
const ready=async p=>{await expect(p.locator('#solve')).toBeEnabled();await expect(p.locator('#error')).toBeHidden();};
async function exported(p){const event=p.waitForEvent('download');await p.locator('#export-json').click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}
async function load(p,source,name,panels){
 await p.locator('#file').setInputFiles({name,mimeType:'text/plain',buffer:Buffer.from(source)});
 await expect(p.locator('#editor')).toHaveValue(source);await ready(p);
 await p.locator('#panels').fill(String(panels));await p.locator('#panels').press('Tab');await ready(p);
}
async function run(p){await p.locator('#solve').click();await expect(p.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});await ready(p);}
test('explicit Pazy static and modal reconstructions reproduce native results in the offline served app',async({page,context},info)=>{
 test.setTimeout(900000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const sb=await readFile('docs/validation/isae-st2-static.json'),mb=await readFile('docs/validation/isae-st2-modes.json');
 const stat=JSON.parse(sb),modal=JSON.parse(mb),modules={};
 expect(stat.status).toBe('COMPARISONS_COMPLETE_NOT_PHYSICALLY_VALIDATED');expect(modal.status).toBe(stat.status);
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py')))modules[n]=sha(await readFile('openswing/'+n));
 expect(modules).toEqual(stat.modules);expect(modules).toEqual(modal.modules);
 await page.goto('/');await ready(page);await context.setOffline(true);const statics=[],modes=[];
 for(const [kind,skin,mass] of [['bending',0,3],['torsion',0,2],['torsion',1,2.8]])for(const layout of ['archive_pylon','measured_tip']){
  const row=Object.values(stat.runs).find(r=>r.specification.kind===kind&&r.specification.skin===skin&&r.specification.mass_kg===mass&&r.specification.layout===layout&&r.specification.panels===32);
  const bytes=await readFile(row.cache);expect(sha(bytes)).toBe(row.sha256);const native=JSON.parse(bytes),old=native.result;
  await load(page,native.derived_source,`derived-pazy-${kind}-${skin}-${layout}.asw`,32);await page.locator('#mode').selectOption('structural');
  await run(page);const result=await exported(page);expect(result.analysis).toBe('structural_static');expect(result.request.source).toBe(native.derived_source);
  expect(result.request.condition).toBeNull();expect(result.software_provenance.modules).toEqual(modules);expect(result.residual).toBeLessThan(1e-8);
  const differences={};
  for(const field of ['applied_force','applied_moment','support_force','support_moment','force_balance','moment_balance']){
   differences[field]=Math.max(...old[field].map((v,i)=>Math.abs(v-result[field][i])));expect(differences[field]).toBeLessThan(2e-8);
  }
  for(const [collection,fields] of [['nodes',['position','rotation']],['elements',['force','moment','strain','curvature_change']]]){
   expect(result[collection].length).toBe(old[collection].length);
   for(const field of fields){let maximum=0;for(let i=0;i<old[collection].length;i++){
    const a=old[collection][i][field].flat(Infinity),b=result[collection][i][field].flat(Infinity);expect(a.length).toBe(b.length);
    for(let j=0;j<a.length;j++)maximum=Math.max(maximum,Math.abs(a[j]-b[j]));
   }differences[collection+'.'+field]=maximum;expect(maximum).toBeLessThan(2e-8);}
  }
  statics.push({specification:row.specification,differences,result});
 }
 await page.screenshot({path:info.outputPath('pazy-static-desktop.png'),fullPage:true});
 for(const row of modal.runs.filter(r=>r.specification.panels===16)){
  const bytes=await readFile(row.cache);expect(sha(bytes)).toBe(row.sha256);const native=JSON.parse(bytes),spec=row.specification;
  await load(page,native.derived_source,`derived-pazy-${spec.orientation}.asw`,16);await page.locator('#mode').selectOption('modes');
  await page.locator('#modal-vacuum').check();await page.locator('#modal-frame').selectOption('fixed');await page.locator('#modal-count').fill('16');
  await page.locator('#modal-method').selectOption('dense');await page.locator('#modal-shift-real').fill('-.1');await page.locator('#modal-shift-imag').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill(String(spec.gravity));
  await run(page);const result=await exported(page);expect(result.request.source).toBe(native.derived_source);expect(result.software_provenance.modules).toEqual(modules);
  expect(result.vacuum).toBe(true);expect(result.base.gravity_body).toEqual([0,0,spec.gravity?-spec.gravity:0]);
  expect(result.diagnostics.base_residual).toBeLessThan(1e-8);expect(result.diagnostics.finite_dimension).toBe(native.diagnostics.finite_dimension);
  const comparisons=[];
  for(const before of native.modes){
   const after=result.modes.filter(m=>m.eigenvalue[1]>0).sort((a,b)=>Math.abs(a.frequency-before.frequency_Hz)-Math.abs(b.frequency-before.frequency_Hz))[0];
   const df=Math.abs(after.frequency-before.frequency_Hz);expect(df).toBeLessThan(2e-6);
   expect(after.right_backward_error).toBeLessThan(1e-9);expect(after.left_backward_error).toBeLessThan(1e-9);
   let real=0,imag=0,aa=0,bb=0;
   for(let j=0;j<after.output.nodes.length;j++)for(let k=0;k<6;k++){
    const f=k<3?after.output.nodes[j].displacement:after.output.nodes[j].rotation,x=[f.real[k%3],f.imag[k%3]],y=[before.shape.real[j][k],before.shape.imag[j][k]];
    real+=x[0]*y[0]+x[1]*y[1];imag+=x[0]*y[1]-x[1]*y[0];aa+=x[0]**2+x[1]**2;bb+=y[0]**2+y[1]**2;
   }
   const mac=(real*real+imag*imag)/(aa*bb);expect(mac).toBeGreaterThan(1-2e-8);comparisons.push({frequency_difference_Hz:df,shape_assurance:mac});
  }
  modes.push({specification:spec,comparisons,result});
 }
 await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
 await page.screenshot({path:info.outputPath('pazy-modes-mobile.png'),fullPage:true});expect(errors).toEqual([]);
 await writeFile(info.outputPath('isae-st2-browser.json'),JSON.stringify({status:'PASS_EXPECTED_OUTCOMES',offline:true,served_build:true,modules,
  test_sha256:sha(await readFile(import.meta.filename)),static_sha256:sha(sb),modal_sha256:sha(mb),statics,modes,full_suite_validated:false},null,2)+'\n');
});
