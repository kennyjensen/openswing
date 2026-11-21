import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import {parseProject} from '../../web/project-data.js';
import {verifySolution} from '../../web/solution-data.js';

const directory='artifacts/isae/source-airflow-feedback-20261031';
async function exported(page,id='#export-json'){
  const promise=page.waitForEvent('download');await page.locator(id).click();
  return JSON.parse(await readFile(await(await promise).path(),'utf8'));
}
async function finish(page,label){
  await expect(page.locator('#runtime-status')).toHaveText(new RegExp(`^(${label}|Analysis stopped|Frequency refinement stopped|Time continuation stopped)$`),{timeout:300000});
  if(await page.locator('#error').isVisible())throw new Error(await page.locator('#error').innerText());
  await expect(page.locator('#runtime-status')).toHaveText(label);
}
function close(a,b){
  if(Array.isArray(b)){expect(a).toHaveLength(b.length);b.forEach((v,i)=>close(a[i],v));}
  else expect(Math.abs(a-b)).toBeLessThanOrEqual(3e-9+3e-7*Math.abs(b));
}

test('source feedback runs offline, reuses matrices and survives saved time and project round trips',async({page,context})=>{
  test.setTimeout(900000);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  const request=JSON.parse(await readFile(`${directory}/frequency-free-request.json`,'utf8'));
  const native=JSON.parse(await readFile(`${directory}/frequency-free-native.json`,'utf8'));
  const controller=request.frequency.controller;
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles(`${directory}/source.asw`);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('frequency');await page.locator('#tab-nodes').click();
  await page.locator('#node-spacing').selectOption('uniform');await page.locator('#node-count').fill('4');
  await page.locator('#node-apply').click();await expect(page.locator('#node-status')).toContainText('5 nodes');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#density-mode').selectOption('custom');await page.locator('#density').fill('1.2');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#speed').fill('23');await page.locator('#alpha').fill('0');await page.locator('#beta').fill('0');
  await page.locator('#stall').uncheck();await page.locator('#aero-lag').check();
  await page.locator('#frequency-frame').selectOption('free');await page.locator('#frequency-inputs').selectOption('controls');
  await page.locator('#feedback-settings').evaluate(e=>e.open=true);
  await page.locator('#feedback-definition').fill(JSON.stringify(controller));await page.locator('#feedback-enabled').check();
  await page.locator('#structural-equations').selectOption('aswing-airflow');await expect(page.locator('#solve')).toBeEnabled();
  await expect(page.locator('#feedback-settings')).toBeVisible();await expect(page.locator('#feedback-enabled')).toBeChecked();
  await page.locator('#powers [data-power="1"]').fill('0');
  await page.locator('#frequency-start').fill('3');await page.locator('#frequency-end').fill('10');
  await page.locator('#frequency-count').fill('2');await page.locator('#frequency-spacing').selectOption('linear');
  await context.setOffline(true);await page.locator('#solve').click();await finish(page,'Analysis converged');
  const first=await exported(page);expect(first.controller.definition).toEqual(controller);
  await page.locator('#frequency-refinement').evaluate(e=>e.open=true);
  await page.locator('#frequency-add-values').fill('5');await page.locator('#frequency-add-list').click();await finish(page,'Frequency refinement complete');
  const frequency=await exported(page);expect(frequency.frequency_refinement.linearization_reused).toBe(true);
  for(const old of first.samples)expect(frequency.samples.find(row=>row.omega===old.omega)).toEqual(old);
  for(const row of frequency.samples){
    const reference=native.samples.find(r=>Math.abs(r.omega-row.omega)<1e-10);expect(reference).toBeTruthy();
    for(const part of ['real','imag']){
      close(row.responses[0].output.sensors[0].displacement_body[part],reference.responses[0].output.sensors[0].displacement_body[part]);
      close(row.responses[0].output.feedback.actuators_E1[part],reference.responses[0].output.feedback.actuators_E1[part]);
    }
  }
  await page.locator('#project-settings').evaluate(e=>e.open=true);
  await page.locator('#project-solution-name').fill('Source feedback frequency');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Saved');
  await page.locator('#mode').selectOption('time');await page.locator('#time-frame').selectOption('free');
  await page.locator('#time-duration').fill('.02');await page.locator('#time-step').fill('.005');await page.locator('#time-order').selectOption('2');
  await page.locator('#forcing-settings').evaluate(e=>e.open=true);
  await page.locator('#time-forcing').fill('time +E1\n0 0\n.01 0\n.01 1\n.2 1\n');
  await page.locator('#solve').click();await finish(page,'Time integration converged');
  const initialTime=await exported(page);expect(initialTime.controller.definition).toEqual(controller);
  await page.locator('#time-scrub').evaluate((e,i)=>{e.value=i;e.dispatchEvent(new Event('input',{bubbles:true}));},initialTime.snapshots.length-1);
  await page.locator('#time-checkpoint-settings').evaluate(e=>e.open=true);await page.locator('#time-checkpoint-use').click();
  await page.locator('#time-continue-duration').fill('.02');await page.locator('#time-continue-step').fill('.005');await page.locator('#time-continue-order').selectOption('2');
  await page.locator('#time-continue').click();await finish(page,'Time continuation converged');
  const time=await exported(page),transient=JSON.parse(await readFile(`${directory}/time-free-native.json`,'utf8'));
  expect(time.restart_context.setup.controller).toEqual(controller);expect(time.snapshots.at(-1).time).toBeCloseTo(.04,12);
  close(time.snapshots.at(-1).nodes.at(-1).position,transient.snapshots.at(-1).nodes.at(-1).position);
  close(time.snapshots.at(-1).feedback.actuators.E1,transient.snapshots.at(-1).feedback.actuators.E1);
  await page.locator('#project-solution-name').fill('Source feedback time');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Saved');
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-frame').selectOption('free');
  await page.locator('#modal-count').fill('1');await page.locator('#modal-method').selectOption('full_shift_invert');
  await page.locator('#modal-shift-real').fill('-1.6');await page.locator('#modal-shift-imag').fill('10');
  await page.locator('#solve').click();await finish(page,'Analysis converged');
  const modes=await exported(page),modal=JSON.parse(await readFile(`${directory}/mode-free-native.json`,'utf8'));
  close(modes.modes[0].eigenvalue,modal.modes[0].eigenvalue);expect(modes.controller.definition).toEqual(controller);
  await page.locator('#project-solution-name').fill('Source feedback modes');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Saved');
  const project=parseProject(JSON.stringify(await exported(page,'#project-export')));
  expect(project.solutions).toHaveLength(3);for(const solution of project.solutions)await verifySolution(solution);
  await context.setOffline(false);await page.reload();await expect(page.locator('#solve')).toBeEnabled();await context.setOffline(true);
  await page.locator('#project-file').setInputFiles({name:'feedback-source.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});
  await page.locator('#project-settings').evaluate(e=>e.open=true);
  for(const solution of project.solutions){
    await page.locator('#project-solutions').selectOption(solution.id);await page.locator('#project-load-solution').click();
    await expect(page.locator('#project-status')).toContainText(`Opened ${solution.name}.`);
    await expect(page.locator('#structural-equations')).toHaveValue('aswing-airflow');await expect(page.locator('#feedback-enabled')).toBeChecked();
    const restored=await exported(page);expect(restored.controller.definition).toEqual(controller);
    expect(restored[solution.kind==='frequency'?'samples':solution.kind==='time'?'snapshots':'modes']).toEqual(solution.data[solution.kind==='frequency'?'samples':solution.kind==='time'?'snapshots':'modes']);
  }
  await page.setViewportSize({width:390,height:844});await page.locator('[data-workspace="plots"]').click();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.screenshot({path:`${directory}/browser-mobile.png`,fullPage:true});expect(errors).toEqual([]);
  await writeFile(`${directory}/browser.json`,JSON.stringify({status:'PASS',errors,frequency,initialTime,time,modes,project})+'\n');
});
