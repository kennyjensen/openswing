import {test,expect} from '@playwright/test';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const sha=b=>createHash('sha256').update(b).digest('hex');
const ready=async page=>{
 await expect(page.locator('#solve')).toBeEnabled();
 await expect(page.locator('#error')).toBeHidden();
};

test('SA-12 ground pose, coefficients and unavailable oblique Trefftz drag reproduce offline',async({page,context},info)=>{
 test.setTimeout(600000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const bytes=await readFile('docs/validation/isae-sa12-wasm-native.json'),study=JSON.parse(bytes);
 const sourceBytes=await readFile('docs/validation/isae-sa12-sources.json'),sources=JSON.parse(sourceBytes);
 const modules={};
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py')))modules[n]=sha(await readFile('openswing/'+n));
 expect(modules).toEqual(study.provenance.modules);
 expect(sha(sourceBytes)).toBe(study.provenance.source_report_sha256);
 await page.goto('/');await ready(page);await context.setOffline(true);
 await page.locator('#panels').fill('100');await page.locator('#panels').press('Tab');await ready(page);
 const rows=[];
 for(const c of sources.models){
  await page.locator('#file').setInputFiles({name:c.name+'.asw',mimeType:'text/plain',buffer:Buffer.from(c.source)});
  await expect(page.locator('#editor')).toHaveValue(c.source);await ready(page);
  await page.locator('#mode').selectOption('rigid');await page.locator('#speed').fill('35.76');
  await page.locator('#beta').fill('0');
  for(const id of ['mach-mode','ground-effect'])await page.locator('#'+id).evaluate(el=>{
   for(let p=el.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;
  });
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#freeze-influences').uncheck();await page.locator('#ground-effect').selectOption('1');
  for(const id of ['position-earth-x','position-earth-y','attitude-bank','attitude-heading','ground-normal-x','ground-normal-y'])await page.locator('#'+id).fill('0');
  await page.locator('#ground-normal-z').fill('1');
  const sample=study.rows.filter(r=>r.specification.case===c.name&&r.specification.modes===0&&
   (r.specification.alpha===0||r.specification.alpha===5||
    (r.specification.height_label==='05'&&r.specification.alpha===10&&r.specification.pose==='level_freestream')));
  for(const expected of sample){
   const q=expected.specification;
   expect(sha(await readFile(expected.cache_path))).toBe(expected.cache_sha256);
   await page.locator('#alpha').fill(String(q.alpha));
   await page.locator('#position-earth-z').fill(String(q.height));
   await page.locator('#attitude-elevation').fill(String(q.pose==='level_freestream'?q.alpha:0));
   await page.locator('#solve').click();
   await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});await ready(page);
   const event=page.waitForEvent('download');await page.locator('#export-json').click();
   const result=JSON.parse(await readFile(await(await event).path(),'utf8'));
   expect(result.software_provenance.modules).toEqual(modules);expect(result.request.source).toBe(c.source);
   expect(result.request.condition.mach).toBe(0);expect(result.request.condition.freeze_influences).toBe(false);
   expect(result.request.condition.ground_effect).toBe(1);
   expect(result.request.condition.position_earth).toEqual([0,0,q.height]);
   expect(result.request.condition.attitude).toEqual([0,q.pose==='level_freestream'?q.alpha:0,0]);
   const differences={};
   for(const k of ['CL','CD','CDi','CDi_near','CDp','Cm','Cl','Cn','CY']){
    if(expected.result[k]===null)expect(result[k]).toBe(null);
    else differences[k]=Math.abs(result[k]-expected.result[k]);
   }
   const difference=Math.max(...Object.values(differences));
   expect(difference).toBeLessThan(2e-7);expect(result.residual).toBeLessThan(1e-8);
   expect(result.trefftz.available).toBe(expected.result.trefftz.available);
   if(expected.result.CDi===null)await expect(page.locator('#cdi')).toHaveText('—');
   rows.push({specification:q,status:'matching_solution',maximum_coefficient_difference:difference,result});
  }
 }
 expect(rows).toHaveLength(17);expect(rows.filter(r=>r.result.CDi===null)).toHaveLength(6);
 expect(errors).toEqual([]);
 await page.screenshot({path:info.outputPath('isae-sa12-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:info.outputPath('isae-sa12-mobile.png'),fullPage:true});
 await writeFile(info.outputPath('isae-sa12-browser.json'),JSON.stringify({status:'PASS',offline:true,
  rows,modules,native_sample_sha256:sha(bytes),sources_sha256:sha(sourceBytes),
  test_sha256:sha(await readFile(import.meta.filename)),web_main_sha256:sha(await readFile('web/main.js'))},null,2)+'\n');
});
