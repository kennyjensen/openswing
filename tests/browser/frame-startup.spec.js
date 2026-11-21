import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';

test('Daedalus at 48 intervals per beam initializes and advances free flight offline',async({page,context},testInfo)=>{
  const duration=Number(process.env.OPENSWING_TIME_DURATION||'.02');
  if(![.02,.2].includes(duration))throw new Error('Daedalus benchmark duration must be .02 or .2.');
  const solveTimeout=duration===.2?900000:300000;
  test.setTimeout(solveTimeout+60000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
    const original=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:original.call(this,type,...args);};
  });
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('dae');
  await expect(page.locator('#model-name')).toHaveText('Daedalus HPA');
  await expect(page.locator('#solve')).toBeEnabled();
  await expect(page.locator('#panels')).toHaveValue('48');
  await page.locator('#speed').fill('30');await page.locator('#alpha').fill('5');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('.1');
  await page.locator('#mode').selectOption('time');await page.locator('#time-frame').selectOption('free');
  await page.locator('#time-duration').fill(String(duration));await page.locator('#time-step').fill('.01');
  await page.evaluate(()=>{
    window.solveMessages=[];
    new MutationObserver(()=>window.solveMessages.push({ms:performance.now(),text:document.querySelector('#runtime-status').textContent}))
      .observe(document.querySelector('#runtime-status'),{childList:true,subtree:true});
  });
  await context.setOffline(true);
  const start=performance.now(),wallStart=Date.now();await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:solveTimeout});
  const seconds=(performance.now()-start)/1000,wallClockSeconds=(Date.now()-wallStart)/1000;
  const pending=page.waitForEvent('download');await page.locator('#export-json').click();
  const response=JSON.parse(await readFile(await(await pending).path(),'utf8'));
  const messages=await page.evaluate(()=>window.solveMessages);
  await writeFile(testInfo.outputPath('response.json'),JSON.stringify(response));
  await writeFile(testInfo.outputPath('measurement.json'),JSON.stringify({seconds,wallClockSeconds,evaluations:response.evaluations,steps:response.accepted_steps,messages},null,2));
  expect(response.frame_mode).toBe('free');expect(response.accepted_steps).toBe(Math.round(duration/.01));expect(response.rejected_steps).toBe(0);
  expect(response.snapshots.at(-1).time).toBe(duration);
  for(const row of response.snapshots){
    expect(row.residual).toBeLessThanOrEqual(1e-8);
    expect(row.operating_constraints).toHaveLength(6);
    for(const c of row.operating_constraints){expect(c.target).toBe(0);expect(Math.abs(c.normalized_residual)).toBeLessThanOrEqual(1e-8);}
  }
  expect(messages.some(row=>/Finding starting equilibrium/.test(row.text))).toBe(true);
  expect(errors).toEqual([]);
  console.log(JSON.stringify({seconds,wallClockSeconds,evaluations:response.evaluations}));
});
