import {test,expect} from '@playwright/test';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const sha=b=>createHash('sha256').update(b).digest('hex');
const ready=async p=>{await expect(p.locator('#solve')).toBeEnabled();await expect(p.locator('#error')).toBeHidden();};
async function exported(p){const event=p.waitForEvent('download');await p.locator('#export-json').click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}
test('primary Pazy nodal inertia and section models reproduce six native modal states offline',async({page,context},info)=>{
 test.setTimeout(900000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const bytes=await readFile('docs/validation/pazy-primary-mapping.json'),study=JSON.parse(bytes),modules={};
 expect(study.status).toBe('COMPARISONS_COMPLETE_NOT_PHYSICALLY_VALIDATED');
 for(const name of(await readdir('openswing')).filter(n=>n.endsWith('.py')))modules[name]=sha(await readFile('openswing/'+name));
 expect(study.modules).toEqual(modules);await page.goto('/');await ready(page);await context.setOffline(true);const rows=[];
 for(const row of study.runs.filter(r=>r.specification.refinement===1||r.specification.refinement===4)){
  const b=await readFile(row.cache);expect(sha(b)).toBe(row.sha256);const old=JSON.parse(b);expect(old.status).toBe('computed');
  await page.locator('#file').setInputFiles({name:`primary-pazy-skin${row.specification.skin}.asw`,mimeType:'text/plain',buffer:Buffer.from(old.source)});
  await expect(page.locator('#editor')).toHaveValue(old.source);await ready(page);
  await page.locator('#node-file').setInputFiles({name:'pazy-mesh.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({format:'openswing-mesh',version:1,panels:old.panels}))});
  await expect(page.locator('#node-table tbody tr')).toHaveCount(old.panels.beams['1'].nodes.length);await ready(page);
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-vacuum').check();await page.locator('#modal-frame').selectOption('fixed');
  await page.locator('#modal-count').fill('16');await page.locator('#modal-method').selectOption('dense');
  await page.locator('#modal-shift-real').fill('-.1');await page.locator('#modal-shift-imag').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});await ready(page);
  const result=await exported(page);expect(result.request.source).toBe(old.source);expect(result.request.panels).toEqual(old.panels);
  expect(result.software_provenance.modules).toEqual(modules);expect(result.vacuum).toBe(true);expect(result.base.gravity_body).toEqual([0,0,0]);
  expect(result.diagnostics.base_residual).toBeLessThan(1e-8);expect(result.diagnostics.finite_dimension).toBe(old.diagnostics.finite_dimension);
  expect(result.base.structural_nodes).toBe(old.base.structural_nodes);
  const comparisons=[];
  for(const before of old.modes){
   const after=result.modes.filter(m=>m.eigenvalue[1]>0).sort((a,b)=>Math.abs(a.frequency-before.frequency_Hz)-Math.abs(b.frequency-before.frequency_Hz))[0];
   const difference=Math.abs(after.frequency-before.frequency_Hz);expect(difference).toBeLessThan(2e-6);
   expect(after.left_backward_error).toBeLessThan(1e-9);expect(after.right_backward_error).toBeLessThan(1e-9);
   let real=0,imag=0,aa=0,bb=0;
   for(let j=0;j<after.output.nodes.length;j++)for(let k=0;k<6;k++){
    const f=k<3?after.output.nodes[j].displacement:after.output.nodes[j].rotation,x=[f.real[k%3],f.imag[k%3]],y=[before.shape.real[j][k],before.shape.imag[j][k]];
    real+=x[0]*y[0]+x[1]*y[1];imag+=x[0]*y[1]-x[1]*y[0];aa+=x[0]**2+x[1]**2;bb+=y[0]**2+y[1]**2;
   }
   const score=(real*real+imag*imag)/(aa*bb);expect(score).toBeGreaterThan(1-2e-8);comparisons.push({frequency_difference_Hz:difference,shape_assurance:score});
  }
  rows.push({specification:row.specification,comparisons,result});
 }
 await page.screenshot({path:info.outputPath('pazy-primary-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
 await page.screenshot({path:info.outputPath('pazy-primary-mobile.png'),fullPage:true});expect(errors).toEqual([]);expect(rows.length).toBe(6);
 await writeFile(info.outputPath('pazy-primary-browser.json'),JSON.stringify({status:'PASS_EXPECTED_OUTCOMES',offline:true,served_build:true,modules,
  native_sha256:sha(bytes),test_sha256:sha(await readFile(import.meta.filename)),rows,full_physical_validation:false},null,2)+'\n');
});
