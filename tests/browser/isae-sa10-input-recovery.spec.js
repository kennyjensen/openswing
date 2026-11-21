import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const sha=b=>createHash('sha256').update(b).digest('hex');
test('loading a valid model clears the previous attachment error',async({page,context},info)=>{
 const bytes=await readFile('docs/validation/isae-sa10-sources.json'),sources=JSON.parse(bytes);
 const invalid=sources.models.find(m=>m.name==='TS_60_45_30');
 const valid=sources.models.find(m=>m.name==='wing_alone');
 await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await context.setOffline(true);
 for(const model of [invalid,valid]){
  await page.locator('#file').setInputFiles({name:model.name+'.asw',mimeType:'text/plain',buffer:Buffer.from(model.source)});
  await expect(page.locator('#editor')).toHaveValue(model.source);
  if(model===invalid){
   await expect(page.locator('#runtime-status')).toHaveText('Configuration needs attention');
   await expect(page.locator('#error')).toContainText("Attachment station is outside beam 2's parameter range.");
   await expect(page.locator('#solve')).toBeDisabled();
  }else{
   await expect(page.locator('#runtime-status')).toHaveText('Configuration ready');
   await expect(page.locator('#solve')).toBeEnabled();
   await page.screenshot({path:info.outputPath('input-recovery.png'),fullPage:true});
   await expect(page.locator('#error')).toBeHidden({timeout:5000});
  }
 }
 await writeFile(info.outputPath('input-recovery.json'),JSON.stringify({status:'PASS',offline:true,sources_sha256:sha(bytes),test_sha256:sha(await readFile(import.meta.filename)),web_main_sha256:sha(await readFile('web/main.js'))},null,2)+'\n');
});
