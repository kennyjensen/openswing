import {test,expect} from '@playwright/test';
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {portableResult} from '../../web/solution-data.js';

async function exported(page,id='#export-json'){
  const pending=page.waitForEvent('download');await page.locator(id).click();
  return JSON.parse(await readFile(await(await pending).path(),'utf8'));
}

test('source feedback time response and project restore retain the physical measurements offline',async({page,context})=>{
  test.setTimeout(240000);
  const started=performance.now(),hash=b=>createHash('sha256').update(b).digest('hex'),modules={};
  for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py'))){
    modules[name]=hash(await readFile('openswing/'+name));
    for(const folder of ['public/kernel','dist/kernel'])expect(hash(await readFile(folder+'/'+name))).toBe(modules[name]);
  }
  const fixture=JSON.parse(await readFile('tests/fixtures/source-feedback-measurements.json','utf8'));
  const errors=[],failures=[],offlineRequests=[];let offline=false;
  page.on('pageerror',e=>errors.push(e.message));context.on('requestfailed',r=>failures.push(r.url()));
  context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))offlineRequests.push(r.url());});
  await page.addInitScript(()=>{
    window.feedbackSolves=[];const original=Worker.prototype.postMessage;
    Worker.prototype.postMessage=function(data,...rest){if(data.request?.action==='time')window.feedbackSolves.push(data.request);return original.call(this,data,...rest);};
  });
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles({name:'feedback-body.asw',mimeType:'text/plain',buffer:Buffer.from(fixture.source)});
  await expect(page.locator('#model-name')).toHaveText(fixture.source.match(/(?:^|\n)Name\s*\n([^\n]+)/)[1]);
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('time');
  await page.locator('#tab-nodes').click();
  await page.locator('#node-spacing').selectOption('uniform');await page.locator('#node-count').fill('4');
  await page.locator('#node-apply').click();await expect(page.locator('#node-status')).toContainText('5 nodes');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#structural-equations').selectOption('aswing-airflow');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#density-mode').selectOption('custom');await page.locator('#density').fill('1.2');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#speed').fill('23');await page.locator('#alpha').fill('0');await page.locator('#beta').fill('0');
  await page.locator('#stall').uncheck();await page.locator('#aero-lag').check();
  await page.locator('#powers [data-power="1"]').fill('0');
  await page.locator('#feedback-settings').evaluate(e=>e.open=true);
  await page.locator('#feedback-definition').fill(JSON.stringify(fixture.time.controller));
  await page.locator('#feedback-enabled').check();
  await page.locator('#time-frame').selectOption('free');
  await page.locator('#time-duration').fill('.02');await page.locator('#time-step').fill('.005');
  await page.locator('#time-order').selectOption('2');
  await page.locator('#forcing-settings').evaluate(e=>e.open=true);
  await page.locator('#time-forcing').fill(fixture.time.forcing);
  await context.setOffline(true);offline=true;
  await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:180000});
  await expect(page.locator('#error')).toBeHidden();
  const time=await exported(page);
  expect(time.request.source).toBe(fixture.source);
  expect(time.structural_operator).toBe(fixture.numerics.structural_operator);
  expect(time.controller.definition).toEqual(fixture.time.controller);
  expect(time.converged).toBe(true);expect(time.accepted_steps).toBe(4);
  expect(time.snapshots.at(-1).time).toBeCloseTo(.02,12);
  expect(time.snapshots.at(-1).nodes.at(-1).position[0]).toBeGreaterThan(2);
  await page.locator('#project-settings').evaluate(e=>e.open=true);
  await page.locator('#project-solution-name').fill('Source free-frame feedback');
  await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Computed solution saved.');
  await page.locator('#time-duration').fill('.04');
  await page.locator('#project-load-solution').click();
  await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');
  expect(await exported(page)).toEqual(portableResult(time));
  expect(Number(await page.locator('#time-duration').inputValue())).toBe(.02);
  expect(await page.evaluate(()=>window.feedbackSolves.length)).toBe(1);
  expect(errors).toEqual([]);expect(failures).toEqual([]);expect(offlineRequests).toEqual([]);
  if(process.env.OPENSWING_FEEDBACK_EVIDENCE){
    const folder=process.env.OPENSWING_FEEDBACK_EVIDENCE;await mkdir(folder,{recursive:true});
    const report={status:'PASS_OFFLINE_FEEDBACK_TIME',modules,errors,failures,offlineRequests,
      seconds:(performance.now()-started)/1000,scope:'Free-frame source feedback step, complete exported history and project save/restore.'};
    for(const [name,value] of Object.entries({time,project:await exported(page,'#project-export'),report}))
      await writeFile(path.join(folder,name+'.json'),JSON.stringify(value)+'\n');
  }
});
