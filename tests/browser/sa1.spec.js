import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {createHash} from 'node:crypto';

test('archived SA-1 import, mesh refinement, PG choices and exports work offline',async({page,context})=>{
  test.skip(!existsSync('.reference/isae-sa1/SA_1.asw'), 'Run scripts/fetch-sa1.py to fetch the unshipped reference model.');
  test.setTimeout(240000);
  const source=await readFile('.reference/isae-sa1/SA_1.asw');
  const study=JSON.parse(await readFile('docs/validation/sa1.json','utf8'));
  expect(createHash('sha256').update(source).digest('hex')).toBe(study.provenance.files['SA_1.asw'].sha256);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await context.setOffline(true);
  await page.locator('#file').setInputFiles('.reference/isae-sa1/SA_1.asw');
  await expect(page.locator('#editor')).toHaveValue(source.toString('utf8'));
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#speed').fill('47.9');await page.locator('#beta').fill('0');
  await page.locator('#stall').check();
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#density-mode').selectOption('custom');await page.locator('#density').fill('1.2256');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  const selected=study.cases.filter(c=>c.specification.name.startsWith('fixed_zero/ASWING/')&&
    c.specification.alpha_deg===18.091&&[96,200].includes(c.specification.panels));
  selected.push(study.cases.find(c=>c.specification.name==='speed_derived/ASWING/200/10'));
  selected.push(study.cases.find(c=>c.specification.name.startsWith('fixed_zero/symmetry/')&&c.specification.alpha_deg===0));
  for(const c of selected){
    expect(c).toBeTruthy();
    const s=c.specification;
    if(await page.locator('#panels').inputValue()!==String(s.panels)){
      await page.locator('#panels').fill(String(s.panels));await page.locator('#panels').press('Tab');
    }
    await expect(page.locator('#solve')).toBeEnabled();
    await page.locator('#alpha').fill(String(s.alpha_deg));
    await page.locator('#mach-mode').selectOption(s.mach===null?'auto':'fixed');
    await page.locator('#solve').click();
    await expect(page.locator('#result-state')).toHaveText('Converged · rigid geometry');
    const dl=page.waitForEvent('download');await page.locator('#export-json').click();
    const actual=JSON.parse(await readFile(await(await dl).path(),'utf8'));
    expect(actual.panels).toBe(s.panels);expect(actual.residual).toBeLessThan(1e-8);
    for(const key of ['CL','CD','CDi','CDp','Cm'])expect(Math.abs(actual[key]-c.result[key])).toBeLessThan(2e-7);
    await expect(page.locator('#cl')).toHaveText(actual.CL.toFixed(4));
    await expect(page.locator('#cd')).toHaveText(actual.CD.toFixed(5));
    if(s.alpha_deg===0)expect(actual.CD).toBeCloseTo(.01123975,12);
    if(s.panels===200&&s.mach===0){
      const canvas=await page.locator('#viewport canvas').evaluate(el=>{
        let wingPixels=null;
        if(el.dataset.renderer==='canvas2d'){
          const pixels=el.getContext('2d').getImageData(0,0,el.width,el.height).data;
          wingPixels=0;
          for(let i=0;i<pixels.length;i+=4)if(pixels[i+1]>150&&pixels[i+1]>pixels[i]+30&&pixels[i+1]>pixels[i+2])wingPixels++;
        }
        return {renderer:el.dataset.renderer,wingPixels,png:el.toDataURL('image/png')};
      });
      if(canvas.wingPixels!==null)expect(canvas.wingPixels).toBeGreaterThan(500);
      expect(canvas.png.startsWith('data:image/png;base64,')).toBe(true);
      await writeFile('test-results/sa1-geometry.png',Buffer.from(canvas.png.split(',')[1],'base64'));
      await page.screenshot({path:'test-results/sa1-desktop.png',fullPage:true});
    }
  }
  // Decimal sideslip must also reach the solver unchanged. Reflection about the
  // wing's symmetry plane preserves lift/drag and reverses lateral coefficients.
  await page.locator('#alpha').fill('8.1351');
  const lateral=[];
  for(const beta of [.037,-.037]){
    await page.locator('#beta').fill(String(beta));await page.locator('#solve').click();
    await expect(page.locator('#result-state')).toHaveText('Converged · rigid geometry');
    const dl=page.waitForEvent('download');await page.locator('#export-json').click();
    const result=JSON.parse(await readFile(await(await dl).path(),'utf8'));
    expect(result.condition.beta).toBe(beta);expect(result.residual).toBeLessThan(1e-8);
    lateral.push(result);
  }
  for(const key of ['CL','CD'])expect(lateral[0][key]).toBeCloseTo(lateral[1][key],8);
  for(const key of ['CY','Cl','Cn'])expect(lateral[0][key]).toBeCloseTo(-lateral[1][key],8);
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#tab-loading').click();
  await page.screenshot({path:'test-results/sa1-mobile.png'});
  expect(errors).toEqual([]);
});
