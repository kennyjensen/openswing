import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import {parseProject} from '../../web/project-data.js';
import {verifySolution} from '../../web/solution-data.js';

const directory='artifacts/isae/source-airflow-20261030';
async function exported(page,id='#export-json'){
  const download=page.waitForEvent('download');await page.locator(id).click();
  return JSON.parse(await readFile(await(await download).path(),'utf8'));
}
async function finish(page,label){
  await expect(page.locator('#runtime-status')).toHaveText(new RegExp(`^(${label}|Analysis stopped|Frequency refinement stopped|Time continuation stopped)$`),{timeout:300000});
  if(await page.locator('#error').isVisible())throw new Error(await page.locator('#error').innerText());
  await expect(page.locator('#runtime-status')).toHaveText(label);
}

test('source airflow runs offline, reuses frequency matrices and restores saved dynamics',async({page,context})=>{
  test.setTimeout(900000);
  page.setDefaultTimeout(30000);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  const native=JSON.parse(await readFile(`${directory}/frequency-native.json`,'utf8'));
  const transient=JSON.parse(await readFile(`${directory}/step-0.002.json`,'utf8'));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles('examples/source-airflow-check.asw');
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
  await page.locator('#frequency-frame').selectOption('fixed');await page.locator('#frequency-inputs').selectOption('controls');
  await page.locator('#structural-equations').selectOption('aswing-airflow');await expect(page.locator('#solve')).toBeEnabled();
  await expect(page.locator('#speed')).toBeVisible();await expect(page.locator('#controls')).toBeVisible();
  await expect(page.locator('#feedback-settings')).toBeVisible();
  await page.locator('#frequency-start').fill('.2');await page.locator('#frequency-end').fill('20');await page.locator('#frequency-count').fill('2');
  await page.locator('#frequency-spacing').selectOption('linear');
  await context.setOffline(true);
  await page.locator('#solve').click();await finish(page,'Analysis converged');
  const first=await exported(page);
  await page.locator('#frequency-refinement').evaluate(el=>el.open=true);
  await page.locator('#frequency-add-values').fill('3, 100');await page.locator('#frequency-add-list').click();
  await finish(page,'Frequency refinement complete');
  const frequency=await exported(page);
  console.log('Source airflow frequency and matrix refinement completed.');
  expect(frequency.structural_operator).toBe('drela-moving-airflow-v1');expect(frequency.vacuum).toBe(false);
  expect(frequency.frequency_refinement.linearization_reused).toBe(true);
  for(const old of first.samples)expect(frequency.samples.find(row=>row.omega===old.omega)).toEqual(old);
  for(const row of frequency.samples){
    const reference=native.samples.find(sample=>Math.abs(sample.omega-row.omega)<1e-10);expect(reference).toBeTruthy();
    for(const key of ['CL','Cm'])for(const part of ['real','imag'])
      expect(row.responses[0].output.global[key][part]).toBeCloseTo(reference.responses[0].output.global[key][part],7);
  }
  await page.locator('#project-settings').evaluate(el=>el.open=true);
  await page.locator('#project-solution-name').fill('Source airflow frequency');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Saved');
  await page.locator('#mode').selectOption('time');
  await expect(page.locator('#structural-equations')).toHaveValue('aswing-airflow');
  await page.locator('#time-frame').selectOption('prescribed');
  await page.locator('#time-duration').fill('.04');await page.locator('#time-step').fill('.002');await page.locator('#time-order').selectOption('2');
  await page.locator('#forcing-settings').evaluate(el=>el.open=true);
  await page.locator('#time-forcing').fill('time +F1\n0 0\n.004 0\n.004 .0001\n.1 .0001\n');
  await page.locator('#solve').click();await finish(page,'Time integration converged');
  let time=await exported(page);const last=time.snapshots.at(-1);
  expect(time.structural_operator).toBe('drela-moving-airflow-v1');expect(time.temporal_policy).toBe('drela-euler-bdf-v1');
  expect(last.time).toBe(.04);expect(last.CL).toBeCloseTo(transient.snapshots.at(-1).CL,10);
  expect(time.snapshots.every(row=>row.residual<1e-8)).toBe(true);
  const initialTime=time;
  await page.locator('#time-scrub').evaluate((el,index)=>{el.value=index;el.dispatchEvent(new Event('input',{bubbles:true}));},time.snapshots.length-1);
  await page.locator('#time-checkpoint-settings').evaluate(el=>el.open=true);
  await page.locator('#time-checkpoint-use').click();await page.locator('#time-continue-duration').fill('.004');
  await page.locator('#time-continue-step').fill('.002');await page.locator('#time-continue-order').selectOption('2');
  await page.locator('#time-continue').click();await finish(page,'Time continuation converged');
  time=await exported(page);expect(time.snapshots.at(-1).time).toBeCloseTo(.044,12);
  expect(time.snapshots.slice(0,initialTime.snapshots.length)).toEqual(
    initialTime.snapshots.map(row=>({...row,restart_context:row.restart_context??initialTime.restart_context})));
  console.log('Source airflow time response and checkpoint continuation completed.');
  await page.locator('#project-solution-name').fill('Source airflow time');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Saved');
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-frame').selectOption('fixed');
  await page.locator('#modal-count').fill('4');await page.locator('#modal-method').selectOption('full_shift_invert');
  await page.locator('#solve').click();await finish(page,'Analysis converged');
  const modes=await exported(page),modeReference=JSON.parse(await readFile(`${directory}/mode-result.json`,'utf8'));
  const roots=result=>result.modes.map(row=>row.eigenvalue[0]).sort((a,b)=>a-b);
  expect(roots(modes)).toHaveLength(4);
  roots(modes).forEach((root,index)=>expect(root).toBeCloseTo(roots(modeReference)[index],5));
  await page.locator('#project-solution-name').fill('Source airflow modes');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Saved');
  console.log('Source airflow Arnoldi modes completed.');
  const project=parseProject(JSON.stringify(await exported(page,'#project-export')));
  for(const solution of project.solutions)await verifySolution(solution);
  await context.setOffline(false);await page.reload();await expect(page.locator('#solve')).toBeEnabled();await context.setOffline(true);
  await page.locator('#project-file').setInputFiles({name:'source-airflow.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});
  await page.locator('#project-settings').evaluate(el=>el.open=true);
  for(const solution of project.solutions){
    await page.locator('#project-solutions').selectOption(solution.id);await page.locator('#project-load-solution').click();
    await expect(page.locator('#project-status')).toContainText(`Opened ${solution.name}.`);
    await expect(page.locator('#structural-equations')).toHaveValue('aswing-airflow');
    const restored=await exported(page);
    if(solution.data.analysis==='frequency_response')expect(restored.samples).toEqual(solution.data.samples);
    else if(solution.data.analysis==='time_response')expect(restored.snapshots).toEqual(solution.data.snapshots);
    else expect(restored.modes).toEqual(solution.data.modes);
  }
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.screenshot({path:`${directory}/browser-mobile.png`,fullPage:true});
  expect(errors).toEqual([]);
  await writeFile(`${directory}/browser.json`,JSON.stringify({status:'PASS',errors,frequency,initialTime,time,modes,project},null,2)+'\n');
});
