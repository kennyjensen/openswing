import {test,expect} from '@playwright/test';
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {portableResult} from '../../web/solution-data.js';

test('source integral-controller trim and saved time launch work offline in the workbench',async({page,context})=>{
  test.setTimeout(180000);
  const modules={},hash=b=>createHash('sha256').update(b).digest('hex');
  for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py'))){
    modules[name]=hash(await readFile('openswing/'+name));
    for(const folder of ['public/kernel','dist/kernel'])expect(hash(await readFile(folder+'/'+name))).toBe(modules[name]);
  }
  const errors=[],requests=[];let offline=false;
  page.on('pageerror',e=>errors.push(e.message));
  context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))requests.push(r.url());});
  const download=async()=>{
    const pending=page.waitForEvent('download');await page.locator('#export-json').click();
    return JSON.parse(await readFile(await(await pending).path(),'utf8'));
  };
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('instrumented-oscillator');
  await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('mounted');
  await page.locator('#structural-equations').selectOption('aswing-airflow');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  const controller={outputs:[{actuator:'E1',terms:[{input:'RY[2]',gain:-200},{input:'RY[2]',gain:-100,mode:'integral'}]}]};
  await page.locator('#feedback-settings').evaluate(e=>e.open=true);
  await page.locator('#feedback-definition').fill(JSON.stringify(controller));
  await page.locator('#feedback-enabled').check();
  await page.locator('#operating-settings').evaluate(e=>e.open=true);
  await page.locator('#add-constraint').click();
  await page.locator('.constraint-variable').selectOption('command.RY[2]');
  await page.locator('.constraint-quantity').selectOption('force.y');
  await page.locator('.constraint-row input').fill('5');
  await context.setOffline(true);offline=true;
  await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged');
  await expect(page.locator('#error')).toBeHidden();
  const trim=await download();
  expect(trim.nodes.at(-1).position[1]).toBeCloseTo(2.01,9);
  expect(trim.operating_values['power.1']).toBeCloseTo(5,8);
  expect(trim.feedback.integrals['RY[2]']).toBeCloseTo(-.05,9);
  expect(trim.feedback.commands['RY[2]']).toBeCloseTo(2.01,9);
  expect(trim.controller.definition).toEqual(controller);
  expect(trim.equilibrium_state.launch.controller).toEqual(controller);
  await page.locator('#project-settings').evaluate(e=>e.open=true);
  await page.locator('#project-solution-name').fill('Integral-control trim');
  await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Computed solution saved.');
  await page.locator('#feedback-definition').fill('{}');
  await page.locator('#project-load-solution').click();
  await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');
  expect(JSON.parse(await page.locator('#feedback-definition').inputValue())).toEqual(controller);
  expect(await download()).toEqual(portableResult(trim));
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);
  await page.locator('#equilibrium-use').click();await page.locator('#mode').selectOption('time');
  await page.locator('#time-settings').evaluate(e=>e.open=true);
  await page.locator('#time-frame').selectOption('prescribed');
  await page.locator('#time-duration').fill('.004');await page.locator('#time-step').fill('.001');
  await page.locator('#time-order').selectOption('2');
  await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time integration converged');
  await expect(page.locator('#error')).toBeHidden();
  const time=await download();
  expect(time.request.action).toBe('launch_time');
  expect(time.initialization.equilibrium_recomputed).toBe(false);
  expect(time.initialization.residual).toBeLessThan(1e-9);
  expect(time.snapshots.at(-1).nodes.at(-1).position[1]).toBeCloseTo(2.01,8);
  expect(time.snapshots.at(-1).feedback.integrals['RY[2]']).toBeCloseTo(-.05,9);
  expect(time.snapshots.at(-1).engines[0].thrust).toBeCloseTo(5,7);
  expect(time.initialization.released_constraints[0].variable).toBe('command.RY[2]');
  expect(errors).toEqual([]);expect(requests).toEqual([]);
  if(process.env.OPENSWING_STEADY_FEEDBACK_EVIDENCE){
    const folder=process.env.OPENSWING_STEADY_FEEDBACK_EVIDENCE;await mkdir(folder,{recursive:true});
    for(const [name,value] of Object.entries({trim,time,report:{status:'PASS_OFFLINE_SOURCE_STEADY_FEEDBACK_UI',modules,errors,requests}}))
      await writeFile(folder+'/browser-'+name+'.json',JSON.stringify(value)+'\n');
  }
});
