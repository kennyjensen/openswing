import {writeFile} from 'node:fs/promises';
import {test, expect} from './static-app.js';

test('fresh production page displays Daedalus and runs the first analysis offline', async ({page, context, baseURL}, info) => {
  if (!process.env.OPENSWING_STATIC_APP) test.skip(true, 'Measure the built static application.');
  test.setTimeout(180000);
  const errors = [];
  const requests = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => requests.push(new URL(request.url()).pathname));
  // Isolate the startup path from optional external widgets and analytics.
  await page.route('**/*', route => new URL(route.request().url()).origin === new URL(baseURL).origin
    ? route.continue()
    : route.abort());
  await page.addInitScript(() => {
    const times = {workerStages:[]};
    window.startupTimes = times;
    const BrowserWorker = window.Worker;
    window.Worker = class extends BrowserWorker {
      constructor(...args) {
        super(...args);
        times.workerCreatedMs = performance.now();
        this.addEventListener('message', ({data}) => {
          if (data.type === 'status' && times.kernelReadyMs === undefined) {
            times.workerStages.push({ms:performance.now(), message:data.message});
          } else if (data.type === 'ready') {
            times.kernelReadyMs = performance.now();
          } else if (data.id === times.inspectRequestId && data.result) {
            times.inspectReplyMs = performance.now();
          }
        });
      }

      postMessage(message, ...args) {
        if (message.request?.action === 'inspect' && times.inspectRequestId === undefined) {
          times.inspectRequestId = message.id;
          times.inspectSentMs = performance.now();
        }
        return super.postMessage(message, ...args);
      }
    };
    const observer = new MutationObserver(() => {
      if (times.previewMs === undefined
          && document.querySelector('#geometry-label')?.textContent === 'Daedalus HPA'
          && document.querySelector('#viewport canvas')) {
        times.previewMs = performance.now();
      }
      const solve = document.querySelector('#solve');
      if (solve && !solve.disabled) {
        times.analysisReadyMs = performance.now();
        observer.disconnect();
      }
    });
    observer.observe(document, {childList:true, subtree:true, attributes:true, attributeFilter:['disabled']});
  });
  await page.goto('/', {waitUntil:'domcontentloaded'});
  await expect(page.locator('#viewport canvas')).toBeVisible();
  await expect(page.locator('#solve')).toBeEnabled({timeout:90000});
  await expect(page.locator('#runtime-status')).toHaveText('Configuration ready');

  const times = await page.evaluate(() => window.startupTimes);
  expect(times.previewMs).toBeGreaterThan(0);
  expect(times.analysisReadyMs).toBeGreaterThan(times.previewMs);
  expect(times.inspectSentMs).toBeGreaterThanOrEqual(times.workerCreatedMs);
  expect(times.kernelReadyMs).toBeGreaterThanOrEqual(times.workerCreatedMs);
  expect(times.inspectReplyMs).toBeGreaterThanOrEqual(Math.max(times.kernelReadyMs, times.inspectSentMs));
  expect(times.analysisReadyMs).toBeGreaterThanOrEqual(times.inspectReplyMs);
  expect(requests).not.toContain('/examples/dae.asw');
  expect(requests.filter(path => path.startsWith('/kernel/'))).toEqual([
    expect.stringMatching(/^\/kernel\/sources-[0-9a-f]{64}\.json$/),
  ]);
  expect(errors).toEqual([]);
  const measurement = {
    ...times,
    kernelStartupMs:times.kernelReadyMs-times.workerCreatedMs,
    inspectMs:times.inspectReplyMs-Math.max(times.kernelReadyMs, times.inspectSentMs),
    finalizeUiMs:times.analysisReadyMs-times.inspectReplyMs,
  };
  const report = info.outputPath('startup.json');
  await writeFile(report, JSON.stringify(measurement, null, 2));

  await context.setOffline(true);
  const solveStart = performance.now();
  await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged', {timeout:90000});
  measurement.firstSolveMs = performance.now()-solveStart;
  await expect(page.locator('#result-state')).toHaveClass(/\bsolved\b/);
  await expect(page.locator('#error')).toBeHidden();
  expect(errors).toEqual([]);
  await writeFile(report, JSON.stringify(measurement, null, 2));
  console.log(JSON.stringify(measurement));
});
