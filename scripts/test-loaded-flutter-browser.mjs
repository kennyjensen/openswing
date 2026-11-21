// Exercise file import, settings, offline solves, mobile plots and JSON/CSV export.
import {chromium} from 'playwright';
import {expect} from '@playwright/test';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import path from 'node:path';

const [bundlePath, output, ...selectedIds] = process.argv.slice(2);
assert(bundlePath && output, 'Usage: node scripts/test-loaded-flutter-browser.mjs BUNDLE NEW_OUTPUT_DIR');
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
await mkdir(output, {recursive: false});
const bytes = await readFile(bundlePath), bundle = JSON.parse(bytes);
const cases = selectedIds.length ? bundle.cases.filter(c => selectedIds.includes(c.id)) : bundle.cases;
assert.equal(cases.length, selectedIds.length || bundle.cases.length, 'Unknown or repeated case ID');
const status = {status: 'RUNNING', bundle_sha256: hash(bytes), selected_cases: cases.map(c => c.id), cases: [], page_errors: [], network_errors: []};
const save = () => writeFile(path.join(output, 'status.json'), JSON.stringify(status, null, 2)+'\n');
await save();
let browser;
try {
  browser = await chromium.launch({headless: true,
    executablePath: process.env.OPENSWING_CHROMIUM_EXECUTABLE || undefined,
    args: process.env.OPENSWING_CHROMIUM_ARGS ? JSON.parse(process.env.OPENSWING_CHROMIUM_ARGS) : ['--no-sandbox']});
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}, acceptDownloads: true});
  const page = await context.newPage();
  page.setDefaultTimeout(120000);
  page.on('pageerror', error => status.page_errors.push(error.message));
  page.on('requestfailed', request => status.network_errors.push({url: request.url(), failure: request.failure()}));
  await page.addInitScript(() => {
    const Original = Worker;
    window.replayObserved = {requests: [], stages: []};
    window.Worker = class extends Original {
      constructor(...args) {
        super(...args);
        this.addEventListener('message', ({data}) => {
          if (data.type === 'progress') window.replayObserved.stages.push(data);
        });
      }
      postMessage(message, ...args) {
        if (message.request?.action === 'modes') window.replayObserved.requests.push(JSON.parse(JSON.stringify(message.request)));
        return super.postMessage(message, ...args);
      }
    };
  });
  await page.goto(process.env.OPENSWING_BASE_URL || 'http://127.0.0.1:8000');
  await expect(page.locator('#solve')).toBeEnabled({timeout: 180000});
  await context.setOffline(true);
  status.offline = true;
  console.log('Ready; network disabled');
  for (const entry of cases) {
    status.current = entry.id; await save();
    await page.setViewportSize({width: 1440, height: 1000});
    const native = entry.native;
    await page.locator('#file').setInputFiles({name: entry.id+'.asw', mimeType: 'text/plain', buffer: Buffer.from(native.source)});
    // A previous solve can still be enabled until the new File.text() resolves.
    await expect(page.locator('#filename')).toHaveText(entry.id+'.asw', {timeout: 120000});
    await expect(page.locator('#solve')).toBeEnabled({timeout: 120000});
    await page.locator('#node-file').setInputFiles({name: 'uniform.json', mimeType: 'application/json',
      buffer: Buffer.from(JSON.stringify({format: 'openswing-mesh', version: 1, panels: native.panels}))});
    await expect(page.locator('#node-table tbody tr')).toHaveCount(native.actual_elements+1, {timeout: 120000});
    await expect(page.locator('#node-spacing')).toHaveValue('uniform', {timeout: 120000});
    await expect(page.locator('#panels')).toHaveValue(String(native.spec.panels));
    await page.waitForFunction(() => !document.querySelector('#node-file').value);
    await expect(page.locator('#solve')).toBeEnabled({timeout: 120000});
    await page.locator('#mode').selectOption('modes');
    await page.locator('#modal-frame').selectOption('fixed');
    await page.locator('#modal-vacuum').uncheck();
    await page.locator('#modal-count').fill('24');
    await page.locator('#modal-method').selectOption('full_shift_invert');
    await page.locator('#modal-shift-real').fill('-0.1');
    await page.locator('#modal-shift-imag').fill('100');
    await page.locator('#modal-step').evaluate(e => e.closest('details').open = true);
    await page.locator('#modal-step').fill('0.00001');
    await page.locator('#speed').fill(String(native.condition.speed));
    await page.locator('#alpha').fill('0');
    await page.locator('#beta').fill('4.17');
    await page.locator('#aero-lag').check();
    await page.locator('#freeze-influences').uncheck();
    await page.locator('#stall').check();
    await page.locator('#atmosphere-settings').evaluate(e => e.open = true);
    await page.locator('#gravity-mode').selectOption('custom');
    await page.locator('#gravity-magnitude').fill('9.805');
    await page.locator('#density-mode').selectOption('custom');
    await page.locator('#density').fill('1.225');
    await page.locator('#mach-mode').selectOption('fixed');
    await page.locator('#pg-mach').fill('0');
    const start = performance.now();
    await page.locator('#solve').click();
    console.log('Solving', entry.id);
    await page.waitForFunction(() => !document.querySelector('#solve').disabled, {}, {timeout: 1200000});
    await expect(page.locator('#runtime-status')).toHaveText('Analysis converged');
    await expect(page.locator('#error')).toBeHidden();
    const seconds = (performance.now()-start)/1000;
    const pending = page.waitForEvent('download');
    await page.locator('#export-json').click();
    const data = await readFile(await (await pending).path());
    const result = JSON.parse(data);
    await writeFile(path.join(output, entry.id+'.json'), data);
    assert.deepEqual(result.software_provenance.modules, bundle.modules);
    assert.equal(result.request.source, native.source);
    assert.deepEqual(result.request.panels, native.panels);
    const condition = {...result.request.condition};
    assert.equal(condition.gravity_magnitude, 9.805);
    condition.gravity_magnitude = null;
    // The browser derives body gravity from Earth gravity at zero attitude;
    // the native reference prescribes the identical body vector explicitly.
    // An explicit zero selects local circulation, as does the kernel's absent
    // per-beam entry. Keep all nonzero basis changes a hard mismatch.
    for (const [beam, count] of Object.entries(condition.circulation_modes)) {
      assert(Object.hasOwn(native.panels.beams, beam));
      assert.equal(count, 0);
    }
    condition.circulation_modes = {};
    for (const [key, value] of Object.entries(condition)) assert.deepEqual(value, native.condition[key], 'Condition '+key);
    for (const [key, value] of Object.entries(entry.request.modes)) assert.deepEqual(result.request.modes[key], value, 'Modal option '+key);
    assert.deepEqual(result.base.gravity_body, native.gravity);
    assert.deepEqual(result.request.operating_constraints, []);
    const candidates = result.modes.filter(m => m.eigenvalue[1] > .1*2*Math.PI);
    const critical = candidates.reduce((a, b) => Math.abs(a.eigenvalue[0]) < Math.abs(b.eigenvalue[0]) ? a : b);
    assert.equal(critical.eigenvalue[0] < 0, entry.id.endsWith('negative'));
    await page.locator('#tab-modes').click();
    await page.locator('#modal-select').selectOption(String(result.modes.indexOf(critical)));
    await page.locator('#modal-quantity').selectOption('nodes.displacement.1');
    await expect(page.locator('#modal-plot polyline')).toHaveCount(2);
    await expect(page.locator('#modal-unit')).toContainText('Displacement y');
    await page.setViewportSize({width: 390, height: 844});
    await page.locator('#workspace-tab-plots').click();
    await expect(page.locator('#modal-plot')).toBeVisible();
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1));
    const csvPending = page.waitForEvent('download');
    await page.locator('#modal-output-csv').click();
    const csv = await readFile(await (await csvPending).path());
    assert(csv.toString().includes('Displacement y real'));
    await writeFile(path.join(output, entry.id+'.csv'), csv);
    await page.locator('#pane-modes').screenshot({path: path.join(output, entry.id+'-mobile.png')});
    await page.locator('#workspace-tab-output').click();
    await expect(page.locator('#export-json')).toBeVisible();
    status.cases.push({id: entry.id, seconds, result_sha256: hash(data), critical_root: critical.eigenvalue});
    await save();
    console.log('Computed and exported', status.cases.at(-1));
  }
  assert.deepEqual(status.page_errors, []);
  assert.deepEqual(status.network_errors, []);
  await writeFile(path.join(output, 'observed.json'), JSON.stringify(await page.evaluate(() => window.replayObserved), null, 2)+'\n');
  status.status = 'COMPUTED_PENDING_INDEPENDENT_COMPARISON';
  delete status.current;
} catch (error) {
  status.status = 'FAIL'; status.error = error.stack; process.exitCode = 1;
} finally {
  await save(); console.log(JSON.stringify(status)); await browser?.close();
}
