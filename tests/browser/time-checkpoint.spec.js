import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
async function download(page,id){const event=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}
async function resume(page){await page.locator('#time-continue').click();await expect(page.locator('#runtime-status')).toHaveText('Time continuation converged',{timeout:180000});}

test('offline checkpoints append or branch physical time history, retain BDF and controller offsets, and import standalone segments',async({page,context})=>{
  test.setTimeout(480000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#example').selectOption('instrumented-oscillator');await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');await page.locator('#mode').selectOption('time');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#feedback-settings').evaluate(e=>e.open=true);await page.locator('#feedback-lag-demo').click();await page.locator('#time-duration').fill('.06');await page.locator('#time-step').fill('.02');await page.locator('#forcing-settings').evaluate(e=>e.open=true);
  const forcing='time +RY[2]\n0 0\n.02 0\n.02 .01\n.12 .01\n';await page.locator('#time-forcing').fill(forcing);await context.setOffline(true);await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:180000});
  const original=await download(page,'#export-json');await page.locator('#time-scrub').fill('2');await page.locator('#time-checkpoint-settings').evaluate(e=>e.open=true);
  const saved=await download(page,'#time-checkpoint-save');expect(saved.format).toBe('openswing-time-checkpoint');expect(saved.state.time).toBeCloseTo(.04,12);expect(saved.older.time).toBeCloseTo(.02,12);expect(saved.state.feedback.at(-1)).toBeGreaterThan(0);
  await page.locator('#time-checkpoint-use').click();await page.locator('#time-continue-duration').fill('.04');await resume(page);
  let out=await download(page,'#export-json');expect(out.snapshots).toHaveLength(5);expect(out.end_time).toBeCloseTo(.08,12);expect(out.retained_steps).toBe(2);expect(out.history_breaks).toEqual([.02]);expect(out.snapshots[3].order).toBe(2);
  expect(out.snapshots[3].feedback.states.lag).toBeCloseTo(original.snapshots[3].feedback.states.lag,7);expect(out.snapshots[3].nodes.at(-1).position[1]).toBeCloseTo(original.snapshots[3].nodes.at(-1).position[1],8);
  expect(out.snapshots[0].restart).toEqual(original.snapshots[0].restart);await page.locator('#time-scrub').fill('4');expect(await download(page,'#export-json')).toEqual(out);
  await page.locator('#time-checkpoint-file').setInputFiles({name:'checkpoint.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(saved))});await page.locator('#time-continue-duration').fill('.04');await resume(page);
  const segment=await download(page,'#export-json');expect(segment.start_time).toBeCloseTo(.04,12);expect(segment.end_time).toBeCloseTo(.08,12);expect(segment.snapshots).toHaveLength(3);expect(segment.snapshots[0].frame.position_earth[0]).toBeCloseTo(-.4,7);expect(segment.snapshots[2].feedback.states.lag).toBeCloseTo(out.snapshots[4].feedback.states.lag,7);
  await expect(page.locator('#time-plot svg')).toBeVisible();await expect(page.locator('#time-plot')).toContainText('0.0400');
  await page.locator('#time-scrub').fill('2');await page.locator('#time-checkpoint-use').click();await page.locator('#time-continue-replace').check();await page.locator('#time-continue-forcing').fill('time +RY[2]\n.08 .02\n.12 .02\n');await resume(page);
  out=await download(page,'#export-json');expect(out.snapshots[3].order).toBe(1);expect(out.forcing.channels[0].initial).toBeCloseTo(2,10);expect(out.snapshots[3].feedback.commands['RY[2]']).toBeCloseTo(2.02,10);
  await page.locator('#time-scrub').fill('0');const prefix=await download(page,'#time-checkpoint-save');expect(prefix.context.setup.forcing).toBe(forcing);
  await page.locator('#time-quantity').selectOption('feedback.states.lag');
  await page.locator('#time-checkpoint-settings').screenshot({path:'test-results/time-checkpoint.png'});await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();await page.locator('#pane-time').screenshot({path:'test-results/time-checkpoint-mobile.png'});
  // Restore the desktop layout before the export assertion: mobile Settings
  // hides this button while the Plots tab displays the checkpoint controls.
  await page.setViewportSize({width:1440,height:1000});
  const invalid=structuredClone(saved);invalid.context.identity.model_sha256='wrong';await page.locator('#time-checkpoint-file').setInputFiles({name:'wrong.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(invalid))});await page.locator('#time-continue').click();await expect(page.locator('#error')).toBeVisible();await expect(page.locator('#error p')).toContainText('do not match');expect(await download(page,'#export-json')).toEqual(out);expect(errors).toEqual([]);
});
