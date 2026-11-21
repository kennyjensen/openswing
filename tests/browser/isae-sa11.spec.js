import {test,expect} from '@playwright/test';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

const sha=b=>createHash('sha256').update(b).digest('hex');
const ready=async page=>{
 await expect(page.locator('#solve')).toBeEnabled();
 await expect(page.locator('#error')).toBeHidden();
};

test('SA-11 source errors, native results and local-Mach failures reproduce offline',async({page,context},info)=>{
 test.setTimeout(600000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const bytes=await readFile('docs/validation/isae-sa11-pilot.json'),study=JSON.parse(bytes);
 const sourceBytes=await readFile('docs/validation/isae-sa11-sources.json'),sources=JSON.parse(sourceBytes);
 const modules={};
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py')))modules[n]=sha(await readFile('openswing/'+n));
 expect(modules).toEqual(study.provenance.modules);
 await page.goto('/');await ready(page);await context.setOffline(true);
 await page.locator('#panels').fill('25');await page.locator('#panels').press('Tab');await ready(page);
 const literal=[];
 for(const name of ['wingtip_up','wingtip_up_and_down','wingtip_up_cant0']){
  const model=sources.models.find(c=>c.name===name);
  const expected=model.error||model.setups.find(s=>s.panels===25).error;
  await page.locator('#file').setInputFiles({name:name+'_literal.asw',mimeType:'text/plain',buffer:Buffer.from(model.source)});
  await expect(page.locator('#editor')).toHaveValue(model.source);
  await expect(page.locator('#runtime-status')).toHaveText('Configuration needs attention');
  await expect(page.locator('#error')).toContainText(expected);
  await expect(page.locator('#solve')).toBeDisabled();await expect(page.locator('#export-json')).toBeDisabled();
  literal.push({case:name,status:'matching_rejection',error:await page.locator('#error').innerText()});
 }
 await page.screenshot({path:info.outputPath('isae-sa11-literal-rejection.png'),fullPage:true});
 const rows=[];
 // End on the unmodified extension: also verifies recovery from winglet errors.
 const cases=[...study.cases.filter(c=>c.name!=='wing_extension'),study.cases.find(c=>c.name==='wing_extension')];
 for(const c of cases){
  await page.locator('#file').setInputFiles({name:c.case_id+'.asw',mimeType:'text/plain',buffer:Buffer.from(c.source)});
  await expect(page.locator('#editor')).toHaveValue(c.source);await ready(page);
  await page.locator('#mode').selectOption('rigid');
  await page.locator('#beta').fill('0');
  await page.locator('#mach-mode').evaluate(el=>{for(let p=el.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;});
  await page.locator('#mach-mode').selectOption('auto');
  await page.locator('#freeze-influences').uncheck();
  const speeds=['wing_alone','wing_extension'].includes(c.name)?[240,272]:[240];
  for(const speed of speeds)for(const alpha of [0,5]){
   const expected=c.runs.find(r=>r.specification.speed===speed&&r.specification.alpha===alpha);
   expect(expected.specification).toEqual({case:c.case_id,panels:25,speed,alpha,pg:'speed',frozen:false});
   await page.locator('#speed').fill(String(speed));await page.locator('#alpha').fill(String(alpha));
   await page.locator('#solve').click();
   if(expected.status==='rejected'){
    expect(expected.details.kind).toBe('section_normal_mach');
    await expect(page.locator('#runtime-status')).toHaveText('Analysis stopped',{timeout:180000});
    await expect(page.locator('#error')).toContainText('Local section-normal Mach reaches unity');
    await expect(page.locator('#export-json')).toBeDisabled();
    const error=await page.locator('#error').innerText();
    const match=error.match(/Maximum M_perp=([\d.eE+-]+)/);expect(match).not.toBeNull();
    const difference=Math.abs(Number(match[1])-expected.details.maximum.normal_mach);
    expect(difference).toBeLessThan(2e-5*Math.max(1,expected.details.maximum.normal_mach));
    rows.push({specification:expected.specification,status:'matching_rejection',error,maximum_normal_mach_difference:difference});
    continue;
   }
   await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});await ready(page);
   const event=page.waitForEvent('download');await page.locator('#export-json').click();
   const result=JSON.parse(await readFile(await(await event).path(),'utf8'));
   expect(result.software_provenance.modules).toEqual(modules);expect(result.request.source).toBe(c.source);
   expect(result.request.condition.mach).toBe(null);expect(result.request.condition.freeze_influences).toBe(false);
   const difference=Math.max(...['CL','CD','CDi','CDi_near','CDp','Cm','Cl','Cn','CY'].map(k=>Math.abs(result[k]-expected.result[k])));
   expect(difference).toBeLessThan(2e-7);expect(result.residual).toBeLessThan(1e-8);
   rows.push({specification:expected.specification,status:'matching_solution',maximum_coefficient_difference:difference,result});
  }
 }
 expect(rows).toHaveLength(14);expect(rows.filter(r=>r.status==='matching_solution')).toHaveLength(8);
 expect(errors).toEqual([]);
 await page.screenshot({path:info.outputPath('isae-sa11-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:info.outputPath('isae-sa11-mobile.png'),fullPage:true});
 await writeFile(info.outputPath('isae-sa11-browser.json'),JSON.stringify({status:'PASS',offline:true,
  literal_rejections:literal,rows,modules,pilot_sha256:sha(bytes),sources_sha256:sha(sourceBytes),
  test_sha256:sha(await readFile(import.meta.filename)),web_main_sha256:sha(await readFile('web/main.js'))},null,2)+'\n');
});
