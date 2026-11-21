import {test, expect} from '@playwright/test';
import {mkdir, readFile, writeFile, readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {portableResult} from '../../web/solution-data.js';

async function download(page, selector='#export-json') {
  const pending=page.waitForEvent('download');
  await page.locator(selector).click();
  return JSON.parse(await readFile(await (await pending).path(),'utf8'));
}

test('source steady trim solves offline and preserves targets through project restoration',async({page,context})=>{
  test.setTimeout(240000);
  const began=performance.now(), modules={}, hash=b=>createHash('sha256').update(b).digest('hex');
  for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py'))){
    modules[name]=hash(await readFile('openswing/'+name));
    for(const folder of ['public/kernel','dist/kernel'])expect(hash(await readFile(folder+'/'+name))).toBe(modules[name]);
  }
  const errors=[], failures=[], offlineRequests=[];
  let offline=false;
  page.on('pageerror',e=>errors.push(e.message));
  context.on('requestfailed',r=>failures.push(r.url()));
  context.on('request',r=>{if(offline&&/^https?:/.test(r.url()))offlineRequests.push(r.url());});
  await page.addInitScript(()=>{
    window.trimSolves=[];const send=Worker.prototype.postMessage;
    Worker.prototype.postMessage=function(data,...rest){if(data.request?.action==='solve')window.trimSolves.push(data.request);return send.call(this,data,...rest);};
  });
  await page.goto('/');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('instrumented-oscillator');
  await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('mounted');
  await page.locator('#structural-equations').selectOption('aswing-coupled');
  await expect(page.locator('#mode')).toHaveValue('mounted');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#operating-settings').evaluate(e=>e.open=true);
  await page.locator('#add-constraint').click();
  await page.locator('.constraint-variable').selectOption('power.1');
  await page.locator('.constraint-quantity').selectOption('force.y');
  await page.locator('.constraint-row input').fill('5');
  await context.setOffline(true);offline=true;
  const solve=async()=>{
    await page.locator('#solve').click();
    await expect(page.locator('#runtime-status')).toHaveText('Analysis converged');
    await expect(page.locator('#error')).toBeHidden();
    return download(page);
  };
  const first=await solve();
  expect(first.operating_values['power.1']).toBeCloseTo(5,7);
  expect(first.nodes.at(-1).position[1]).toBeCloseTo(2.01,9);
  expect(first.numerics.structural_operator).toBe('drela-steady-coupled-v1');
  await page.locator('#project-settings').evaluate(e=>e.open=true);
  await page.locator('#project-solution-name').fill('Source force trim');
  await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Computed solution saved.');
  const project=await download(page,'#project-export');
  await page.locator('#alpha').fill('3');
  await page.locator('#project-load-solution').click();
  await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');
  await expect(page.locator('#structural-equations')).toHaveValue('aswing-coupled');
  await expect(page.locator('.constraint-variable')).toHaveValue('power.1');
  await expect(page.locator('.constraint-row input')).toHaveValue('5');
  expect(await download(page)).toEqual(portableResult(first));
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);
  await page.locator('#equilibrium-use').click();
  await page.locator('.constraint-row input').fill('8');
  const second=await solve();
  expect(second.operating_values['power.1']).toBeCloseTo(8,7);
  expect(second.nodes.at(-1).position[1]).toBeCloseTo(2.016,9);
  expect(second.request.initial_state).toBeTruthy();
  expect(second.operating_constraints[0].target).toBe(8);
  expect(await page.evaluate(()=>window.trimSolves.length)).toBe(2);
  expect(errors).toEqual([]);expect(failures).toEqual([]);expect(offlineRequests).toEqual([]);
  if(process.env.OPENSWING_TRIM_EVIDENCE){
    const folder=process.env.OPENSWING_TRIM_EVIDENCE;
    await mkdir(folder,{recursive:true});
    for(const [name,value] of Object.entries({first,second,project,report:{status:'PASS_OFFLINE_UI',
      scope:'Two full source steady engine trims, project save/restore and saved-equilibrium target change.',
      errors,failures,offlineRequests,modules,seconds:(performance.now()-began)/1000}}))await writeFile(path.join(folder,name+'.json'),JSON.stringify(value)+'\n');
  }
});
