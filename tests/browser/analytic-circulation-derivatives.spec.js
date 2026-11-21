import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';

async function download(page,selector){
  const pending=page.waitForEvent('download');
  await page.locator(selector).click();
  return readFile(await(await pending).path(),'utf8');
}

test('packaged mounted derivatives use analytic circulation offline with current and frozen influences',async({page,context},testInfo)=>{
  test.setTimeout(240000);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.addInitScript(()=>{
    const original=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:original.call(this,type,...args);};
  });
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles('tests/data/derivative-quiet-wing.asw');
  await expect(page.locator('#model-name')).toHaveText('Analytic circulation derivative regression wing');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('mounted');
  await page.locator('#speed').fill('30');await page.locator('#alpha').fill('0');await page.locator('#beta').fill('0');
  await page.locator('#stall').uncheck();
  await page.locator('#atmosphere-settings').evaluate(element=>element.open=true);
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('.1');
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#circulation-settings').evaluate(element=>element.open=true);
  await page.locator('#derivative-settings').evaluate(element=>element.open=true);
  await page.locator('#derivatives-enable').check();
  for(const input of await page.locator('#derivative-parameters input').all())await input.setChecked(['alpha','p','control.1'].includes(await input.inputValue()));
  await context.setOffline(true);
  const results=[];
  for(const frozen of [false,true]){
    await page.locator('#freeze-influences').setChecked(frozen);
    await page.locator('#solve').click();
    await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:120000});
    const result=JSON.parse(await download(page,'#export-json'));
    results.push(result);
    await writeFile(testInfo.outputPath(`result-${frozen?'frozen':'current'}.json`),JSON.stringify(result,null,2)+'\n');
    const d=result.derivatives;
    expect(d.method).toBe('implicit residual derivatives with analytic circulation columns');
    expect(d.step).toBe(1e-5);expect(d.response).toBe('fixed_acceleration');
    expect(d.parameters.map(p=>p.name)).toEqual(['alpha','p','control.1']);
    expect(Math.max(...d.linear_residuals)).toBeLessThan(1e-8);
    expect(d.column_scaled_reciprocal_condition).toBeGreaterThan(1e-10);
    expect(result.condition.freeze_influences).toBe(frozen);
    expect(result.residual).toBeLessThan(1e-8);
    expect(Object.keys(result.software_provenance.modules)).toContain('derivative_circulation.py');
    expect(Math.abs(d.matrices.coefficients[2][2])).toBeGreaterThan(0);
    await page.locator('#tab-derivatives').click();
    await expect(page.locator('#derivative-table tr')).toHaveCount(7);
    const csv=await download(page,'#derivative-csv');
    expect(csv).toContain('"control.1 / file flap setting"');
    await writeFile(testInfo.outputPath(`coefficients-${frozen?'frozen':'current'}.csv`),csv);
    await page.locator('#derivative-column').selectOption('2');
    await page.locator('#derivative-field').selectOption('section_curvature.0');
    await expect(page.locator('#derivative-plot .section-point')).toHaveCount(4);
    const sectionCsv=await download(page,'#derivative-structure-csv');
    expect(sectionCsv.trim().split('\n')).toHaveLength(5);
    await writeFile(testInfo.outputPath(`curvature-${frozen?'frozen':'current'}.csv`),sectionCsv);
  }
  await page.setViewportSize({width:390,height:844});
  await page.locator('#workspace-tab-output').click();
  await page.locator('#derivative-plot').scrollIntoViewIfNeeded();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.screenshot({path:testInfo.outputPath('analytic-derivatives-mobile.png')});
  expect(JSON.parse(await download(page,'#export-json'))).toEqual(results[1]);
  expect(errors).toEqual([]);
});
