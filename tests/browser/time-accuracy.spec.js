import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
async function download(page,id){const event=page.waitForEvent('download');await page.locator(id).click();return readFile(await(await event).path(),'utf8');}
const data=async(page,id='#export-json')=>JSON.parse(await download(page,id));
function checkOscillator(result){
  const wd=Math.sqrt(243.75);
  for(const s of result.snapshots){
    const t=s.time,q=.002*Math.exp(-2.5*t)*(Math.cos(wd*t)+2.5/wd*Math.sin(wd*t));
    const v=-.5/wd*Math.exp(-2.5*t)*Math.sin(wd*t);
    expect(Math.abs(s.nodes.at(-1).position[1]-2-q)/.002).toBeLessThan(.02);
    expect(Math.abs(s.local_velocity.at(-1)[1]-v)/(.002*Math.sqrt(250))).toBeLessThan(.02);
    if(s.accuracy)expect(s.accuracy.maximum_ratio).toBeLessThanOrEqual(1);
  }
}

test('offline temporal refinement checks a released spring, retains checkpoint policy and restores archives',async({page,context})=>{
  test.setTimeout(600000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('instrumented-oscillator');
  await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await expect(page.locator('#node-table tbody tr')).toHaveCount(5);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('mounted');await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
  await page.locator('#powers input[data-power="1"]').fill('1');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await context.setOffline(true);await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);await page.locator('#equilibrium-use').click();
  await page.locator('#mode').selectOption('time');
  await page.locator('#time-duration').fill('.12');await page.locator('#time-step').fill('.06');
  await page.locator('#time-order').selectOption('2');
  await page.locator('#time-accuracy-settings').evaluate(e=>e.open=true);await page.locator('#time-accuracy-enabled').check();
  await page.locator('#time-accuracy-rtol').fill('.001');await page.locator('#time-accuracy-atol').fill('.000001');
  await page.locator('#forcing-settings').evaluate(e=>e.open=true);await page.locator('#time-forcing').fill('time E1\n0 0\n.2 0');
  await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:300000});
  const original=await data(page);expect(original.request.action).toBe('launch_time');checkOscillator(original);
  expect(original.accuracy.rejected_accuracy_steps).toBeGreaterThan(0);
  expect(original.accuracy.maximum_accepted_ratio).toBeLessThanOrEqual(1);
  expect(original.internal_steps).toBe(2*original.accepted_steps);
  expect(original.snapshots[0].forcing_values.E1).toBe(1);
  expect(original.snapshots[1].forcing_values.E1).toBe(0);
  await expect(page.locator('#time-summary')).toContainText('Temporal refinement');
  await page.locator('#time-quantity').selectOption('accuracy.maximum_ratio');await expect(page.locator('#time-plot svg')).toBeVisible();
  const csv=await download(page,'#time-csv');expect(csv).toContain('Temporal discrepancy / tolerance');expect(csv).toContain('Time between reported endpoints');
  await page.locator('#time-scrub').fill(String(original.snapshots.length-1));
  await page.locator('#time-checkpoint-settings').evaluate(e=>e.open=true);
  const saved=await data(page,'#time-checkpoint-save');
  expect(saved.context.method.accuracy.rtol).toBe(.001);
  expect(saved.older.time).toBe(original.snapshots.at(-1).accuracy.midpoint_time);
  await page.locator('#time-checkpoint-use').click();
  await page.locator('#time-continue-accuracy-settings').evaluate(e=>e.open=true);
  await expect(page.locator('#time-continue-accuracy-enabled')).toBeChecked();
  await expect(page.locator('#time-continue-accuracy-rtol')).toHaveValue('0.001');
  await page.locator('#time-continue-duration').fill('.02');await page.locator('#time-continue').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time continuation converged',{timeout:240000});
  const continued=await data(page);checkOscillator(continued);
  expect(continued.end_time).toBeCloseTo(.14,12);expect(continued.retained_steps).toBe(original.accepted_steps);
  expect(continued.internal_steps).toBe(2*continued.accepted_steps);
  expect(continued.snapshots[0].restart).toEqual(original.snapshots[0].restart);
  await page.locator('#time-quantity').selectOption('accuracy.maximum_ratio');
  await page.locator('#pane-time').screenshot({path:'test-results/time-accuracy.png'});
  // Changing the policy preserves checked prefix values and leaves genuine
  // gaps in the new fixed-step segment's discrepancy history.
  await page.locator('#time-scrub').fill(String(continued.snapshots.length-1));
  await page.locator('#time-checkpoint-use').click();
  await page.locator('#time-continue-accuracy-enabled').uncheck();
  await page.locator('#time-continue-step').fill('.01');await page.locator('#time-continue-duration').fill('.02');
  await page.locator('#time-continue').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time continuation converged',{timeout:180000});
  const fixed=await data(page);checkOscillator(fixed);
  expect(fixed.end_time).toBeCloseTo(.16,12);expect(fixed.accuracy).toBeUndefined();
  expect(fixed.internal_steps).toBe(continued.internal_steps+fixed.accepted_steps-continued.accepted_steps);
  expect(fixed.snapshots.at(-1).accuracy).toBeUndefined();
  await page.locator('#time-quantity').selectOption('accuracy.maximum_ratio');
  await expect(page.locator('#time-summary')).toContainText('new segment uses fixed steps');
  expect(await page.locator('#time-plot circle').count()).toBe(continued.snapshots.filter(s=>s.accuracy).length);
  await page.locator('#project-settings').evaluate(e=>e.open=true);
  await page.locator('#project-solution-name').fill('Checked temporal accuracy');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Computed solution saved.');
  await page.locator('#time-accuracy-rtol').fill('.01');
  await page.locator('#project-load-solution').click();
  await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');
  expect(await data(page)).toEqual(fixed);await expect(page.locator('#time-accuracy-rtol')).toHaveValue('.001');
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#time-accuracy-settings').screenshot({path:'test-results/time-accuracy-mobile.png'});
  await writeFile('test-results/time-accuracy-values.json',JSON.stringify({accuracy:continued.accuracy,internal_steps:fixed.internal_steps,snapshots:fixed.snapshots.map(s=>({time:s.time,position:s.nodes.at(-1).position,velocity:s.local_velocity.at(-1),accuracy:s.accuracy??null}))},null,2)+'\n');
  expect(errors).toEqual([]);
});
