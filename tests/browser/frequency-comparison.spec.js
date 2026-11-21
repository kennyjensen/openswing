import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
async function download(page,id){const event=page.waitForEvent('download');await page.locator(id).click();return readFile(await(await event).path(),'utf8');}
const saved=async page=>JSON.parse(await download(page,'#export-json'));
async function done(page,status='Analysis converged'){
  await expect(page.locator('#runtime-status')).toHaveText(new RegExp(`^(?:${status}|Analysis stopped|Frequency refinement stopped|Kernel unavailable)$`),{timeout:240000});
  if(await page.locator('#error').isVisible())throw new Error(await page.locator('#error').innerText());
  expect(await page.locator('#runtime-status').textContent()).toBe(status);
}
async function prepare(page,file,name){
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#file').setInputFiles(file);await expect(page.locator('#model-name')).toHaveText(name);
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#alpha').fill('0');await page.locator('#speed').fill('10');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-spacing').selectOption('linear');await page.locator('#frequency-start').fill('0');await page.locator('#frequency-end').fill('30');await page.locator('#frequency-count').fill('4');
}
async function quantity(page,group,label){await page.locator('#frequency-group').selectOption(group);await page.locator('#frequency-quantity').selectOption({label});}
async function range(page,first,last){await page.locator('#frequency-compare-first').selectOption(String(first));await page.locator('#frequency-compare-last').selectOption(String(last));await page.locator('#frequency-compare-range').click();}

