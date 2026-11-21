import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
async function downloaded(page,id,json=false){const event=page.waitForEvent('download');await page.locator(id).click();const text=await readFile(await(await event).path(),'utf8');return json?JSON.parse(text):text;}

test('annotated ROM imports offline with real matrices, phase, literal units and unchanged original export',async({page,context})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#tab-romfiles').click();await context.setOffline(true);
  const original=await readFile('examples/mechanical-reference.rom','utf8');
  await page.locator('#romfile-file').setInputFiles('examples/mechanical-reference.rom');
  await expect(page.locator('#romfile-summary')).toContainText('2 printed modes · 3 real states · 2 inputs · 4 outputs');
  const result=await downloaded(page,'#romfile-json',true);
  expect(result.model.source).toBe(original);expect(result.real_matrices.A).toHaveLength(3);
  expect(result.samples[0].response.real[0][0]).toBeCloseTo(.002,12);
  expect(result.samples[0].response.real[3][1]).toBeCloseTo(.5,12);
  await expect(page.locator('#romfile-units')).toContainText('unspecified input unit');
  await page.locator('#romfile-mode').selectOption('1');await expect(page.locator('#romfile-pole')).toContainText('Printed mode 8');
  await expect(page.locator('#romfile-modal')).toContainText('filter value [1]');
  await page.locator('#romfile-input').selectOption('1');await page.locator('#romfile-output').selectOption('3');
  await expect(page.locator('#romfile-gain svg')).toBeVisible();await expect(page.locator('#romfile-phase svg')).toBeVisible();
  expect(await downloaded(page,'#romfile-original')).toBe(original);
  const normalized=await downloaded(page,'#romfile-save');expect(normalized).toBe(result.normalized_text);expect(normalized).toContain('#   Mode:    8');
  await page.locator('#pane-romfiles').screenshot({path:'test-results/rom-file.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  await page.locator('#pane-romfiles').screenshot({path:'test-results/rom-file-mobile.png'});
  await page.locator('#romfile-frequencies').fill('1, 10, 20');await expect(page.locator('#romfile-json')).toBeDisabled();
  expect(await downloaded(page,'#romfile-original')).toBe(original);await page.locator('#romfile-evaluate').click();
  await expect(page.locator('#romfile-json')).toBeEnabled();expect((await downloaded(page,'#romfile-json',true)).samples.map(x=>x.omega)).toEqual([1,10,20]);
  expect(errors).toEqual([]);
});

test('ROM import rejects truncated direct data and shows explicit pole gaps without changing the aircraft',async({page})=>{
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();const aircraft=await page.locator('#model-name').textContent();
  await page.locator('#tab-romfiles').click();const original=await readFile('examples/mechanical-reference.rom','utf8');
  await page.locator('#romfile-file').setInputFiles({name:'truncated.rom',mimeType:'text/plain',buffer:Buffer.from(original.trimEnd().split('\n').slice(0,-1).join('\n'))});
  await expect(page.locator('#error')).toBeVisible();await expect(page.locator('#error p')).toContainText('direct-matrix output');
  await expect(page.locator('#romfile-json')).toBeDisabled();await page.locator('#close-error').click();
  const pole=original.replace(/# Eigenvalue: [^\n]+/,'# Eigenvalue: 0 2 1/s');
  await page.locator('#romfile-frequencies').fill('1, 2, 3');
  await page.locator('#romfile-file').setInputFiles({name:'pole.rom',mimeType:'text/plain',buffer:Buffer.from(pole)});
  await expect(page.locator('#romfile-summary')).toContainText('2/3 frequencies resolved');
  await expect(page.locator('#romfile-response')).toContainText('retained pole');
  expect(await page.locator('#model-name').textContent()).toBe(aircraft);
});
