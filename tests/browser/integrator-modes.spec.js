import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
async function saved(page){const event=page.waitForEvent('download');await page.locator('#export-json').click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}

test('offline rotating rigid modes keep exact integrators distinct from physical instability',async({page,context})=>{
  test.setTimeout(300000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#example').selectOption('guided-body');await expect(page.locator('#model-name')).toHaveText('Guided rigid-body demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#motion-settings').evaluate(e=>e.open=true);await page.locator('#rates-y').fill(String(360/Math.PI));
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-frame').selectOption('mixed');await page.locator('#modal-load-Fx').selectOption('prescribed');await page.locator('#modal-load-Mx').selectOption('load');await page.locator('#modal-load-Mz').selectOption('load');await page.locator('#modal-vacuum').check();await page.locator('#modal-count').fill('12');
  await context.setOffline(true);await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  const result=await saved(page);const zero=result.modes.filter(m=>m.exact_integrator);expect(zero).toHaveLength(8);expect(zero.every(m=>m.eigenvalue[0]===0&&m.eigenvalue[1]===0&&m.stability==='neutral')).toBeTruthy();
  expect(result.diagnostics.integrator_deflation.count).toBe(8);expect(result.diagnostics.finite_dimension).toBe(12);expect(result.modes.filter(m=>m.stability==='unstable')).toHaveLength(1);
  const unstable=result.modes.findIndex(m=>m.stability==='unstable');expect(result.modes[unstable].eigenvalue[0]).toBeCloseTo(1/Math.sqrt(2),7);expect(result.modes[unstable].exact_integrator).toBe(false);
  await expect(page.locator('#modal-summary')).toContainText('8 exact zero roots identified');await page.locator('#modal-select').selectOption(String(result.modes.findIndex(m=>m.exact_integrator)));await expect(page.locator('#modal-detail')).toContainText('Exact zero from an integrator equation');
  const oscillatory=result.modes.findIndex(m=>Math.abs(m.eigenvalue[1])>1);expect(result.modes[oscillatory].stability).toBe('near neutral');expect(result.modes[oscillatory].stability_tolerance).toBeGreaterThan(0);await page.locator('#modal-select').selectOption(String(oscillatory));await expect(page.locator('#modal-detail')).toContainText('not an error bound');
  let event=page.waitForEvent('download');await page.locator('#modal-csv').click();const csv=await readFile(await(await event).path(),'utf8');expect(csv).toContain('exact integrator');expect(csv).toContain('growth display threshold [1/T]');expect(csv.trim().split('\n')).toHaveLength(13);
  await page.locator('#modal-select').selectOption(String(unstable));await expect(page.locator('#modal-detail')).toContainText('unstable');await page.locator('#modal-view').selectOption('earth');await page.locator('#modal-phase').fill('90');expect(await saved(page)).toEqual(result);
  await page.locator('#pane-modes').screenshot({path:'test-results/integrator-modes.png'});await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();await page.locator('#pane-modes').screenshot({path:'test-results/integrator-modes-mobile.png'});expect(errors).toEqual([]);
});
