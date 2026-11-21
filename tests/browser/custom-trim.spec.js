import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
async function download(page,id='#export-json'){const event=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}
async function prepare(page){
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('instrumented-oscillator');await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('mounted');await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#operating-settings').evaluate(e=>e.open=true);await page.locator('#add-constraint').click();
  await page.locator('.constraint-variable').selectOption('power.1');await page.locator('.constraint-quantity').selectOption('user');
  await page.locator('.constraint-row input').fill('.01');await page.locator('[data-custom="residual_scale"]').fill('.01');
}
async function solve(page){await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:240000});await expect(page.locator('#error')).toBeHidden();}

test('custom displacement and strain targets solve physical controls, export and reject undefined sensors offline',async({page,context})=>{
  test.setTimeout(480000);const errors=[];page.on('pageerror',e=>errors.push(e.message));await prepare(page);await context.setOffline(true);await solve(page);
  const a=await download(page);expect(a.operating_values['power.1']).toBeCloseTo(5,7);expect(a.sensors[1].displacement_body[1]).toBeCloseTo(.01,9);
  expect(a.request.operating_constraints[0].expression).toBe('sensor("2.displacement_body.y")');
  await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText('CUSTOM TRIM EQUATIONS');await expect(page.locator('#pane-report')).toContainText('sensor("2.displacement_body.y")');
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);const saved=await download(page,'#equilibrium-save');expect(saved.launch.released_constraints[0].residual_scale).toBe(.01);await page.locator('#equilibrium-use').click();
  await page.getByLabel('Use a sensor measurement',{exact:true}).selectOption('2.strain.s');await page.locator('.constraint-row input').fill('.01');
  await expect(page.locator('[data-custom="unit"]')).toHaveValue('dimensionless');await expect(page.locator('#export-json')).toBeDisabled();await solve(page);
  const b=await download(page);expect(b.operating_values['power.1']).toBeCloseTo(10,7);expect(b.sensors[1].displacement_body[1]).toBeCloseTo(.02,9);expect(b.sensors[1].strain[1]).toBeCloseTo(.01,9);
  // Other row operations preserve the custom editor's definition.
  await page.locator('#add-constraint').click();await expect(page.locator('[data-custom="expression"]')).toHaveValue('sensor("2.strain.s")');await page.locator('.constraint-row').last().getByRole('button',{name:'Remove constraint'}).click();
  await page.locator('#custom-trim-settings').screenshot({path:'test-results/custom-trim.png'});await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();await page.locator('#custom-trim-settings').screenshot({path:'test-results/custom-trim-mobile.png'});
  await page.locator('[data-custom="expression"]').fill('sensor("2.shell_strain")');await page.locator('#solve').click();await expect(page.locator('#error')).toContainText('undefined');await expect(page.locator('#export-json')).toBeDisabled();
  await page.locator('#clear-constraints').click();await expect(page.locator('#custom-trim-settings')).toBeHidden();expect(errors).toEqual([]);
});

test('saved custom trim is released for the analytical Bode response',async({page,context})=>{
  test.setTimeout(480000);await prepare(page);await context.setOffline(true);await solve(page);
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);await page.locator('#equilibrium-use').click();await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-count').fill('3');await page.locator('#frequency-spacing').selectOption('linear');await page.locator('#frequency-start').fill('0');await page.locator('#frequency-end').fill('20');await page.locator('#frequency-inputs').selectOption('controls');await solve(page);
  const f=await download(page);expect(f.base.custom_trim.one_sided_tangent_ratio).toBeLessThan(1);
  for(const row of f.samples){const d=row.responses[0].output.sensors[1].displacement_body,w=row.omega,re=500-2*w*w,im=10*w,den=re*re+im*im;expect(d.real[1]).toBeCloseTo(re/den,9);expect(d.imag[1]).toBeCloseTo(-im/den,9);}
  await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText('CUSTOM TRIM EQUATIONS');await expect(page.locator('#pane-report')).toContainText('sensor("2.displacement_body.y")');
});

test('weighted trim requires the controller stored in an imported equilibrium',async({page,context})=>{
  test.setTimeout(240000);await prepare(page);
  const study=JSON.parse(await readFile('docs/validation/custom-trim.json','utf8'));
  const saved=study.cases.find(c=>c.specification.name==='closed_loop').result.static.equilibrium_state;
  await page.locator('.constraint-quantity').selectOption('minimum_control');
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);
  await page.locator('#equilibrium-file').setInputFiles({name:'controller-equilibrium.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(saved))});
  await expect(page.locator('#equilibrium-enable')).toBeChecked();await context.setOffline(true);
  await page.locator('#solve').click();await expect(page.locator('#error')).toContainText('matching controller definition');await expect(page.locator('#export-json')).toBeDisabled();
});
