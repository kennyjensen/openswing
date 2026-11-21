import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {createHash} from 'node:crypto';

test('archived SA-2 imports and compares mesh, PG and frozen choices offline',async({page,context})=>{
  test.skip(!existsSync('.reference/isae-sa2/SA_2.asw'),'Run scripts/fetch-sa2.py to fetch the unshipped reference model.');
  test.setTimeout(360000);
  const source=await readFile('.reference/isae-sa2/SA_2.asw');
  const study=JSON.parse(await readFile('docs/validation/sa2.json','utf8'));
  expect(createHash('sha256').update(source).digest('hex')).toBe(study.provenance.files['SA_2.asw'].sha256);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await context.setOffline(true);
  await page.locator('#file').setInputFiles('.reference/isae-sa2/SA_2.asw');
  await expect(page.locator('#editor')).toHaveValue(source.toString('utf8'));
  await expect(page.locator('#solve')).toBeEnabled();await page.locator('#mode').selectOption('rigid');
  await page.locator('#speed').fill('49.9');await page.locator('#beta').fill('0');await page.locator('#stall').check();
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#density-mode').selectOption('custom');await page.locator('#density').fill('1.2256');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#circulation-settings').evaluate(e=>e.open=true);
  const names=['current_fixed_zero/polar/100/4','current_fixed_zero/polar/200/4',
               'current_speed_derived/polar/200/4','frozen_fixed_zero/polar/200/4',
               'frozen_speed_derived/polar/200/4','current_fixed_zero/symmetry/0.0'];
  const exported=[];
  for(const name of names){
    const c=study.cases.find(c=>c.specification.name===name);expect(c,name).toBeTruthy();const s=c.specification;
    if(await page.locator('#panels').inputValue()!==String(s.panels)){
      await page.locator('#panels').fill(String(s.panels));await page.locator('#panels').press('Tab');
    }
    await expect(page.locator('#solve')).toBeEnabled();await page.locator('#alpha').fill(String(s.alpha_deg));
    await page.locator('#mach-mode').selectOption(s.mach===null?'auto':'fixed');
    await page.locator('#freeze-influences').setChecked(s.freeze_influences);
    await page.locator('#solve').click();
    await expect(page.locator('#result-state')).toHaveText('Converged · rigid geometry',{timeout:120000});
    const dl=page.waitForEvent('download');await page.locator('#export-json').click();
    const actual=JSON.parse(await readFile(await(await dl).path(),'utf8'));
    expect(actual.panels).toBe(s.panels);expect(actual.residual).toBeLessThan(1e-8);
    expect(actual.condition.freeze_influences).toBe(s.freeze_influences);
    expect(actual.aerodynamic_influences.frozen).toBe(s.freeze_influences);
    for(const key of ['CL','CD','CDi','CDp','Cm'])expect(Math.abs(actual[key]-c.result[key]),name+'/'+key).toBeLessThan(2e-7);
    await expect(page.locator('#cl')).toHaveText(actual.CL.toFixed(4));
    await expect(page.locator('#cd')).toHaveText(actual.CD.toFixed(5));
    if(s.alpha_deg===0)expect(actual.CD).toBeCloseTo(study.geometry.zero_incidence_CD,12);
    exported.push({name,CL:actual.CL,CD:actual.CD,Cm:actual.Cm,mach:actual.mach,frozen:actual.aerodynamic_influences.frozen});
    if(name==='current_fixed_zero/polar/200/4'){
      await page.locator('#viewport').screenshot({path:'test-results/sa2-geometry.png'});
      await page.locator('#tab-loading').click();await page.screenshot({path:'test-results/sa2-desktop.png',fullPage:true});
    }
  }
  // Sweep is read from the literal model, rather than the benchmark title.
  expect(study.geometry.beam_sweep_deg).toBeCloseTo(35.2654607653,8);
  expect(study.reference.primary_table_4[0].CD_pressure).toBeNull();
  await page.locator('#panels').fill('400');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();await page.locator('#alpha').fill('10.5');
  await page.locator('#solve').click();
  await expect(page.locator('#error')).toContainText('Local section-normal Mach reaches unity',{timeout:120000});
  await expect(page.locator('#export-json')).toBeDisabled();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#circulation-settings').scrollIntoViewIfNeeded();await page.screenshot({path:'test-results/sa2-mobile.png'});
  await writeFile('test-results/sa2-browser-values.json',JSON.stringify(exported,null,2)+'\n');
  expect(errors).toEqual([]);
});
