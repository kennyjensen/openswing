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
const retainedPath=process.env.OPENSWING_SAVED_POSITION_RESULT;
test(retainedPath?'retained browser position solve displays offline and continues on mobile':
  'saved equilibrium launches a position history offline and continues on mobile',async({page,context})=>{
  test.setTimeout(900000);
  const output=process.env.OPENSWING_RUN_OUTPUT||'test-results/saved-position';
  await mkdir(output,{recursive:true});
  const started=Date.now(),errors=[],external=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',request=>{if(/^https?:/.test(request.url())&&!/^http:\/\/(127\.0\.0\.1|localhost):/.test(request.url()))external.push(request.url());});
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled({timeout:180000});
  page.on('console',message=>{if(message.text().startsWith('saved-position-status:'))console.log(message.text());});
  await page.evaluate(()=>{
    const element=document.getElementById('runtime-status');let last=0;
    new MutationObserver(()=>{
      const value=element.textContent;
      if(Date.now()-last>10000||/converged|stopped/.test(value)){
        console.log('saved-position-status: '+value);last=Date.now();
      }
    }).observe(element,{subtree:true,characterData:true,childList:true});
  });
  await page.locator('#file').setInputFiles('tests/inverse_history/saved/inputs/both-root.asw');
  await expect(page.locator('#model-name')).toHaveText('Cold inverse axial body');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled({timeout:180000});
  await page.locator('#mode').selectOption('time');
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);
  await page.locator('#equilibrium-file').setInputFiles('tests/inverse_history/saved/inputs/saved-equilibrium.json');
  await expect(page.locator('#equilibrium-enable')).toBeChecked();
  await expect(page.locator('#equilibrium-help')).toContainText('Earth-position');
  await page.locator('#time-frame').selectOption('mixed');
  await page.locator('[data-time-load="Fx"]').selectOption('prescribed');
  await page.locator('[data-time-load="Fy"]').selectOption('load');
  await page.locator('[data-time-target="Fy"]').fill('0');
  await page.locator('#time-duration').fill('.04');await page.locator('#time-step').fill('.04');
  await page.locator('#time-order').selectOption('5');
  await page.locator('#time-actuator-settings').evaluate(e=>e.open=true);
  await page.locator('#time-actuators').fill('E1 RY 0');
  await page.locator('#forcing-settings').evaluate(e=>e.open=true);
  await page.locator('#time-forcing').fill('time RY\n-1 .2\n0 0\n1 .2');
  await context.setOffline(true);
  let retained=null;
  if(retainedPath){
    retained=JSON.parse(await readFile(retainedPath,'utf8'));
    await page.locator('#project-settings').evaluate(e=>e.open=true);
    const project=JSON.parse(await download(page,'#project-export-current'));
    const solution=await sealSolution({id:'retained-position',name:'Retained browser position solve',
      created_at:new Date().toISOString(),kind:'time',configuration:project.cases[0].configuration,
      data:retained,auxiliary:{},view:{},provenance:retained.software_provenance});
    project.solutions=[solution];project.selected_solution=solution.id;
    await page.locator('#project-file').setInputFiles({name:'retained-position.json',mimeType:'application/json',
      buffer:Buffer.from(JSON.stringify(project))});
    await expect(page.locator('#project-status')).toContainText('Project opened.');
    await page.locator('#project-load-solution').click();
    await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');
  }else{
    await page.locator('#solve').click();
    await expect(page.locator('#runtime-status')).toHaveText(/^(Time integration converged|Analysis stopped)$/,{timeout:720000});
    expect(await page.locator('#runtime-status').textContent(),await page.locator('#error').textContent()).toBe('Time integration converged');
  }
  const result=JSON.parse(await download(page,'#export-json'));
  const resultPath=path.join(output,'result.json');await writeFile(resultPath,JSON.stringify(result)+'\n');
  if(retained)expect(result).toEqual(retained);
  expect(result.request.action).toBe('launch_time');expect(result.accepted_steps).toBe(1);
  expect(result.rejected_steps).toBe(0);
  expect(result.launch_transition.before_input.saved_equilibrium).toEqual(JSON.parse(await readFile('tests/inverse_history/saved/inputs/saved-equilibrium.json','utf8')));
  await promisify(execFile)('python3',['scripts/verify-saved-position.py','--result',resultPath,'--report',path.join(output,'mechanics.json')]);
  expect(Object.keys(result.software_provenance.modules).sort()).toEqual((await readdir('openswing')).filter(n=>n.endsWith('.py')).sort());
  for(const [name,hash] of Object.entries(result.software_provenance.modules))
    expect(createHash('sha256').update(await readFile('openswing/'+name)).digest('hex')).toBe(hash);
  await page.setViewportSize({width:390,height:844});
  await page.locator('#workspace-tab-plots').click();
  await page.locator('#time-quantity').selectOption('inverse.actual|power.1|position_earth.y');
  await expect(page.locator('#time-unit')).toContainText('Achieved RY');
  await expect(page.locator('#time-plot svg')).toBeVisible();
  const csv=await download(page,'#time-csv');await writeFile(path.join(output,'position.csv'),csv);
  const rows=csv.trim().split('\n').map(line=>line.match(/"(?:[^"]|"")*"/g).map(cell=>cell.slice(1,-1).replaceAll('""','"')));
  const actual=rows[0].findIndex(label=>label.startsWith('Achieved')&&label.includes('E1'));
  const residual=rows[0].findIndex(label=>label.startsWith('Target residual')&&label.includes('E1'));
  expect(actual).toBeGreaterThan(0);expect(residual).toBeGreaterThan(0);
  for(const row of rows.slice(1)){
    const t=Number(row[0]);expect(Math.abs(Number(row[actual])-(.3*t*t-.1*t*t*t))).toBeLessThan(1e-8);
    expect(Math.abs(Number(row[residual]))).toBeLessThan(1e-8);
  }
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#time-plot').screenshot({path:path.join(output,'mobile-position.png')});
  await page.locator('#time-scrub').fill('1');
  await page.locator('#time-checkpoint-settings').evaluate(e=>e.open=true);
  await page.locator('#time-checkpoint-use').click();
  await page.locator('#time-continue-order').selectOption('2');
  await page.locator('#time-continue-duration').fill('.02');await page.locator('#time-continue-step').fill('.02');
  await page.locator('#time-continue').click();
  await expect(page.locator('#runtime-status')).toHaveText(/^(Time continuation (converged|stopped)|Analysis stopped)$/,{timeout:180000});
  expect(await page.locator('#runtime-status').textContent(),await page.locator('#error').textContent()).toBe('Time continuation converged');
  await page.locator('#workspace-tab-output').click();
  const resumed=JSON.parse(await download(page,'#export-json'));
  const resumedPath=path.join(output,'resumed.json');await writeFile(resumedPath,JSON.stringify(resumed)+'\n');
  expect(resumed.snapshots).toHaveLength(3);
  for(const [i,old] of result.snapshots.entries()){
    const {restart_context,...physical}=resumed.snapshots[i];
    expect(physical).toEqual(old);
    expect(restart_context).toEqual(result.restart_context);
  }
  expect(resumed.snapshots[2].restart.accepted_method.kind).toBe('bdf');
  await promisify(execFile)('python3',['scripts/verify-saved-position.py','--result',resumedPath,'--report',path.join(output,'resumed-mechanics.json')]);
  expect(errors).toEqual([]);expect(external).toEqual([]);
  await writeFile(path.join(output,'status.json'),JSON.stringify({status:'PASS',seconds:(Date.now()-started)/1000,
    launch_origin:retainedPath?'retained_browser_export':'fresh_worker_solve',retained_file:retainedPath??null,
    offline:true,viewport:390,source_sha256:result.software_provenance.modules,errors,external},null,2)+'\n');
});
