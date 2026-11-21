import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import {parseProject} from '../../web/project-data.js';
import {verifySolution} from '../../web/solution-data.js';
const directory='artifacts/isae/source-body-still-air-20261031';
async function exported(page,id='#export-json'){
  const event=page.waitForEvent('download');await page.locator(id).click();
  return JSON.parse(await readFile(await(await event).path(),'utf8'));
}
async function done(page,label='Analysis converged'){
  await expect(page.locator('#runtime-status')).toHaveText(new RegExp(`^(${label}|Analysis stopped|Frequency refinement stopped)$`),{timeout:300000});
  if(await page.locator('#error').isVisible())throw new Error(await page.locator('#error').innerText());
  await expect(page.locator('#runtime-status')).toHaveText(label);
}
const close=(a,b)=>{if(Array.isArray(b)){expect(a).toHaveLength(b.length);b.forEach((v,i)=>close(a[i],v));}else expect(Math.abs(a-b)).toBeLessThanOrEqual(3e-10+4e-7*Math.abs(b));};

test('body still-air coefficients, modes and reused spectra survive offline project restoration',async({page,context})=>{
  test.setTimeout(900000);const errors=[];page.on('pageerror',error=>errors.push(error.message));
  const references=JSON.parse(await readFile(`${directory}/references.json`,'utf8'));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles(`${directory}/source.asw`);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('modes');
  await page.locator('#tab-nodes').click();await page.locator('#node-spacing').selectOption('uniform');
  await page.locator('#node-count').fill('4');await page.locator('#node-apply').click();
  await expect(page.locator('#node-status')).toContainText('5 nodes');
  await page.locator('#atmosphere-settings').evaluate(el=>el.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#modal-count').fill('1');await page.locator('#modal-method').selectOption('full_shift_invert');
  const results={};
  for(const [policy,factor] of [['aswing-still-air',1],['aswing-still-air',2],['midpoint',2]]){
    await page.locator('#structural-equations').selectOption(policy);await expect(page.locator('#solve')).toBeEnabled();
    if(policy==='midpoint'){
      await page.locator('#modal-quiescent').check();await expect(page.locator('#modal-frame')).toHaveValue('fixed');
    }
    await page.locator('#modal-quiescent-density').fill('10');
    await expect(page.locator('#body-added-mass')).toBeVisible();await page.locator('#body-added-mass').selectOption(String(factor));
    const name=`mode-${policy==='midpoint'?'midpoint':'source'}-${factor}`;
    await page.locator('#modal-shift-real').fill('-.1');await page.locator('#modal-shift-imag').fill(String(references[name].omega));
    await context.setOffline(true);await page.locator('#solve').click();await done(page);
    const result=await exported(page);results[name]=result;
    close(result.modes[0].eigenvalue,[0,references[name].omega]);expect(result.fluid.body_added_mass_factor).toBe(factor);
    expect(result.base.equilibrium_state.identity.quiescent_body_added_mass_factor).toBe(factor);
    await page.locator('#project-settings').evaluate(el=>el.open=true);
    await page.locator('#project-solution-name').fill(name);await page.locator('#project-save-solution').click();
    await expect(page.locator('#project-solutions option')).toHaveCount(Object.keys(results).length);
  }
  console.log('Source and midpoint body modes preserve both coefficient choices.');
  await page.locator('#mode').selectOption('frequency');await page.locator('#structural-equations').selectOption('aswing-still-air');
  await page.locator('#modal-quiescent-density').fill('10');await page.locator('#body-added-mass').selectOption('2');
  await page.locator('#frequency-inputs').selectOption('initial');
  const request=JSON.parse(await readFile(`${directory}/frequency-2-request.json`,'utf8'));
  await page.locator('#frequency-initial-settings').evaluate(el=>el.open=true);
  await page.locator('#frequency-initial').fill(JSON.stringify(request.frequency.inputs));await page.locator('#frequency-initial-shift').fill('.3');
  await page.locator('#frequency-start').fill('1');await page.locator('#frequency-end').fill('15');await page.locator('#frequency-count').fill('2');
  await page.locator('#frequency-spacing').selectOption('linear');await page.locator('#solve').click();await done(page);
  const first=await exported(page);
  await page.locator('#frequency-refinement').evaluate(el=>el.open=true);
  await page.locator('#frequency-add-values').fill('4, 8');await page.locator('#frequency-add-list').click();
  await done(page,'Frequency refinement complete');const frequency=await exported(page);
  expect(frequency.frequency_refinement.linearization_reused).toBe(true);expect(frequency.samples).toHaveLength(4);
  for(const old of first.samples)expect(frequency.samples.find(row=>row.omega===old.omega)).toEqual(old);
  const native=JSON.parse(await readFile(`${directory}/frequency-2-native.json`,'utf8'));
  for(const row of frequency.samples){
    const ref=native.samples.find(x=>Math.abs(x.omega-row.omega)<1e-10);expect(ref).toBeTruthy();
    const actual=row.responses[0].output.nodes,expected=ref.responses[0].output.nodes;
    for(let i=0;i<actual.length;i++)for(const key of ['displacement','velocity'])for(const part of ['real','imag'])close(actual[i][key][part],expected[i][key][part]);
  }
  expect(frequency.base.fluid.body_added_mass_factor).toBe(2);results.frequency=frequency;
  await page.locator('#project-solution-name').fill('body spectrum');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-solutions option')).toHaveCount(4);
  const project=parseProject(JSON.stringify(await exported(page,'#project-export')));expect(project.solutions).toHaveLength(4);
  for(const solution of project.solutions)await verifySolution(solution);
  await context.setOffline(false);await page.reload();await expect(page.locator('#solve')).toBeEnabled();await context.setOffline(true);
  await page.locator('#project-file').setInputFiles({name:'body-still-air.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});
  await page.locator('#project-settings').evaluate(el=>el.open=true);
  for(const solution of project.solutions){
    await page.locator('#project-solutions').selectOption(solution.id);await page.locator('#project-load-solution').click();
    await expect(page.locator('#project-status')).toContainText(`Opened ${solution.name}.`);
    const restored=await exported(page),factor=solution.data.base.fluid.body_added_mass_factor;
    await expect(page.locator('#body-added-mass')).toHaveValue(String(factor));
    if(solution.data.analysis==='frequency_response')expect(restored.samples).toEqual(solution.data.samples);
    else expect(restored.modes).toEqual(solution.data.modes);
  }
  await page.setViewportSize({width:390,height:844});await page.locator('[data-workspace="plots"]').click();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.screenshot({path:`${directory}/browser-mobile.png`,fullPage:true});expect(errors).toEqual([]);
  await writeFile(`${directory}/browser.json`,JSON.stringify({status:'PASS',errors,results,project},null,2)+'\n');
});
