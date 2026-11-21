import {test,expect} from '@playwright/test';
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

test.use({launchOptions:{executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,
  args:['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native',
    '--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']}});

async function download(page,selector){
  const pending=page.waitForEvent('download');await page.locator(selector).click();
  return readFile(await(await pending).path(),'utf8');
}

function mechanics(snapshots){
  const past=[];
  for(const s of snapshots){
    const t=s.time,v=-10+.4*t+.3*t*t-.1*t*t*t;
    let a=.4,x=0;
    if(past.length){
      const p=past.at(-1),h=t-p.t;
      if(past.length===1){a=(v-p.v)/h;x=p.x+h*v;}
      else{
        const q=past.at(-2),k=p.t-q.t;
        const c0=(2*h+k)/(h*(h+k)),c1=-(h+k)/(h*k),c2=h/(k*(h+k));
        a=c0*v+c1*p.v+c2*q.v;x=(v-c1*p.x-c2*q.x)/c0;
      }
      expect(s.restart.accepted_method.scheme).toBe('openswing-so3-bdf-v2');
      expect(s.restart.accepted_method.nonlinear_tolerance).toBeLessThan(1e-8);
    }
    expect(Math.abs(s.operating_values['power.1']-a)).toBeLessThan(1e-7);
    expect(Math.abs(s.frame.velocity_origin_body[0]-v)).toBeLessThan(1e-9);
    expect(Math.abs(s.frame.position_earth[0]-x)).toBeLessThan(1e-8);
    expect(Math.max(...s.applied_force.map(Math.abs))).toBeLessThan(1e-8);
    expect(s.residual).toBeLessThanOrEqual(1e-8);
    past.push({t,v,x});
  }
}

test('inverse velocity solves, target plots and checkpoint continuation work offline on mobile',async({page,context})=>{
  test.setTimeout(720000);
  const output=process.env.OPENSWING_RUN_OUTPUT||'test-results/inverse-histories';
  await mkdir(output,{recursive:true});
  const errors=[],external=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',request=>{if(/^https?:/.test(request.url())&&!/^http:\/\/(127\.0\.0\.1|localhost):/.test(request.url()))external.push(request.url());});
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled({timeout:180000});
  await page.locator('#file').setInputFiles('tests/fixtures/inverse-history-curved.asw');
  await expect(page.locator('#model-name')).toHaveText('Guided rigid-body demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled({timeout:180000});
  await page.locator('#mode').selectOption('time');
  await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#time-frame').selectOption('free');
  await page.locator('#time-duration').fill('.04');await page.locator('#time-step').fill('.02');
  await page.locator('#time-order').selectOption('2');
  await page.locator('#time-actuator-settings').evaluate(e=>e.open=true);
  await page.locator('#time-actuators').fill('E1 velocity_earth.x -10');
  await page.locator('#forcing-settings').evaluate(e=>e.open=true);
  await page.locator('#time-forcing').fill('time velocity_earth.x\n-1 -10.2\n0 -10\n1 -9.4');
  await context.setOffline(true);await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:480000});
  const result=JSON.parse(await download(page,'#export-json'));
  await writeFile(path.join(output,'cold-result.json'),JSON.stringify(result)+'\n');
  expect(result.accepted_steps).toBe(2);expect(result.rejected_steps).toBe(0);
  expect(result.snapshots[0].initial_phase).toBe('cold_inverse_history');mechanics(result.snapshots);
  expect(Object.keys(result.software_provenance.modules).sort()).toEqual((await readdir('openswing')).filter(n=>n.endsWith('.py')).sort());
  for(const [name,hash] of Object.entries(result.software_provenance.modules))
    expect(createHash('sha256').update(await readFile('openswing/'+name)).digest('hex')).toBe(hash);
  await page.setViewportSize({width:390,height:844});
  await page.locator('#workspace-tab-output').click();
  await expect(page.locator('#pane-report')).toContainText('Cold inverse-history initialization');
  await page.locator('#workspace-tab-plots').click();
  for(const [key,label] of [
    ['inverse.target|power.1|velocity_earth.x','Target velocity_earth.x'],
    ['inverse.actual|power.1|velocity_earth.x','Achieved velocity_earth.x'],
    ['inverse.normalized_residual|power.1|velocity_earth.x','Target residual velocity_earth.x'],
    ['forcing_values.velocity_earth.x','Input velocity_earth.x'],
  ]){
    await page.locator('#time-quantity').selectOption(key);
    await expect(page.locator('#time-unit')).toContainText(label);
    await expect(page.locator('#time-plot svg')).toBeVisible();
    const csv=await download(page,'#time-csv');expect(csv).toContain(label);
    await writeFile(path.join(output,key.split('|')[0].replaceAll('.','-')+'.csv'),csv);
  }
  await page.locator('#time-quantity').selectOption('inverse.actual|power.1|velocity_earth.x');
  await page.locator('#time-plot').screenshot({path:path.join(output,'mobile-target-plot.png')});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#time-scrub').fill(String(result.snapshots.length-1));
  await page.locator('#time-checkpoint-settings').evaluate(e=>e.open=true);
  await page.locator('#time-checkpoint-use').click();
  await page.locator('#time-continue-duration').fill('.04');
  await page.locator('#time-continue').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time continuation converged',{timeout:180000});
  await page.locator('#workspace-tab-output').click();
  const resumed=JSON.parse(await download(page,'#export-json'));
  await writeFile(path.join(output,'resumed-result.json'),JSON.stringify(resumed)+'\n');
  expect(resumed.snapshots).toHaveLength(5);mechanics(resumed.snapshots);
  expect(resumed.checkpoint_validation.level).toBe('recorded_discrete_equations');
  await page.locator('#workspace-tab-output').click();
  await expect(page.locator('#pane-report')).toContainText('Checkpoint continuation');
  expect(errors).toEqual([]);expect(external).toEqual([]);
  await writeFile(path.join(output,'status.json'),JSON.stringify({status:'PASS',snapshots:resumed.snapshots.length,
    offline:true,viewport:390,source_sha256:result.software_provenance.modules,errors,external},null,2)+'\n');
});
