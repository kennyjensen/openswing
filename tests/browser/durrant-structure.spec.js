import {test, expect} from '@playwright/test';
import {readFile, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

test('published-table wing reconstructions import, solve and export vacuum modes offline', async ({page, context}) => {
  test.setTimeout(360000);
  const study = JSON.parse(await readFile('docs/validation/durrant-structure.json', 'utf8'));
  expect(study.complete_planned_grid).toBe(true);
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
    const native = study.cases.find(c => c.spec.wing === wing && c.spec.panels === 8 && Object.keys(c.spec).length === 2);
    await page.locator('#file').setInputFiles({name: `durrant-${wing}-reconstruction.asw`, mimeType: 'text/plain', buffer: Buffer.from(native.source)});
    await expect(page.locator('#model-name')).toContainText('structural reconstruction');
    await expect(page.locator('#solve')).toBeEnabled();
    await page.locator('#node-file').setInputFiles({name: 'uniform.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify({format: 'openswing-mesh', version: 1, panels: {default: 8, beams: {'1': {count: 8, spacing: 'uniform'}}}}))});
    // Await the committed import before editing other settings; edits during
    // its asynchronous inspection intentionally invalidate a stale mesh import.
    await expect(page.locator('#node-table tbody tr')).toHaveCount(native.actual_elements+1);
    await expect(page.locator('#node-spacing')).toHaveValue('uniform');
    await expect(page.locator('#panels')).toHaveValue('8');
    await expect(page.locator('#solve')).toBeEnabled();
    await page.locator('#mode').selectOption('modes');
    await page.locator('#modal-vacuum').check();
    await page.locator('#modal-count').fill('24');
    await page.locator('#modal-method').selectOption('full_shift_invert');
    await page.locator('#atmosphere-settings').evaluate(e => e.open = true);
    await page.locator('#gravity-mode').selectOption('custom');
    await page.locator('#gravity-magnitude').fill('0');
    await page.locator('#solve').click();
    await expect(page.locator('#runtime-status')).toHaveText('Analysis converged', {timeout: 150000});
    await expect(page.locator('#error')).toBeHidden();
    await expect(page.locator('#modal-summary')).toContainText('Vacuum');
    await expect(page.locator('#modal-summary')).toContainText('total finite spectrum unclassified');
    const download = page.waitForEvent('download');
    await page.locator('#export-json').click();
    const result = JSON.parse(await readFile(await (await download).path(), 'utf8'));
    expect(result.base.mesh_discretization.settings).toEqual({default: 8, beams: {'1': {count: 8, spacing: 'uniform'}}});
    expect(result.base.structural_elements).toBe(native.actual_elements);
    const roots = result.modes.filter(m => m.eigenvalue[1] > .001).sort((a, b) => a.eigenvalue[1]-b.eigenvalue[1]).slice(0, 9);
    expect(roots).toHaveLength(9);
    for (let i = 0; i < roots.length; i++) {
      expect(Math.abs(roots[i].eigenvalue[1]/(2*Math.PI)-native.frequencies_Hz[i])).toBeLessThan(2e-5);
      expect(roots[i].right_backward_error).toBeLessThan(1e-9);
    }
    expect(result.base.mass_properties.mass).toBeCloseTo(native.mass_properties.mass, 10);
    await page.locator('#tab-modes').click();
    await expect(page.locator('#modal-roots svg')).toBeVisible();
    await page.locator('#pane-modes').screenshot({path: `test-results/durrant-${wing}-modes.png`});
    records.push({wing, frequencies_Hz: roots.map(m => m.eigenvalue[1]/(2*Math.PI)), mass: result.base.mass_properties.mass});
  }
  await page.setViewportSize({width: 390, height: 844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1)).toBe(true);
  await writeFile('test-results/durrant-browser-values.json', JSON.stringify(records, null, 2)+'\n');
  expect(errors).toEqual([]);
});
