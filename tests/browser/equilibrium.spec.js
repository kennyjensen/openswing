import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
async function downloaded(page,id){const event=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}

test('physical equilibrium export, import and continuation work offline and reject a changed mesh',async({page,context})=>{
  test.setTimeout(300000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('instrumented-oscillator');await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('mounted');await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#powers input').fill('1');await context.setOffline(true);await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:120000});
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);
  const saved=await downloaded(page,'#equilibrium-save');expect(saved.format).toBe('openswing-equilibrium');expect(saved.positions.at(-1)[1]).toBeCloseTo(2.002,8);
  await page.locator('#equilibrium-use').click();await expect(page.locator('#equilibrium-enable')).toBeChecked();
  await page.locator('#powers input').fill('3');await page.locator('#speed').fill('40');await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:120000});
  const warm=await downloaded(page,'#export-json');expect(warm.equilibrium_initialization.initialization).toBe('saved physical equilibrium');expect(warm.sensors[1].displacement_body[1]).toBeCloseTo(.006,8);
  expect(warm.support_force[1]).toBeCloseTo(-3,6);expect(warm.equilibrium_state.positions.at(-1)[1]).toBeCloseTo(2.006,8);
  await page.locator('#equilibrium-clear').click();await expect(page.locator('#equilibrium-enable')).toBeDisabled();
  await page.locator('#equilibrium-file').setInputFiles({name:'saved.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(saved))});await expect(page.locator('#equilibrium-status')).toContainText('saved.json');
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-count').fill('2');await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  const modal=await downloaded(page,'#export-json');expect(modal.base.equilibrium_initialization.initialization).toBe('saved physical equilibrium');expect(modal.base.sensors[1].displacement_body[1]).toBeCloseTo(.006,8);
  const snapshot=await downloaded(page,'#equilibrium-save');await page.locator('#modal-phase').fill('90');expect(await downloaded(page,'#equilibrium-save')).toEqual(snapshot);
  await page.locator('#equilibrium-settings').screenshot({path:'test-results/equilibrium.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();await page.locator('#equilibrium-settings').screenshot({path:'test-results/equilibrium-mobile.png'});
  await page.locator('#mode').selectOption('time');await expect(page.locator('#equilibrium-enable')).toBeEnabled();
  await page.locator('#mode').selectOption('mounted');await page.locator('#panels').fill('8');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#solve').click();
  await expect(page.locator('#error')).toBeVisible();await expect(page.locator('#error p')).toContainText('mesh');await expect(page.locator('#equilibrium-save')).toBeDisabled();
  expect(errors).toEqual([]);
});
