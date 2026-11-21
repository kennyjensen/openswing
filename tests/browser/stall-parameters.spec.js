import {test,expect} from '@playwright/test';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const mesa=process.env.OPENSWING_WEBGL_DRIVER==='mesa';
test.use({launchOptions:{executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,
  args:mesa?['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native',
    '--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']:
    ['--no-sandbox','--use-gl=angle','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader']}});
const data=async(page,id='#export-json')=>{const d=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await d).path(),'utf8'));};
async function solve(page,message='Analysis converged'){
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText(message,{timeout:180000});
  await expect(page.locator('#error')).toBeHidden();return data(page);
}
async function open(page,panels=16){
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled({timeout:180000});
  await page.locator('#example').selectOption('stall-branch');await expect(page.locator('#filename')).toHaveText('stall-branch.asw');
  await expect(page.locator('#solve')).toBeEnabled({timeout:180000});await page.locator('#mode').selectOption('rigid');
  if(await page.locator('#panels').inputValue()!==String(panels)){
    await page.locator('#panels').fill(String(panels));await page.locator('#panels').press('Tab');
  }
  await expect(page.locator('#solve')).toBeEnabled({timeout:180000});await page.locator('#speed').fill('47.9');await page.locator('#alpha').fill('25');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#stall-settings').evaluate(e=>e.open=true);
  await expect(page.locator('#stall-factor')).toHaveValue('40');await expect(page.locator('#stall-width')).toHaveValue('0.05');
}

test('stall parameters change verified loads and survive cases and computed archives offline',async({page,context})=>{
  test.setTimeout(900000);await mkdir('test-results',{recursive:true});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const study=JSON.parse(await readFile('docs/validation/stall-parameters.json','utf8'));
  await open(page);await context.setOffline(true);const actuals=[];
  for(const item of study.finite){
    const s=item.specification;console.log('Stall browser case',s.factor,s.width);
    await page.locator('#stall-factor').fill(String(s.factor));await page.locator('#stall-width').fill(String(s.width));
    await expect(page.locator('#export-json')).toBeDisabled();const result=await solve(page);
    expect(result.condition.stall_factor).toBe(s.factor);expect(result.condition.stall_width).toBe(s.width);
    expect(result.condition.stall).toBe(true);expect(result.residual).toBeLessThan(1e-8);
    for(const k of ['CL','CD','CDp','Cm'])expect(Math.abs(result[k]-item.result.coefficients[k])).toBeLessThan(2e-7);
    for(const [name,hash] of Object.entries(result.software_provenance.modules))expect(createHash('sha256').update(await readFile('openswing/'+name)).digest('hex')).toBe(hash);
    await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText(`Leakage factor K_s: ${s.factor}`);
    await expect(page.locator('#pane-report')).toContainText(`Transition width delta_cl: ${s.width}`);
    actuals.push(result);
  }
  const original=actuals.at(-1);await page.locator('#project-settings').evaluate(e=>e.open=true);
  await page.locator('#project-case-name').fill('Broad stall transition');await page.locator('#project-add').click();
  await expect(page.locator('#project-status')).toContainText('New case saved');
  await page.locator('#project-solution-name').fill('Broad transition result');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Computed solution saved');
  await page.locator('#stall-factor').fill('10');await page.locator('#stall-width').fill('.01');
  await page.locator('#project-load').click();await expect(page.locator('#project-status')).toContainText('Loaded Broad stall transition');
  await expect(page.locator('#stall-factor')).toHaveValue('40');await expect(page.locator('#stall-width')).toHaveValue('0.15');
  await page.locator('#project-load-solution').click();await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation');
  expect(await data(page)).toEqual(original);
  await page.locator('#stall').uncheck();const disabled=await solve(page);
  expect(disabled.condition.stall_factor).toBe(40);expect(disabled.condition.stall_width).toBe(.15);
  for(const k of ['CL','CD','Cm'])expect(Math.abs(disabled[k]-actuals[0][k])).toBeLessThan(2e-7);
  await expect(page.locator('#viewport canvas')).toHaveAttribute('data-renderer','webgl');
  expect(await page.locator('#viewport canvas').evaluate(e=>e.getContext('webgl2').isContextLost())).toBe(false);
  await page.locator('#stall-settings').screenshot({path:'test-results/stall-parameters-desktop.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#stall-settings').screenshot({path:'test-results/stall-parameters-mobile.png'});
  await writeFile('test-results/stall-parameters-values.json',JSON.stringify(actuals,null,2)+'\n');expect(errors).toEqual([]);
});

test('old cases restore the original stall defaults and invalid parameters are rejected',async({page,context})=>{
  test.setTimeout(300000);
  await open(page,4);await context.setOffline(true);await page.locator('#project-settings').evaluate(e=>e.open=true);
  await page.locator('#project-case-name').fill('Old stall case');const old=await data(page,'#project-export-current');
  delete old.cases[0].configuration.fields['stall-factor'];delete old.cases[0].configuration.fields['stall-width'];
  await page.locator('#stall-factor').fill('10');await page.locator('#stall-width').fill('.15');
  await page.locator('#project-file').setInputFiles({name:'old-stall.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(old))});
  await expect(page.locator('#project-status')).toContainText('Project opened');await page.locator('#project-load').click();
  await expect(page.locator('#project-status')).toContainText('Loaded Old stall case');
  await expect(page.locator('#stall-factor')).toHaveValue('40');await expect(page.locator('#stall-width')).toHaveValue('0.05');
  for(const [id,value,message] of [['stall-factor','','leakage factor'],['stall-factor','-1','leakage factor'],['stall-width','','transition width'],['stall-width','0','transition width']]){
    await page.locator('#stall-factor').fill('40');await page.locator('#stall-width').fill('.05');
    await page.locator('#'+id).fill(value);await page.locator('#solve').click();await expect(page.locator('#error')).toContainText(message);
    await expect(page.locator('#export-json')).toBeDisabled();await page.locator('#close-error').click();
  }
});

test('saved equilibrium time launch retains its stall parameters over current controls',async({page,context})=>{
  test.setTimeout(540000);await open(page,4);await context.setOffline(true);await page.locator('#mode').selectOption('mounted');
  await page.locator('#stall-factor').fill('10');await page.locator('#stall-width').fill('.15');const base=await solve(page);
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);await page.locator('#equilibrium-use').click();
  await page.locator('#stall-factor').fill('80');await page.locator('#stall-width').fill('.01');await page.locator('#mode').selectOption('time');
  await expect(page.locator('#equilibrium-status')).toContainText('Saved stall: enabled, K_s=10, delta_cl=0.15');
  await page.locator('#time-duration').fill('.02');await page.locator('#time-step').fill('.01');
  const result=await solve(page,'Time integration converged');expect(result.condition.stall_factor).toBe(10);expect(result.condition.stall_width).toBe(.15);
  expect(result.restart_context.setup.condition.stall_factor).toBe(10);expect(result.restart_context.setup.condition.stall_width).toBe(.15);
  for(const snapshot of result.snapshots)for(const key of ['CL','CD','Cm'])expect(Math.abs(snapshot[key]-base[key])).toBeLessThan(2e-7);
  await writeFile('test-results/stall-parameters-launch.json',JSON.stringify(result,null,2)+'\n');
});
