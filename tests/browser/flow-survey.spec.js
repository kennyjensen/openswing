import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
async function download(page,id,json=true){const event=page.waitForEvent('download');await page.locator(id).click();const text=await readFile(await(await event).path(),'utf8');return json?JSON.parse(text):text;}
async function sample(page){await page.locator('#flow-sample').click();await expect(page.locator('#flow-json')).toBeEnabled({timeout:180000});return download(page,'#flow-json');}

test('offline arbitrary-plane surveys preserve rigid and time states and export their physical components',async({page,context})=>{
  test.setTimeout(900000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await page.locator('#gust-settings').evaluate(e=>e.open=true);await page.locator('#gust-kind').selectOption('expression');
  await page.locator('#gust-expr-z').fill('.1*sin(3*t)+.01*y');await page.locator('#gust-time').fill('.2');
  await context.setOffline(true);await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged');
  const steady=await download(page,'#export-json');await page.locator('#tab-flow').click();
  await page.locator('#flow-normal-x').fill('1');await page.locator('#flow-normal-y').fill('2');await page.locator('#flow-normal-z').fill('3');
  const field=await sample(page);expect(field.state_kind).toBe('prescribed_circulation');expect(field.position).toHaveLength(441);
  for(let i=0;i<field.position.length;i++){expect(field.velocity.gust[i][2]).toBeCloseTo(.1*Math.sin(.6)+.01*field.position_earth[i][1],10);for(let j=0;j<3;j++)expect(field.velocity.relative[i][j]).toBeCloseTo(field.velocity.kinematic[i][j]+field.velocity.air[i][j],10);}
  expect(await download(page,'#export-json')).toEqual(steady);
  await page.locator('#flow-component').selectOption('gust');await page.locator('#flow-color').selectOption('normal');await expect(page.locator('#flow-plot svg')).toBeVisible();
  const csv=await download(page,'#flow-csv',false);expect(csv.trim().split('\n')).toHaveLength(442);expect(csv).toContain('gust_normal_L_per_T');
  expect(await download(page,'#flow-svg',false)).toContain('gust · normal');
  await page.locator('#pane-flow').screenshot({path:'test-results/flow-survey-desktop.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();await page.locator('#pane-flow').screenshot({path:'test-results/flow-survey-mobile.png'});
  await page.locator('#flow-origin-z').fill('2');await page.locator('#flow-origin-z').press('Tab');await expect(page.locator('#flow-json')).toBeDisabled();
  await page.locator('#flow-frame').selectOption('earth');const earth=await sample(page);expect(earth.coordinates).toBe('earth');
  await page.locator('#flow-normal-x').fill('0');await page.locator('#flow-normal-y').fill('0');await page.locator('#flow-normal-z').fill('0');await page.locator('#flow-sample').click();await expect(page.locator('#error')).toContainText('normal must be nonzero');await page.locator('#close-error').click();
  await page.locator('#flow-normal-z').fill('1');
  // Incomplete plot settings must not block an unrelated flight analysis.
  await page.locator('#flow-nu').fill('1');
  await page.locator('#mode').selectOption('time');await page.locator('#time-duration').fill('.04');await page.locator('#time-step').fill('.02');await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:300000});
  const trajectory=await download(page,'#export-json');await page.locator('#time-scrub').fill('1');await page.locator('#tab-flow').click();await page.locator('#flow-nu').fill('21');
  const transient=await sample(page);expect(transient.state_kind).toBe('time_checkpoint');expect(transient.time).toBeCloseTo(.02,12);
  expect(transient.request.survey.checkpoint.state.time).toBe(.02);for(let i=0;i<transient.position.length;i++)expect(transient.velocity.gust[i][2]).toBeCloseTo(.1*Math.sin(.06)+.01*transient.position_earth[i][1],10);
  expect(await download(page,'#export-json')).toEqual(trajectory);await page.locator('#time-scrub').fill('2');await expect(page.locator('#flow-json')).toBeDisabled();expect(errors).toEqual([]);
});
