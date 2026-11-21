import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
async function setup(page){
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles('examples/instrumented-oscillator.asw');await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#alpha').fill('0');await page.locator('#speed').fill('10');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
}
async function json(page){const event=page.waitForEvent('download');await page.locator('#export-json').click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}

test('steady sensor table and time histories run offline with specific force, GPS, CSV and input invalidation',async({page,context})=>{
  test.setTimeout(220000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await setup(page);await expect(page.locator('#sensor-settings')).toBeVisible();
  await context.setOffline(true);await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged');
  await page.locator('#tab-sensors').click();await expect(page.locator('#sensor-select option')).toHaveCount(2);await page.locator('#sensor-select').selectOption('2');
  await expect(page.locator('#sensor-table')).toContainText('Specific force');await expect(page.locator('#sensor-detail')).toContainText('rigid-only');
  let event=page.waitForEvent('download');await page.locator('#sensor-csv').click();let csv=await readFile(await(await event).path(),'utf8');
  expect(csv).toContain('physical input units');expect(csv).toContain('velocity_earth.0');
  const rigid=await json(page);expect(rigid.sensors[1].speed).toBeCloseTo(10,10);expect(rigid.sensors[1].velocity_earth[0]).toBeCloseTo(-10,10);
  await page.locator('#mode').selectOption('time');await page.locator('#time-duration').fill('0.06');await page.locator('#time-step').fill('0.02');
  await page.locator('#time-forcing').evaluate(e=>e.closest('details').open=true);
  await page.locator('#time-forcing').fill('time E1\n0 0\n.03 .03\n.06 .06\n');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:140000});
  await page.locator('#time-quantity').selectOption('sensor.acceleration_sensor.1');await page.locator('#time-sensor').selectOption('2');await expect(page.locator('#time-plot svg')).toBeVisible();
  const result=await json(page);expect(result.snapshots.at(-1).sensors[1].acceleration_sensor[1]).toBeGreaterThan(.005);
  expect(result.snapshots[0].sensors[1].velocity_earth[0]).toBeCloseTo(-10,10);
  await page.locator('#time-scrub').fill(String(result.snapshots.length-1));await page.locator('#tab-sensors').click();await expect(page.locator('#sensor-summary')).toContainText('t=0.06000000');
  event=page.waitForEvent('download');await page.locator('#sensor-csv').click();csv=await readFile(await(await event).path(),'utf8');expect(csv).toContain('acceleration_sensor.1');
  await page.locator('#pane-sensors').screenshot({path:'test-results/sensor-time.png'});
  await page.locator('#sensor-flow').selectOption('kinematic');await expect(page.locator('#export-json')).toBeDisabled();await expect(page.locator('#sensor-csv')).toBeDisabled();
  expect(errors).toEqual([]);
});

test('complex sensor outputs are available in Bode and modal views without changing saved values',async({page})=>{
  test.setTimeout(220000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await setup(page);await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-inputs').selectOption('controls');
  await page.locator('#frequency-start').fill('1');await page.locator('#frequency-end').fill('10');await page.locator('#frequency-count').fill('3');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:130000});
  await page.locator('#frequency-group').selectOption('sensors');await page.locator('#frequency-quantity').selectOption({label:'acceleration sensor β [input L/T²]'});await page.locator('#frequency-station').selectOption('1');
  await expect(page.locator('#frequency-gain-plot svg')).toBeVisible();await page.locator('#frequency-sample').selectOption('2');
  await page.locator('#tab-sensors').click();await page.locator('#sensor-select').selectOption('2');await expect(page.locator('#sensor-summary')).toContainText('Harmonic perturbation');await expect(page.locator('#sensor-table thead')).toContainText('Imaginary');
  const result=await json(page),s=result.samples[2].responses[0].output.sensors[1];expect(s.acceleration_sensor.real[1]).toBeCloseTo(-.3,8);expect(s.acceleration_sensor.imag[1]).toBeCloseTo(.1,8);
  await page.locator('#frequency-phase').fill('120');await page.locator('#frequency-amplitude').fill('3');expect(await json(page)).toEqual(result);
  await page.locator('#pane-sensors').screenshot({path:'test-results/sensor-bode.png'});
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-count').fill('2');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:130000});
  await page.locator('#modal-quantity').selectOption('sensors.acceleration_sensor.1');await expect(page.locator('#modal-plot polyline')).toHaveCount(2);
  await page.locator('#tab-sensors').click();await expect(page.locator('#sensor-summary')).toContainText('Mode 1');await expect(page.locator('#sensor-summary')).toContainText('per saved right eigenvector');
  const modal=await json(page);expect(modal.modes[0].output.sensors).toHaveLength(2);
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  expect(errors).toEqual([]);
});
