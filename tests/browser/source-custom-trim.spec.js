import {test,expect} from '@playwright/test';
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {portableResult} from '../../web/solution-data.js';

test('source strain trim, redundant controls, project restore and time launch work offline',async({page,context})=>{
  test.setTimeout(240000);
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
  const line='1 0 1 2 0 2 0 0 1 0 1 0 -1 0 0';
  const source=(await readFile('examples/instrumented-oscillator.asw','utf8'))
    .replace(line,line+'\n2 0 1 2 0 2 0 0 1 0 2 0 -1 0 0')
    .replace('0 0 1000 .02\n2 2 1000 .02','0 0 1000 0\n2 2 2000 0');
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles({name:'source-custom.asw',mimeType:'text/plain',buffer:Buffer.from(source)});
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
  await page.locator('#operating-settings').evaluate(e=>e.open=true);
  await page.locator('#add-constraint').click();
  await page.locator('.constraint-variable').selectOption('power.1');
  await page.locator('.constraint-quantity').selectOption('user');
  await page.locator('.constraint-row input').fill('.005');
  await page.getByLabel('Use a sensor measurement',{exact:true}).selectOption('2.strain.s');
  await page.locator('[data-custom="residual_scale"]').fill('.01');
  await page.locator('#add-constraint').click();
  await page.locator('.constraint-variable').last().selectOption('power.2');
  await page.locator('.constraint-quantity').last().selectOption('minimum_control');
  await page.locator('.allocation-control[data-variable="power.2"] input[data-cost="weight"]').fill('4');
  await context.setOffline(true);offline=true;
  await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged');
  await expect(page.locator('#error')).toBeHidden();
  const trim=await download();
  expect(trim.operating_values['power.1']).toBeCloseTo(5,5);
  expect(trim.operating_values['power.2']).toBeCloseTo(2.5,5);
  expect(trim.sensors[1].strain[1]).toBeCloseTo(.005,9);
  expect(trim.sensors[1].strain_sample_t).toBe(2);
  expect(trim.operating_constraints[0].actual).toBeCloseTo(trim.sensors[1].strain[1],11);
  expect(trim.support_force[1]).toBeCloseTo(-10,7);
  expect(trim.control_allocation.equality_residual).toBeLessThan(1e-8);
  expect(trim.control_allocation.normalized_stationarity).toBeLessThan(2e-6);
  await page.locator('#project-settings').evaluate(e=>e.open=true);
  await page.locator('#project-solution-name').fill('Source custom allocation');
  await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Computed solution saved.');
  await page.locator('[data-custom="expression"]').fill('0');
  await page.locator('#project-load-solution').click();
  await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');
  expect(await download()).toEqual(portableResult(trim));
  await expect(page.locator('[data-custom="expression"]')).toHaveValue('sensor("2.strain.s")');
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);
  await page.locator('#equilibrium-use').click();await page.locator('#mode').selectOption('time');
  await page.locator('#time-settings').evaluate(e=>e.open=true);
  await page.locator('#time-frame').selectOption('prescribed');
  await page.locator('#time-duration').fill('.002');await page.locator('#time-step').fill('.002');
  await page.locator('#time-order').selectOption('2');await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time integration converged');
  await expect(page.locator('#error')).toBeHidden();
  const time=await download();
  expect(time.initialization.equilibrium_recomputed).toBe(false);
  expect(time.initialization.residual).toBeLessThan(1e-8);
  expect(time.initialization.released_constraints.map(c=>c.quantity)).toEqual(trim.equilibrium_state.launch.released_constraints.map(c=>c.quantity));
  expect(time.snapshots.at(-1).nodes.at(-1).position[1]).toBeCloseTo(trim.nodes.at(-1).position[1],8);
  expect(time.snapshots.at(-1).sensors[1].strain[1]).toBeCloseTo(.005,8);
  expect(errors).toEqual([]);expect(requests).toEqual([]);
  if(process.env.OPENSWING_CUSTOM_TRIM_EVIDENCE){
    const folder=process.env.OPENSWING_CUSTOM_TRIM_EVIDENCE;await mkdir(folder,{recursive:true});
    for(const [name,value] of Object.entries({trim,time,report:{status:'PASS_OFFLINE_SOURCE_CUSTOM_TRIM_UI',modules,errors,requests}}))
      await writeFile(folder+'/browser-'+name+'.json',JSON.stringify(value)+'\n');
  }
});
