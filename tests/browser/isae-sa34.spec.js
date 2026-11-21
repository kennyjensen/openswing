import {test,expect} from '@playwright/test';
import {readFile,writeFile,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
test('literal SA-3/4 inputs solve and export offline with Fortran numeric syntax',async({page,context},info)=>{
 test.setTimeout(240000);
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
  const kernelModules={},served=new Set();
  if(process.env.OPENSWING_KERNEL){
    const root=path.resolve(process.env.OPENSWING_KERNEL,'openswing');
    const names=(await readdir(root)).filter(name=>name.endsWith('.py'));
    const sources=new Map();
    for(const name of names){
      const bytes=await readFile(path.join(root,name));sources.set(name,bytes);
      kernelModules[name]=createHash('sha256').update(bytes).digest('hex');
    }
    await context.route('**/kernel/**',async route=>{
      const name=new URL(route.request().url()).pathname.split('/').pop();
      if(name==='sources.json'){
        names.forEach(name=>served.add(name));
        return route.fulfill({contentType:'application/json',body:JSON.stringify({format:'openswing-kernel-sources',version:1,
          sources:names.map(name=>[name,sources.get(name).toString('utf8')])})});
      }
      if(name==='manifest.json')return route.fulfill({contentType:'application/json',body:JSON.stringify(names)});
      if(!names.includes(name))throw new Error('Unexpected kernel module '+name);
      served.add(name);
      await route.fulfill({contentType:'text/plain',body:sources.get(name)});
    });
  }

 const probes=JSON.parse(await readFile('docs/validation/isae-sa34-probes.json','utf8'));
 if(!process.env.OPENSWING_KERNEL){
  const audit=JSON.parse(await readFile('docs/validation/reference-compatibility.json','utf8'));
  expect(probes.modules).toEqual(audit.baseline_modules);
  expect(Object.keys(audit.candidate_modules).filter(n=>audit.candidate_modules[n]!==audit.baseline_modules[n])).toEqual(['asw.py']);
  for(const probe of probes.cases){
   const digest=createHash('sha256').update(await readFile(probe.path)).digest('hex');
   const before=audit.baseline_snapshot.records.find(r=>r.source_sha256===digest);
   const after=audit.candidate_snapshot.records.find(r=>r.path===before.path);
   expect(before.literal.status).toBe('parsed');expect(after.literal).toEqual(before.literal);
  }
  Object.assign(kernelModules,audit.candidate_modules);
 }
 await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
 await context.setOffline(true);
 const results=[];
 for(const probe of probes.cases){
  const source=await readFile(probe.path,'utf8');
  await page.locator('#file').setInputFiles(probe.path);
  await expect(page.locator('#editor')).toHaveValue(source);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#panels').fill('100');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#speed').fill('89.4');await page.locator('#alpha').fill('5');await page.locator('#beta').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#density-mode').selectOption('custom');await page.locator('#density').fill('1.2256');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#solve').click();await expect(page.locator('#result-state')).toHaveText('Converged · rigid geometry');
  const event=page.waitForEvent('download');await page.locator('#export-json').click();
  const result=JSON.parse(await readFile(await(await event).path(),'utf8'));
  expect(result.panels).toBe(100);expect(result.residual).toBeLessThan(1e-8);
  for(const key of ['CL','CD','Cm','CDi','CDp'])expect(Math.abs(result[key]-probe.result[key])).toBeLessThan(2e-7);
  expect(result.software_provenance.modules).toEqual(kernelModules);
  results.push({case:probe.case,result});
 }
 await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.screenshot({path:info.outputPath('sa34-mobile.png')});
 expect(errors).toEqual([]);if(process.env.OPENSWING_KERNEL)expect(served.size).toBe(Object.keys(kernelModules).length);
 await writeFile(info.outputPath('sa34-browser.json'),JSON.stringify({status:'PASS',results,kernelModules}));
});
