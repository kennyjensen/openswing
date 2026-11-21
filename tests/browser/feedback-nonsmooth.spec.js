import { test, expect } from '@playwright/test';
import { readFile, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';

const mesa = process.env.OPENSWING_WEBGL_DRIVER === 'mesa';
test.use({ viewport: { width: 390, height: 844 }, launchOptions: {
  executablePath: process.env.OPENSWING_CHROMIUM_EXECUTABLE,
  args: mesa ? ['--no-sandbox', '--use-gl=angle', '--use-angle=vulkan', '--use-vulkan=native',
    '--ignore-gpu-blocklist', '--enable-features=Vulkan', '--disable-gpu-compositing'] :
    ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader-webgl', '--enable-unsafe-swiftshader'],
} });

async function workspace(page, name) {
  await page.locator(`#workspace-tab-${name}`).click();
  await expect(page.locator(`#workspace-tab-${name}`)).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator(`#workspace-${name}`)).toBeVisible();
}

async function download(page, selector) {
  await expect(page.locator(selector)).toBeEnabled();
  const event = page.waitForEvent('download');
  await page.locator(selector).click();
  return readFile(await (await event).path(), 'utf8');
}

const closeVector = (actual, expected, tolerance) => {
  expect(actual).toHaveLength(expected.length);
  for (let i = 0; i < expected.length; i++) {
    expect(Number.isFinite(actual[i])).toBe(true);
    expect(Math.abs(actual[i] - expected[i])).toBeLessThanOrEqual(tolerance);
  }
};

