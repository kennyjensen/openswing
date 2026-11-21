import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
async function download(page,id){const event=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}

test('offline nonlinear disturbance retains physical fields, switches inputs afterward and continues from a checkpoint',async({page,context})=>{
  test.setTimeout(1800000);const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',message=>{if(message.text().startsWith('Initializer progress:'))console.log(message.text());});
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('instrumented-oscillator');await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('mounted');await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#feedback-settings').evaluate(e=>e.open=true);await page.locator('#feedback-enabled').check();
  await page.locator('#feedback-definition').fill(JSON.stringify({commands:{'RY[2]':2},outputs:[{actuator:'E1',expression:"-20*tanh(5*error('RY[2]'))"}]}));
  await context.setOffline(true);await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);const seed=await download(page,'#equilibrium-save');await page.locator('#equilibrium-use').click();
  await page.locator('#mode').selectOption('time');await page.locator('#time-initial-settings').evaluate(e=>e.open=true);
  const profile=JSON.parse(await readFile('examples/initial-nonlinear-spring.json','utf8'));
  await page.locator('#time-initial-file').setInputFiles({name:'initial.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(profile))});await expect(page.locator('#time-initial-enable')).toBeChecked();
  expect(await download(page,'#time-initial-save')).toEqual(profile.state);
  await page.locator('#time-order').selectOption('5');await page.locator('#time-duration').fill('.02');await page.locator('#time-step').fill('.01');
  await page.locator('#forcing-settings').evaluate(e=>e.open=true);await page.locator('#time-forcing').fill('time +RY[2]\n0 .03\n.1 .03');
  await page.evaluate(()=>{let previous='';new MutationObserver(()=>{const text=document.getElementById('runtime-status').textContent,match=text.match(/state · (\d+)\/(\d+)/);if(!match)return;const bucket=Math.floor(Number(match[1])/50);if(bucket!==previous){console.log('Initializer progress: '+text);previous=bucket;}}).observe(document.getElementById('runtime-status'),{childList:true,subtree:true,characterData:true});});
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toContainText('Completing initial physical state',{timeout:120000});
  await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:1500000});
  const result=await download(page,'#export-json'),first=result.snapshots[0];expect(result.request.action).toBe('launch_time');expect(result.method).toBe('Radau IIA (3 stages)');expect(result.snapshots[1].order).toBe(5);expect(result.request.equilibrium_state).toEqual(seed);expect(result.initialization.disturbance).toEqual(profile.state);
  expect(first.nodes.at(-1).position[1]).toBeCloseTo(2.2,10);expect(first.local_velocity.at(-1)[1]).toBeCloseTo(.1,10);
  expect(first.local_acceleration.at(-1)[1]).toBeCloseTo((-100-1-20*Math.tanh(1))/2,6);expect(first.feedback.actuators.E1).toBeCloseTo(-20*Math.tanh(1),7);
  expect(first.forcing_values['RY[2]']).toBe(2);expect(result.snapshots[1].feedback.commands['RY[2]']).toBeCloseTo(2.03,10);
  expect(result.initialization.consistency.prescribed_coordinate_error).toBe(0);expect(result.initialization.consistency.refinements).toHaveLength(2);
  await page.locator('#time-quantity').selectOption('node.velocity.1');await page.locator('#time-node').selectOption(String(first.nodes.at(-1).index));await expect(page.locator('#time-plot svg')).toBeVisible();
  await page.locator('#time-scrub').fill('1');expect(await download(page,'#export-json')).toEqual(result);
  await page.locator('#time-checkpoint-settings').evaluate(e=>e.open=true);await page.locator('#time-checkpoint-use').click();await page.locator('#time-continue-duration').fill('.01');await page.locator('#time-continue').click();await expect(page.locator('#runtime-status')).toHaveText('Time continuation converged',{timeout:180000});
  const resumed=await download(page,'#export-json');expect(resumed.snapshots.at(-1).local_velocity.at(-1)[1]).toBeCloseTo(result.snapshots.at(-1).local_velocity.at(-1)[1],8);
  await page.locator('#time-initial-settings').screenshot({path:'test-results/nonlinear-initial-settings.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();await page.locator('#time-initial-settings').screenshot({path:'test-results/nonlinear-initial-mobile.png'});
  await page.locator('#equilibrium-enable').uncheck();await page.locator('#solve').click();await expect(page.locator('#error')).toContainText('requires an enabled loaded saved equilibrium');
  expect(errors).toEqual([]);
});
