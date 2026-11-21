import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
async function saved(page){const event=page.waitForEvent('download');await page.locator('#export-json').click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}

test('offline mixed modes and six harmonic frame inputs preserve physical units and exports',async({page,context})=>{
  test.setTimeout(360000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#example').selectOption('guided-body');await expect(page.locator('#model-name')).toHaveText('Guided rigid-body demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-frame').selectOption('mixed');await expect(page.locator('#frequency-load-settings')).toBeVisible();await page.locator('#frequency-load-Mz').selectOption('load');await page.locator('#frequency-inputs').selectOption('frame');
  await page.locator('#frequency-start').fill('1');await page.locator('#frequency-end').fill('3');await page.locator('#frequency-count').fill('2');await context.setOffline(true);
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  const result=await saved(page);expect(result.frame_mode).toBe('mixed');expect(result.frame_load_targets).toEqual({'force.x':0,'moment.z':0});
  expect(result.inputs.map(v=>v.name)).toEqual(['target.force.x','acceleration.y','acceleration.z','angular_acceleration.x','angular_acceleration.y','target.moment.z']);
  for(const s of result.samples){const w=s.omega;expect(s.responses[0].output.frame.velocity_origin_body.imag[0]).toBeCloseTo(1/w,7);expect(s.responses[1].output.frame.position_earth.real[1]).toBeCloseTo(-1/w**2,7);expect(s.responses[5].output.frame.rates_body.imag[2]).toBeCloseTo(.25/w,7);expect(s.responses[5].output.global.applied_moment.real[2]).toBeCloseTo(1,7);}
  await page.locator('#frequency-input').selectOption('5');await page.locator('#frequency-group').selectOption('frame');await page.locator('#frequency-quantity').selectOption({label:'rates body z [rad/T]'});await expect(page.locator('#frequency-unit')).toContainText('input F L');await expect(page.locator('#frequency-gain-plot svg')).toBeVisible();
  const event=page.waitForEvent('download');await page.locator('#frequency-csv').click();const csv=await readFile(await(await event).path(),'utf8');expect(csv).toContain('target.moment.z');expect(csv).toContain('rad/T / (input F L)');
  await page.locator('#frequency-settings').screenshot({path:'test-results/dynamic-constraints.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();await page.locator('#frequency-settings').screenshot({path:'test-results/dynamic-constraints-mobile.png'});
  await page.locator('#frequency-target-Fx').fill('1');await expect(page.locator('#export-json')).toBeDisabled();await expect(page.locator('#frequency-transport')).toBeHidden();
  await page.locator('#frequency-load-Fx').selectOption('prescribed');await page.locator('#frequency-load-Mz').selectOption('prescribed');await page.locator('#solve').click();await expect(page.locator('#error p')).toContainText('at least one net-load');
  await page.locator('#frequency-frame').selectOption('fixed');await page.locator('#solve').click();await expect(page.locator('#error p')).toContainText('free or mixed');
  await page.locator('#frequency-frame').selectOption('prescribed');await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  const prescribed=await saved(page);expect(prescribed.frame_mode).toBe('prescribed');expect(prescribed.frame_load_targets).toEqual({});expect(prescribed.inputs.map(v=>v.name)).toEqual(['acceleration.x','acceleration.y','acceleration.z','angular_acceleration.x','angular_acceleration.y','angular_acceleration.z']);
  for(const s of prescribed.samples){expect(s.responses[0].output.frame.velocity_origin_body.imag[0]).toBeCloseTo(-1/s.omega,7);expect(s.responses[5].output.frame.rates_body.imag[2]).toBeCloseTo(-1/s.omega,7);expect(s.responses[5].output.global.applied_moment.real[2]).toBeCloseTo(-4,7);}
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-frame').selectOption('mixed');await page.locator('#modal-load-Mz').selectOption('load');await page.locator('#modal-count').fill('12');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});const modes=await saved(page);expect(modes.frame_load_targets).toEqual({'force.x':0,'moment.z':0});expect(modes.diagnostics.finite_dimension).toBe(12);expect(modes.modes.every(m=>Math.hypot(...m.eigenvalue)<1e-6)).toBeTruthy();await expect(page.locator('#modal-roots svg')).toBeVisible();
  await page.locator('#rom-settings').evaluate(e=>e.open=true);expect(await page.locator('#rom-inputs option').allTextContents()).toContain('target force x');expect(await page.locator('#rom-inputs option').allTextContents()).toContain('angular_acceleration y');
  await page.locator('#modal-target-Fx').fill('.1');await expect(page.locator('#export-json')).toBeDisabled();await expect(page.locator('#mode-transport')).toBeHidden();expect(errors).toEqual([]);
});
