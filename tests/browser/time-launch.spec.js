import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
async function download(page,id){const event=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}

test('offline saved PI trim launches unchanged, switches forcing after snapshot zero and continues from a checkpoint',async({page,context})=>{
  test.setTimeout(360000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('instrumented-oscillator');await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('mounted');await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#feedback-settings').evaluate(e=>e.open=true);await page.locator('#feedback-demo').click();
  const control=JSON.parse(await page.locator('#feedback-definition').inputValue());control.commands={'RY[2]':2};await page.locator('#feedback-definition').fill(JSON.stringify(control));
  await page.locator('#operating-settings').evaluate(e=>e.open=true);await page.locator('#add-constraint').click();await page.locator('.constraint-variable').selectOption('command.RY[2]');await page.locator('.constraint-quantity').selectOption('force.y');await page.getByLabel('Target value',{exact:true}).fill('5');
  await context.setOffline(true);await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);const seed=await download(page,'#equilibrium-save');expect(seed.feedback.commands['RY[2]']).toBeCloseTo(2.01,8);expect(seed.launch.controller.commands['RY[2]']).toBe(2);
  await page.locator('#equilibrium-use').click();await page.locator('#mode').selectOption('time');await expect(page.locator('#equilibrium-enable')).toBeEnabled();
  await expect(page.locator('#equilibrium-help')).toContainText('without recomputing');
  // These fields belong to a new cold solve and must not alter the saved launch.
  await page.locator('#speed').fill('40');await page.locator('#powers input').fill('9');await page.locator('#feedback-definition').fill('invalid JSON deliberately ignored for a saved launch');
  await page.locator('#time-duration').fill('.04');await page.locator('#time-step').fill('.02');await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:180000});
  const held=await download(page,'#export-json');expect(held.request.action).toBe('launch_time');expect(held.continuation_steps).toBe(0);expect(held.condition.speed).toBe(10);
  for(const s of held.snapshots){expect(s.feedback.actuators.E1).toBeCloseTo(5,7);expect(s.feedback.integrals['RY[2]']).toBeCloseTo(-.05,8);expect(s.feedback.commands['RY[2]']).toBeCloseTo(2.01,8);}
  await page.locator('#forcing-settings').evaluate(e=>e.open=true);await page.locator('#time-forcing').fill('time +RY[2]\n0 .01\n.12 .01');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:180000});const changed=await download(page,'#export-json');
  expect(changed.request.equilibrium_state).toEqual(seed);expect(changed.snapshots[0].feedback).toEqual(held.snapshots[0].feedback);expect(changed.snapshots[0].forcing_values['RY[2]']).toBeCloseTo(2.01,8);
  expect(changed.snapshots[1].feedback.commands['RY[2]']).toBeCloseTo(2.02,8);expect(changed.snapshots[1].feedback.actuators.E1).toBeGreaterThan(5);
  await page.locator('#time-scrub').fill('2');expect(await download(page,'#export-json')).toEqual(changed);
  await page.locator('#time-checkpoint-settings').evaluate(e=>e.open=true);await page.locator('#time-checkpoint-use').click();await page.locator('#time-continue-duration').fill('.02');await page.locator('#time-continue').click();await expect(page.locator('#runtime-status')).toHaveText('Time continuation converged',{timeout:180000});
  const continued=await download(page,'#export-json');expect(continued.snapshots).toHaveLength(4);expect(continued.snapshots[3].order).toBe(2);expect(continued.snapshots[0].restart).toEqual(changed.snapshots[0].restart);
  await page.locator('#equilibrium-settings').screenshot({path:'test-results/time-launch.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();await page.locator('#equilibrium-settings').screenshot({path:'test-results/time-launch-mobile.png'});
  expect(errors).toEqual([]);
});

test('a saved vacuum modal base launches and renders structural time states without invented aerodynamic data',async({page,context})=>{
  test.setTimeout(240000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  const source='Name\nVacuum launch oscillator\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.80665 1.225 340.294\nEnd\nReference\n2 1 2\nEnd\nGround\n1 0 0\nEnd\nWeight\n1 2 0 2 0 19.6133\nEnd\nBeam 1\nAxial spring\nt y EA tdeps\n0 0 1000 .02\n2 2 1000 .02\nEnd\n';
  await page.locator('#file').setInputFiles({name:'vacuum.asw',mimeType:'text/plain',buffer:Buffer.from(source)});await expect(page.locator('#model-name')).toHaveText('Vacuum launch oscillator');
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-vacuum').check();await page.locator('#modal-count').fill('2');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await context.setOffline(true);await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);await page.locator('#equilibrium-use').click();await page.locator('#mode').selectOption('time');await page.locator('#time-duration').fill('.02');await page.locator('#time-step').fill('.01');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:120000});await expect(page.locator('#cl')).toHaveText('—');await expect(page.locator('#pane-report')).toContainText('STRUCTURAL TIME RESPONSE');
  const out=await download(page,'#export-json');expect(out.condition).toBeNull();expect(out.snapshots).toHaveLength(3);expect(out.snapshots[0].gravity_body).toEqual([0,0,0]);expect(out.restart_context.setup.gravity_magnitude).toBe(0);
  await page.locator('#time-quantity').selectOption('max_displacement');await expect(page.locator('#time-plot svg')).toBeVisible();await page.locator('#time-scrub').fill('2');await page.locator('#time-view').selectOption('earth');expect(await download(page,'#export-json')).toEqual(out);expect(errors).toEqual([]);
});
