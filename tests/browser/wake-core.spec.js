import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
const data=async(page,id)=>{const d=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await d).path(),'utf8'));};
async function solve(page,text='Analysis converged'){
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText(text,{timeout:180000});
  await expect(page.locator('#error')).toBeHidden();return data(page,'#export-json');
}

test('core changes interacting-surface loads and survives cases, flow inspection and time launch offline',async({page,context})=>{
  test.setTimeout(360000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const study=JSON.parse(await readFile('docs/validation/wake-core.json','utf8'));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('wake-interaction');await expect(page.locator('#filename')).toHaveText('wake-interaction.asw');
  await expect(page.locator('#solve')).toBeEnabled();await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();await page.locator('#speed').fill('30');await page.locator('#alpha').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#circulation-settings').evaluate(e=>e.open=true);await expect(page.locator('#wake-core-ratio')).toHaveValue('0.25');
  await page.locator('#mode').selectOption('mounted');await context.setOffline(true);
  let saved;
  for(const ratio of [.25,1]){
    await page.locator('#wake-core-ratio').fill(String(ratio));await expect(page.locator('#export-json')).toBeDisabled();
    const actual=await solve(page),expected=study.cases.find(c=>c.specification.panels===4&&c.specification.ratio===ratio).reference;
    expect(actual.wake_core.ratio).toBe(ratio);actual.force.forEach((v,i)=>expect(v).toBeCloseTo(expected.force[i],7));
    await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText(`WAKE CORE · r/c = ${ratio}`);
    saved=actual;
  }
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);await page.locator('#equilibrium-use').click();
  await page.locator('#project-settings').evaluate(e=>e.open=true);await page.locator('#project-case-name').fill('Large wake core');await page.locator('#project-add').click();
  await expect(page.locator('#project-status')).toContainText('New case saved');await page.locator('#wake-core-ratio').fill('.25');await page.locator('#project-load').click();
  await expect(page.locator('#project-status')).toContainText('Loaded Large wake core');await expect(page.locator('#wake-core-ratio')).toHaveValue('1');
  await page.locator('#wake-core-ratio').fill('.25');await page.locator('#mode').selectOption('time');
  await expect(page.locator('#equilibrium-status')).toContainText('Saved wake core r/c: 1');
  await page.locator('#time-duration').fill('.02');await page.locator('#time-step').fill('.01');
  const history=await solve(page,'Time integration converged');expect(history.condition.wake_core_ratio).toBe(1);
  for(const s of history.snapshots){expect(s.wake_core.ratio).toBe(1);s.force.forEach((v,i)=>expect(v).toBeCloseTo(saved.force[i],6));}
  await page.locator('#tab-flow').click();await page.locator('#flow-sample').click();await expect(page.locator('#flow-json')).toBeEnabled({timeout:180000});
  const field=await data(page,'#flow-json');expect(field.condition.wake_core_ratio).toBe(1);expect(field.wake_core.ratio).toBe(1);
  await page.locator('#circulation-settings').scrollIntoViewIfNeeded();await page.locator('#circulation-settings').screenshot({path:'test-results/wake-core-controls.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#equilibrium-status').scrollIntoViewIfNeeded();await page.screenshot({path:'test-results/wake-core-mobile.png'});expect(errors).toEqual([]);
});

test('older cases restore the original quarter-chord default and invalid ratios are diagnosed',async({page,context})=>{
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await context.setOffline(true);
  await page.locator('#project-settings').evaluate(e=>e.open=true);await page.locator('#project-case-name').fill('Older core case');
  const project=await data(page,'#project-export-current');delete project.cases[0].configuration.fields['wake-core-ratio'];
  await page.locator('#circulation-settings').evaluate(e=>e.open=true);await page.locator('#wake-core-ratio').fill('1');
  await page.locator('#project-file').setInputFiles({name:'old-project.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});
  await expect(page.locator('#project-status')).toContainText('Project opened');await page.locator('#project-load').click();
  await expect(page.locator('#project-status')).toContainText('Loaded Older core case');await expect(page.locator('#wake-core-ratio')).toHaveValue('0.25');
  for(const value of ['', '-.1']){
    await page.locator('#wake-core-ratio').fill(value);await page.locator('#solve').click();await expect(page.locator('#error')).toContainText('Wake core radius/chord must be a finite nonnegative number');await page.locator('#close-error').click();
  }
});
