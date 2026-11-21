import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
const data=async(page,id)=>{const d=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await d).path(),'utf8'));};
async function solve(page,text='Analysis converged'){
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText(text,{timeout:180000});
  await expect(page.locator('#error')).toBeHidden();return data(page,'#export-json');
}

test('frozen influences change loads and survive case restore, saved launch and flow inspection offline',async({page,context})=>{
  test.setTimeout(360000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const study=JSON.parse(await readFile('docs/validation/frozen-influences.json','utf8'));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('wake-interaction');await expect(page.locator('#filename')).toHaveText('wake-interaction.asw');
  await expect(page.locator('#solve')).toBeEnabled();await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();await page.locator('#alpha').fill('8');await page.locator('#beta').fill('4');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#circulation-settings').evaluate(e=>e.open=true);await expect(page.locator('#freeze-influences')).toBeChecked();
  await page.locator('#freeze-influences').uncheck(); // Historical current-influence control.
  await page.locator('#mode').selectOption('mounted');await context.setOffline(true);
  const current=await solve(page);expect(current.aerodynamic_influences.frozen).toBe(false);
  await page.locator('#freeze-influences').check();await expect(page.locator('#export-json')).toBeDisabled();
  const frozen=await solve(page),expected=study.cases[0].reference;
  expect(frozen.aerodynamic_influences.frozen).toBe(true);
  frozen.force.forEach((v,i)=>expect(v).toBeCloseTo(expected.force[i],7));
  expect(Math.hypot(...frozen.force.map((v,i)=>v-current.force[i]))).toBeGreaterThan(1);
  await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText('AERODYNAMIC INFLUENCES · FROZEN (K/F)');
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);await page.locator('#equilibrium-use').click();
  await page.locator('#project-settings').evaluate(e=>e.open=true);await page.locator('#project-case-name').fill('Frozen influences');await page.locator('#project-add').click();
  await expect(page.locator('#project-status')).toContainText('New case saved');await page.locator('#freeze-influences').uncheck();await page.locator('#project-load').click();
  await expect(page.locator('#project-status')).toContainText('Loaded Frozen influences');await expect(page.locator('#freeze-influences')).toBeChecked();
  await page.locator('#freeze-influences').uncheck();await page.locator('#mode').selectOption('time');
  await expect(page.locator('#equilibrium-status')).toContainText('Saved influences: frozen');
  await page.locator('#time-duration').fill('.02');await page.locator('#time-step').fill('.01');
  const history=await solve(page,'Time integration converged');expect(history.condition.freeze_influences).toBe(true);
  for(const s of history.snapshots){expect(s.aerodynamic_influences.frozen).toBe(true);s.force.forEach((v,i)=>expect(v).toBeCloseTo(frozen.force[i],6));}
  await page.locator('#tab-flow').click();await page.locator('#flow-sample').click();await expect(page.locator('#flow-json')).toBeEnabled({timeout:180000});
  const field=await data(page,'#flow-json');expect(field.condition.freeze_influences).toBe(true);expect(field.aerodynamic_influences.frozen).toBe(true);
  await page.locator('#circulation-settings').scrollIntoViewIfNeeded();await page.locator('#circulation-settings').screenshot({path:'test-results/frozen-influence-controls.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#equilibrium-status').scrollIntoViewIfNeeded();await page.screenshot({path:'test-results/frozen-influence-mobile.png'});expect(errors).toEqual([]);
});

test('older cases retain current influences when the new setting is absent',async({page,context})=>{
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await context.setOffline(true);
  await page.locator('#project-settings').evaluate(e=>e.open=true);await page.locator('#project-case-name').fill('Older influence case');
  await expect(page.locator('#freeze-influences')).toBeChecked();
  const project=await data(page,'#project-export-current');
  expect(project.cases[0].configuration.fields['freeze-influences']).toBe(true);
  delete project.cases[0].configuration.fields['freeze-influences'];
  await page.locator('#circulation-settings').evaluate(e=>e.open=true);await page.locator('#freeze-influences').check();
  await page.locator('#project-file').setInputFiles({name:'old-project.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});
  await expect(page.locator('#project-status')).toContainText('Project opened');await page.locator('#project-load').click();
  await expect(page.locator('#project-status')).toContainText('Loaded Older influence case');await expect(page.locator('#freeze-influences')).not.toBeChecked();
});
