import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
import {tableRows} from '../../web/frequency-overlay-data.js';
async function download(page,id){const event=page.waitForEvent('download');await page.locator(id).click();return readFile(await(await event).path(),'utf8');}
const saved=async page=>JSON.parse(await download(page,'#export-json'));
async function done(page,status='Analysis converged'){await expect(page.locator('#runtime-status')).toHaveText(status,{timeout:240000});await expect(page.locator('#error')).toBeHidden();}
async function quantity(page,group,label){await page.locator('#frequency-group').selectOption(group);await page.locator('#frequency-quantity').selectOption({label});}

test('offline Bode overlays preserve physical units, samples, computed state, exports and refinement lifecycle',async({page,context})=>{
  test.setTimeout(600000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#example').selectOption('instrumented-oscillator');await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#alpha').fill('0');await page.locator('#speed').fill('10');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-spacing').selectOption('linear');await page.locator('#frequency-start').fill('0');await page.locator('#frequency-end').fill('20');await page.locator('#frequency-count').fill('3');await page.locator('#frequency-inputs').selectOption('controls');
  await context.setOffline(true);await page.locator('#solve').click();await done(page);const before=await saved(page);
  for(const p of before.samples){const a=500-2*p.omega**2,b=10*p.omega,d=a*a+b*b,v=p.responses[0].output.sensors[1].displacement_body;expect(v.real[1]).toBeCloseTo(a/d,8);expect(v.imag[1]).toBeCloseTo(-b/d,8);}
  await quantity(page,'sensors','displacement body y [input L]');await page.locator('#frequency-station').selectOption('1');
  await page.locator('#frequency-comparison').evaluate(e=>e.open=true);await page.locator('#frequency-compare-current').click();await page.locator('#frequency-overlay-settings').evaluate(e=>e.open=true);
  await page.locator('#frequency-overlay-file').setInputFiles('examples/oscillator-bode.csv');await expect(page.locator('#frequency-overlay-mode')).toHaveValue('table');
  await page.locator('#frequency-overlay-delimiter').selectOption('comma');await page.locator('#frequency-overlay-skip').fill('1');await page.locator('#frequency-overlay-format').selectOption('polar_deg');await page.locator('#frequency-overlay-frequency-unit').selectOption('cycles');await page.locator('#frequency-overlay-response-scale').fill('.001');
  await page.locator('#frequency-overlay-preview').click();await expect(page.locator('#frequency-overlay-status')).toContainText('21 samples, 20 finite and 1 gaps');await expect(page.locator('#frequency-overlay-add')).toBeEnabled();
  // Changing the target cannot add a preview constructed for another quantity.
  await quantity(page,'global','force y [input F]');await expect(page.locator('#frequency-overlay-add')).toBeDisabled();
  await quantity(page,'sensors','displacement body y [input L]');await page.locator('#frequency-station').selectOption('1');await page.locator('#frequency-overlay-preview').click();await page.locator('#frequency-overlay-add').click();
  await expect(page.locator('.frequency-trace')).toHaveCount(2);await expect(page.locator('.frequency-comparison-group')).toHaveCount(1);await expect(page.locator('.frequency-comparison-group circle')).toHaveCount(46);
  const selected=await page.locator('#frequency-sample').inputValue();await page.locator('.frequency-comparison-group circle[data-trace="1"][data-frequency="8"]').first().focus();await page.keyboard.press('Enter');await expect(page.locator('#frequency-overlay-detail')).toContainText('No computed geometry');await expect(page.locator('#frequency-sample')).toHaveValue(selected);
  const csv=await download(page,'#frequency-compare-csv'),rows=tableRows(csv).map(r=>r.cells),header=rows.shift(),column=name=>header.indexOf(name),external=rows.filter(r=>r[column('source')]==='external');expect(external).toHaveLength(21);
  expect(JSON.parse(external[0][column('source mapping')]).responseScale).toBe(.001);expect(external[11][column('real')]).toBe('');expect(external[11][column('status')]).toContain('Missing external');
  for(const [i,r] of external.entries()){const w=2*Math.PI*i/4;expect(Number(r[column('omega [rad/T]')])).toBeCloseTo(w,12);if(i===11)continue;const a=500-2*w*w,b=10*w,d=a*a+b*b;expect(Number(r[column('real')])).toBeCloseTo(a/d,12);expect(Number(r[column('imag')])).toBeCloseTo(-b/d,12);}
  await page.locator('.frequency-trace input').last().uncheck();await expect(page.locator('.frequency-comparison-group circle')).toHaveCount(6);await page.locator('.frequency-trace input').last().check();
  const event=page.waitForEvent('download');await page.locator('.frequency-comparison-group button').click();const svg=await readFile(await(await event).path(),'utf8');expect(svg).toContain('External');expect(svg).not.toMatch(/NaN|Infinity/);
  expect(await saved(page)).toEqual(before);
  const single=await download(page,'#frequency-csv');await page.locator('#frequency-overlay-file').setInputFiles({name:'saved-bode.csv',mimeType:'text/csv',buffer:Buffer.from(single)});await expect(page.locator('#frequency-overlay-mode')).toHaveValue('bode');await page.locator('#frequency-overlay-response-scale').fill('1');
  await quantity(page,'global','force y [input F]');await page.locator('#frequency-overlay-preview').click();await expect(page.locator('#frequency-overlay-status')).toContainText('selected target');await expect(page.locator('#frequency-overlay-add')).toBeDisabled();
  await quantity(page,'sensors','displacement body y [input L]');await page.locator('#frequency-station').selectOption('1');await page.locator('#frequency-overlay-preview').click();await page.locator('#frequency-overlay-add').click();await expect(page.locator('.frequency-trace')).toHaveCount(3);
  await page.locator('#frequency-refinement').evaluate(e=>e.open=true);await page.locator('#frequency-add-values').fill('5');await page.locator('#frequency-add-list').click();await done(page,'Frequency refinement complete');await expect(page.locator('.frequency-trace')).toHaveCount(3);
  const refined=await saved(page);expect(refined.samples).toHaveLength(4);for(const p of before.samples)expect(refined.samples.find(q=>q.omega===p.omega)).toEqual(p);
  expect(tableRows(await download(page,'#frequency-compare-csv'))).toHaveLength(29); // header + 4 computed + 21 analytic + 3 saved
  await page.locator('#frequency-overlay-file').setInputFiles({name:'invalid-grid.txt',mimeType:'text/plain',buffer:Buffer.from('0 1 0\n0 2 0\n')});await page.locator('#frequency-overlay-delimiter').selectOption('whitespace');await page.locator('#frequency-overlay-skip').fill('0');await page.locator('#frequency-overlay-preview').click();await expect(page.locator('#frequency-overlay-status')).toContainText('strictly increasing');await expect(page.locator('#frequency-overlay-add')).toBeDisabled();await expect(page.locator('.frequency-trace')).toHaveCount(3);
  await page.locator('#frequency-overlay-file').setInputFiles({name:'comparison.csv',mimeType:'text/csv',buffer:Buffer.from(csv)});await expect(page.locator('#frequency-overlay-series option')).toHaveCount(2);await page.locator('#frequency-overlay-series').selectOption('1');await page.locator('#frequency-overlay-preview').click();await expect(page.locator('#frequency-overlay-status')).toContainText('21 samples');
  await page.locator('#frequency-overlay-settings').screenshot({path:'test-results/frequency-overlays-desktop.png'});await page.locator('.frequency-comparison-group').screenshot({path:'test-results/frequency-overlays-plot.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.locator('#frequency-overlay-settings').screenshot({path:'test-results/frequency-overlays-mobile.png'});
  // A file read completing after invalidation cannot attach data to a new result.
  await page.evaluate(()=>{const original=File.prototype.text;File.prototype.text=function(){if(this.name==='delayed.txt')return new Promise(resolve=>{window.finishOverlayRead=()=>resolve('0 1 0');});return original.call(this);};});
  await page.locator('#frequency-overlay-file').setInputFiles({name:'delayed.txt',mimeType:'text/plain',buffer:Buffer.from('0 1 0')});await page.waitForFunction(()=>!!window.finishOverlayRead);
  await page.locator('#alpha').fill('1');await page.evaluate(()=>window.finishOverlayRead());await expect(page.locator('.frequency-trace')).toHaveCount(0);await expect(page.locator('#frequency-overlay-preview')).toBeDisabled();await expect(page.locator('#frequency-overlay-add')).toBeDisabled();await expect(page.locator('#frequency-overlay-source')).toBeHidden();
  expect(errors).toEqual([]);
});
