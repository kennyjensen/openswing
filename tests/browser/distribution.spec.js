import { test, expect } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';

test('extracted local bundle cold-starts, solves and exports without external requests', async ({ page, context }, info) => {
  test.skip(!process.env.OPENSWING_LOCAL_BUNDLE_TEST, 'Requires a separately served extracted local bundle.');
  test.setTimeout(240000);
  const requests = [], blocked = [];
  context.on('request', request => requests.push(request.url()));
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) return route.continue();
    blocked.push(url.href);
    return route.abort();
  });
  await page.addInitScript(() => {
    const get = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, ...args) {
      return type === 'webgl2' ? null : get.call(this, type, ...args);
    };
  });
  const metadata = await (await page.request.get('/distribution.json')).json();
  expect(metadata.kind).toBe('local');
  expect(metadata.validation).toBeNull();
  const source = await (await page.request.get('/openswing-source.zip')).body();
  expect(source.length).toBe(metadata.source.bytes);
  expect(createHash('sha256').update(source).digest('hex')).toBe(metadata.source.sha256);
  await page.goto('/');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#about-button').click();
  await expect(page.locator('#validation-archives')).toContainText('packaged separately');
  await expect(page.locator('#raw-validation-download')).toHaveCount(0);
  await page.locator('#close-about').click();
  await context.setOffline(true);
  await page.locator('#mode').selectOption('mounted');
  await page.evaluate(() => {
    for (const [selector, value, event] of [
      ['#panels', '4', 'change'], ['#alpha', '5', 'input'], ['[data-control="1"]', '3', 'input'],
    ]) {
      const input = document.querySelector(selector);
      input.value = value;
      input.dispatchEvent(new Event(event, { bubbles: true }));
    }
  });
  await page.locator('#solve').click();
  await expect(page.locator('#result-state')).toHaveText('Converged · mounted equilibrium');
  const download = page.waitForEvent('download');
  await page.locator('#export-json').click();
  const result = JSON.parse(await readFile(await (await download).path(), 'utf8'));
  expect(result.converged).toBe(true);
  expect(result.residual).toBeLessThan(1e-8);
  expect(result.CL).toBeGreaterThan(.3);
  expect(result.CL).toBeLessThan(.6);
  expect(result.structural_nodes).toBeGreaterThan(0);
  const pins = {};
  for (const name of Object.keys(result.software_provenance.modules)) {
    pins[name] = createHash('sha256').update(await readFile(`openswing/${name}`)).digest('hex');
  }
  expect(result.software_provenance.modules).toEqual(pins);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('#workspace-tab-plots').click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  await page.screenshot({ path: info.outputPath('local-mobile.png') });
  expect(blocked).toEqual([]);
  expect(requests.length).toBeGreaterThan(10);
  for (const url of requests) expect(new URL(url).origin).toBe(new URL(page.url()).origin);
  await writeFile(info.outputPath('local-bundle.json'), JSON.stringify({ metadata, requests, blocked, result }));
});

test('hosted build offers the available optional validation archive', async ({ page }, info) => {
  test.skip(!process.env.OPENSWING_HOSTED_URL, 'Requires a hosted distribution build.');
  const origin = process.env.OPENSWING_HOSTED_URL;
  await page.goto(origin);
  const metadata = await (await page.request.get(`${origin}/distribution.json`)).json();
  expect(metadata.kind).toBe('hosted');
  expect(metadata.validation.archives).toBeGreaterThan(0);
  await page.locator('#about-button').click();
  await expect(page.locator('#raw-validation-download')).toHaveAttribute('href', '/openswing-validation.zip');
  await expect(page.locator('#raw-validation-download')).toContainText(`${metadata.validation.archives} archives`);
  const response = await page.request.head(`${origin}/openswing-validation.zip`);
  expect(response.ok()).toBe(true);
  expect(Number(response.headers()['content-length'])).toBe(metadata.validation.bytes);
  await writeFile(info.outputPath('hosted-bundle.json'), JSON.stringify(metadata));
});
