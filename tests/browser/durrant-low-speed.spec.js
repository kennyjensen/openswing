import {test, expect} from '@playwright/test';
import {readFile, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

test('low-airspeed wing modes retain air inertia in offline solves and exports', async ({page, context}) => {
  test.setTimeout(420000);
  const study = JSON.parse(await readFile('docs/validation/durrant-low-speed.json', 'utf8'));
  expect(study.cases).toHaveLength(20);
  for (const [file, wanted] of Object.entries(study.source_sha256)) {
    expect(createHash('sha256').update(await readFile(file)).digest('hex'), file).toBe(wanted);
  }
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.locator('#solve')).toBeEnabled();
  await context.setOffline(true);
  const records = [];
  for (const wing of ['25', '75']) {
    const native = study.cases.find(c => c.spec.wing === wing && c.spec.panels === 8);
    await page.locator('#file').setInputFiles({name: `durrant-${wing}-aero.asw`, mimeType: 'text/plain', buffer: Buffer.from(native.source)});
    await expect(page.locator('#model-name')).toContainText('aerodynamic reconstruction');
    await expect(page.locator('#solve')).toBeEnabled();
    const panels = {default: 8, beams: {'1': {count: 8, spacing: 'uniform'}}};
    await page.locator('#node-file').setInputFiles({name: 'uniform.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify({format: 'openswing-mesh', version: 1, panels}))});
    await expect(page.locator('#node-table tbody tr')).toHaveCount(native.actual_elements+1);
    await expect(page.locator('#node-spacing')).toHaveValue('uniform');
    await expect(page.locator('#panels')).toHaveValue('8');
    await expect(page.locator('#solve')).toBeEnabled();
    await page.locator('#mode').selectOption('modes');
    await page.locator('#modal-vacuum').uncheck();
    await page.locator('#modal-count').fill('24');
    await page.locator('#modal-method').selectOption('full_shift_invert');
    await page.locator('#modal-shift-imag').fill('1200');
    await page.locator('#speed').fill('0.01');
    await page.locator('#alpha').fill('0');
    await page.locator('#beta').fill('0');
    await page.locator('#atmosphere-settings').evaluate(e => e.open = true);
    await page.locator('#gravity-mode').selectOption('custom');
    await page.locator('#gravity-magnitude').fill('0');
    await page.locator('#density-mode').selectOption('custom');
    await page.locator('#density').fill('1.225');
    await page.locator('#mach-mode').selectOption('fixed');
    await page.locator('#pg-mach').fill('0');
    await page.locator('#solve').click();
    await expect(page.locator('#runtime-status')).toHaveText('Analysis converged', {timeout: 180000});
    await expect(page.locator('#error')).toBeHidden();
    const download = page.waitForEvent('download');
    await page.locator('#export-json').click();
    const result = JSON.parse(await readFile(await (await download).path(), 'utf8'));
    expect(result.vacuum).toBe(false);
    expect(result.condition.speed).toBe(.01);
    expect(result.base.operating_values.speed).toBeCloseTo(.01, 12);
    expect(result.base.mesh_discretization.settings).toEqual(panels);
    expect(result.base.structural_elements).toBe(native.actual_elements);
    const roots = result.modes.filter(m => m.eigenvalue[1] > 20).sort((a, b) => a.eigenvalue[1]-b.eigenvalue[1]).slice(0, 9);
    expect(roots).toHaveLength(9);
    for (let i = 0; i < roots.length; i++) {
      expect(Math.abs(roots[i].eigenvalue[1]/(2*Math.PI)-native.frequencies_Hz[i])).toBeLessThan(2e-5);
      expect(Math.abs(roots[i].eigenvalue[0]-native.growth_per_s[i])).toBeLessThan(2e-6);
      expect(roots[i].right_backward_error).toBeLessThan(1e-9);
    }
    await page.locator('#tab-modes').click();
    await page.locator('#modal-select').selectOption(String(result.modes.indexOf(roots[0])));
    await page.locator('#modal-quantity').selectOption('nodes.displacement.1');
    await expect(page.locator('#modal-plot polyline')).toHaveCount(2);
    await expect(page.locator('#modal-unit')).toContainText('Displacement y');
    const csvDownload = page.waitForEvent('download');
    await page.locator('#modal-output-csv').click();
    const csv = await readFile(await (await csvDownload).path(), 'utf8');
    expect(csv).toContain('Displacement y real');
    await page.locator('#pane-modes').screenshot({path: `test-results/durrant-low-speed-${wing}.png`});
    records.push({wing, eigenvalues: roots.map(m => m.eigenvalue), speed: result.base.operating_values.speed, panels});
  }
  await page.setViewportSize({width: 390, height: 844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1)).toBe(true);
  await writeFile('test-results/durrant-low-speed-browser.json', JSON.stringify(records, null, 2)+'\n');
  expect(errors).toEqual([]);
});