test('offline gust-family comparison preserves physical phase, units, stations, exports and refined grids',async({page,context})=>{
  test.setTimeout(600000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await prepare(page,'examples/gust-modes.asw','Gust-mode phase demonstrator');await page.locator('#frequency-inputs').selectOption('all');await page.locator('#frequency-gust-settings').evaluate(e=>e.open=true);await page.locator('#frequency-span-mode').fill('9');expect(await page.locator('#frequency-span-mode').evaluate(e=>e.checkValidity())).toBe(true);await page.locator('#frequency-span-mode').fill('2');await page.locator('#frequency-parity').selectOption('both');
  await context.setOffline(true);await page.locator('#solve').click();await done(page);const before=await saved(page);expect(before.inputs).toHaveLength(6);
  for(const p of before.samples)for(let input=1;input<6;input++){
    const c=before.inputs[input],amplitude=2.45*(c.symmetry==='sine'?Math.sin(Math.PI*c.span_mode*.6):Math.cos(Math.PI*c.span_mode*.6)),f=p.responses[input].output.global.force;
    expect(f.real[2]).toBeCloseTo(amplitude*Math.cos(-p.omega*.12),8);expect(f.imag[2]).toBeCloseTo(amplitude*Math.sin(-p.omega*.12),8);
  }
  await page.locator('#frequency-input').selectOption('1');await quantity(page,'global','force z [input F]');await page.locator('#frequency-comparison').evaluate(e=>e.open=true);await range(page,1,5);
  await expect(page.locator('.frequency-trace')).toHaveCount(5);await expect(page.locator('.frequency-comparison-group')).toHaveCount(1);await expect(page.locator('.frequency-comparison-group circle')).toHaveCount(40);
  await range(page,5,1);await expect(page.locator('#frequency-compare-status')).toContainText('First input must precede');await expect(page.locator('.frequency-trace')).toHaveCount(5);
  await page.locator('.frequency-comparison-group circle[data-trace="4"][data-frequency="2"]').first().click();await expect(page.locator('#frequency-input')).toHaveValue('5');await expect(page.locator('#frequency-detail')).toContainText('ω=20.0000');
  await page.locator('#frequency-compare-current').click();await expect(page.locator('.frequency-trace')).toHaveCount(5);
  await page.locator('#frequency-input').selectOption('0');await quantity(page,'global','force y [input F]');await page.locator('#frequency-compare-current').click();await expect(page.locator('.frequency-comparison-group')).toHaveCount(2);
  await quantity(page,'sensors','position earth Y [input L]');await page.locator('#frequency-compare-stations').click();await expect(page.locator('.frequency-trace')).toHaveCount(8);await expect(page.locator('.frequency-comparison-group')).toHaveCount(3);await expect(page.locator('#frequency-compare-traces')).toContainText('Sensor 1');await expect(page.locator('#frequency-compare-traces')).toContainText('Sensor 2');
  await page.locator('#frequency-input').selectOption('1');await quantity(page,'global','moment x [input F·L]');await page.locator('#frequency-compare-current').click();await expect(page.locator('.frequency-comparison-group')).toHaveCount(4);
  const csv=await download(page,'#frequency-compare-csv');expect(csv.trim().split('\n')).toHaveLength(37);expect(csv).toContain('response unit');expect(csv).toContain('gust sine n=2');expect(csv).toContain('Sensor 2');
  await page.locator('.frequency-trace input').first().uncheck();expect((await download(page,'#frequency-compare-csv')).trim().split('\n')).toHaveLength(33);await page.locator('.frequency-trace input').first().check();
  let event=page.waitForEvent('download');await page.locator('.frequency-comparison-group button').first().click();const file=await event,svg=await readFile(await file.path(),'utf8');await writeFile('test-results/frequency-comparison-browser.svg',svg);expect(svg).toContain('gust sine n=2');expect(svg).not.toMatch(/NaN|Infinity/);expect(await page.evaluate(text=>new DOMParser().parseFromString(text,'image/svg+xml').querySelector('parsererror')?.textContent??'',svg)).toBe('');
  expect(await saved(page)).toEqual(before);
  await page.locator('#frequency-refinement').evaluate(e=>e.open=true);await page.locator('#frequency-add-values').fill('5, 35');await page.locator('#frequency-add-list').click();await done(page,'Frequency refinement complete');await expect(page.locator('.frequency-trace')).toHaveCount(9);expect((await download(page,'#frequency-compare-csv')).trim().split('\n')).toHaveLength(55);await expect(page.locator('#frequency-detail')).toContainText('ω=20.0000');
  const refined=await saved(page);for(const old of before.samples)expect(refined.samples.find(s=>s.omega===old.omega)).toEqual(old);
  await page.locator('.frequency-comparison-group').first().screenshot({path:'test-results/frequency-comparison-gust.png'});await page.locator('.frequency-comparison-group').last().screenshot({path:'test-results/frequency-comparison-moment.png'});
  await page.locator('#frequency-comparison').screenshot({path:'test-results/frequency-comparison-desktop.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.locator('#frequency-comparison').screenshot({path:'test-results/frequency-comparison-mobile.png'});
  await page.locator('.frequency-trace button').last().click();await expect(page.locator('.frequency-trace')).toHaveCount(8);await page.locator('#alpha').fill('1');await expect(page.locator('.frequency-trace')).toHaveCount(0);await expect(page.locator('#frequency-compare-current')).toBeDisabled();expect(errors).toEqual([]);
});

test('periodic response and shifted initial spectra compare separately and select the correct geometry meaning',async({page,context})=>{
  test.setTimeout(480000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await prepare(page,'examples/instrumented-oscillator.asw','Instrumented spring-mass demonstrator');await page.locator('#frequency-inputs').selectOption('controls');await page.locator('#frequency-initial-settings').evaluate(e=>e.open=true);await page.locator('#frequency-initial-file').setInputFiles('examples/initial-spring.json');await page.locator('#frequency-initial-shift').fill('.7');
  await context.setOffline(true);await page.locator('#solve').click();await done(page);const before=await saved(page);
  await quantity(page,'nodes','displacement y [input L]');await page.locator('#frequency-comparison').evaluate(e=>e.open=true);await range(page,0,2);await expect(page.locator('.frequency-comparison-group')).toHaveCount(2);await expect(page.locator('.frequency-trace')).toHaveCount(3);
  await expect(page.locator('.frequency-comparison-group').nth(1)).toContainText('Initial-state spectrum');await expect(page.locator('.frequency-comparison-group').nth(1)).toContainText('input L · input T');
  await page.locator('.frequency-comparison-group circle[data-trace="1"][data-frequency="1"]').first().focus();await page.keyboard.press('Enter');await expect(page.locator('#frequency-input')).toHaveValue('1');await expect(page.locator('#frequency-transport')).toBeHidden();await expect(page.locator('#geometry-label')).toContainText('INITIAL-STATE SPECTRUM');
  await page.locator('.frequency-comparison-group circle[data-trace="0"][data-frequency="1"]').first().click();await expect(page.locator('#frequency-input')).toHaveValue('0');await expect(page.locator('#frequency-transport')).toBeVisible();
  await page.locator('#frequency-gain').selectOption('db');await page.locator('#frequency-phase-mode').selectOption('wrap');await page.locator('#frequency-axis').selectOption('log');await expect(page.locator('#frequency-compare-status')).toContainText('Zero frequency is omitted');expect(await page.locator('.frequency-comparison-group circle[data-frequency="0"]').count()).toBe(0);
  const csv=await download(page,'#frequency-compare-csv');expect(csv.trim().split('\n')).toHaveLength(13);expect(csv).toContain('X(s) / profile amplitude');expect(csv).toContain('"0","0","0.7"');expect(csv).toContain('wrapped ±180 degrees');
  expect(await saved(page)).toEqual(before);await page.locator('#frequency-compare-clear').click();await expect(page.locator('.frequency-trace')).toHaveCount(0);await expect(page.locator('#frequency-compare-csv')).toBeDisabled();expect(errors).toEqual([]);
});
