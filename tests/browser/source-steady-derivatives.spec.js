import {test,expect} from '@playwright/test';
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {portableResult} from '../../web/solution-data.js';

test('source controller derivatives export and restore offline with source section metadata',async({page,context})=>{
  test.setTimeout(180000);
  const modules={},hash=b=>createHash('sha256').update(b).digest('hex');
  for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py'))){
    modules[name]=hash(await readFile('openswing/'+name));
    for(const folder of ['public/kernel','dist/kernel'])expect(hash(await readFile(folder+'/'+name))).toBe(modules[name]);
  }
  const errors=[],requests=[];let offline=false;
  page.on('pageerror',e=>errors.push(e.message));
  context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))requests.push(r.url());});
  const download=async(id='#export-json')=>{
    const pending=page.waitForEvent('download');await page.locator(id).click();
    return readFile(await(await pending).path(),'utf8');
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
  const controller={commands:{'RY[2]':2.01},outputs:[{actuator:'E1',terms:[
    {input:'RY[2]',gain:-200},{input:'RY[2]',gain:-100,mode:'integral'}]}]};
  await page.locator('#feedback-settings').evaluate(e=>e.open=true);
  await page.locator('#feedback-definition').fill(JSON.stringify(controller));await page.locator('#feedback-enabled').check();
  await page.locator('#derivative-settings').evaluate(e=>e.open=true);await page.locator('#derivatives-enable').check();
  for(const input of await page.locator('#derivative-parameters input').all())
    await input.setChecked(['command.E1','command.RY[2]'].includes(await input.inputValue()));
  await context.setOffline(true);offline=true;await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:120000});
  await expect(page.locator('#error')).toBeHidden();
  const trim=JSON.parse(await download()),d=trim.derivatives;
  const row=name=>d.matrices.feedback[d.feedback_rows.findIndex(r=>r.name===name)];
  expect(d.parameters.map(p=>p.name)).toEqual(['command.E1','command.RY[2]']);
  expect(d.matrices.positions.at(-1)[1][0]).toBeCloseTo(0,8);
  expect(d.matrices.positions.at(-1)[1][1]).toBeCloseTo(1,8);
  expect(row('actuators.E1')[0]).toBeCloseTo(0,7);expect(row('actuators.E1')[1]).toBeCloseTo(500,5);
  expect(row('integrals.RY[2]')[0]).toBeCloseTo(.01,7);expect(row('integrals.RY[2]')[1]).toBeCloseTo(-5,6);
  expect(d.section_output_fields.section_strain.sample_location).toBe('element constitutive average');
  expect(Math.max(...d.linear_residuals)).toBeLessThan(1e-9);
  await page.locator('#tab-derivatives').click();await page.locator('#derivative-matrix').selectOption('feedback');
  await expect(page.locator('#derivative-table')).toContainText('integrals.RY[2]');
  await expect(page.locator('#derivative-plot svg')).toBeVisible();
  const csv=await download('#derivative-csv');expect(csv).toContain('command.E1 / file engine setting');
  expect(csv).toContain('integrals.RY[2] [input L · input T]');
  await page.locator('#derivative-field').selectOption('section_strain.1');
  await page.locator('#derivative-column').selectOption('1');
  await expect(page.locator('#derivative-plot-note')).toContainText('element constitutive average');
  await expect(page.locator('#derivative-plot-note')).toContainText('nonorthogonal');
  const sectionCSV=await download('#derivative-structure-csv');
  expect(sectionCSV).toContain('"element constitutive average"');expect(sectionCSV).not.toContain('material midpoint');
  for(const section of d.matrices.section_strain){expect(section[1][0]).toBeCloseTo(0,8);expect(section[1][1]).toBeCloseTo(.5,8);}
  await page.locator('#project-settings').evaluate(e=>e.open=true);
  await page.locator('#project-solution-name').fill('Source derivatives');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Computed solution saved.');
  await page.locator('#derivatives-enable').uncheck();await page.locator('#project-load-solution').click();
  await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');
  await expect(page.locator('#derivatives-enable')).toBeChecked();
  expect(JSON.parse(await download())).toEqual(portableResult(trim));
  expect(errors).toEqual([]);expect(requests).toEqual([]);
  if(process.env.OPENSWING_STEADY_DERIVATIVES_EVIDENCE){
    const folder=process.env.OPENSWING_STEADY_DERIVATIVES_EVIDENCE;await mkdir(folder,{recursive:true});
    for(const [name,value] of Object.entries({trim,report:{status:'PASS_OFFLINE_SOURCE_STEADY_DERIVATIVES_UI',modules,errors,requests}}))
      await writeFile(folder+'/browser-'+name+'.json',JSON.stringify(value)+'\n');
    await writeFile(folder+'/browser-feedback.csv',csv);
    await writeFile(folder+'/browser-sections.csv',sectionCSV);
  }
});
