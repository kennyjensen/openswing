import {test,expect} from '@playwright/test';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
test.use({launchOptions:{executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,
  args:['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native',
    '--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']}});
const data=async(page,id='#export-json')=>{const event=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await event).path(),'utf8'));};

test('inverse actuator histories, solved plots, case archives and checkpoint continuation work offline',async({page,context})=>{
  test.setTimeout(600000);await mkdir('test-results',{recursive:true});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled({timeout:180000});
  await page.locator('#example').selectOption('inverse-actuators');await expect(page.locator('#model-name')).toHaveText('Inverse actuator demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled({timeout:180000});
  await page.locator('#mode').selectOption('time');await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#time-frame').selectOption('free');await page.locator('#time-duration').fill('.12');await page.locator('#time-step').fill('.02');
  await page.locator('#time-actuator-settings').evaluate(e=>e.open=true);await page.locator('#time-actuators').fill('E1 Ax .2');
  await page.locator('#forcing-settings').evaluate(e=>e.open=true);await page.locator('#time-forcing').fill('time +Ax\n0 0\n.12 .12');
  await context.setOffline(true);await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:240000});
  const result=await data(page);expect(result.actuator_constraints).toEqual([{variable:'power.1',quantity:'acceleration.x',target:.2}]);
  for(const s of result.snapshots){
    expect(s.operating_values['power.1']).toBeCloseTo(.2+s.time,7);
    expect(s.frame.acceleration_reference_body[0]).toBeCloseTo(.2+s.time,7);
    expect(Math.abs(s.frame.velocity_origin_body[0]-(-10+.2*s.time+.5*s.time**2))).toBeLessThan(.0004);
    for(const f of s.applied_force)expect(Math.abs(f)).toBeLessThan(2e-8);
  }
  for(const [name,hash] of Object.entries(result.software_provenance.modules))expect(createHash('sha256').update(await readFile('openswing/'+name)).digest('hex')).toBe(hash);
  await page.locator('#tab-time').click();await page.locator('#time-quantity').selectOption('actuator.power.1');
  await expect(page.locator('#time-unit')).toContainText('Solved E1');await expect(page.locator('#time-plot svg')).toBeVisible();
  const csvEvent=page.waitForEvent('download');await page.locator('#time-csv').click();
  expect(await readFile(await(await csvEvent).path(),'utf8')).toContain('Solved E1 [engine setting]');
  await page.locator('#project-settings').evaluate(e=>e.open=true);await page.locator('#project-case-name').fill('Inverse acceleration');await page.locator('#project-add').click();
  await expect(page.locator('#project-status')).toContainText('New case saved');await page.locator('#project-solution-name').fill('Solved thrust');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Computed solution saved');
  await page.locator('#time-actuators').fill('E1 Ax 0');await expect(page.locator('#export-json')).toBeDisabled();await page.locator('#project-load').click();
  await expect(page.locator('#time-actuators')).toHaveValue('E1 Ax .2');await page.locator('#project-load-solution').click();
  await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation');expect(await data(page)).toEqual(result);
  await page.locator('#tab-time').click();await page.locator('#time-scrub').fill(String(result.snapshots.length-1));
  await page.locator('#time-checkpoint-settings').evaluate(e=>e.open=true);await page.locator('#time-checkpoint-use').click();
  await page.locator('#time-continue-duration').fill('.04');await page.locator('#time-continue').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time continuation converged',{timeout:240000});
  const resumed=await data(page);expect(resumed.actuator_constraints).toEqual(result.actuator_constraints);
  for(const s of resumed.snapshots.filter(s=>s.time>.12))expect(s.operating_values['power.1']).toBeCloseTo(0,8);
  await page.locator('#time-quantity').selectOption('actuator.power.1');
  await expect(page.locator('#viewport canvas')).toHaveAttribute('data-renderer','webgl');
  expect(await page.locator('#viewport canvas').evaluate(e=>e.getContext('webgl2').isContextLost())).toBe(false);
  await page.locator('#time-actuator-settings').screenshot({path:'test-results/time-actuators-desktop.png'});
  await page.locator('#time-plot').screenshot({path:'test-results/time-actuators-plot.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#time-actuator-settings').screenshot({path:'test-results/time-actuators-mobile.png'});
  await page.locator('#time-actuators').fill('E1 Ax 0\nE1 Ay 0');await page.locator('#solve').click();await expect(page.locator('#error p')).toContainText('only once');
  await writeFile('test-results/time-actuators-browser.json',JSON.stringify({result,resumed},null,2)+'\n');expect(errors).toEqual([]);
});

test('legacy cases default to prescribed actuators and saved equilibria launch with inverse targets',async({page,context})=>{
  test.setTimeout(600000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled({timeout:180000});
  await page.locator('#example').selectOption('inverse-actuators');await expect(page.locator('#model-name')).toHaveText('Inverse actuator demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled({timeout:180000});
  await page.locator('#mode').selectOption('time');await page.locator('#time-actuator-settings').evaluate(e=>e.open=true);
  await page.locator('#project-settings').evaluate(e=>e.open=true);await page.locator('#project-case-name').fill('Legacy actuator case');
  const old=await data(page,'#project-export-current');delete old.cases[0].configuration.fields['time-actuators'];
  await page.locator('#time-actuators').fill('E1 Ax .2');
  await page.locator('#project-file').setInputFiles({name:'legacy-actuators.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(old))});
  await expect(page.locator('#project-status')).toContainText('Project opened');await page.locator('#project-load').click();
  await expect(page.locator('#time-actuators')).toHaveValue('');
  await page.locator('#mode').selectOption('mounted');await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#motion-settings').evaluate(e=>e.open=true);await page.locator('#acceleration-x').fill('.2');
  await page.locator('#powers [data-power="1"]').fill('.2');await context.setOffline(true);
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:240000});
  const base=await data(page);expect(base.applied_force[0]).toBeCloseTo(0,8);
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);await page.locator('#equilibrium-use').click();
  await page.locator('#mode').selectOption('time');await page.locator('#time-frame').selectOption('free');
  await page.locator('#time-actuator-settings').evaluate(e=>e.open=true);await page.locator('#time-actuators').fill('E1 Ax .2');
  await page.locator('#time-duration').fill('.04');await page.locator('#time-step').fill('.02');
  await page.locator('#forcing-settings').evaluate(e=>e.open=true);await page.locator('#time-forcing').fill('time Ax\n0 .4\n.04 .6');
  await page.locator('#powers [data-power="1"]').fill('9');await page.locator('#acceleration-x').fill('99');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:240000});
  const result=await data(page);expect(result.request.action).toBe('launch_time');
  expect(result.snapshots[0].operating_values['power.1']).toBeCloseTo(.2,8);
  for(const s of result.snapshots.slice(1))expect(s.operating_values['power.1']).toBeCloseTo(.4+5*s.time,7);
  await writeFile('test-results/time-actuators-launch.json',JSON.stringify(result,null,2)+'\n');expect(errors).toEqual([]);
});
