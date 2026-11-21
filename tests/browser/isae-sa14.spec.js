import {test,expect} from '@playwright/test';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const sha=b=>createHash('sha256').update(b).digest('hex');
const ready=async page=>{await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();};

test('SA-14 original inputs, mixed PG settings and body loads reproduce offline',async({page,context},info)=>{
 test.setTimeout(600000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const bytes=await readFile('docs/validation/isae-sa14-pilot.json'),study=JSON.parse(bytes);
 const sourceBytes=await readFile('docs/validation/isae-sa14-sources.json'),sources=JSON.parse(sourceBytes);
 const wasmBytes=await readFile('docs/validation/isae-sa14-wasm.json'),wasm=JSON.parse(wasmBytes),modules={};
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py')))modules[n]=sha(await readFile('openswing/'+n));
 expect(modules).toEqual(study.provenance.modules);expect(sha(sourceBytes)).toBe(study.provenance.source_report_sha256);
 await page.goto('/');await ready(page);await context.setOffline(true);
 await page.locator('#panels').fill('50');await page.locator('#panels').press('Tab');await ready(page);
 const rows=[],display=[];let expectedCount=0;
 // End with the valid wing-only input to check recovery after source failures.
 const order=['wing_body','infinite_body','body_only','wing_only'];
 for(const name of order){
  const c=sources.models.find(c=>c.name===name),outcome=wasm.display.find(c=>c.case===name).actual;
  await page.locator('#file').setInputFiles({name:name+'.asw',mimeType:'text/plain',buffer:Buffer.from(c.source)});
  await expect(page.locator('#editor')).toHaveValue(c.source);
  if(outcome.status==='rejected'){
   await expect(page.locator('#runtime-status')).toHaveText('Configuration needs attention');
   await expect(page.locator('#error')).toContainText(outcome.error);
   await expect(page.locator('#solve')).toBeDisabled();await expect(page.locator('#export-json')).toBeDisabled();
   display.push({case:name,status:'matching_rejection',error:await page.locator('#error').innerText()});continue;
  }
  await ready(page);display.push({case:name,status:'constructed'});
  await page.locator('#mode').selectOption('rigid');await page.locator('#speed').fill('70');await page.locator('#beta').fill('0');
  for(const id of ['mach-mode','ground-effect'])await page.locator('#'+id).evaluate(el=>{
   for(let p=el.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;
  });
  await page.locator('#ground-effect').selectOption('0');await page.locator('#freeze-influences').uncheck();
  const selected=study.rows.filter(r=>r.specification.case===name&&r.specification.panels===50&&
    ((r.specification.pg==='speed'&&[0,4.7].includes(r.specification.alpha))||
     (r.specification.pg==='zero'&&[0,8.8,12.9].includes(r.specification.alpha))||
     (r.specification.pg==='primary_0.19'&&r.specification.alpha===8.8)));
  expectedCount+=selected.length;
  for(const expected of selected){
   const q=expected.specification,r=expected.result;expect(sha(await readFile(expected.cache_path))).toBe(expected.cache_sha256);
   await page.locator('#alpha').fill(String(q.alpha));
   await page.locator('#mach-mode').selectOption(q.pg==='speed'?'auto':'fixed');
   if(q.pg!=='speed')await page.locator('#pg-mach').fill(String(r.actual_mach));
   await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});await ready(page);
   const download=page.waitForEvent('download');await page.locator('#export-json').click();
   const result=JSON.parse(await readFile(await(await download).path(),'utf8'));
   expect(result.software_provenance.modules).toEqual(modules);expect(result.request.source).toBe(c.source);
   expect(result.request.condition.mach).toBe(q.pg==='speed'?null:r.actual_mach);
   const differences={};
   for(const [k,v] of Object.entries(r.coefficients)){
    if(v===null)expect(result[k]).toBe(null);else differences[k]=Math.abs(result[k]-v);
   }
   const coefficient=Math.max(...Object.values(differences));expect(coefficient).toBeLessThan(2e-8);
   const strips=[...r.profiles,...r.body_strips];expect(result.strips.length).toBe(strips.length);
   const forces=result.strips.map(s=>{
    const p=strips.find(p=>p.beam===s.beam&&Math.abs(p.t-s.t)<1e-10);expect(p).toBeTruthy();
    return Math.max(...s.force.map((v,i)=>Math.abs(v-p.force[i])));
   });
   const force=Math.max(...forces);expect(force).toBeLessThan(2e-5);expect(result.residual).toBeLessThan(1e-8);
   rows.push({specification:q,status:'matching_solution',maximum_coefficient_difference:coefficient,maximum_strip_force_difference:force,result});
  }
 }
 expect(rows.length).toBe(expectedCount);expect(rows.length).toBeGreaterThan(0);expect(display).toHaveLength(4);expect(errors).toEqual([]);
 await page.screenshot({path:info.outputPath('isae-sa14-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:info.outputPath('isae-sa14-mobile.png'),fullPage:true});
 await writeFile(info.outputPath('isae-sa14-browser.json'),JSON.stringify({status:'PASS_EXPECTED_OUTCOMES',offline:true,
  rows,display,modules,native_sha256:sha(bytes),sources_sha256:sha(sourceBytes),wasm_sha256:sha(wasmBytes),
  test_sha256:sha(await readFile(import.meta.filename)),web_main_sha256:sha(await readFile('web/main.js'))},null,2)+'\n');
});
