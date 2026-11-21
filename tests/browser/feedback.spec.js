import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
async function setup(page){
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('instrumented-oscillator');
  await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#mode').selectOption('time');
  await page.locator('#feedback-settings').evaluate(e=>e.open=true);
}
async function exported(page){
  const event=page.waitForEvent('download');await page.locator('#export-json').click();
  return JSON.parse(await readFile(await(await event).path(),'utf8'));
}

test('PI command tracking runs offline and exports actual actuator and integral histories',async({page,context})=>{
  test.setTimeout(240000);const errors=[];page.on('pageerror',e=>errors.push(e.message));await setup(page);
  await page.locator('#feedback-demo').click();await page.locator('#time-duration').fill('0.06');await page.locator('#time-step').fill('0.02');
  await page.locator('#forcing-settings').evaluate(e=>e.open=true);
  await page.locator('#time-forcing').fill('time +RY[2]\n0 0\n.02 .01\n.06 .01');
  await context.setOffline(true);await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:180000});
  const out=await exported(page);expect(out.controller.integral_channels).toEqual(['RY[2]']);
  expect(out.snapshots.at(-1).feedback.integrals['RY[2]']).toBeLessThan(0);
  expect(out.snapshots.at(-1).feedback.actuators.E1).toBeGreaterThan(1);
  await page.locator('#time-quantity').selectOption('feedback.integrals.RY[2]');
  await expect(page.locator('#time-plot svg')).toBeVisible();
  await page.locator('#time-scrub').fill(String(out.snapshots.length-1));
  await page.locator('#tab-feedback').click();await expect(page.locator('#feedback-table')).toContainText('integrals · RY[2]');
  let event=page.waitForEvent('download');await page.locator('#feedback-csv').click();
  const csv=await readFile(await(await event).path(),'utf8');expect(csv).toContain('integrals_RY[2]');expect(csv).toContain('input L · input T');
  event=page.waitForEvent('download');await page.locator('#feedback-save').click();
  expect(JSON.parse(await readFile(await(await event).path(),'utf8'))).toEqual(out.controller.definition);
  await page.locator('#pane-feedback').screenshot({path:'test-results/feedback-time.png'});
  await page.locator('#feedback-enabled').uncheck();await expect(page.locator('#feedback-csv')).toBeDisabled();
  expect(errors).toEqual([]);
});

