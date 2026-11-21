import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';

async function download(page,selector){
  const pending=page.waitForEvent('download');await page.locator(selector).click();
  return readFile(await(await pending).path(),'utf8');
}

test('offline section sensitivities show analytical strain/stress, export all columns and preserve missing data',async({page,context},testInfo)=>{
  test.setTimeout(240000);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  // The companion WebGL checks cover geometry. Exercise the fallback and
  // actual packaged worker here, including offline numerical computation.
  await page.addInitScript(()=>{
    const original=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:original.call(this,type,...args);};
  });
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles('examples/axial-torsion.asw');
  await expect(page.locator('#model-name')).toHaveText('Axial and torsional response');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('mounted');await page.locator('#alpha').fill('0');
  await page.locator('[data-power="1"]').fill('.2');
  await page.locator('#atmosphere-settings').evaluate(element=>element.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#derivative-settings').evaluate(element=>element.open=true);
  await page.locator('#derivatives-enable').check();
  for(const input of await page.locator('#derivative-parameters input').all())await input.setChecked(['power.1','alpha'].includes(await input.inputValue()));
  await context.setOffline(true);await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:120000});
  await page.locator('#tab-derivatives').click();
  await page.locator('#derivative-column').selectOption('1');
  await page.locator('#derivative-field').selectOption('shell_shear_stress');
  await expect(page.locator('#derivative-plot .section-point')).toHaveCount(4);
  await expect(page.locator('#derivative-plot-note')).toContainText('input F / L^2');
  await expect(page.locator('#derivative-plot-note')).toContainText('material-midpoint');
  const result=JSON.parse(await download(page,'#export-json'));
  expect(result.derivatives.parameters.map(p=>p.name)).toEqual(['alpha','power.1']);
  for(const row of result.derivatives.matrices.shell_shear_stress){expect(row[0]).toBeCloseTo(0,6);expect(row[1]).toBeCloseTo(250,4);}
  const csv=await download(page,'#derivative-structure-csv');
  expect(csv.trim().split('\n')).toHaveLength(5);
  expect(csv).toContain('"alpha / (rad)","power.1 / (file engine setting)"');
  expect(csv).toContain('"material midpoint"');
  const values=csv.trim().split('\n').slice(1).map(row=>Number(row.split(',').at(-1).replaceAll('"','')));
  for(const value of values)expect(value).toBeCloseTo(250,4);
  await page.locator('#derivative-field').selectOption('shell_axial_strain');
  const titles=await page.locator('#derivative-plot .section-point title').allTextContents();
  expect(titles).toHaveLength(4);for(const title of titles)expect(Number(title.split('derivative=')[1])).toBeCloseTo(.003,8);
  await page.setViewportSize({width:390,height:844});
  await page.locator('#workspace-tab-output').click();
  await page.locator('#derivative-plot').scrollIntoViewIfNeeded();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.screenshot({path:testInfo.outputPath('section-derivatives-mobile.png')});
  expect(JSON.parse(await download(page,'#export-json'))).toEqual(result);
  await page.setViewportSize({width:1440,height:1000});
  const source=(await readFile('examples/axial-torsion.asw','utf8')).replace('t Cshell Nshell Atshell\n0 .1 .2 .004\n2 .1 .2 .004\n','');
  await page.locator('#file').setInputFiles({name:'missing-shell.asw',mimeType:'text/plain',buffer:Buffer.from(source)});
  await expect(page.locator('#solve')).toBeEnabled();await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:120000});
  await page.locator('#tab-derivatives').click();await page.locator('#derivative-field').selectOption('shell_shear_stress');
  await expect(page.locator('#derivative-plot')).toContainText('unavailable');
  const missing=await download(page,'#derivative-structure-csv');
  for(const line of missing.trim().split('\n').slice(1))expect(line).toMatch(/,"",""$/);
  expect(errors).toEqual([]);
});
