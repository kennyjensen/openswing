import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const sections = ['editor', 'settings', 'plots', 'output'];
// Same established software-driver selection as the WebGL acceptance suite.
const mesa = process.env.OPENSWING_WEBGL_DRIVER === 'mesa';
test.use({ viewport: { width: 390, height: 844 }, launchOptions: {
  executablePath: process.env.OPENSWING_CHROMIUM_EXECUTABLE,
  args: mesa ? ['--no-sandbox', '--use-gl=angle', '--use-angle=vulkan', '--use-vulkan=native',
    '--ignore-gpu-blocklist', '--enable-features=Vulkan', '--disable-gpu-compositing'] :
    ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader-webgl', '--enable-unsafe-swiftshader'],
} });

async function selected(page, name) {
  await expect(page.locator(`#workspace-tab-${name}`)).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator(`#workspace-${name}`)).toBeVisible();
  for (const other of sections.filter(value => value !== name)) {
    await expect(page.locator(`#workspace-tab-${other}`)).toHaveAttribute('aria-selected', 'false');
    await expect(page.locator(`#workspace-${other}`)).toBeHidden();
  }
  await expect(page.locator('#analysis-actions #solve')).toBeVisible();
  await expect(page.locator('#analysis-actions #runtime-status')).toBeVisible();
}

async function navigate(page, name) {
  await page.locator(`#workspace-tab-${name}`).click();
  await selected(page, name);
}

async function noOverflow(page) {
  await expect.poll(() => page.evaluate(() => ({
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
    viewport: innerWidth,
  }))).toMatchObject({ viewport: page.viewportSize().width });
  expect(await page.evaluate(() => Math.max(document.documentElement.scrollWidth,
    document.body.scrollWidth) <= innerWidth + 1)).toBe(true);
}

async function sameCanvas(page, original) {
  await expect(page.locator('#viewport canvas')).toHaveCount(1);
  expect(await page.locator('#viewport canvas').evaluate((canvas, first) => canvas === first, original)).toBe(true);
}

async function download(page, selector) {
  await expect(page.locator(selector)).toBeEnabled();
  const event = page.waitForEvent('download');
  await page.locator(selector).click();
  return readFile(await (await event).path(), 'utf8');
}

async function healthyDrawing(page, testInfo, name) {
  const canvas = page.locator('#viewport canvas');
  await canvas.scrollIntoViewIfNeeded();
  const state = await canvas.evaluate(element => {
    const renderer = element.dataset.renderer;
    const gl = renderer === 'webgl' ? element.getContext('webgl2') : null;
    return { renderer, width: element.width, height: element.height,
      lost: gl ? gl.isContextLost() : false, error: gl ? gl.getError() : 0 };
  });
  expect(['webgl', 'canvas2d']).toContain(state.renderer);
  expect(state.width).toBeGreaterThan(100);
  expect(state.height).toBeGreaterThan(100);
  expect(state.lost).toBe(false);
  expect(state.error).toBe(0);
  // Inspect the compositor image; WebGL need not preserve its drawing buffer.
  const bytes = await canvas.screenshot({ path: testInfo.outputPath(`${name}.png`) });
  const colored = await page.evaluate(async encoded => {
    const image = new Image();
    image.src = `data:image/png;base64,${encoded}`;
    await image.decode();
    const copy = document.createElement('canvas');
    copy.width = image.width; copy.height = image.height;
    const context = copy.getContext('2d');
    context.drawImage(image, 0, 0);
    const pixels = context.getImageData(0, 0, copy.width, copy.height).data;
    let count = 0;
    for (let i = 0; i < pixels.length; i += 4) {
      const [r, g, b] = pixels.subarray(i, i + 3);
      if ((r > 95 && r > 1.4 * g && r > 1.4 * b) || (r > 170 && g > 130 && b < 160)) count++;
    }
    return count;
  }, bytes.toString('base64'));
  expect(colored).toBeGreaterThan(50);
  await testInfo.attach(`${name}-rendering`, {
    body: JSON.stringify({ ...state, colored_pixels: colored }), contentType: 'application/json',
  });
}

