import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
import {frequencyRange} from '../../web/frequency-results.js';

test.use({actionTimeout:30000});
async function finished(page,expected){
  await expect(page.locator('#runtime-status')).toHaveText(new RegExp(`^(?:${expected}|Analysis stopped|Frequency refinement stopped|Kernel unavailable)$`),{timeout:300000});
  if(await page.locator('#error').isVisible())throw new Error(await page.locator('#error').innerText());
  expect(await page.locator('#runtime-status').textContent()).toBe(expected);
}

async function saved(page){
  const mobile=await page.locator('#workspace-tabs').isVisible();
  const previous=mobile?await page.locator('#workspace-tabs [aria-selected="true"]').getAttribute('id'):null;
  if(mobile)await page.locator('#workspace-tab-output').click();
  const event=page.waitForEvent('download');await page.locator('#export-json').click();
  const result=JSON.parse(await readFile(await(await event).path(),'utf8'));
  if(previous)await page.locator('#'+previous).click();
  return result;
}

test('frequency ranges preserve requested endpoints and nearby physical frequencies',()=>{
  const values=frequencyRange(.1,100,4,true);expect(values[0]).toBe(.1);expect(values.at(-1)).toBe(100);
  expect(frequencyRange(0,2,3)).toEqual([0,1,2]);
  expect(()=>frequencyRange(0,2,3,true)).toThrow('positive start');expect(()=>frequencyRange(1,2,NaN)).toThrow('2–200');
});

test('offline Bode refinement retains the frozen base, exact old samples, selection and complete exports',async({page,context})=>{
  test.setTimeout(900000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles('examples/forced-oscillator.asw');await expect(page.locator('#model-name')).toHaveText('Forced spring-mass demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#alpha').fill('0');await page.locator('#speed').fill('10');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-inputs').selectOption('controls');await page.locator('#frequency-start').fill('1');await page.locator('#frequency-end').fill('100');await page.locator('#frequency-count').fill('3');
  await context.setOffline(true);await page.locator('#solve').click();await finished(page,'Analysis converged');const before=await saved(page);
  await page.locator('#frequency-group').selectOption('nodes');await page.locator('#frequency-quantity').selectOption({label:'displacement y [input L]'});await page.locator('#frequency-sample').selectOption('1');await page.locator('#frequency-phase').fill('90');await page.locator('#frequency-amplitude').fill('10');await page.locator('#frequency-view').selectOption('earth');
  await page.locator('#frequency-refinement').evaluate(e=>e.open=true);await expect(page.locator('#frequency-add-range')).toBeEnabled();
  await page.locator('#frequency-add-start').fill('14');await page.locator('#frequency-add-end').fill('18');await page.locator('#frequency-add-count').fill('5');await page.locator('#frequency-add-range').click();await finished(page,'Frequency refinement complete');
  await expect(page.locator('#frequency-add-status')).toContainText('5 new frequencies');await expect(page.locator('#frequency-quantity option:checked')).toHaveText('displacement y [input L]');await expect(page.locator('#frequency-phase')).toHaveValue('90');await expect(page.locator('#frequency-amplitude')).toHaveValue('10');await expect(page.locator('#frequency-view')).toHaveValue('earth');await expect(page.locator('#frequency-detail')).toContainText('ω=10.0000');
  await page.locator('#frequency-add-values').fill('0, 1, 200, 16');await page.locator('#frequency-add-list').click();await finished(page,'Frequency refinement complete');
  await expect(page.locator('#frequency-add-status')).toContainText('2 new frequencies');await expect(page.locator('#frequency-add-status')).toContainText('2 exact duplicates');await expect(page.locator('#frequency-axis')).toHaveValue('linear');await expect(page.locator('#frequency-detail')).toContainText('ω=10.0000');
  const result=await saved(page);expect(result.samples).toHaveLength(10);expect(result.base).toEqual(before.base);expect(result.frequency_session).toEqual(before.frequency_session);expect(result.diagnostics).toEqual(before.diagnostics);
  for(const old of before.samples)expect(result.samples.find(s=>s.omega===old.omega)).toEqual(old);
  expect(result.request.frequency.frequencies).toEqual(result.samples.map(s=>s.omega));
  for(const row of result.samples){const w=row.omega,re=500-2*w*w,im=10*w,d=row.responses[0].output.nodes.at(-1).displacement;expect(d.real[1]).toBeCloseTo(re/(re*re+im*im),10);expect(d.imag[1]).toBeCloseTo(-im/(re*re+im*im),10);}
  const event=page.waitForEvent('download');await page.locator('#frequency-csv').click();expect((await readFile(await(await event).path(),'utf8')).trim().split('\n')).toHaveLength(11);
  await page.locator('#pane-frequency').screenshot({path:'test-results/frequency-refinement.png'});await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();await page.locator('#frequency-refinement').screenshot({path:'test-results/frequency-refinement-mobile.png'});
  await page.locator('#frequency-add-values').fill('1 16');await page.locator('#frequency-add-list').click();await expect(page.locator('#frequency-add-status')).toContainText('0 new frequencies');expect((await saved(page)).samples).toEqual(result.samples);
  await page.locator('#frequency-add-values').fill('-1');await page.locator('#frequency-add-list').click();await expect(page.locator('#error')).toContainText('nonnegative');expect((await saved(page)).samples).toEqual(result.samples);await page.locator('#close-error').click();
  // An unfinished refinement draft must not block an unrelated new analysis.
  await page.locator('#frequency-add-start').fill('');await page.locator('#workspace-tab-settings').click();await page.locator('#solve').click();await finished(page,'Analysis converged');expect((await saved(page)).samples).toHaveLength(3);
  await page.locator('#workspace-tab-settings').click();await page.locator('#alpha').fill('1');await expect(page.locator('#export-json')).toBeDisabled();await expect(page.locator('#frequency-add-list')).toBeDisabled();expect(errors).toEqual([]);
});