test('.con bindings drive closed-loop modes and command Bode response with immutable exports',async({page})=>{
  test.setTimeout(300000);const errors=[];page.on('pageerror',e=>errors.push(e.message));await setup(page);
  const con='1 7 2 -1\n1 1\n0\n0\n200\n1 8 2 -1\n1 1\n0\n0\n20\n1 9 2 -1\n1 1\n0\n0\n100\n';
  const bindings={outputs:{1:{actuator:'E1'}},inputs:{'2:7':{input:'RY[2]'},'2:8':{input:'UY[2]'},'2:9':{input:'RY[2]',mode:'integral'}}};
  await page.locator('#feedback-definition').fill(JSON.stringify({bindings}));
  await page.locator('#feedback-file').setInputFiles({name:'original.con',mimeType:'text/plain',buffer:Buffer.from(con)});
  await expect(page.locator('#feedback-enabled')).toBeChecked();
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-count').fill('3');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  const modes=await exported(page);expect(modes.controller.definition.con).toBe(con);
  expect(modes.modes).toHaveLength(3);expect(modes.modes.every(m=>m.eigenvalue[0]<0)).toBeTruthy();
  await page.locator('#tab-feedback').click();await expect(page.locator('#feedback-summary')).toContainText('per saved right eigenvector');
  await expect(page.locator('#feedback-table thead')).toContainText('Imaginary');
  await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-inputs').selectOption('controls');
  await page.locator('#frequency-spacing').selectOption('linear');await page.locator('#frequency-start').fill('0');
  await page.locator('#frequency-end').fill('10');await page.locator('#frequency-count').fill('3');await page.locator('#feedback-harmonic').fill('RY[2]');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  const bode=await exported(page);expect(bode.inputs).toHaveLength(2);
  expect(bode.samples[0].responses[1].output.sensors[1].displacement_body.real[1]).toBeCloseTo(1,7);
  await page.locator('#frequency-input').selectOption('1');await page.locator('#frequency-group').selectOption('feedback');
  await page.locator('#frequency-quantity').selectOption({label:'integrals RY[2] [input L · input T]'});
  await expect(page.locator('#frequency-gain-plot svg')).toBeVisible();
  await page.locator('#tab-feedback').click();await expect(page.locator('#feedback-summary')).toContainText('per unit input L');
  await page.locator('#frequency-phase').fill('90');await page.locator('#frequency-amplitude').fill('0.01');expect(await exported(page)).toEqual(bode);
  await page.locator('#pane-feedback').screenshot({path:'test-results/feedback-bode.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  expect(errors).toEqual([]);
});

test('steady PI trim solves a measurement command and preserves it in the modal base offline',async({page,context})=>{
  test.setTimeout(300000);const errors=[];page.on('pageerror',e=>errors.push(e.message));await setup(page);
  await page.locator('#mode').selectOption('mounted');await expect(page.locator('#feedback-settings')).toBeVisible();
  await page.locator('#feedback-demo').click();
  const law=JSON.parse(await page.locator('#feedback-definition').inputValue());law.commands={'RY[2]':2.01};
  await page.locator('#feedback-definition').fill(JSON.stringify(law));
  await context.setOffline(true);await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  let out=await exported(page);expect(out.feedback.actuators.E1).toBeCloseTo(5,6);
  expect(out.feedback.integrals['RY[2]']).toBeCloseTo(-.05,7);
  await page.locator('#tab-feedback').click();await expect(page.locator('#feedback-summary')).toContainText('Steady controller equilibrium');
  await expect(page.locator('#feedback-table')).toContainText('input L · input T');
  await page.locator('#operating-settings').evaluate(e=>e.open=true);await page.locator('#add-constraint').click();
  await page.locator('.constraint-variable').selectOption('command.RY[2]');
  await page.locator('.constraint-quantity').selectOption('force.y');await page.getByLabel('Target value',{exact:true}).fill('2');
  await expect(page.locator('#feedback-csv')).toBeDisabled();await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  out=await exported(page);expect(out.feedback.commands['RY[2]']).toBeCloseTo(2.004,7);
  expect(out.controller.commands['RY[2]']).toBeCloseTo(2.004,7);
  expect(out.feedback.actuators.E1).toBeCloseTo(2,6);expect(out.feedback.integrals['RY[2]']).toBeCloseTo(-.02,7);
  expect(out.operating_constraints[0].actual).toBeCloseTo(2,6);
  await page.locator('#tab-feedback').click();const event=page.waitForEvent('download');await page.locator('#feedback-csv').click();
  const csv=await readFile(await(await event).path(),'utf8');expect(csv).toContain('Steady controller equilibrium');expect(csv).toContain('commands_RY[2]');
  await page.locator('#pane-feedback').screenshot({path:'test-results/feedback-steady.png'});
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-count').fill('3');await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  out=await exported(page);expect(out.controller.commands['RY[2]']).toBeCloseTo(2.004,7);
  expect(out.base.feedback.actuators.E1).toBeCloseTo(2,6);expect(out.base.steady_trim.operating_constraints[0].actual).toBeCloseTo(2,6);
  await expect(page.locator('#pane-report')).toContainText('CLOSED-LOOP BASE TRIM');
  expect(out.modes).toHaveLength(3);expect(out.modes.every(m=>m.eigenvalue[0]<0)).toBeTruthy();
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  expect(errors).toEqual([]);
});

test('custom actuator lag runs offline with state histories, modes and complex rate exports',async({page,context})=>{
  test.setTimeout(360000);const errors=[];page.on('pageerror',e=>errors.push(e.message));await setup(page);
  await page.locator('#feedback-lag-demo').click();await page.locator('#time-duration').fill('.04');await page.locator('#time-step').fill('.02');
  await page.locator('#forcing-settings').evaluate(e=>e.open=true);await page.locator('#time-forcing').fill('time +RY[2]\n0 0\n.02 0\n.02 .01\n.04 .01');
  await context.setOffline(true);await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:180000});
  let out=await exported(page);expect(out.controller.state_channels).toEqual(['lag']);
  expect(out.snapshots[0].feedback.states.lag).toBe(0);expect(out.snapshots.at(-1).feedback.states.lag).toBeGreaterThan(0);
  await page.locator('#time-quantity').selectOption('feedback.states.lag');await expect(page.locator('#time-plot svg')).toBeVisible();
  await page.locator('#time-scrub').fill(String(out.snapshots.length-1));await page.locator('#tab-feedback').click();
  await expect(page.locator('#feedback-table')).toContainText('state rates');
  await expect(page.locator('#feedback-table')).toContainText('file engine setting / input T');
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-count').fill('3');await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  out=await exported(page);expect(out.modes).toHaveLength(3);expect(out.modes.every(m=>m.eigenvalue[0]<0)).toBeTruthy();
  expect(out.diagnostics.state_layout.feedback.states).toEqual(['lag']);expect(out.modes[0].output.feedback.states_lag).toHaveProperty('imag');
  await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-inputs').selectOption('controls');
  await page.locator('#frequency-spacing').selectOption('linear');await page.locator('#frequency-start').fill('0');await page.locator('#frequency-end').fill('10');
  await page.locator('#frequency-count').fill('2');await page.locator('#feedback-harmonic').fill('RY[2]');await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  out=await exported(page);expect(out.samples[0].responses[1].output.feedback.states_lag.real).toBeCloseTo(500*200/700,5);
  await page.locator('#frequency-input').selectOption('1');await page.locator('#frequency-group').selectOption('feedback');
  await page.locator('#frequency-quantity').selectOption({label:'state rates lag [file engine setting / input T]'});
  await expect(page.locator('#frequency-gain-plot svg')).toBeVisible();await page.locator('#tab-feedback').click();
  const event=page.waitForEvent('download');await page.locator('#feedback-csv').click();const csv=await readFile(await(await event).path(),'utf8');
  expect(csv).toContain('state_rates_lag');expect(csv).toContain('file engine setting / input T');
  await page.locator('#pane-feedback').screenshot({path:'test-results/custom-controller-bode.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  expect(errors).toEqual([]);
});

test('imported nonlinear anti-windup controller solves saturation and retains state units',async({page,context})=>{
  test.setTimeout(180000);await setup(page);await page.locator('#mode').selectOption('mounted');
  const law=JSON.parse(await readFile('examples/antiwindup-controller.json','utf8'));law.commands={'RY[2]':2.02};
  await page.locator('#feedback-file').setInputFiles({name:'antiwindup.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(law))});
  await page.locator('#operating-settings').evaluate(e=>e.open=true);await page.locator('#add-constraint').click();
  await expect(page.locator('.constraint-variable option[value="command.RY[2]"]')).toHaveText('Command RY[2]');
  await page.locator('#clear-constraints').click();await context.setOffline(true);await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  const out=await exported(page);expect(out.feedback.actuators.E1).toBeCloseTo(5,5);expect(out.feedback.states.I).toBeCloseTo(-.031,6);
  await page.locator('#tab-feedback').click();await expect(page.locator('#feedback-table')).toContainText('input L · input T');
  await page.locator('#pane-feedback').screenshot({path:'test-results/custom-controller-steady.png'});
});
