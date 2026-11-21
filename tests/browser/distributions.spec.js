import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
async function download(page,id){const event=page.waitForEvent('download');await page.locator(id).click();return readFile(await(await event).path(),'utf8');}
async function openEditor(page){
 const mobile=page.locator('#workspace-tab-editor');await (await mobile.isVisible()?mobile:page.locator('#tab-editor')).click();
 await page.locator('#properties-panel').evaluate(e=>e.open=true);
}
async function load(page,name){
 const select=page.locator('#distribution-name');
 if(await select.locator('option').evaluateAll((options,value)=>options.some(o=>o.value===value),name))await select.selectOption(name);
 else{await select.selectOption('');await page.locator('#distribution-custom-name').fill(name);await page.locator('#distribution-custom-name').press('Tab');}
 await expect(page.locator('#distribution-name')).toBeEnabled();
}
async function change(page,selector,value){const input=page.locator(selector);await input.fill(value);await input.press('Tab');await expect(page.locator('#distribution-name')).toBeEnabled();}
async function run(page){await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:120000});return JSON.parse(await download(page,'#export-json'));}

test('offline property edits apply automatically, change mechanics, save/reload and undo',async({page,context})=>{
 test.setTimeout(300000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
 const source=await readFile('examples/instrumented-oscillator.asw','utf8');
 await page.locator('#file').setInputFiles({name:'spring.asw',mimeType:'text/plain',buffer:Buffer.from(source)});
 await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');
 await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
 await page.locator('#mode').selectOption('mounted');await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
 await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');await page.locator('#powers input').fill('10');
 await context.setOffline(true);const base=await run(page);expect(base.nodes.at(-1).position[1]).toBeCloseTo(2.02,9);
 await openEditor(page);await load(page,'EA');
 await change(page,'#distribution-scale','2');
 await expect(page.locator('#distribution-plot svg')).toBeVisible();expect((await page.locator('#distribution-plot svg').boundingBox()).height).toBeGreaterThan(100);await expect(page.locator('#export-json')).toBeDisabled();await expect(page.locator('#solve')).toBeEnabled();
 await expect(page.getByRole('spinbutton',{name:'Value 1',exact:true})).toHaveValue('2000');
 await expect(page.locator('#powers input')).toHaveValue('10');
 const saved=await download(page,'#save');expect(saved).toBe(source.replace('0 0 1000 .02\n2 2 1000 .02','0 0 2000 .02\n2 2 2000 .02'));
 const edited=await run(page);expect(edited.nodes.at(-1).position[1]).toBeCloseTo(2.01,9);expect(edited.support_force[1]).toBeCloseTo(-10,7);
 expect(edited.equilibrium_state.identity.model_sha256).not.toBe(base.equilibrium_state.identity.model_sha256);
 await openEditor(page);await expect(page.locator('#distribution-undo')).toBeEnabled();await page.locator('#distribution-undo').click();await expect(page.locator('#solve')).toBeEnabled();
 await expect(page.getByRole('spinbutton',{name:'Value 1',exact:true})).toHaveValue('1000');expect(await download(page,'#save')).toBe(source);
 // Invalid geometry is rejected and leaves the accepted source and solve available.
 await load(page,'y');await change(page,'#distribution-table tbody tr:nth-child(2) td:nth-child(2) input','0');
 await expect(page.locator('#distribution-status')).toHaveClass(/distribution-error/);expect(await download(page,'#save')).toBe(source);await expect(page.locator('#solve')).toBeEnabled();
 // A raw-text draft cannot be overwritten by a property edit or undo.
 await page.locator('#tab-editor').click();await page.locator('#editor').fill(source+'! pending draft\n');await openEditor(page);await expect(page.locator('#distribution-edit')).toBeDisabled();await expect(page.locator('#distribution-undo')).toBeDisabled();await expect(page.locator('#distribution-status')).toContainText('ASW edits');
 // Reopening an edited ASW independently reproduces the same physical response.
 await page.locator('#file').setInputFiles({name:'edited.asw',mimeType:'text/plain',buffer:Buffer.from(saved)});await expect(page.locator('#solve')).toBeEnabled();
 await page.locator('#powers input').fill('10');const reloaded=await run(page);expect(reloaded.nodes.at(-1).position[1]).toBeCloseTo(2.01,9);
 await openEditor(page);await load(page,'EA');await page.locator('#pane-distributions').screenshot({path:'test-results/distribution-editor.png'});
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();await page.locator('#pane-distributions').screenshot({path:'test-results/distribution-editor-mobile.png'});
 expect(errors).toEqual([]);
});

test('station insertion, doubled corners, per-property symmetry and new flap undo',async({page,context})=>{
 await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
 const rectangular=await readFile('examples/rectangular.asw','utf8');await page.locator('#file').setInputFiles({name:'wing.asw',mimeType:'text/plain',buffer:Buffer.from(rectangular)});await expect(page.locator('#solve')).toBeEnabled();
 await context.setOffline(true);await openEditor(page);await load(page,'dCLdF1');
 await expect(page.locator('#distribution-table tbody tr')).toHaveCount(6);await expect(page.locator('#distribution-plot-note')).toContainText('Full station grid');
 await load(page,'alpha');await page.getByRole('button',{name:'Insert after station 1',exact:true}).click();await expect(page.locator('#distribution-table tbody tr')).toHaveCount(3);
 await page.getByRole('button',{name:'Insert after station 2',exact:true}).click();await expect(page.locator('#distribution-name')).toBeEnabled();await change(page,'#distribution-table tbody tr:nth-child(3) td:nth-child(1) input','3');await change(page,'#distribution-table tbody tr:nth-child(3) td:nth-child(2) input','4');await change(page,'#distribution-table tbody tr:nth-child(4) td:nth-child(2) input','4');
 await expect(page.locator('#distribution-plot .distribution-curve')).toHaveCount(4);
 await expect(page.locator('#distribution-table tbody tr')).toHaveCount(4);const corner=await download(page,'#save');expect(corner).toContain('t alpha\n0 0\n3 0\n3 4\n6 4');
 await page.getByRole('button',{name:'Delete station 3',exact:true}).click();await expect(page.locator('#distribution-table tbody tr')).toHaveCount(3);
 await expect(page.locator('#distribution-undo')).toBeEnabled();await page.locator('#distribution-undo').click();await expect(page.locator('#distribution-table tbody tr')).toHaveCount(4);
 await load(page,'dCLdF12');await change(page,'#distribution-offset','.05');await expect(page.locator('[data-control="12"]')).toHaveCount(1);
 await expect(page.locator('#distribution-undo')).toBeEnabled();await page.locator('#distribution-undo').click();await expect(page.locator('[data-control="12"]')).toHaveCount(0);
 expect(await download(page,'#save')).not.toContain('t dCLdF12');
 await load(page,'EA');await expect(page.locator('#distribution-name')).toHaveValue('EA');
});
