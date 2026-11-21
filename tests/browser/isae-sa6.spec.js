import {test,expect} from '@playwright/test';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const sha=b=>createHash('sha256').update(b).digest('hex');
const ready=async p=>{await expect(p.locator('#solve')).toBeEnabled();await expect(p.locator('#error')).toBeHidden();};
test('all seven SA-6 literal models solve offline with signed controls and native coefficients',async({page,context},info)=>{
 test.setTimeout(600000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const bytes=await readFile('docs/validation/isae-sa6.json'),study=JSON.parse(bytes),modules={};
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py')))modules[n]=sha(await readFile('openswing/'+n));
 expect(modules).toEqual(study.provenance.modules);
 await page.goto('/');await ready(page);await context.setOffline(true);const rows=[];
 await page.locator('#circulation-settings').evaluate(e=>e.open=true);await page.locator('#freeze-influences').uncheck(); // This archived study used current influences.
 for(const c of study.cases.filter(c=>!c.reconstructed)){
  const path='.reference/isae-validation/'+study.provenance.revision+'/'+c.path,source=await readFile(path,'utf8');
  await page.locator('#file').setInputFiles(path);await expect(page.locator('#editor')).toHaveValue(source);await ready(page);
  await page.locator('#mode').selectOption('rigid');await page.locator('#panels').fill('40');await page.locator('#panels').press('Tab');await ready(page);
  await page.locator('#speed').fill('20');await page.locator('input[data-control="1"]').fill(String(4*c.physical_delta_to_F1));
  // Expand the existing advanced settings to set the same independent PG Mach.
  await page.locator('#mach-mode').evaluate(el=>{for(let p=el.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;});
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  for(const alpha of [0,8,12]){
   await page.locator('#alpha').fill(String(alpha));await page.locator('#solve').click();
   await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});await ready(page);
   const event=page.waitForEvent('download');await page.locator('#export-json').click();const r=JSON.parse(await readFile(await(await event).path(),'utf8'));
   expect(r.software_provenance.modules).toEqual(modules);expect(r.request.source).toBe(source);expect(r.request.condition.mach).toBe(0);
   expect(r.request.condition.controls['1']).toBe(4*c.physical_delta_to_F1);expect(r.request.condition.freeze_influences).toBe(false);
   const expected=c.runs.find(r=>r.specification.panels===40&&r.specification.alpha===alpha&&r.specification.delta===4&&!r.specification.frozen);
   expect(expected.status).toBe('computed');let difference=0;
   for(const k of ['Cl','Cn','CL','CD','Cm'])difference=Math.max(difference,Math.abs(r[k]-expected.result[k]));
   expect(difference).toBeLessThan(2e-8);expect(r.residual).toBeLessThan(1e-8);
   rows.push({case:c.case_id,alpha,maximum_coefficient_difference:difference,result:r});
  }
 }
 expect(rows).toHaveLength(21);expect(errors).toEqual([]);await page.screenshot({path:info.outputPath('isae-sa6-desktop.png'),fullPage:true});
 await writeFile(info.outputPath('isae-sa6-browser.json'),JSON.stringify({status:'PASS',offline:true,rows,modules,study_sha256:sha(bytes),test_sha256:sha(await readFile(import.meta.filename))},null,2)+'\n');
});