async function stackedPlots(page) {
  await expect(page.locator('#workspace-plots #viewport')).toBeVisible();
  await expect(page.locator('#workspace-plots #pane-loading')).toBeVisible();
  await expect(page.locator('#workspace-plots #pane-modes')).toBeVisible();
  const boxes = await Promise.all(['#viewport', '#pane-loading', '#pane-modes'].map(id => page.locator(id).boundingBox()));
  expect(boxes.every(Boolean)).toBe(true);
  expect(boxes[0].y + boxes[0].height).toBeLessThanOrEqual(boxes[1].y + 1);
  expect(boxes[1].y + boxes[1].height).toBeLessThanOrEqual(boxes[2].y + 1);
}

test('mobile workspaces preserve one live model, solve and export through navigation and resize', async ({ page, context }, testInfo) => {
  test.setTimeout(180000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => {
    // Observe real requests without replacing the worker or numerical solve.
    window.mobileSolveRequests = 0;
    const post = Worker.prototype.postMessage;
    Worker.prototype.postMessage = function (message, ...arguments_) {
      if (message?.request?.action === 'solve') window.mobileSolveRequests++;
      return post.call(this, message, ...arguments_);
    };
  });
  await page.goto('/');
  await expect(page.locator('#solve')).toBeEnabled();
  await selected(page, 'plots');
  await expect(page.locator('#workspace-tabs')).toHaveAttribute('role', 'tablist');
  await stackedPlots(page);
  const canvas = await page.locator('#viewport canvas').elementHandle();
  const editor = await page.locator('#editor').elementHandle();
  const solve = await page.locator('#solve').elementHandle();

  await navigate(page, 'editor');
  await expect(page.locator('#workspace-editor #file')).toHaveCount(1);
  await expect(page.locator('#workspace-editor #project-settings')).toHaveCount(1);
  await page.locator('#file').setInputFiles('examples/rectangular.asw');
  await expect(page.locator('#model-name')).toHaveText('Rectangular research wing');
  await expect(page.locator('#solve')).toBeEnabled();
  const source = (await page.locator('#editor').inputValue()).replace('Rectangular research wing', 'Mobile edited wing');
  await page.locator('#editor').fill(source);
  await expect(page.locator('#solve')).toBeDisabled();
  await navigate(page, 'settings');
  await page.locator('#speed').fill('37');
  await page.locator('#alpha').fill('4');
  await page.locator('#mode').selectOption('rigid');
  await navigate(page, 'output');
  await navigate(page, 'editor');
  await expect(page.locator('#editor')).toHaveValue(source);
  await page.locator('#apply').click();
  await expect(page.locator('#model-name')).toHaveText('Mobile edited wing');
  await expect(page.locator('#solve')).toBeEnabled();
  await navigate(page, 'settings');
  await expect(page.locator('#speed')).toHaveValue('37');
  await expect(page.locator('#alpha')).toHaveValue('4');
  await page.locator('#panels').fill('4');
  await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();

  // Moving configuration controls out of the desktop sidebar must not remove
  // them from a saved case's numerical settings.
  await navigate(page, 'editor');
  await page.locator('#project-settings').evaluate(element => { element.open = true; });
  await page.locator('#project-case-name').fill('Mobile numerical inputs');
  await page.locator('#project-add').click();
  await expect(page.locator('#project-status')).toContainText('New case saved');
  const saved = JSON.parse(await download(page, '#project-export'));
  const savedCase = saved.cases.find(item => item.name === 'Mobile numerical inputs');
  expect(savedCase).toBeTruthy();
  expect(savedCase.configuration.source).toBe(source);
  expect(savedCase.configuration.mesh).toBe(4);
  expect(savedCase.configuration.fields).toMatchObject({ speed: '37', alpha: '4', mode: 'rigid' });
  await testInfo.attach('mobile-saved-case', { body: JSON.stringify(saved), contentType: 'application/json' });

  // Run remains global, but invalid operating inputs in a hidden Settings tab
  // must be revealed and rejected before sending any solve to the real worker.
  for (const [id, invalid, valid] of [['alpha', '100', '4'], ['speed', '0', '37']]) {
    await navigate(page, 'settings');
    await page.locator(`#${id}`).fill(invalid);
    expect(await page.locator(`#${id}`).evaluate(element => element.checkValidity())).toBe(false);
    await navigate(page, 'plots');
    const requests = await page.evaluate(() => window.mobileSolveRequests);
    await page.locator('#solve').click();
    await selected(page, 'settings');
    await expect(page.locator('#error')).toContainText('Enter a valid value');
    await expect(page.locator('#cancel')).toBeHidden();
    expect(await page.evaluate(() => window.mobileSolveRequests)).toBe(requests);
    await page.locator(`#${id}`).fill(valid);
    await page.locator('#close-error').click();
  }
  // A visible but unrelated auxiliary sweep input is not part of rigid setup.
  await navigate(page, 'plots');
  await page.locator('#stability-settings').evaluate(element => { element.open = true; });
  await page.locator('#stability-depth').fill('-1');
  expect(await page.locator('#stability-depth').evaluate(element => element.checkValidity())).toBe(false);
  await context.setOffline(true);
  await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged', { timeout: 90000 });
  await expect(page.locator('#error')).toBeHidden();
  await navigate(page, 'plots');
  await stackedPlots(page);
  await expect(page.locator('#plot svg')).toBeVisible();
  await navigate(page, 'output');
  await expect(page.locator('#workspace-output #pane-report')).toContainText('RIGID STEADY ANALYSIS');
  await expect(page.locator('#workspace-output #heading-report')).toHaveText('Solver report');
  await expect(page.locator('#heading-report + #pane-report')).toBeVisible();
  await expect(page.locator('#pane-report #heading-report')).toHaveCount(0);
  const result = JSON.parse(await download(page, '#export-json'));
  expect(result.converged).toBe(true);
  expect(result.residual).toBeLessThan(1e-8);
  expect(result.request.mode).toBe('rigid');
  expect(result.request.condition.speed).toBe(37);
  expect(result.request.condition.alpha).toBe(4);
  expect(result.request.source).toContain('Mobile edited wing');
  expect(result.strips.length).toBeGreaterThan(0);
  expect(await page.evaluate(() => window.mobileSolveRequests)).toBe(1);
  await testInfo.attach('rigid-result', { body: JSON.stringify(result), contentType: 'application/json' });

  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    for (const name of sections) {
      await navigate(page, name);
      await noOverflow(page);
      await sameCanvas(page, canvas);
    }
  }
  // Standard roving focus works with automatic or explicit Enter activation.
  await page.locator('#workspace-tab-plots').focus();
  await page.keyboard.press('ArrowLeft');
  await expect(page.locator('#workspace-tab-settings')).toBeFocused();
  await page.keyboard.press('Enter');
  await selected(page, 'settings');
  await page.keyboard.press('Home');
  await expect(page.locator('#workspace-tab-editor')).toBeFocused();
  await page.keyboard.press('Enter');
  await selected(page, 'editor');
  await page.keyboard.press('End');
  await expect(page.locator('#workspace-tab-output')).toBeFocused();
  await page.keyboard.press('Enter');
  await selected(page, 'output');
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('#workspace-tab-editor')).toBeFocused();
  await page.keyboard.press('Enter');
  await selected(page, 'editor');
  await expect(page.locator('#workspace-tabs [role="tab"][tabindex="0"]')).toHaveCount(1);

  for (const width of [1440, 390, 1024, 320]) {
    await page.setViewportSize({ width, height: 900 });
    if (width > 720) {
      await expect(page.locator('#workspace-tabs')).toBeHidden();
      await expect(page.locator('#mobile-workbench')).toBeHidden();
      await expect(page.locator('.tabbar')).toBeVisible();
      await expect(page.locator('#tab-editor')).toBeFocused();
      await page.locator('#tab-editor').click();
      await expect(page.locator('#editor')).toBeVisible();
    } else {
      await expect(page.locator('#workspace-tab-editor')).toBeFocused();
      await navigate(page, 'editor');
      await expect(page.locator('#workspace-editor #editor')).toBeVisible();
    }
    await expect(page.locator('#editor')).toHaveValue(source);
    await expect(page.locator('#speed')).toHaveValue('37');
    await sameCanvas(page, canvas);
    expect(await page.locator('#editor').evaluate((element, original) => element === original, editor)).toBe(true);
    expect(await page.locator('#solve').evaluate((element, original) => element === original, solve)).toBe(true);
    await noOverflow(page);
  }
  // Existing detail-tab callers must route the mobile workspace without hiding
  // neighboring plot cards; computed-solution restore uses this same path.
  await page.locator('#tab-modes').evaluate(element => element.click());
  await selected(page, 'plots');
  await stackedPlots(page);
  await page.locator('#top-view').click();
  await healthyDrawing(page, testInfo, 'rigid-mobile-after-roundtrips');
  await navigate(page, 'output');
  expect(JSON.parse(await download(page, '#export-json'))).toEqual(result);
  expect(errors).toEqual([]);
});

