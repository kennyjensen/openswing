import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

test('stalled circulation continuation, reflected roots and exports work offline',async({page,context})=>{
  test.setTimeout(300000);
  const study=JSON.parse(await readFile('docs/validation/stall-circulation.json','utf8'));
  const source=await readFile('examples/stall-branch.asw');
  expect(createHash('sha256').update(source).digest('hex')).toBe(study.source_sha256['examples/stall-branch.asw']);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('stall-branch');
  await expect(page.locator('#editor')).toHaveValue(source.toString('utf8'));
  await expect(page.locator('#solve')).toBeEnabled();
  await context.setOffline(true);
  await page.locator('#speed').fill('47.9');await page.locator('#beta').fill('0');
  await page.locator('#stall').check();
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#density-mode').selectOption('custom');await page.locator('#density').fill('1.2256');
  await page.locator('#mach-mode').selectOption('auto');
  const selected=study.cases.filter(c=>c.specification.mach===null&&[24,96].includes(c.specification.panels)&&Math.abs(c.specification.alpha)===60);
  selected.push(study.cases.find(c=>c.specification.alpha===75&&c.specification.mach===null&&c.specification.step===.04));
  selected.push(study.cases.find(c=>c.specification.alpha===85&&c.specification.mach===null&&c.specification.step===.04));
  expect(selected).toHaveLength(6);
  for(const c of selected){
    const s=c.specification;
    if(await page.locator('#panels').inputValue()!==String(s.panels)){
      await page.locator('#panels').fill(String(s.panels));await page.locator('#panels').press('Tab');
    }
    await expect(page.locator('#solve')).toBeEnabled();
    await page.locator('#alpha').fill(String(s.alpha));await page.locator('#solve').click();
    await expect(page.locator('#result-state')).toHaveText('Converged · rigid geometry',{timeout:120000});
    const dl=page.waitForEvent('download');await page.locator('#export-json').click();
    const r=JSON.parse(await readFile(await(await dl).path(),'utf8'));
    expect(r.panels).toBe(s.panels);expect(r.condition.alpha).toBe(s.alpha);
    expect(r.circulation_solver.method).toBe('continuation');expect(r.circulation_solver.path).toBe('pseudo-arclength');
    expect(r.circulation_solver.final_regularization).toBe(0);
    expect(r.circulation_solver.trace.at(-1).parameter).toBe(1);
    expect(r.residual).toBeLessThan(1e-9);
    for(const key of ['CL','CD','Cm'])expect(Math.abs(r[key]-c.result.coefficients[key])).toBeLessThan(2e-7);
    await page.locator('#tab-report').click();
    await expect(page.locator('#pane-report')).toContainText('Arclength continuation:');
    await expect(page.locator('#pane-report')).toContainText('Final regularization: 0');
    await expect(page.locator('#pane-report')).toContainText('uniqueness and aircraft stability are not established');
  }
  await page.locator('#tab-loading').click();
  const csv=page.waitForEvent('download');await page.locator('#csv').click();
  const table=await readFile(await(await csv).path(),'utf8');
  expect(table).toContain('circulation');expect(table.trim().split('\n')).toHaveLength(97);
  const canvas=await page.locator('#viewport canvas').evaluate(el=>({renderer:el.dataset.renderer,png:el.toDataURL('image/png')}));
  expect(canvas.png.length).toBeGreaterThan(2000);
  await writeFile('test-results/stall-circulation-geometry.png',Buffer.from(canvas.png.split(',')[1],'base64'));
  await page.screenshot({path:'test-results/stall-circulation-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.screenshot({path:'test-results/stall-circulation-mobile.png'});
  await page.locator('#alpha').fill('60');
  await expect(page.locator('#export-json')).toBeDisabled();
  expect(errors).toEqual([]);
});
