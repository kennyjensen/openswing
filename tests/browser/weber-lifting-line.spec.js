import {test,expect} from '@playwright/test';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';

const mesa=process.env.OPENSWING_WEBGL_DRIVER==='mesa';
test.use({launchOptions:{executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,
  args:mesa?['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native',
    '--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']:
    ['--no-sandbox','--use-gl=angle','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader']}});

test('tabulated swept-wing input solves and rejects invalid refinement offline',async({page,context})=>{
  test.setTimeout(360000);await mkdir('test-results',{recursive:true});
  const study=JSON.parse(await readFile('docs/validation/weber-lifting-line.json','utf8'));
  const source=await readFile('examples/weber-tabulated.asw');
  expect(createHash('sha256').update(source).digest('hex')).toBe(study.source_sha256['examples/weber-tabulated.asw']);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await context.setOffline(true);
  await page.locator('#file').setInputFiles('examples/weber-tabulated.asw');
  await expect(page.locator('#editor')).toHaveValue(source.toString());
  await expect(page.locator('#model-name')).toHaveText('Tabulated swept-wing lifting-line study');
  await page.locator('#mode').selectOption('rigid');await page.locator('#speed').fill('49.6824');
  await page.locator('#beta').fill('0');await page.locator('#stall').uncheck();
  await page.locator('#atmosphere-settings').evaluate(element=>element.open=true);
  await page.locator('#density-mode').selectOption('custom');await page.locator('#density').fill('1.2256');
  await page.locator('#circulation-settings').evaluate(element=>element.open=true);
  const selections=[['current_zero_pg',24,2.1],['current_zero_pg',48,10.5],
    ['current_speed_pg',24,2.1],['frozen_zero_pg',24,2.1],['current_zero_pg',24,0]];
  const actuals=[];
  for(const [mode,panels,alpha] of selections){
    console.log(`Computed case: ${mode}, ${panels} requested intervals, alpha ${alpha}`);
    const expected=study.cases.find(c=>c.specification.mode===mode&&c.specification.panels===panels&&c.specification.alpha_deg===alpha);
    expect(expected?.status).toBe('computed');const spec=expected.specification;
    if(await page.locator('#panels').inputValue()!==String(panels)){
      await page.locator('#panels').fill(String(panels));await page.locator('#panels').press('Tab');
    }
    await expect(page.locator('#solve')).toBeEnabled();await page.locator('#alpha').fill(String(alpha));
    await page.locator('#mach-mode').selectOption(spec.mach===null?'auto':'fixed');
    if(spec.mach!==null)await page.locator('#pg-mach').fill('0');
    await page.locator('#freeze-influences').setChecked(spec.freeze_influences);
    await page.locator('#solve').click();
    await expect(page.locator('#result-state')).toHaveText('Converged · rigid geometry',{timeout:120000});
    const download=page.waitForEvent('download');await page.locator('#export-json').click();
    const result=JSON.parse(await readFile(await(await download).path(),'utf8'));
    expect(result.condition.stall).toBe(false);expect(result.panels).toBe(expected.result.panels);
    expect(result.condition.freeze_influences).toBe(spec.freeze_influences);
    expect(result.aerodynamic_influences.frozen).toBe(spec.freeze_influences);
    expect(result.residual).toBeLessThan(1e-8);
    for(const key of ['CL','CD','CDi','CDp','Cm'])expect(Math.abs(result[key]-expected.result[key]),mode+'/'+key).toBeLessThan(2e-7);
    expect(result.software_provenance.modules).toBeTruthy();
    actuals.push({specification:spec,CL:result.CL,CD:result.CD,Cm:result.Cm,panels:result.panels,provenance:result.software_provenance});
    if(mode==='current_zero_pg'&&alpha===2.1){
      await page.locator('#top-view').click();
      await expect(page.locator('#viewport canvas')).toHaveAttribute('data-renderer','webgl');
      expect(await page.locator('#viewport canvas').evaluate(element=>element.getContext('webgl2').isContextLost())).toBe(false);
      await page.locator('#viewport').screenshot({path:'test-results/weber-lifting-line-geometry.png'});
      await page.locator('#tab-loading').click();
      await page.screenshot({path:'test-results/weber-lifting-line-desktop.png',fullPage:true});
    }
  }
  console.log('Rejected case: current_zero_pg, 512 requested intervals, alpha 2.1');
  await page.locator('#panels').fill('512');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();await page.locator('#alpha').fill('2.1');
  await page.locator('#solve').click();
  await expect(page.locator('#error')).toContainText('Local section-normal Mach reaches unity',{timeout:120000});
  await expect(page.locator('#export-json')).toBeDisabled();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#error').scrollIntoViewIfNeeded();
  await page.screenshot({path:'test-results/weber-lifting-line-mobile.png'});
  expect(errors).toEqual([]);
  await writeFile('test-results/weber-lifting-line-values.json',JSON.stringify(actuals,null,2)+'\n');
});
