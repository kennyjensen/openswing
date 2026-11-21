import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';

test.use({launchOptions:{executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,
  args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-webgl','--js-flags=--max-old-space-size=192']}});

const ready=async page=>{await expect(page.locator('#solve')).toBeEnabled();};
async function download(page,selector){
  const pending=page.waitForEvent('download');await page.locator(selector).click();
  return JSON.parse(await readFile(await(await pending).path(),'utf8'));
}
async function loadProgress(page,value){
  await page.locator('#steady-progress-file').setInputFiles({name:'progress.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(value))});
  await expect(page.locator('#runtime-status')).toHaveText('Case inputs restored');await ready(page);
}
async function advance(page,first=false){
  await page.locator(first?'#steady-progress-start':'#steady-progress-next').click();
  await expect(page.locator('#runtime-status')).toHaveText(/^(Equilibrium paused at|Analysis converged)/);
  await ready(page);await expect(page.locator('#error')).toBeHidden();
}

test('real worker progress survives reload, rejects stale/corrupt resumes and finishes the exact axial equilibrium',async({page},info)=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
    window.progressRequests=[];const send=Worker.prototype.postMessage;
    Worker.prototype.postMessage=function(data,...rest){if(data.request?.action==='solve')window.progressRequests.push(data.request);return send.call(this,data,...rest);};
  });
  await page.goto('/');await ready(page);
  await page.locator('#file').setInputFiles('tests/fixtures/steady-progress.asw');
  await expect(page.locator('#model-name')).toHaveText('Resumable axial equilibrium');await ready(page);
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await ready(page);
  await page.locator('#mode').selectOption('structural');
  await page.locator('#structural-equations').selectOption('aswing-section');await ready(page);
  await page.locator('#static-gravity-mode').selectOption('custom');
  await page.locator('#static-gravity-x').fill('0');await page.locator('#static-gravity-y').fill('1');await page.locator('#static-gravity-z').fill('0');
  await page.locator('#steady-progress-settings').evaluate(e=>e.open=true);
  await advance(page,true);
  await expect(page.locator('#result-state')).toHaveText('Unfinished equilibrium');
  for(const selector of ['#export-json','#csv','#equilibrium-save','#equilibrium-use'])await expect(page.locator(selector)).toBeDisabled();
  const first=await download(page,'#steady-progress-save');
  expect(first.checkpoint.load_fraction).toBeGreaterThan(0);expect(first.checkpoint.load_fraction).toBeLessThan(1);
  expect(first.checkpoint.physical_residual).toBeLessThanOrEqual(1e-12);
  expect(first.request.numerics.structural_operator).toBe('drela-steady-section-v1');
  await page.locator('#panels').fill('5');
  await expect(page.locator('#steady-progress-start')).toBeDisabled();
  await expect(page.locator('#steady-progress-next')).toBeDisabled();
  await expect(page.locator('#steady-progress-save')).toBeEnabled();
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await ready(page);
  await expect(page.locator('#steady-progress-next')).toBeEnabled();
  const solves=await page.evaluate(()=>window.progressRequests.length);
  await page.locator('#static-gravity-y').fill('2');await page.locator('#steady-progress-next').click();
  await expect(page.locator('#error')).toContainText('Solve inputs changed');
  expect(await page.evaluate(()=>window.progressRequests.length)).toBe(solves);
  expect(await download(page,'#steady-progress-save')).toEqual(first);
  await page.locator('#steady-progress-restore').click();
  await expect(page.locator('#runtime-status')).toHaveText('Case inputs restored');await ready(page);
  await expect(page.locator('#static-gravity-y')).toHaveValue('1');
  expect(await page.evaluate(()=>window.progressRequests.length)).toBe(solves);

  await page.setViewportSize({width:390,height:844});
  await page.locator('#workspace-tab-settings').click();
  await expect(page.locator('#steady-progress-next')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#steady-progress-settings').screenshot({path:info.outputPath('mobile-progress.png')});
  await page.setViewportSize({width:1440,height:1000});
  await page.reload();await ready(page);
  await page.locator('#steady-progress-settings').evaluate(e=>e.open=true);
  await loadProgress(page,first);
  expect(await page.evaluate(()=>window.progressRequests.length)).toBe(0);
  await expect(page.locator('#mode')).toHaveValue('structural');
  await expect(page.locator('#structural-equations')).toHaveValue('aswing-section');
  await expect(page.locator('#static-gravity-y')).toHaveValue('1');
  expect(await download(page,'#steady-progress-save')).toEqual(first);

  // Terminate after dispatch, before the worker can return an accepted step.
  await page.evaluate(()=>{document.querySelector('#steady-progress-next').click();document.querySelector('#cancel').click();});
  await ready(page);await expect(page.locator('#cancel')).toBeHidden();
  expect(await download(page,'#steady-progress-save')).toEqual(first);

  const corrupt=structuredClone(first);corrupt.checkpoint.coordinates[0]+=.01;
  await loadProgress(page,corrupt);await page.locator('#steady-progress-next').click();
  await expect(page.locator('#error')).toContainText('checksum');await ready(page);
  await expect(page.locator('#export-json')).toBeDisabled();
  expect(await download(page,'#steady-progress-save')).toEqual(corrupt);
  await loadProgress(page,first);
  const fractions=[first.checkpoint.load_fraction];
  for(let i=0;i<12;i++){
    await advance(page);
    if(await page.locator('#steady-progress-save').isDisabled())break;
    const saved=await download(page,'#steady-progress-save');
    expect(saved.checkpoint.load_fraction).toBeGreaterThan(fractions.at(-1));
    fractions.push(saved.checkpoint.load_fraction);
  }
  await expect(page.locator('#steady-progress-status')).toContainText('Full-load equilibrium converged');
  await expect(page.locator('#equilibrium-save')).toBeEnabled();await expect(page.locator('#equilibrium-use')).toBeEnabled();
  const resumed=await download(page,'#export-json');
  expect(resumed.converged).toBe(true);expect(resumed.continuation_status).toBe('complete');
  expect(resumed.residual).toBeLessThanOrEqual(1e-12);
  expect(resumed.nodes.at(-1).position[1]).toBeCloseTo(2.004,11);
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged');await ready(page);
  const ordinary=await download(page,'#export-json');
  expect(ordinary.nodes).toEqual(resumed.nodes);expect(ordinary.elements).toEqual(resumed.elements);
  expect(ordinary.equilibrium_state).toEqual(resumed.equilibrium_state);
  expect(errors).toEqual([]);
  await writeFile(info.outputPath('report.json'),JSON.stringify({status:'PASS',fractions,first,resumed,ordinary,errors},null,2)+'\n');
});

test('mounted source-airflow jobs retain circulation and recover the ordinary coupled equilibrium',async({page},info)=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await ready(page);
  await page.locator('#file').setInputFiles('tests/fixtures/steady-progress-mounted.asw');
  await expect(page.locator('#model-name')).toHaveText('Synthetic source joints');await ready(page);
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await ready(page);
  await page.locator('#mode').selectOption('mounted');
  await page.locator('#structural-equations').selectOption('aswing-airflow');await ready(page);
  await page.locator('#speed').fill('8');await page.locator('#alpha').fill('5');await page.locator('#beta').fill('1');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#steady-progress-settings').evaluate(e=>e.open=true);
  await advance(page,true);
  const first=await download(page,'#steady-progress-save');
  expect(first.request.condition.speed).toBe(8);expect(first.request.condition.alpha).toBe(5);
  expect(first.request.numerics.structural_operator).toBe('drela-moving-airflow-v1');
  const layout=first.checkpoint.context.coordinates;
  expect(layout.operating_start).toBeGreaterThan(layout.gamma_start);
  expect(first.checkpoint.coordinates.slice(layout.gamma_start,layout.operating_start).some(v=>Math.abs(v)>1e-6)).toBe(true);
  await loadProgress(page,first);
  const fractions=[first.checkpoint.load_fraction];
  for(let i=0;i<12;i++){
    await advance(page);
    if(await page.locator('#steady-progress-save').isDisabled())break;
    const saved=await download(page,'#steady-progress-save');
    expect(saved.checkpoint.load_fraction).toBeGreaterThan(fractions.at(-1));fractions.push(saved.checkpoint.load_fraction);
  }
  await expect(page.locator('#steady-progress-status')).toContainText('Full-load equilibrium converged');
  const resumed=await download(page,'#export-json');
  expect(resumed.residual).toBeLessThanOrEqual(1e-12);expect(Math.abs(resumed.CL)).toBeGreaterThan(.01);
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged');await ready(page);
  const ordinary=await download(page,'#export-json');
  for(const name of ['CL','CD','CDi','Cm'])expect(resumed[name]).toBeCloseTo(ordinary[name],10);
  expect(resumed.nodes.length).toBe(ordinary.nodes.length);
  for(let i=0;i<resumed.nodes.length;i++)for(let j=0;j<3;j++)expect(resumed.nodes[i].position[j]).toBeCloseTo(ordinary.nodes[i].position[j],10);
  expect(errors).toEqual([]);
  await writeFile(info.outputPath('report.json'),JSON.stringify({status:'PASS',fractions,first,resumed,ordinary,errors},null,2)+'\n');
});
