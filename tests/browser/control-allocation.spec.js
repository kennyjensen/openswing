import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
async function download(page,id='#export-json'){const event=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}
async function prepare(page){
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('redundant-thrust');await expect(page.locator('#model-name')).toHaveText('Redundant thrust allocation');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('mounted');await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#operating-settings').evaluate(e=>e.open=true);
}
async function add(page,variable,quantity,target=0){
  await page.locator('#add-constraint').click();const row=page.locator('.constraint-row').last();await row.locator('.constraint-variable').selectOption(variable);await row.locator('.constraint-quantity').selectOption(quantity);if(quantity!=='minimum_control')await row.locator('input').fill(String(target));
}
const cost=(page,name,key)=>page.locator(`.allocation-control[data-variable="${name}"] input[data-cost="${key}"]`);
async function solve(page){await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:240000});await expect(page.locator('#error')).toBeHidden();}

test('weighted redundant thrust satisfies hard loads, preserves costs and exports its local optimum offline',async({page,context})=>{
  test.setTimeout(480000);const errors=[];page.on('pageerror',e=>errors.push(e.message));await prepare(page);
  await add(page,'power.1','force.x',20);await add(page,'power.2','minimum_control');await cost(page,'power.2','weight').fill('4');await add(page,'power.3','minimum_control');await cost(page,'power.3','weight').fill('2');
  await expect(cost(page,'power.2','weight')).toHaveValue('4');await context.setOffline(true);await solve(page);
  const out=await download(page),expected=[40/4.75,5/4.75,10/4.75];
  for(let i=0;i<3;i++)expect(out.operating_values[`power.${i+1}`]).toBeCloseTo(expected[i],5);
  expect(out.applied_force[0]).toBeCloseTo(20,8);expect(out.control_allocation.equality_residual).toBeLessThan(1e-8);expect(out.control_allocation.normalized_stationarity).toBeLessThan(2e-6);
  expect(out.request.operating_constraints.map(c=>c.weight)).toEqual([1,4,2]);
  await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText('WEIGHTED CONTROL TRIM');await expect(page.locator('#pane-report')).toContainText('Least-squares control effort');
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);const saved=await download(page,'#equilibrium-save');
  expect(saved.launch.released_constraints.map(c=>c.weight)).toEqual([1,4,2]);await page.locator('#equilibrium-use').click();
  await page.locator('.constraint-quantity').nth(1).selectOption('moment.z');await page.locator('.constraint-row input').nth(1).fill('0');await solve(page);
  const trim=await download(page);expect(trim.applied_force[0]).toBeCloseTo(20,8);expect(trim.applied_moment[2]).toBeCloseTo(0,8);expect(trim.control_allocation.free_directions).toBe(1);
  // With E2=2*E1 and E3=20-4*E1, minimize E1²+4*E2²+2*E3².
  const e1=160/49;expect(trim.operating_values['power.1']).toBeCloseTo(e1,5);expect(trim.operating_values['power.2']).toBeCloseTo(2*e1,5);expect(trim.operating_values['power.3']).toBeCloseTo(20-4*e1,5);
  await page.locator('#allocation-settings').screenshot({path:'test-results/control-allocation.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();await page.locator('#allocation-settings').screenshot({path:'test-results/control-allocation-mobile.png'});
  await cost(page,'power.3','weight').fill('0');await expect(page.locator('#export-json')).toBeDisabled();await page.locator('#solve').click();await expect(page.locator('#error')).toContainText('weights must be positive');
  await page.locator('#clear-constraints').click();await expect(page.locator('#allocation-settings')).toBeHidden();expect(errors).toEqual([]);
});

test('saved weighted spring trim is released for the analytical Bode response',async({page,context})=>{
  test.setTimeout(480000);await prepare(page);
  const source=(await readFile('examples/instrumented-oscillator.asw','utf8')).replace('1 0 1 2 0 2 0 0 1 0 1 0 -1 0 0','1 0 1 2 0 2 0 0 1 0 1 0 -1 0 0\n2 0 1 2 0 2 0 0 1 0 2 0 -1 0 0');
  await page.locator('#file').setInputFiles({name:'redundant-spring.asw',mimeType:'text/plain',buffer:Buffer.from(source)});await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');
  await add(page,'power.1','force.y',5);await add(page,'power.2','minimum_control');await cost(page,'power.2','weight').fill('4');await context.setOffline(true);await solve(page);
  const out=await download(page);expect(out.sensors[1].displacement_body[1]).toBeCloseTo(.01,8);expect(out.operating_values['power.1']).toBeCloseTo(2.5,5);expect(out.operating_values['power.2']).toBeCloseTo(1.25,5);
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);await page.locator('#equilibrium-use').click();await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-count').fill('3');await page.locator('#frequency-spacing').selectOption('linear');await page.locator('#frequency-start').fill('0');await page.locator('#frequency-end').fill('20');await page.locator('#frequency-inputs').selectOption('controls');await solve(page);
  const f=await download(page);expect(f.base.control_allocation.free_directions).toBe(1);expect(f.base.control_allocation.normalized_stationarity).toBeLessThan(2e-6);
  for(const row of f.samples){const d=row.responses[1].output.nodes.at(-1).displacement,w=row.omega,re=500-2*w*w,im=10*w,den=re*re+im*im;expect(d.real[1]).toBeCloseTo(2*re/den,9);expect(d.imag[1]).toBeCloseTo(-2*im/den,9);}
  await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText('WEIGHTED CONTROL TRIM');
});
