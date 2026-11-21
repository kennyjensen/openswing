import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
async function download(page,id){const event=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}

test('Fourier circulation solves offline, preserves physical saved states and exposes local defects',async({page,context})=>{
  test.setTimeout(240000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles('examples/rectangular.asw');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#circulation-settings').evaluate(e=>e.open=true);
  const modes=page.locator('[data-circulation-beam="1"]');await modes.fill('3');
  await page.locator('#mode').selectOption('mounted');
  await context.setOffline(true);await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged');
  const base=await download(page,'#export-json');
  expect(base.condition.circulation_modes).toEqual({'1':3});
  expect(base.circulation_discretization.independent_unknowns).toBe(3);
  expect(base.lifting_panels).toBeGreaterThan(3);expect(base.circulation_residual).toHaveLength(3);
  expect(Math.max(...base.circulation_local_residual.map(Math.abs))).toBeGreaterThan(1e-6);
  await expect(page.locator('#circulation-note')).toContainText('3 circulation unknowns');
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);
  const saved=await download(page,'#equilibrium-save');expect(saved.identity.circulation_modes).toEqual({'1':3});
  expect(saved.circulation).toHaveLength(base.lifting_panels);
  await page.locator('#equilibrium-use').click();await page.locator('#mode').selectOption('time');
  await page.locator('#time-duration').fill('.02');await page.locator('#time-step').fill('.01');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Time integration converged');
  const history=await download(page,'#export-json');
  for(const s of history.snapshots){expect(s.circulation_residual).toHaveLength(3);expect(s.circulation_rate).toHaveLength(base.lifting_panels);expect(s.CL).toBeCloseTo(base.CL,8);}
  await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText('CIRCULATION DISCRETIZATION');
  await page.screenshot({path:'test-results/fourier-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await expect(page.locator('#circulation-note')).toBeVisible();await page.locator('#circulation-note').scrollIntoViewIfNeeded();
  await page.screenshot({path:'test-results/fourier-mobile.png'});
  await page.locator('#mode').selectOption('mounted');await modes.fill('2');
  await expect(page.locator('#circulation-note')).toBeHidden();
  await page.locator('#solve').click();await expect(page.locator('#error')).toBeVisible();
  await expect(page.locator('#error p')).toContainText('mesh');
  await page.locator('#equilibrium-clear').click();await page.locator('#mode').selectOption('rigid');await modes.fill('100');
  await page.locator('#solve').click();await expect(page.locator('#error p')).toContainText('mode count exceeds');
  expect(errors).toEqual([]);
});
