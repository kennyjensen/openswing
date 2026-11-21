import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

async function output(page) {
  const pending=page.waitForEvent('download');
  await page.locator('#export-json').click();
  return JSON.parse(await readFile(await(await pending).path(),'utf8'));
}

function equations(result) {
  expect(result.frame_mode).toBe('free');
  for(const row of result.snapshots) {
    expect(row.residual).toBeLessThanOrEqual(1e-8);
    if(row.collocation) {
      expect(row.collocation.maximum_stage_residual).toBeLessThanOrEqual(row.collocation.stage_tolerance);
      expect(row.order).toBe(5);
    }
    for(const c of row.operating_constraints) {
      expect(c.target).toBe(0);
      expect(Math.abs(c.normalized_residual)).toBeLessThanOrEqual(1e-8);
    }
  }
}

test('offline free-flight Radau flap response exports and resumes its physical stages',async({page,context},testInfo)=>{
  test.setTimeout(300000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled({timeout:180000});
  await page.locator('#example').selectOption('transient-wing');
  await expect(page.locator('#model-name')).toHaveText('Elastic transient demonstrator');
  await page.locator('#panels').fill('8');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#speed').fill('20');await page.locator('#alpha').fill('3');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('.1');
  await page.locator('#mode').selectOption('time');await page.locator('#time-frame').selectOption('free');
  await page.locator('#time-order').selectOption('5');
  await page.locator('#time-duration').fill('.04');await page.locator('#time-step').fill('.01');
  await page.locator('#forcing-settings').evaluate(e=>e.open=true);
  await page.locator('#time-forcing').fill('time +F1\n0 0\n.02 0\n.02 1\n.1 1');
  await context.setOffline(true);
  await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:180000});
  const original=await output(page);equations(original);
  expect(original.method).toBe('Radau IIA (3 stages)');
  expect(original.snapshots.at(-1).time).toBe(.04);
  expect(original.rejected_steps).toBe(0);
  expect(Math.max(...original.snapshots.at(-1).local_velocity.flat().map(Math.abs))).toBeGreaterThan(.001);
  for(const name of ['structured_radau.py','radau_time.py']) {
    expect(original.software_provenance.modules[name]).toBe(
      createHash('sha256').update(await readFile('openswing/'+name)).digest('hex'));
  }
  await writeFile(testInfo.outputPath('response.json'),JSON.stringify(original));
  await page.locator('#time-scrub').fill(String(original.snapshots.length-1));
  await page.locator('#time-checkpoint-settings').evaluate(e=>e.open=true);
  await page.locator('#time-checkpoint-use').click();
  await expect(page.locator('#time-continue-order')).toHaveValue('5');
  await page.locator('#time-continue-duration').fill('.02');
  await page.locator('#time-continue-step').fill('.01');
  await page.locator('#time-continue').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time continuation converged',{timeout:120000});
  const resumed=await output(page);
  await writeFile(testInfo.outputPath('resumed.json'),JSON.stringify(resumed));
  equations(resumed);
  expect(resumed.snapshots.at(-1).time).toBeCloseTo(.06,12);
  expect(resumed.retained_steps).toBe(original.accepted_steps);
  // Joining a continuation attaches the original context to its retained
  // rows. Every original value must remain exact; that metadata is additive.
  expect(resumed.snapshots.slice(0,original.snapshots.length)).toMatchObject(original.snapshots);
  for(const row of resumed.snapshots.slice(0,original.snapshots.length))
    expect(row.restart_context).toEqual(original.restart_context);
  expect(resumed.checkpoint_validation.discrete_replayed).toBe(true);
  await page.locator('#tab-time').click();
  expect(await page.locator('#time-plot polyline').count()).toBeGreaterThan(0);
  expect(errors).toEqual([]);
});
