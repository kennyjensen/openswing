import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
async function saved(page){const event=page.waitForEvent('download');await page.locator('#export-json').click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}
async function setup(page){
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#example').selectOption('instrumented-oscillator');await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-spacing').selectOption('linear');await page.locator('#frequency-start').fill('0');await page.locator('#frequency-end').fill('30');await page.locator('#frequency-count').fill('4');
  await page.locator('#feedback-settings').evaluate(e=>e.open=true);
}

test('offline broken-loop plots match actuator and measurement commands and preserve physical exports',async({page,context})=>{
  test.setTimeout(240000);const errors=[];page.on('pageerror',e=>errors.push(e.message));await setup(page);
  await page.locator('#feedback-lag-demo').click();await page.locator('#feedback-harmonic').fill('RY[2]');
  await page.locator('#frequency-inputs').selectOption('all');
  await context.setOffline(true);await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  const result=await saved(page);expect(result.inputs.map(c=>c.name)).toEqual(['power.1','gust cosine n=0','command.RY[2]']);
  expect(result.samples[0].responses[0].broken_loop.value.real).toBeCloseTo(-.4,7);
  await page.locator('#frequency-display').selectOption('broken_loop');await expect(page.locator('#frequency-unit')).toContainText('x = power.1');await expect(page.locator('#frequency-group')).toBeHidden();await expect(page.locator('#frequency-gain-plot svg')).toBeVisible();
  await page.locator('#frequency-gain').selectOption('db');await page.locator('#frequency-gain-plot circle[data-frequency="1"]').click();
  await expect(page.locator('#frequency-detail')).toContainText('Broken loop 1 − u/x');
  // At w=10: P=300+100i, -(200+200i)/P - .05i*w = -.8-.9i.
  const gain=result.samples[1].responses[0].broken_loop.value;expect(gain.real).toBeCloseTo(-.8,7);expect(gain.imag).toBeCloseTo(-.9,7);
  let event=page.waitForEvent('download');await page.locator('#frequency-csv').click();const download=await event;expect(download.suggestedFilename()).toBe('openswing-broken-loop.csv');let csv=await readFile(await download.path(),'utf8');expect(csv).toContain('1 - u/x');expect(csv).toContain('real [dimensionless]');expect(csv.trim().split('\n')).toHaveLength(5);
  await page.locator('#frequency-comparison').evaluate(e=>e.open=true);await page.locator('#frequency-compare-first').selectOption('0');await page.locator('#frequency-compare-last').selectOption('2');await page.locator('#frequency-compare-range').click();
  await expect(page.locator('.frequency-trace')).toHaveCount(3);await expect(page.locator('.frequency-comparison-group')).toHaveCount(1);await expect(page.locator('.frequency-comparison-group h3')).toContainText('dimensionless');
  event=page.waitForEvent('download');await page.locator('#frequency-compare-csv').click();const comparisonCSV=await readFile(await(await event).path(),'utf8');expect(comparisonCSV.trim().split('\n')).toHaveLength(13);expect(comparisonCSV).toContain('measurements_RY[2]');expect(comparisonCSV).toContain('no matching aircraft response');
  await page.locator('.frequency-comparison-group circle[data-trace="2"][data-frequency="1"]').first().click();await expect(page.locator('#frequency-input')).toHaveValue('2');
  await page.locator('#frequency-input').selectOption('2');await expect(page.locator('#frequency-unit')).toContainText('x = RY[2]');await expect(page.locator('#frequency-unit')).toContainText('both in input L');
  await page.locator('#frequency-phase-mode').selectOption('wrap');await page.locator('#frequency-view').selectOption('earth');await page.locator('#frequency-phase').fill('90');await page.locator('#frequency-amplitude').fill('.01');expect(await saved(page)).toEqual(result);
  await page.locator('#pane-frequency').screenshot({path:'test-results/broken-loop.png'});await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();await page.locator('#pane-frequency').screenshot({path:'test-results/broken-loop-mobile.png'});
  await page.locator('#frequency-input').selectOption('1');await expect(page.locator('#frequency-unit')).toContainText('no matching aircraft response');await expect(page.locator('#frequency-gain-plot svg')).toHaveCount(0);await expect(page.locator('#frequency-detail')).toContainText('Unavailable');
  event=page.waitForEvent('download');await page.locator('#frequency-csv').click();csv=await readFile(await(await event).path(),'utf8');expect(csv).toContain('no matching aircraft response');
  await page.locator('#frequency-display').selectOption('response');await expect(page.locator('#frequency-group')).toBeVisible();await page.locator('#frequency-group').selectOption('nodes');await page.locator('#frequency-quantity').selectOption({label:'displacement y [input L]'});expect(await saved(page)).toEqual(result);expect(errors).toEqual([]);
});

test('zero matching response is a broken-loop gap without removing the physical solution',async({page,context})=>{
  test.setTimeout(180000);await setup(page);await page.locator('#frequency-inputs').selectOption('controls');await page.locator('#frequency-count').fill('2');
  await page.locator('#feedback-enabled').check();await page.locator('#feedback-definition').fill(JSON.stringify({outputs:[{actuator:'E1',terms:[{input:'RY[2]',gain:0}]}]}));await page.locator('#feedback-harmonic').fill('RY[2]');
  await context.setOffline(true);await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:140000});
  const result=await saved(page);expect(result.samples.every(s=>s.converged&&!s.responses[1].broken_loop.available)).toBeTruthy();
  await page.locator('#frequency-input').selectOption('1');await page.locator('#frequency-display').selectOption('broken_loop');await expect(page.locator('#frequency-detail')).toContainText('Matched response is zero');await expect(page.locator('#frequency-gain-plot svg')).toHaveCount(0);await expect(page.locator('#frequency-phase-plot svg')).toHaveCount(0);await expect(page.locator('#frequency-transport')).toBeVisible();
  await page.locator('#frequency-input').selectOption('0');await expect(page.locator('#frequency-gain-plot svg')).toBeVisible();
  expect(await saved(page)).toEqual(result);
});
