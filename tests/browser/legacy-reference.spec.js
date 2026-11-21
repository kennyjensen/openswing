import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

test('published zero-origin legacy model imports, solves and saves unchanged offline',async({page,context},info)=>{
 test.setTimeout(180000);
 const probe=JSON.parse(await readFile('docs/validation/reference-browser-probe.json','utf8'));
 const source=await readFile(probe.path,'utf8');
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
 await context.setOffline(true);
 await page.locator('#file').setInputFiles(probe.path);
 await expect(page.locator('#editor')).toHaveValue(source);
 await expect(page.locator('#solve')).toBeEnabled();
 let download=page.waitForEvent('download');await page.locator('#save').click();
 expect(await readFile(await(await download).path(),'utf8')).toBe(source);
 await page.locator('#mode').selectOption('rigid');
 await page.locator('#panels').fill(String(probe.settings.panels));await page.locator('#panels').press('Tab');
 await expect(page.locator('#solve')).toBeEnabled();
 for(const key of ['speed','alpha','beta'])await page.locator('#'+key).fill(String(probe.settings[key]));
 await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
 await page.locator('#density-mode').selectOption('custom');await page.locator('#density').fill(String(probe.settings.density));
 await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
 await page.locator('#solve').click();await expect(page.locator('#result-state')).toHaveText('Converged · rigid geometry');
 download=page.waitForEvent('download');await page.locator('#export-json').click();
 const result=JSON.parse(await readFile(await(await download).path(),'utf8'));
 // Required attachment/control stations may split a requested interval.
 expect(result.panels).toBe(probe.result.panels);expect(result.residual).toBeLessThan(1e-8);
 for(const key of ['CL','CD','CY','Cm','Cl','Cn','CDi','CDp'])expect(Math.abs(result[key]-probe.result[key])).toBeLessThan(2e-12);
 expect(result.software_provenance.modules).toEqual(probe.modules);
 const audit=JSON.parse(await readFile('docs/validation/reference-setup.json','utf8'));
 const rejected=audit.cases.find(r=>r.path.includes('ST2')&&r.path.includes('Modal_Undeformed'));
 expect(rejected.status).toBe('rejected');
 const prefix=probe.path.slice(0,probe.path.indexOf('/3 - Structure/'));
 await page.locator('#file').setInputFiles(prefix+'/'+rejected.path);
 await expect(page.locator('#editor')).toHaveValue(await readFile(prefix+'/'+rejected.path,'utf8'));
 // Browser inspection also constructs attachment geometry and rejects this
 // source before analysis. Await the new document, not a stale enabled button.
 await expect(page.locator('#error')).toContainText("Attachment station is outside beam 1's parameter range.");
 await expect(page.locator('#solve')).toBeDisabled();
 expect(errors).toEqual([]);
 await writeFile(info.outputPath('reference-browser.json'),JSON.stringify({status:'PASS',kernelModules:probe.modules,
  source_sha256:createHash('sha256').update(source).digest('hex'),result,
  rejected_source:rejected.path,rejected_error:rejected.error,rejection_stage:'browser_geometry_inspection',offline:true},null,2)+'\n');
});
