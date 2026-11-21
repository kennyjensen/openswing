import {test,expect} from '@playwright/test';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const sha=b=>createHash('sha256').update(b).digest('hex');
const ready=async page=>{await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();};

test('SA-14 explicit incidence models reproduce eight native states offline',async({page,context},info)=>{
 test.setTimeout(600000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const bytes=await readFile('docs/validation/isae-sa14-incidence.json'),study=JSON.parse(bytes);
 const sourceBytes=await readFile('docs/validation/isae-sa14-incidence-sources.json'),sources=JSON.parse(sourceBytes);
 const modules={};for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py')))modules[n]=sha(await readFile('openswing/'+n));
 expect(modules).toEqual(study.provenance.modules);expect(sha(sourceBytes)).toBe(study.provenance.incidence_source_sha256);
 await page.goto('/');await ready(page);await context.setOffline(true);
 const rows=[];
 for(const name of ['wing_frame','body_frame']){
  const source=sources.variants[name].source;
  await page.locator('#panels').fill('50');await page.locator('#panels').press('Tab');await ready(page);
  await page.locator('#file').setInputFiles({name:'isae-sa14-iw4-'+name+'.asw',mimeType:'text/plain',buffer:Buffer.from(source)});
  await expect(page.locator('#editor')).toHaveValue(source);await ready(page);
  await page.locator('#mode').selectOption('rigid');await page.locator('#speed').fill('70');await page.locator('#beta').fill('0');
  for(const id of ['mach-mode','ground-effect'])await page.locator('#'+id).evaluate(el=>{
   for(let p=el.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;
  });
  await page.locator('#ground-effect').selectOption('0');await page.locator('#freeze-influences').uncheck();
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0.19');
  const selected=study.rows.filter(r=>r.specification.case===name&&r.specification.pg==='primary_0.19'&&
    (r.specification.panels===50||(r.specification.panels===100&&r.specification.alpha_w===12.9)));
  expect(selected).toHaveLength(4);
  for(const expected of selected){
   const q=expected.specification,r=expected.result;expect(sha(await readFile(expected.cache_path))).toBe(expected.cache_sha256);
   await page.locator('#panels').fill(String(q.panels));await page.locator('#panels').press('Tab');await ready(page);
   await page.locator('#alpha').fill(String(q.alpha));
   await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});await ready(page);
   const download=page.waitForEvent('download');await page.locator('#export-json').click();
   const result=JSON.parse(await readFile(await(await download).path(),'utf8'));
   expect(result.software_provenance.modules).toEqual(modules);expect(result.request.source).toBe(source);
   expect(result.request.condition.mach).toBe(.19);expect(result.request.condition.alpha).toBe(q.alpha);
   const differences={};for(const [k,v] of Object.entries(r.coefficients)){
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
 expect(rows).toHaveLength(8);expect(errors).toEqual([]);
 await page.screenshot({path:info.outputPath('isae-sa14-incidence-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:info.outputPath('isae-sa14-incidence-mobile.png'),fullPage:true});
 await writeFile(info.outputPath('isae-sa14-incidence-browser.json'),JSON.stringify({status:'PASS_8_INCIDENCE_OFFLINE_BROWSER_REPLAYS',offline:true,
  rows,modules,native_sha256:sha(bytes),incidence_sources_sha256:sha(sourceBytes),
  test_sha256:sha(await readFile(import.meta.filename)),web_main_sha256:sha(await readFile('web/main.js'))},null,2)+'\n');
});
