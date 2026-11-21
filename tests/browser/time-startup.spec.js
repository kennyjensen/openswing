import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';

for(const example of ['rectangular','dae'])test(`${example}: 48-panel nonlinear response starts visibly and finishes offline`,async({page,context},testInfo)=>{
  test.setTimeout(360000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
    const original=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:original.call(this,type,...args);};
  });
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption(example);
  await page.locator('#panels').fill('48');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('time');
  await page.locator('#time-frame').selectOption('prescribed');
  await page.locator('#time-duration').fill('0.2');await page.locator('#time-step').fill('0.01');
  await page.evaluate(()=>{
    window.solveMessages=[];
    new MutationObserver(()=>window.solveMessages.push({ms:performance.now(),text:document.querySelector('#runtime-status').textContent}))
      .observe(document.querySelector('#runtime-status'),{childList:true,subtree:true});
  });
  await context.setOffline(true);
  const start=Date.now();await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toContainText('Finding starting equilibrium',{timeout:15000});
  await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:300000});
  const seconds=(Date.now()-start)/1000;
  const pending=page.waitForEvent('download');await page.locator('#export-json').click();
  const out=JSON.parse(await readFile(await(await pending).path(),'utf8'));
  expect(out.accepted_steps).toBe(20);expect(out.rejected_steps).toBe(0);
  expect(out.snapshots.at(-1).time).toBe(.2);
  for(const snapshot of out.snapshots){
    expect(snapshot.residual).toBeLessThanOrEqual(1e-8);
    expect(Math.abs(snapshot.CL-out.snapshots[0].CL)).toBeLessThan(1e-8);
    expect(Math.max(...snapshot.local_velocity.flat().map(Math.abs))).toBeLessThan(1e-8);
  }
  expect(errors).toEqual([]);
  const messages=await page.evaluate(()=>window.solveMessages);
  await writeFile(testInfo.outputPath('response.json'),JSON.stringify(out));
  await writeFile(testInfo.outputPath('measurement.json'),JSON.stringify({example,seconds,evaluations:out.evaluations,steps:out.accepted_steps,messages},null,2));
  console.log(JSON.stringify({example,seconds,evaluations:out.evaluations,steps:out.accepted_steps}));
});
