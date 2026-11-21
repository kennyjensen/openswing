import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';

test('full saved Daedalus reuses beam factors and exports its complete response offline',async({page,context},info)=>{
  test.setTimeout(1800000);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  let last=0;
  await page.exposeFunction('influenceProgress',row=>{
    if(Date.now()-last>10000){console.log(JSON.stringify(row));last=Date.now();}
  });
  await page.addInitScript(()=>{
    const original=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:original.call(this,type,...args);};
  });
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('dae');
  await expect(page.locator('#model-name')).toHaveText('Daedalus HPA');
  await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#panels')).toHaveValue('48');
  await page.locator('#speed').fill('30');await page.locator('#alpha').fill('5');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('.1');
  await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-count').fill('2');
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);
  await page.locator('#equilibrium-file').setInputFiles('tests/fixtures/dae-geometry-equilibrium.json');
  await expect(page.locator('#equilibrium-enable')).toBeChecked();
  await page.evaluate(()=>{
    window.influenceMessages=[];
    new MutationObserver(()=>{
      const row={ms:performance.now(),text:document.querySelector('#runtime-status').textContent};
      window.influenceMessages.push(row);window.influenceProgress(row);
    }).observe(document.querySelector('#runtime-status'),{childList:true,subtree:true});
  });
  await context.setOffline(true);
  const start=performance.now(),wall=Date.now();await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:1500000});
  const seconds=(performance.now()-start)/1000,wallSeconds=(Date.now()-wall)/1000;
  const event=page.waitForEvent('download');await page.locator('#export-json').click();
  const result=JSON.parse(await readFile(await(await event).path(),'utf8'));
  expect(result.converged).toBe(true);expect(result.samples.map(s=>s.omega)).toEqual([.1,100]);
  expect(result.inputs).toHaveLength(4);expect(result.diagnostics.full_dimension).toBe(5167);
  expect(result.diagnostics.loaded_matrices_reused).toBe(false);
  expect(result.diagnostics.harmonic_structure.beam_equations_eliminated).toBe(1650);
  expect(result.diagnostics.harmonic_structure.beam_reduced_dimension).toBe(3517);
  expect(result.diagnostics.state_linearization.equilibrium_columns_reused).toBe(result.diagnostics.state_layout.network_size);
  const rank=result.base.equilibrium_initialization;
  expect(rank.rank_check).toBe('sparse inverse-norm certificate');
  expect(rank.column_scaled_reciprocal_condition).toBeNull();
  expect(rank.column_scaled_reciprocal_condition_lower_bound).toBeGreaterThan(1e-10);
  for(const sample of result.samples){
    expect(sample.responses).toHaveLength(4);
    expect(sample.diagnostics.factor_dimensions).toEqual([1867,1867,1867,1867]);
    expect(sample.diagnostics.beam_equations_eliminated).toEqual([1650,1650,1650,1650]);
    for(const residual of sample.diagnostics.scaled_residuals)expect(residual).toBeLessThanOrEqual(1e-7);
    for(const response of sample.responses)expect(response.state.real).toHaveLength(5167);
  }
  await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
  await expect(page.locator('#frequency-gain-plot svg')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  const download=page.waitForEvent('download');await page.locator('#frequency-csv').click();
  expect((await readFile(await(await download).path(),'utf8')).trim().split('\n')).toHaveLength(3);
  expect(errors).toEqual([]);
  const messages=await page.evaluate(()=>window.influenceMessages);
  expect(messages.some(row=>row.text.includes('checking constraint independence'))).toBe(true);
  expect(messages.some(row=>row.text.includes('full constraint check'))).toBe(false);
  expect(messages.some(row=>row.text.includes('preparing reusable beam factors'))).toBe(true);
  await writeFile(info.outputPath('full-dae.json'),JSON.stringify({seconds,wallSeconds,messages,result,
    qualification:'Saved-equilibrium launch, full 48-interval mesh, two endpoint frequencies and four inputs. Software viewer; unchanged numerical WebAssembly worker. This is not a timing comparison with a cold or 21-frequency run.'}));
  console.log(JSON.stringify({seconds,wallSeconds}));
});
