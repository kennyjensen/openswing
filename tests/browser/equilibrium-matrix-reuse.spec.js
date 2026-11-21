import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';

async function report(page){
  const event=page.waitForEvent('download');await page.locator('#export-json').click();
  return JSON.parse(await readFile(await(await event).path(),'utf8'));
}
async function run(page){
  await page.evaluate(()=>{window.matrixMessages=[];});
  const start=performance.now(),wall=Date.now();await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText(/^(Analysis converged|Analysis stopped|Kernel unavailable)$/,{timeout:2400000});
  expect(await page.locator('#runtime-status').textContent()).toBe('Analysis converged');
  return {seconds:(performance.now()-start)/1000,wallSeconds:(Date.now()-wall)/1000,
          messages:await page.evaluate(()=>window.matrixMessages),result:await report(page)};
}
async function setup(page){
  let last=0;
  await page.exposeFunction('matrixProgress',row=>{
    if(Date.now()-last>10000){console.log(JSON.stringify(row));last=Date.now();}
  });
  await page.addInitScript(()=>{
    const get=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:get.call(this,type,...args);};
  });
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.evaluate(()=>{
    window.matrixMessages=[];
    new MutationObserver(()=>{
      const row={ms:performance.now(),text:document.querySelector('#runtime-status').textContent};
      window.matrixMessages.push(row);window.matrixProgress(row);
    })
      .observe(document.querySelector('#runtime-status'),{childList:true,subtree:true});
  });
}

test('offline new Bode runs reuse a loaded model and invalidate it after condition changes',async({page,context},info)=>{
  test.setTimeout(900000);await setup(page);
  await page.locator('#file').setInputFiles('examples/forced-oscillator.asw');
  await expect(page.locator('#model-name')).toHaveText('Forced spring-mass demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#alpha').fill('0');await page.locator('#speed').fill('10');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-inputs').selectOption('controls');
  await page.locator('#frequency-count').fill('3');await context.setOffline(true);
  const first=await run(page);expect(first.result.diagnostics.loaded_matrices_reused).toBe(false);
  await page.locator('#frequency-start').fill('1');await page.locator('#frequency-end').fill('30');
  const second=await run(page);expect(second.result.diagnostics.loaded_matrices_reused).toBe(true);
  expect(second.messages.some(e=>e.text.includes('reusing loaded equilibrium and response matrices'))).toBe(true);
  expect(second.messages.some(e=>e.text.includes('building response model'))).toBe(false);
  for(const sample of second.result.samples){
    const w=sample.omega,re=500-2*w*w,im=10*w,den=re*re+im*im;
    const d=sample.responses[0].output.nodes.at(-1).displacement;
    expect(d.real[1]).toBeCloseTo(re/den,10);expect(d.imag[1]).toBeCloseTo(-im/den,10);
  }
  await page.locator('#speed').fill('11');const changed=await run(page);
  expect(changed.result.diagnostics.loaded_matrices_reused).toBe(false);
  expect(changed.messages.some(e=>e.text.includes('building response model'))).toBe(true);
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);
  await page.locator('#equilibrium-use').click();
  const seeded=await run(page);
  expect(seeded.result.diagnostics.state_linearization.equilibrium_columns_reused).toBe(seeded.result.diagnostics.state_layout.network_size);
  expect(seeded.messages.some(e=>e.text.includes('equilibrium derivative columns'))).toBe(true);
  await writeFile(info.outputPath('reuse.json'),JSON.stringify({first,second,changed,seeded}));
});

test('full offline Daedalus keeps its matrices for a new 21-frequency run',async({page,context},info)=>{
  test.setTimeout(3600000);await setup(page);
  await page.locator('#example').selectOption('dae');await expect(page.locator('#model-name')).toHaveText('Daedalus HPA');
  await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#panels')).toHaveValue('48');
  await page.locator('#speed').fill('30');await page.locator('#alpha').fill('5');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('.1');
  await page.locator('#mode').selectOption('frequency');await context.setOffline(true);
  const first=await run(page);expect(first.result.diagnostics.loaded_matrices_reused).toBe(false);
  await writeFile(info.outputPath('first.json'),JSON.stringify(first));
  // The ordinary Run button starts a new sweep; it must retain the complete
  // operator when the range changes, despite invalidating the old UI result.
  await page.locator('#frequency-start').fill('.2');await page.locator('#frequency-end').fill('80');
  const second=await run(page);expect(second.result.diagnostics.loaded_matrices_reused).toBe(true);
  await writeFile(info.outputPath('second.json'),JSON.stringify(second));
  expect(second.result.diagnostics.full_dimension).toBe(5167);expect(second.result.samples).toHaveLength(21);
  expect(second.result.inputs).toHaveLength(4);expect(second.result.converged).toBe(true);
  expect(second.messages.some(e=>e.text.includes('reusing loaded equilibrium and response matrices'))).toBe(true);
  expect(second.messages.some(e=>/building response model|inertia and damping/.test(e.text))).toBe(false);
  for(const sample of second.result.samples){
    expect(sample.responses).toHaveLength(4);
    for(const value of sample.diagnostics.scaled_residuals)expect(value).toBeLessThanOrEqual(1e-7);
    for(const r of sample.responses)expect(r.state.real).toHaveLength(5167);
  }
  await expect(page.locator('#frequency-gain-plot svg')).toBeVisible();
  const download=page.waitForEvent('download');await page.locator('#frequency-csv').click();
  expect((await readFile(await(await download).path(),'utf8')).trim().split('\n')).toHaveLength(22);
  console.log(JSON.stringify({firstSeconds:first.seconds,firstWall:first.wallSeconds,reusedSeconds:second.seconds,reusedWall:second.wallSeconds}));
});
