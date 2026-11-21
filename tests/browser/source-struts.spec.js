import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import {parseProject} from '../../web/project-data.js';
import {verifySolution} from '../../web/solution-data.js';

const directory='artifacts/isae/source-struts-20261030';
async function exported(page,id='#export-json'){
  const download=page.waitForEvent('download');await page.locator(id).click();
  return JSON.parse(await readFile(await(await download).path(),'utf8'));
}
async function finish(page,label){
  await expect(page.locator('#runtime-status')).toHaveText(new RegExp(`^(${label}|Analysis stopped|Frequency refinement stopped|Time continuation stopped)$`),{timeout:300000});
  if(await page.locator('#error').isVisible())throw new Error(await page.locator('#error').innerText());
  await expect(page.locator('#runtime-status')).toHaveText(label);
}
function close(actual,expected){
  if(Array.isArray(expected)){
    expect(actual).toHaveLength(expected.length);expected.forEach((value,index)=>close(actual[index],value));
  }else expect(Math.abs(actual-expected)).toBeLessThanOrEqual(3e-9+3e-7*Math.abs(expected));
}

test('braced source dynamics run offline with reuse, continuation and saved solutions',async({page,context})=>{
  test.setTimeout(900000);page.setDefaultTimeout(30000);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  const native=JSON.parse(await readFile(`${directory}/frequency-free-native.json`,'utf8'));
  const transient=JSON.parse(await readFile(`${directory}/time-native.json`,'utf8'));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles(`${directory}/source.asw`);
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('frequency');
  await page.locator('#tab-nodes').click();
  await page.locator('#node-spacing').selectOption('uniform');await page.locator('#node-count').fill('4');
  await page.locator('#node-apply').click();await expect(page.locator('#node-status')).toContainText('5 nodes');
  await page.locator('#atmosphere-settings').evaluate(el=>el.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#density-mode').selectOption('custom');await page.locator('#density').fill('1.2');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#speed').fill('23');await page.locator('#alpha').fill('0');await page.locator('#beta').fill('0');
  await page.locator('#stall').uncheck();await page.locator('#aero-lag').check();
  await page.locator('#frequency-frame').selectOption('free');await page.locator('#frequency-inputs').selectOption('controls');
  await page.locator('#structural-equations').selectOption('aswing-airflow');await expect(page.locator('#solve')).toBeEnabled();
  await expect(page.locator('#powers [data-power="1"]')).toBeVisible();
  await page.locator('#powers [data-power="1"]').fill('0');
  await expect(page.locator('#feedback-settings')).toBeHidden();
  await page.locator('#frequency-start').fill('1');await page.locator('#frequency-end').fill('15');await page.locator('#frequency-count').fill('2');
  await page.locator('#frequency-spacing').selectOption('linear');
  await page.locator('#strut-mode').selectOption('wire');
  await context.setOffline(true);
  await page.locator('#solve').click();await finish(page,'Analysis converged');
  const first=await exported(page);
  await page.locator('#frequency-refinement').evaluate(el=>el.open=true);
  await page.locator('#frequency-add-values').fill('4, 8');await page.locator('#frequency-add-list').click();
  await finish(page,'Frequency refinement complete');
  const frequency=await exported(page);
  expect(frequency.structural_operator).toBe('drela-moving-airflow-v1');expect(frequency.vacuum).toBe(false);
  expect(frequency.frequency_refinement.linearization_reused).toBe(true);
  for(const old of first.samples)expect(frequency.samples.find(row=>row.omega===old.omega)).toEqual(old);
  expect(frequency.samples).toHaveLength(4);
  expect(frequency.base.strut_mode).toBe('wire');
  expect(frequency.base.struts[0].slack).toBe(false);
  for(const row of frequency.samples){
    const reference=native.samples.find(sample=>Math.abs(sample.omega-row.omega)<1e-10);expect(reference).toBeTruthy();
    const actual=row.responses[0].output,expected=reference.responses[0].output;
    for(const key of ['CL','CD','Cm','force','moment'])for(const part of ['real','imag'])close(actual.global[key][part],expected.global[key][part]);
    actual.nodes.forEach((node,index)=>{for(const key of ['displacement','velocity'])for(const part of ['real','imag'])close(node[key][part],expected.nodes[index][key][part]);});
    close(actual.nodes.at(-1).displacement.real[1],1/(750-3*row.omega**2));
  }
  console.log('Powered frequency response and reused matrices match exact spring dynamics.');
  await page.locator('#project-settings').evaluate(el=>el.open=true);
  await page.locator('#project-solution-name').fill('Powered source frequency');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Saved');
  await page.locator('#mode').selectOption('time');
  await expect(page.locator('#structural-equations')).toHaveValue('aswing-airflow');
  await page.locator('#time-frame').selectOption('free');
  await page.locator('#time-duration').fill('.04');await page.locator('#time-step').fill('.0025');await page.locator('#time-order').selectOption('2');
  await page.locator('#forcing-settings').evaluate(el=>el.open=true);
  await page.locator('#time-forcing').fill('time +E1\n0 0\n.01 0\n.01 1\n.2 1\n');
  await page.locator('#solve').click();await finish(page,'Time integration converged');
  let time=await exported(page);const initialTime=time;
  expect(time.structural_operator).toBe('drela-moving-airflow-v1');expect(time.temporal_policy).toBe('drela-euler-bdf-v1');
  expect(time.snapshots.at(-1).time).toBe(.04);
  await page.locator('#time-scrub').evaluate((el,index)=>{el.value=index;el.dispatchEvent(new Event('input',{bubbles:true}));},time.snapshots.length-1);
  await page.locator('#time-checkpoint-settings').evaluate(el=>el.open=true);
  await page.locator('#time-checkpoint-use').click();await page.locator('#time-continue-duration').fill('.04');
  await page.locator('#time-continue-step').fill('.0025');await page.locator('#time-continue-order').selectOption('2');
  await page.locator('#time-continue').click();await finish(page,'Time continuation converged');
  time=await exported(page);expect(time.snapshots.at(-1).time).toBeCloseTo(.08,12);
  expect(time.snapshots.slice(0,initialTime.snapshots.length)).toEqual(
    initialTime.snapshots.map(row=>({...row,restart_context:row.restart_context??initialTime.restart_context})));
  const last=time.snapshots.at(-1),reference=transient.snapshots.at(-1);
  for(const key of ['force','moment','local_velocity','local_rates','circulation_rate'])close(last[key],reference[key]);
  for(const key of ['position','axes','force','moment','axial_velocity','thrust','torque'])close(last.engines[0][key],reference.engines[0][key]);
  last.nodes.forEach((node,index)=>close(node.position,reference.nodes[index].position));
  expect(time.snapshots.every(row=>row.residual<1e-8)).toBe(true);
  console.log('Power-step response and checkpoint continuation match the native uninterrupted history.');
  await page.locator('#project-solution-name').fill('Powered source time');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Saved');
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-frame').selectOption('free');
  await page.locator('#modal-count').fill('1');await page.locator('#modal-method').selectOption('full_shift_invert');
  await page.locator('#modal-shift-real').fill('-.1');await page.locator('#modal-shift-imag').fill(String(Math.sqrt(250)));
  await page.locator('#solve').click();await finish(page,'Analysis converged');
  const modes=await exported(page),modeReference=JSON.parse(await readFile(`${directory}/mode-native.json`,'utf8'));
  expect(modes.modes).toHaveLength(1);close(modes.modes[0].eigenvalue,modeReference.modes[0].eigenvalue);
  close(modes.modes[0].eigenvalue,[0,Math.sqrt(250)]);
  await page.locator('#project-solution-name').fill('Powered source modes');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Saved');
  const project=parseProject(JSON.stringify(await exported(page,'#project-export')));
  for(const solution of project.solutions){
    await verifySolution(solution);expect(solution.configuration.fields['strut-mode']).toBe('wire');
  }
  await context.setOffline(false);await page.reload();await expect(page.locator('#solve')).toBeEnabled();await context.setOffline(true);
  await page.locator('#project-file').setInputFiles({name:'powered-source.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});
  await page.locator('#project-settings').evaluate(el=>el.open=true);
  for(const solution of project.solutions){
    await page.locator('#project-solutions').selectOption(solution.id);await page.locator('#project-load-solution').click();
    await expect(page.locator('#project-status')).toContainText(`Opened ${solution.name}.`);
    await expect(page.locator('#structural-equations')).toHaveValue('aswing-airflow');
    await expect(page.locator('#strut-mode')).toHaveValue('wire');
    await expect(page.locator('#powers [data-power="1"]')).toBeVisible();
    const restored=await exported(page);
    if(solution.data.analysis==='frequency_response')expect(restored.samples).toEqual(solution.data.samples);
    else if(solution.data.analysis==='time_response')expect(restored.snapshots).toEqual(solution.data.snapshots);
    else expect(restored.modes).toEqual(solution.data.modes);
  }
  await page.setViewportSize({width:390,height:844});await page.locator('[data-workspace="plots"]').click();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.screenshot({path:`${directory}/browser-mobile.png`,fullPage:true});
  expect(errors).toEqual([]);
  await writeFile(`${directory}/browser.json`,JSON.stringify({status:'PASS',errors,frequency,initialTime,time,modes,project},null,2)+'\n');
});
