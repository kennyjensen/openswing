import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
async function downloaded(page,id,json=true){const event=page.waitForEvent('download');await page.locator(id).click();const text=await readFile(await(await event).path(),'utf8');return json?JSON.parse(text):text;}

test('offline aeroelastic speed progression brackets instability, preserves point modes and invalidates edited sweeps',async({page,context})=>{
  test.setTimeout(600000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('heave-pitch');await expect(page.locator('#model-name')).toHaveText('Heave and pitch research wing');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#speed').fill('40');await page.locator('#alpha').fill('0');await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-count').fill('8');await page.locator('#modal-step').evaluate(e=>e.closest('details').open=true);await page.locator('#modal-step').fill('0.000001');
  await context.setOffline(true);await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  const initial=await downloaded(page,'#export-json');
  await page.locator('#stability-settings').evaluate(e=>e.open=true);await page.locator('#stability-values').fill('40, 45, 50');await page.locator('#stability-refine').uncheck();await page.locator('#stability-adaptive').check();await page.locator('#stability-absolute').fill('0.001');await page.locator('#stability-build').click();
  await expect(page.locator('#runtime-status')).toHaveText('Stability sweep finished',{timeout:300000});
  const result=await downloaded(page,'#stability-json');expect(result.converged).toBeTruthy();expect(result.spectrum_complete).toBeTruthy();
  expect(result.settings.parameter_atol).toBe(.001);expect(result.settings.warm_start).toBeTruthy();expect(result.settings.adaptive).toBeTruthy();expect(result.points.every(p=>p.initialization.warm)).toBeTruthy();expect(result.points[1].initialization.parent_value).toBe(40);await expect(page.locator('#stability-summary')).toContainText('1 points with growing roots');expect(result.boundaries).toHaveLength(1);expect(result.boundaries[0].bracket).toEqual([45,50]);expect(result.boundaries[0].direction).toBe('destabilizing');expect(result.boundaries[0].status).toBe('unrefined');
  expect(result.points[2].roots.some(r=>r.eigenvalue[0]>.7&&r.eigenvalue[1]>30)).toBeTruthy();
  expect(await downloaded(page,'#export-json')).toEqual(initial);
  await expect(page.locator('#stability-root-plot svg')).toBeVisible();await expect(page.locator('#stability-growth-plot svg')).toBeVisible();await expect(page.locator('#stability-boundaries')).toContainText('oscillatory instability candidate');
  expect(await downloaded(page,'#stability-csv',false)).toContain('shape assurance');
  await page.locator('#stability-settings').screenshot({path:'test-results/stability.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();await page.locator('#stability-settings').screenshot({path:'test-results/stability-mobile.png'});
  await page.locator('#stability-point').selectOption('2');await page.locator('#stability-inspect').click();
  const point=await downloaded(page,'#export-json');expect(point.condition.speed).toBe(50);expect(point.modes).toEqual(result.points[2].result.modes);await expect(page.locator('#modal-summary')).toContainText('Sweep point: speed = 50');
  await page.locator('#modal-phase').fill('90');expect(await downloaded(page,'#stability-json')).toEqual(result);
  await page.locator('#stability-values').fill('50, 40');await expect(page.locator('#stability-json')).toBeDisabled();await page.locator('#stability-build').click();
  await expect(page.locator('#error')).toBeVisible();await expect(page.locator('#error p')).toContainText('strictly increasing');expect(errors).toEqual([]);
});
