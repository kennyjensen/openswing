import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';

for(const frame of ['prescribed','free'])test(`48-panel ${frame} flap transient exports a complete physical response offline`,async({page,context},testInfo)=>{
  test.setTimeout(240000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
    const original=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:original.call(this,type,...args);};
  });
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('transient-wing');
  await expect(page.locator('#model-name')).toHaveText('Elastic transient demonstrator');
  if(await page.locator('#panels').inputValue()!=='48'){
    await page.locator('#panels').fill('48');await page.locator('#panels').press('Tab');
  }
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#speed').fill('20');await page.locator('#alpha').fill('3');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('.1');
  await page.locator('#mode').selectOption('time');await page.locator('#time-frame').selectOption(frame);
  await page.locator('#time-duration').fill(frame==='free'?'.2':'.04');await page.locator('#time-step').fill('.01');
  await page.locator('#forcing-settings').evaluate(e=>e.open=true);
  await page.locator('#time-forcing').fill('time +F1\n0 0\n.02 0\n.02 1\n.04 1');
  await page.evaluate(()=>{
    window.solveMessages=[];
    new MutationObserver(()=>window.solveMessages.push({ms:performance.now(),text:document.querySelector('#runtime-status').textContent}))
      .observe(document.querySelector('#runtime-status'),{childList:true,subtree:true});
  });
  await context.setOffline(true);
  const start=performance.now(),wallStart=Date.now();await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:180000});
  const seconds=(performance.now()-start)/1000,wallClockSeconds=(Date.now()-wallStart)/1000;
  const pending=page.waitForEvent('download');await page.locator('#export-json').click();
  const out=JSON.parse(await readFile(await(await pending).path(),'utf8'));
  const messages=await page.evaluate(()=>window.solveMessages);
  await writeFile(testInfo.outputPath('response.json'),JSON.stringify(out));
  await writeFile(testInfo.outputPath('measurement.json'),JSON.stringify({seconds,wallClockSeconds,evaluations:out.evaluations,builds:out.jacobian_builds,steps:out.accepted_steps,messages},null,2));
  expect(out.snapshots.at(-1).time).toBe(frame==='free'?.2:.04);expect(out.rejected_steps).toBe(0);
  expect(out.frame_mode).toBe(frame);expect(out.jacobian_builds).toBeGreaterThan(0);
  if(frame==='free')for(const row of out.snapshots){
    expect(row.operating_constraints.map(c=>c.quantity)).toEqual(['force.x','force.y','force.z','moment.x','moment.y','moment.z']);
    for(const constraint of row.operating_constraints){
      expect(constraint.target).toBe(0);
      expect(Math.abs(constraint.normalized_residual)).toBeLessThanOrEqual(1e-8);
    }
  }
  expect(Math.max(...out.snapshots.at(-1).local_velocity.flat().map(Math.abs))).toBeGreaterThan(.001);
  for(const row of out.snapshots)expect(row.residual).toBeLessThanOrEqual(1e-8);
  expect(messages.some(row=>/matrix update.*assembling/.test(row.text))).toBe(true);
  expect(errors).toEqual([]);
  console.log(JSON.stringify({seconds,evaluations:out.evaluations,builds:out.jacobian_builds}));
});
