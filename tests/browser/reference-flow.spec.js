import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
async function download(page,id='#export-json'){const event=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}
async function prepare(page,example,name){
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption(example);await expect(page.locator('#model-name')).toHaveText(name);
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('mounted');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#gust-settings').evaluate(e=>e.open=true);
  await page.locator('#operating-settings').evaluate(e=>e.open=true);
}
async function gust(page,velocity){await page.locator('#gust-file').setInputFiles({name:'wind.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({type:'uniform',velocity}))});}
async function solve(page){await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});await expect(page.locator('#error')).toBeHidden();}
function vector(speed,a,b){a*=Math.PI/180;b*=Math.PI/180;return [speed*Math.cos(a)*Math.cos(b),-speed*Math.sin(b),speed*Math.sin(a)*Math.cos(b)];}

test('reference airflow preset and local pressure targets solve gust compensation offline',async({page,context})=>{
  test.setTimeout(300000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await prepare(page,'gust-modes','Gust-mode phase demonstrator');
  await page.locator('#speed').fill('20');await page.locator('#alpha').fill('6');await page.locator('#beta').fill('-3');
  await gust(page,[3,-1,2]);await context.setOffline(true);
  await page.locator('#free-flight').click();await expect(page.locator('.constraint-row')).toHaveCount(6);
  await page.locator('#reference-airflow').click();await expect(page.locator('.constraint-row')).toHaveCount(3);
  expect(await page.locator('.constraint-quantity').evaluateAll(es=>es.map(e=>e.value))).toEqual(['reference.speed','reference.alpha','reference.beta']);
  await solve(page);const out=await download(page),desired=vector(20,6,-3),still=desired.map((x,i)=>x-[3,-1,2][i]);
  expect(out.operating_values.speed).toBeCloseTo(Math.hypot(...still),7);
  for(let i=0;i<3;i++){expect(out.reference_flow.relative_velocity_body[i]).toBeCloseTo(desired[i],7);expect(out.force[i]).toBeCloseTo(.5*out.atmosphere.density*.4*20*desired[i],6);}
  expect(out.request.condition.speed).toBe(20);expect(out.reference_flow.speed).toBeCloseTo(20,7);
  expect(out.atmosphere.dynamic_pressure).toBeCloseTo(.5*out.atmosphere.density*out.operating_values.speed**2,7);
  await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText('REFERENCE AIRFLOW · INCLUDES LOCAL GUST');
  await expect(page.locator('#pane-report')).toContainText('Still-atmosphere reference speed');
  await page.locator('#operating-settings').screenshot({path:'test-results/reference-airflow-targets.png'});
  await page.locator('.constraint-quantity').first().selectOption('reference.equivalent_airspeed');
  await expect(page.locator('#export-json')).toBeDisabled();await solve(page);
  const eas=await download(page);expect(eas.reference_flow.equivalent_airspeed).toBeCloseTo(20,7);
  await page.locator('.constraint-quantity').first().selectOption('reference.dynamic_pressure');await page.locator('.constraint-row input').first().fill('200');
  await solve(page);const pressure=await download(page);expect(pressure.reference_flow.dynamic_pressure).toBeCloseTo(200,7);
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  await page.locator('#operating-settings').screenshot({path:'test-results/reference-airflow-mobile.png'});
  await page.locator('.constraint-row input').first().fill('0');await page.locator('#solve').click();
  await expect(page.locator('#error')).toContainText('targets must be positive');await expect(page.locator('#export-json')).toBeDisabled();
  await page.locator('#clear-constraints').click();await gust(page,desired.map(x=>-x));await solve(page);
  const cancelled=await download(page);expect(cancelled.reference_flow.speed).toBeLessThan(1e-12);expect(cancelled.reference_flow.alpha).toBeNull();expect(cancelled.reference_flow.beta).toBeNull();
  await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText('Local alpha [deg] undefined; beta [deg] undefined');
  await page.locator('#reference-airflow').click();await page.locator('#solve').click();
  await expect(page.locator('#error')).toContainText('reference.alpha is undefined');await expect(page.locator('#export-json')).toBeDisabled();expect(errors).toEqual([]);
});

test('saved reference-airflow trim retains solved motion in a loaded Bode base',async({page,context})=>{
  test.setTimeout(300000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await prepare(page,'instrumented-oscillator','Instrumented spring-mass demonstrator');
  await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');await page.locator('#beta').fill('0');await page.locator('#powers input').fill('2');
  await gust(page,[2,1,-.5]);await context.setOffline(true);await page.locator('#reference-airflow').click();await solve(page);
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);const saved=await download(page,'#equilibrium-save');
  expect(saved.positions.at(-1)[1]).toBeCloseTo(2.004,8);await page.locator('#equilibrium-use').click();
  await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-count').fill('3');await page.locator('#frequency-spacing').selectOption('linear');await page.locator('#frequency-start').fill('0');await page.locator('#frequency-end').fill('20');await page.locator('#frequency-inputs').selectOption('controls');
  await solve(page);const out=await download(page);
  expect(out.base.equilibrium_initialization.initialization).toBe('saved physical equilibrium');
  expect(out.base.reference_flow.speed).toBeCloseTo(10,8);expect(out.base.operating_values.speed).toBeCloseTo(Math.sqrt(65.25),7);
  for(const row of out.samples){const d=row.responses[0].output.nodes.at(-1).displacement,w=row.omega,re=500-2*w*w,im=10*w,den=re*re+im*im;expect(d.real[1]).toBeCloseTo(re/den,9);expect(d.imag[1]).toBeCloseTo(-im/den,9);}
  await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText('REFERENCE AIRFLOW · INCLUDES LOCAL GUST');
  expect(errors).toEqual([]);
});