test('mobile offline controller refuses nearby alternatives and retains a unique saturation boundary', async ({ page, context }, testInfo) => {
  test.setTimeout(450000);
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  const names = (await readdir('openswing')).filter(name => name.endsWith('.py')).sort();
  const sourcePins = Object.fromEntries(await Promise.all(names.map(async name => [name,
    createHash('sha256').update(await readFile(`openswing/${name}`)).digest('hex')])));
  expect(names).toHaveLength(59);

  await page.goto('/');
  await expect(page.locator('#solve')).toBeEnabled();
  await workspace(page, 'editor');
  await page.locator('#file').setInputFiles('examples/guided-body.asw');
  await expect(page.locator('#model-name')).toHaveText('Guided rigid-body demonstrator');
  // Edit the actual ASW source: 1 kg, coincident references, unit +x thrust,
  // zero engine torque, no aerodynamics, and a disabled propulsive jet.
  const source = `${await page.locator('#editor').inputValue()}\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\n`;
  await page.locator('#editor').fill(source);
  await expect(page.locator('#solve')).toBeDisabled();
  await page.locator('#apply').click();
  await expect(page.locator('#solve')).toBeEnabled();
  await workspace(page, 'settings');
  await page.locator('#panels').fill('4');
  await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#speed').fill('10');
  await page.locator('#alpha').fill('0');
  await page.locator('#powers input').fill('0');
  await page.locator('#atmosphere-settings > summary').click();
  await page.locator('#gravity-mode').selectOption('custom');
  await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#mach-mode').selectOption('fixed');
  await page.locator('#pg-mach').fill('0');
  await page.locator('#mode').selectOption('time');
  await page.locator('#time-frame').selectOption('free');
  await page.locator('#time-order').selectOption('5');
  await page.locator('#time-duration').fill('.02');
  await page.locator('#time-step').fill('.02');
  await page.locator('#feedback-settings > summary').click();
  await page.locator('#feedback-enabled').check();
  const ambiguous = { outputs: [{ actuator: 'E1', residual: "actuator('E1')-clip(actuator('E1'),0,1)" }] };
  await page.locator('#feedback-definition').fill(JSON.stringify(ambiguous));

  // Both numerical requests use the real already-loaded packaged worker offline.
  await context.setOffline(true);
  await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis stopped', { timeout: 180000 });
  await expect(page.locator('#error')).toBeVisible();
  await expect(page.locator('#error p')).toContainText('Nonsmooth controller has unresolved nearby accepted alternatives');
  await expect(page.locator('#error p')).toContainText('control authority is not certified');
  await expect(page.locator('#solve')).toBeEnabled();
  await expect(page.locator('#cancel')).toBeHidden();
  await expect(page.locator('#time-transport')).toBeHidden();
  const refusal = await page.locator('#error p').textContent();
  await page.locator('#error').screenshot({ path: testInfo.outputPath('cold-controller-refusal.png') });
  await workspace(page, 'output');
  for (const selector of ['#export-json', '#csv', '#time-csv', '#feedback-csv']) {
    await expect(page.locator(selector)).toBeDisabled();
  }
  await testInfo.attach('cold-controller-refusal', { body: JSON.stringify({
    message: refusal, definition: ambiguous, offline: true, exported_result: false,
  }), contentType: 'application/json' });

  await page.locator('#close-error').click();
  await workspace(page, 'settings');
  const regular = { outputs: [{ actuator: 'E1', expression: "clip(.3-.5*measurement('Ax'),0,.2)" }] };
  await page.locator('#feedback-definition').fill(JSON.stringify(regular));
  await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time integration converged', { timeout: 180000 });
  await expect(page.locator('#error')).toBeHidden();
  await expect(page.locator('#workspace-tab-plots')).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#workspace-plots #viewport canvas')).toBeVisible();
  await expect(page.locator('#workspace-plots #pane-time')).toBeVisible();
  await page.locator('#time-quantity').selectOption('feedback.actuators.E1');
  await expect(page.locator('#time-plot svg')).toBeVisible();
  await expect(page.locator('#time-plot circle')).toHaveCount(2);
  await page.locator('#time-plot').screenshot({ path: testInfo.outputPath('unique-controller-time-history.png') });
  expect(await download(page, '#time-csv')).toContain('0.02');
  await page.locator('#time-scrub').fill('1');
  await workspace(page, 'output');
  await expect(page.locator('#workspace-output #pane-report')).toBeVisible();
  await expect(page.locator('#workspace-output #pane-feedback')).toBeVisible();
  await expect(page.locator('#feedback-table')).toContainText('actuators · E1');
  await expect(page.locator('#feedback-table')).toContainText('measurements · Ax');
  const result = JSON.parse(await download(page, '#export-json'));

  // Independent mechanics: F = m*a and F = clip(.3-.5*a, 0, .2) have
  // the unique solution F=a=.2. For identity attitude, Ux=-10+.2*t
  // and Px=-10*t+.1*t*t; Radau integrates these polynomials exactly.
  expect(result.analysis).toBe('time_response');
  expect(result.converged).toBe(true);
  expect(result.method).toBe('Radau IIA (3 stages)');
  expect(result.frame_mode).toBe('free');
  expect(result.accepted_steps).toBe(1);
  expect(result.rejected_steps).toBe(0);
  expect(result.snapshots).toHaveLength(2);
  expect(result.request.source).toBe(source);
  expect(result.request.condition.speed).toBe(10);
  expect(result.request.condition.gravity_magnitude).toBe(0);
  expect(result.controller.definition).toEqual(regular);
  expect(result.software_provenance.modules).toEqual(sourcePins);
  expect(result.snapshots.map(row => row.time)).toEqual([0, .02]);
  for (const row of result.snapshots) {
    expect(Math.abs(row.feedback.actuators.E1 - .2)).toBeLessThanOrEqual(1e-7);
    expect(Math.abs(row.feedback.measurements.Ax - .2)).toBeLessThanOrEqual(1e-7);
    closeVector(row.frame.acceleration_reference_body, [.2, 0, 0], 1e-7);
    closeVector(row.frame.velocity_origin_body, [-10+.2*row.time, 0, 0], 1e-8);
    closeVector(row.frame.position_earth, [-10*row.time+.1*row.time**2, 0, 0], 1e-8);
    closeVector(row.frame.rates_body, [0, 0, 0], 1e-8);
    closeVector(row.frame.angular_acceleration_body, [0, 0, 0], 1e-8);
    closeVector(row.frame.body_to_earth.flat(), [1, 0, 0, 0, 1, 0, 0, 0, 1], 1e-8);
    expect(row.residual).toBeLessThanOrEqual(1e-8);
  }
  const collocation = result.snapshots[1].collocation;
  expect(collocation.stages).toBe(3);
  expect(collocation.maximum_stage_residual).toBeLessThanOrEqual(collocation.stage_tolerance);
  await testInfo.attach('unique-controller-result', { body: JSON.stringify(result), contentType: 'application/json' });
  await testInfo.attach('expected-source-pins', { body: JSON.stringify(sourcePins), contentType: 'application/json' });
  expect(pageErrors).toEqual([]);
});
