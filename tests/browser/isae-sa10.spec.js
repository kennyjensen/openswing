import {test,expect} from '@playwright/test';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const sha=b=>createHash('sha256').update(b).digest('hex');
const ready=async page=>{await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();};
test('SA-10 literal rejection and five literal plus explicitly repaired models solve offline',async({page,context},info)=>{
 test.setTimeout(600000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const bytes=await readFile('docs/validation/isae-sa10.json'),study=JSON.parse(bytes),modules={};
 const sources=JSON.parse(await readFile('docs/validation/isae-sa10-sources.json'));
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py')))modules[n]=sha(await readFile('openswing/'+n));
 expect(modules).toEqual(study.provenance.modules);
 await page.goto('/');await ready(page);await context.setOffline(true);
 await page.locator('#circulation-settings').evaluate(e=>e.open=true);await page.locator('#freeze-influences').uncheck(); // This archived study used current influences.
 await page.locator('#panels').fill('25');await page.locator('#panels').press('Tab');await ready(page);
 const bad=sources.models.find(c=>c.name==='TS_60_45_30');
 await page.locator('#file').setInputFiles({name:'TS_60_45_30_literal.asw',mimeType:'text/plain',buffer:Buffer.from(bad.source)});
 await expect(page.locator('#editor')).toHaveValue(bad.source);
 await expect(page.locator('#error')).toContainText("Attachment station is outside beam 2's parameter range.");
 await expect(page.locator('#runtime-status')).toHaveText('Configuration needs attention');
 await expect(page.locator('#solve')).toBeDisabled();await expect(page.locator('#export-json')).toBeDisabled();
 await page.screenshot({path:info.outputPath('isae-sa10-literal-rejection.png'),fullPage:true});
 const rows=[];
 for(const c of study.cases){
  await page.locator('#file').setInputFiles({name:c.case_id+'.asw',mimeType:'text/plain',buffer:Buffer.from(c.source)});
  await expect(page.locator('#editor')).toHaveValue(c.source);await ready(page);
  await page.locator('#mode').selectOption('rigid');await page.locator('#panels').fill('25');await page.locator('#panels').press('Tab');await ready(page);
  await page.locator('#speed').fill('55');await page.locator('#beta').fill('0');
  await page.locator('#mach-mode').evaluate(el=>{for(let p=el.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;});
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  for(const alpha of [5,15,25]){
   const expected=c.runs.find(r=>r.specification.panels===25&&r.specification.alpha===alpha&&r.specification.pg==='zero'&&!r.specification.frozen);
   await page.locator('#alpha').fill(String(alpha));await page.locator('#solve').click();
   if(expected.status==='rejected'){
    await expect(page.locator('#runtime-status')).toHaveText('Analysis stopped',{timeout:180000});
    await expect(page.locator('#error')).toBeVisible();rows.push({case:c.case_id,alpha,status:'matching_rejection'});continue;
   }
   await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});await ready(page);
   const event=page.waitForEvent('download');await page.locator('#export-json').click();const r=JSON.parse(await readFile(await(await event).path(),'utf8'));
   expect(r.software_provenance.modules).toEqual(modules);expect(r.request.source).toBe(c.source);
   expect(r.request.condition.mach).toBe(0);expect(r.request.condition.freeze_influences).toBe(false);
   let difference=0;for(const k of ['Cl','Cn','CL','CD','Cm','CDi','CDp'])difference=Math.max(difference,Math.abs(r[k]-expected.result[k]));
   expect(difference).toBeLessThan(2e-7);expect(r.residual).toBeLessThan(1e-8);
   rows.push({case:c.case_id,alpha,status:'matching_solution',maximum_coefficient_difference:difference,result:r});
  }
 }
 expect(rows).toHaveLength(18);
 const last=study.cases.at(-1);
 const rejected=last.runs.find(r=>r.specification.panels===25&&r.specification.alpha===15&&r.specification.pg==='zero'&&r.specification.frozen);
 expect(rejected.status).toBe('rejected');expect(rejected.error).toContain('Local section-normal Mach reaches unity');
 await page.locator('#freeze-influences').evaluate(el=>{for(let p=el.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;});
 await page.locator('#alpha').fill('15');await page.locator('#freeze-influences').check();await page.locator('#solve').click();
 await expect(page.locator('#runtime-status')).toHaveText('Analysis stopped',{timeout:180000});
 await expect(page.locator('#error')).toContainText('Local section-normal Mach reaches unity');
 await expect(page.locator('#export-json')).toBeDisabled();
 const domainError=await page.locator('#error').innerText();
 await page.screenshot({path:info.outputPath('isae-sa10-domain-rejection.png'),fullPage:true});
 await page.locator('#freeze-influences').uncheck();await page.locator('#solve').click();
 await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});await ready(page);
 const restoredEvent=page.waitForEvent('download');await page.locator('#export-json').click();
 const restored=JSON.parse(await readFile(await(await restoredEvent).path(),'utf8'));
 expect(restored.request.condition.freeze_influences).toBe(false);
 const expected=last.runs.find(r=>r.specification.panels===25&&r.specification.alpha===15&&r.specification.pg==='zero'&&!r.specification.frozen);
 const restoredDifference=Math.max(...['CL','CD','Cm','CDi'].map(k=>Math.abs(restored[k]-expected.result[k])));
 expect(restoredDifference).toBeLessThan(2e-7);expect(errors).toEqual([]);
 const domainRecovery={status:'PASS',case:last.case_id,alpha:15,panels:25,native_error:rejected.error,browser_error:domainError,restored_coefficient_difference:restoredDifference,restored_result:restored};
 await page.screenshot({path:info.outputPath('isae-sa10-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:info.outputPath('isae-sa10-mobile.png'),fullPage:true});
 await writeFile(info.outputPath('isae-sa10-browser.json'),JSON.stringify({status:'PASS',offline:true,literal_rejection:bad.name,domain_recovery:domainRecovery,rows,modules,study_sha256:sha(bytes),test_sha256:sha(await readFile(import.meta.filename))},null,2)+'\n');
});
