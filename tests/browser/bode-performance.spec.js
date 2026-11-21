import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';

test('default Daedalus Bode sweep finishes offline with clear progress and full outputs',async({page,context},info)=>{
  const solveTimeout=2400000;test.setTimeout(solveTimeout+90000);
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
  await page.locator('#mode').selectOption('frequency');
  await expect(page.locator('#frequency-count')).toHaveValue('21');
  let lastProgress=0;
  await page.exposeFunction('bodeProgress',row=>{
    if(Date.now()-lastProgress>=10000){console.log(JSON.stringify(row));lastProgress=Date.now();}
  });
  await page.evaluate(()=>{
    window.solveMessages=[];
    new MutationObserver(()=>{
      const row={ms:performance.now(),text:document.querySelector('#runtime-status').textContent};
      window.solveMessages.push(row);window.bodeProgress(row);
    })
      .observe(document.querySelector('#runtime-status'),{childList:true,subtree:true});
  });
  await context.setOffline(true);
  const start=performance.now(),wallStart=Date.now();await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:solveTimeout});
  const seconds=(performance.now()-start)/1000,wallClockSeconds=(Date.now()-wallStart)/1000;
  const pending=page.waitForEvent('download');await page.locator('#export-json').click();
  const response=JSON.parse(await readFile(await(await pending).path(),'utf8'));
  const messages=await page.evaluate(()=>window.solveMessages);
  await writeFile(info.outputPath('response.json'),JSON.stringify(response));
  await writeFile(info.outputPath('measurement.json'),JSON.stringify({seconds,wallClockSeconds,messages},null,2));
  expect(response.converged).toBe(true);expect(response.samples).toHaveLength(21);
  expect(response.diagnostics.full_dimension).toBe(5167);
  expect(response.diagnostics.matrix_storage).toBe('sparse full descriptor');
  for(const sample of response.samples){
    expect(sample.responses).toHaveLength(response.inputs.length);
    for(const residual of sample.diagnostics.scaled_residuals)expect(residual).toBeLessThanOrEqual(1e-7);
    for(const r of sample.responses){expect(r.output.nodes.length).toBe(response.base.nodes.length);expect(r.state.real).toHaveLength(5167);}
  }
  for(const label of ['finding loaded equilibrium','building response model','inertia and damping','frequencies completed','preparing plots'])
    expect(messages.some(row=>row.text.includes(label))).toBe(true);
  await expect(page.locator('#frequency-gain-plot svg')).toBeVisible();
  await expect(page.locator('#frequency-phase-plot svg')).toBeVisible();
  const csv=page.waitForEvent('download');await page.locator('#frequency-csv').click();
  expect((await readFile(await(await csv).path(),'utf8')).trim().split('\n')).toHaveLength(22);
  expect(errors).toEqual([]);
  console.log(JSON.stringify({seconds,wallClockSeconds,dimension:response.diagnostics.full_dimension}));
});
