import {test,expect} from '@playwright/test';
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';
import {sealSolution} from '../../web/solution-data.js';

test.use({launchOptions:{executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,
  args:['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native',
    '--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']}});

async function download(page,selector){
  const pending=page.waitForEvent('download');await page.locator(selector).click();
  return readFile(await(await pending).path(),'utf8');
}

const retainedPath=process.env.OPENSWING_SAVED_SPLINE_RESULT;
test(retainedPath?'retained browser spline result displays and resumes offline on mobile':
  'saved equilibrium launches a curved velocity table and resumes offline on mobile',async({page,context})=>{
  test.setTimeout(900000);
  const output=process.env.OPENSWING_RUN_OUTPUT||'test-results/saved-spline';
  await mkdir(output,{recursive:true});
  const started=Date.now(),errors=[],external=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',request=>{if(/^https?:/.test(request.url())&&!/^http:\/\/(127\.0\.0\.1|localhost):/.test(request.url()))external.push(request.url());});
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled({timeout:180000});
  await page.locator('#file').setInputFiles('tests/inverse_history/saved/inputs/both-root.asw');
  await expect(page.locator('#model-name')).toHaveText('Cold inverse axial body');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled({timeout:180000});
  await page.locator('#mode').selectOption('time');
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);
  await page.locator('#equilibrium-file').setInputFiles('tests/inverse_history/saved/inputs/saved-equilibrium.json');
  await expect(page.locator('#equilibrium-enable')).toBeChecked();
  await expect(page.locator('#equilibrium-help')).toContainText('explicit target table');
  await page.locator('#time-frame').selectOption('mixed');
  await page.locator('[data-time-load="Fx"]').selectOption('prescribed');
  await page.locator('[data-time-load="Fy"]').selectOption('load');
  await page.locator('[data-time-target="Fy"]').fill('0');
  await page.locator('#time-duration').fill('.06');await page.locator('#time-step').fill('.02');
  await page.locator('#time-order').selectOption('5');
  await page.locator('#time-actuator-settings').evaluate(e=>e.open=true);
  await page.locator('#time-actuators').fill('E1 velocity_earth.y 0');
  await page.locator('#forcing-settings').evaluate(e=>e.open=true);
  await page.locator('#time-forcing').fill('time velocity_earth.y\n0 0\n.04 .024\n1 .792');
  await context.setOffline(true);
  let retained=null;
  if(retainedPath){
    // Reopen an actual exported solve through the public solution archive UI.
    // This path explicitly does not claim to repeat its initial worker solve.
    retained=JSON.parse(await readFile(retainedPath,'utf8'));
    await page.locator('#project-settings').evaluate(e=>e.open=true);
    const project=JSON.parse(await download(page,'#project-export-current'));
    const solution=await sealSolution({id:'retained-spline',name:'Retained browser spline',
      created_at:new Date().toISOString(),kind:'time',configuration:project.cases[0].configuration,
      data:retained,auxiliary:{},view:{},provenance:retained.software_provenance});
    project.solutions=[solution];project.selected_solution=solution.id;
    await page.locator('#project-file').setInputFiles({name:'retained-spline.json',mimeType:'application/json',
      buffer:Buffer.from(JSON.stringify(project))});
    await expect(page.locator('#project-status')).toContainText('Project opened.');
    await page.locator('#project-load-solution').click();
    await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');
    await expect(page.locator('#solve')).toBeEnabled();
  }else{
    await page.locator('#solve').click();
    await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:720000});
  }
  const result=JSON.parse(await download(page,'#export-json'));
  if(retained)expect(result).toEqual(retained);
  const resultPath=path.join(output,'result.json');await writeFile(resultPath,JSON.stringify(result)+'\n');
  expect(result.request.action).toBe('launch_time');
  expect(result.accepted_steps).toBe(3);expect(result.rejected_steps).toBe(0);
  await promisify(execFile)('.venv/bin/python',['scripts/verify-saved-spline.py','--result',resultPath,
    '--report',path.join(output,'mechanics.json')]);
  expect(Object.keys(result.software_provenance.modules).sort()).toEqual((await readdir('openswing')).filter(n=>n.endsWith('.py')).sort());
  for(const [name,hash] of Object.entries(result.software_provenance.modules))
    expect(createHash('sha256').update(await readFile('openswing/'+name)).digest('hex')).toBe(hash);
  await page.setViewportSize({width:390,height:844});
  await page.locator('#workspace-tab-output').click();
  await expect(page.locator('#pane-report')).toContainText('completed right state');
  await page.locator('#workspace-tab-plots').click();
  await page.locator('#time-quantity').selectOption('inverse.actual|power.1|velocity_earth.y');
  await expect(page.locator('#time-unit')).toContainText('Achieved velocity_earth.y');
  await expect(page.locator('#time-plot svg')).toBeVisible();
  await writeFile(path.join(output,'velocity.csv'),await download(page,'#time-csv'));
  await page.locator('#time-plot').screenshot({path:path.join(output,'mobile-velocity.png')});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  // Branch before the interior knot, then cross it again from the owned checkpoint.
  await page.locator('#time-scrub').fill('1');
  await page.locator('#time-checkpoint-settings').evaluate(e=>e.open=true);
  await page.locator('#time-checkpoint-use').click();
  await page.locator('#time-continue-duration').fill('.04');
  await page.locator('#time-continue').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time continuation converged',{timeout:180000});
  await page.locator('#workspace-tab-output').click();
  const resumed=JSON.parse(await download(page,'#export-json'));
  const resumedPath=path.join(output,'resumed-result.json');await writeFile(resumedPath,JSON.stringify(resumed)+'\n');
  expect(resumed.snapshots).toHaveLength(4);
  expect(resumed.checkpoint_validation.level).toBe('recorded_discrete_equations');
  await promisify(execFile)('.venv/bin/python',['scripts/verify-saved-spline.py','--result',resumedPath,
    '--report',path.join(output,'resumed-mechanics.json')]);
  expect(errors).toEqual([]);expect(external).toEqual([]);
  await writeFile(path.join(output,'status.json'),JSON.stringify({status:'PASS',seconds:(Date.now()-started)/1000,
    launch_origin:retainedPath?'retained_browser_export':'fresh_worker_solve',
    retained_file:retainedPath??null,initial_export_unchanged:retained?true:null,
    offline:true,viewport:390,source_sha256:result.software_provenance.modules,errors,external},null,2)+'\n');
});
