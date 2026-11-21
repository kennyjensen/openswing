import {test,expect} from '@playwright/test';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const sha=b=>createHash('sha256').update(b).digest('hex');
const ready=async page=>{await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();};

test('SA-14 extended polar states, frozen influences and validity rejections reproduce offline',async({page,context},info)=>{
 test.setTimeout(600000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const bytes=await readFile('docs/validation/isae-sa14-polars.json'),study=JSON.parse(bytes);
 const sourceBytes=await readFile('docs/validation/isae-sa14-sources.json'),sources=JSON.parse(sourceBytes);
 const wasmBytes=await readFile('docs/validation/isae-sa14-polars-wasm.json'),wasm=JSON.parse(wasmBytes),modules={};
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py')))modules[n]=sha(await readFile('openswing/'+n));
 expect(modules).toEqual(study.provenance.modules);expect(sha(sourceBytes)).toBe(study.provenance.inputs['docs/validation/isae-sa14-sources.json']);
 expect(wasm.status).toBe('PASS_EXTENDED_POLAR_RUNTIME_REPLAY');expect(wasm.native_sha256).toBe(sha(bytes));
 await page.goto('/');await ready(page);await context.setOffline(true);
 await page.locator('#panels').fill('100');await page.locator('#panels').press('Tab');await ready(page);
 const rows=[];
 for(const name of ['wing_body','infinite_body','wing_only']){
  const source=sources.models.find(c=>c.name===name).source;
  await page.locator('#file').setInputFiles({name:name+'.asw',mimeType:'text/plain',buffer:Buffer.from(source)});
  await expect(page.locator('#editor')).toHaveValue(source);await ready(page);
  await page.locator('#mode').selectOption('rigid');await page.locator('#speed').fill('70');await page.locator('#beta').fill('0');
  for(const id of ['mach-mode','ground-effect','freeze-influences'])await page.locator('#'+id).evaluate(el=>{
   for(let p=el.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;
  });
  await page.locator('#ground-effect').selectOption('0');
  const find=(alpha,pg,frozen)=>study.rows.find(r=>r.specification.case===name&&r.specification.panels===100&&r.specification.alpha===alpha&&r.specification.pg===pg&&r.specification.frozen===frozen);
  const selected=[find(0,'zero',false),find(31,'speed',false),find(31,'zero',true)];
  if(name!=='infinite_body')selected.push(study.rows.filter(r=>r.specification.case===name&&r.specification.panels===100&&r.specification.pg==='primary_0.19'&&r.specification.frozen).sort((a,b)=>b.specification.alpha-a.specification.alpha)[0]);
  if(name==='wing_only')selected.push(find(0,'zero',false)); // recovery after a stopped state
  for(const expected of selected){
   expect(expected).toBeTruthy();const q=expected.specification;
   expect(sha(await readFile(expected.cache_path))).toBe(expected.cache_sha256);
   await page.locator('#alpha').fill(String(q.alpha));await page.locator('#freeze-influences').setChecked(q.frozen);
   await page.locator('#mach-mode').selectOption(q.pg==='speed'?'auto':'fixed');
   if(q.pg!=='speed')await page.locator('#pg-mach').fill(q.pg==='zero'?'0':'0.19');
   await page.locator('#solve').click();
   if(expected.status==='rejected'){
    expect(expected.details.kind).toBe('section_normal_mach');
    await expect(page.locator('#runtime-status')).toHaveText('Analysis stopped',{timeout:180000});
    await expect(page.locator('#error')).toContainText('Local section-normal Mach reaches unity');
    await expect(page.locator('#export-json')).toBeDisabled();
    const error=await page.locator('#error').innerText(),match=error.match(/Maximum M_perp=([\d.eE+-]+)/);expect(match).not.toBeNull();
    const difference=Math.abs(Number(match[1])-expected.details.maximum.normal_mach);expect(difference).toBeLessThan(2e-5);
    rows.push({specification:q,status:'matching_rejection',error,maximum_normal_mach_difference:difference});continue;
   }
   await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});await ready(page);
   const download=page.waitForEvent('download');await page.locator('#export-json').click();
   const result=JSON.parse(await readFile(await(await download).path(),'utf8'));
   expect(result.software_provenance.modules).toEqual(modules);expect(result.request.source).toBe(source);
   expect(result.request.condition.freeze_influences).toBe(q.frozen);
   expect(result.request.condition.mach).toBe(q.pg==='speed'?null:q.pg==='zero'?0:0.19);
   const r=expected.result,differences=[];
   for(const [k,v] of Object.entries(r.coefficients)){if(v===null)expect(result[k]).toBe(null);else differences.push(Math.abs(result[k]-v));}
   const coefficient=Math.max(...differences);expect(coefficient).toBeLessThan(2e-8);
   const cache=JSON.parse(await readFile(expected.cache_path));expect(result.strips.length).toBe(cache.result.strips.length);
   const force=Math.max(...result.strips.map(s=>{
    const p=cache.result.strips.find(p=>p.beam===s.beam&&Math.abs(p.t-s.t)<1e-10);expect(p).toBeTruthy();
    return Math.max(...s.force.map((v,i)=>Math.abs(v-p.force[i])));
   }));expect(force).toBeLessThan(2e-5);expect(result.residual).toBeLessThan(1e-8);
   rows.push({specification:q,status:'matching_solution',maximum_coefficient_difference:coefficient,maximum_strip_force_difference:force,result});
  }
 }
 expect(rows).toHaveLength(12);expect(rows.some(r=>r.status==='matching_rejection')).toBe(true);expect(rows.at(-1).status).toBe('matching_solution');expect(errors).toEqual([]);
 await page.screenshot({path:info.outputPath('isae-sa14-polars-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:info.outputPath('isae-sa14-polars-mobile.png'),fullPage:true});
 await writeFile(info.outputPath('isae-sa14-polars-browser.json'),JSON.stringify({status:'PASS_EXTENDED_POLAR_OFFLINE_BROWSER',offline:true,
  rows,modules,native_sha256:sha(bytes),sources_sha256:sha(sourceBytes),wasm_sha256:sha(wasmBytes),
  test_sha256:sha(await readFile(import.meta.filename)),web_main_sha256:sha(await readFile('web/main.js'))},null,2)+'\n');
});