test('mobile Plots stack actual vacuum eigenmodes with geometry and preserve exported modes', async ({ page, context }, testInfo) => {
  test.setTimeout(200000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.locator('#solve')).toBeEnabled();
  const canvas = await page.locator('#viewport canvas').elementHandle();
  await navigate(page, 'editor');
  // Same independent damped spring/mass oracle as modes.spec.js: m=2,
  // EA/L=500, constitutive relaxation .02, eigenvalues -2.5 +/- i sqrt(243.75).
  const source = 'Name\nMobile vacuum oscillator\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.80665 1.225 340.294\nEnd\nReference\n2 1 2\nEnd\nGround\n1 0 0\nEnd\nWeight\n1 2 0 2 0 19.6133\nEnd\nBeam 1\nAxial spring\nt y EA tdeps\n0 0 1000 .02\n2 2 1000 .02\nEnd\n';
  await page.locator('#file').setInputFiles({ name: 'mobile-oscillator.asw', mimeType: 'text/plain', buffer: Buffer.from(source) });
  await expect(page.locator('#model-name')).toHaveText('Mobile vacuum oscillator');
  await navigate(page, 'settings');
  await page.locator('#panels').fill('4');
  await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('modes');
  await page.locator('#modal-vacuum').check();
  await page.locator('#modal-count').fill('2');
  await page.locator('#modal-method').selectOption('shift_invert');
  await page.locator('#atmosphere-settings').evaluate(element => { element.open = true; });
  await page.locator('#gravity-mode').selectOption('custom');
  await page.locator('#gravity-magnitude').fill('0');
  await context.setOffline(true);
  await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged', { timeout: 150000 });
  await expect(page.locator('#error')).toBeHidden();
  await selected(page, 'plots');
  await stackedPlots(page);
  await expect(page.locator('#modal-roots svg')).toBeVisible();
  await page.locator('#modal-quantity').selectOption('nodes.displacement.1');
  await expect(page.locator('#modal-plot polyline')).toHaveCount(2);
  await expect(page.locator('#modal-summary')).toContainText('Vacuum');
  await navigate(page, 'output');
  await expect(page.locator('#workspace-output #heading-report')).toHaveText('Solver report');
  await expect(page.locator('#heading-report + #pane-report')).toBeVisible();
  const result = JSON.parse(await download(page, '#export-json'));
  expect(result.analysis).toBe('eigenmodes');
  expect(result.diagnostics.method).toBe('shift_invert');
  expect(result.base.gravity_body).toEqual([0, 0, 0]);
  expect(result.base.mass_properties.mass).toBeCloseTo(2, 10);
  expect(result.modes).toHaveLength(2);
  for (const mode of result.modes) {
    expect(mode.eigenvalue[0]).toBeCloseTo(-2.5, 6);
    expect(Math.abs(mode.eigenvalue[1])).toBeCloseTo(Math.sqrt(250 - 6.25), 6);
  }
  await navigate(page, 'plots');
  const csv = await download(page, '#modal-output-csv');
  expect(csv).toContain('Displacement y imaginary');
  expect(csv.split('\n').length).toBeGreaterThan(4);
  await page.locator('#modal-phase').fill('90');
  await page.locator('#modal-play').click();
  await expect(page.locator('#modal-play')).toHaveText('Pause');
  await expect.poll(() => page.locator('#modal-phase').inputValue()).not.toBe('90');
  await navigate(page, 'output');
  await expect(page.locator('#modal-play')).toHaveText('Play phase');
  expect(JSON.parse(await download(page, '#export-json'))).toEqual(result);
  await page.setViewportSize({ width: 320, height: 844 });
  await navigate(page, 'plots');
  await stackedPlots(page);
  await noOverflow(page);
  await sameCanvas(page, canvas);
  await page.locator('#fit').click();
  await healthyDrawing(page, testInfo, 'modal-mobile');
  await testInfo.attach('modal-result', { body: JSON.stringify(result), contentType: 'application/json' });
  expect(errors).toEqual([]);
});
