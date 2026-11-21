import {test,expect} from '@playwright/test';
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
test.use({launchOptions:{executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,
  args:['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native',
    '--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']}});
async function download(page,id){
  const pending=page.waitForEvent('download');await page.locator(id).click();
  return readFile(await(await pending).path(),'utf8');
}
async function continued(page,timeout){
  await expect(page.locator('#runtime-status')).toHaveText(/^Time continuation (converged|stopped)$/,{timeout});
  expect(await page.locator('#runtime-status').textContent(),await page.locator('#error').textContent()).toBe('Time continuation converged');
}
function mechanics(result){
  for(const s of result.snapshots){
    const t=s.time,f=s.frame,p=-10*t+.2*t*t-t**3/15,v=-10+.4*t-.2*t*t,a=.4*(1-t);
    for(const [actual,expected] of [[f.position_earth[0],p],[f.velocity_origin_body[0],v],
      [f.acceleration_reference_body[0],a],[s.operating_values['power.1'],a]])
      expect(Math.abs(actual-expected)).toBeLessThan(1e-7);
    expect(s.restart.state.position_history.time).toBe(t);
  }
}
test('offline Radau position continuation preserves target plots and branches into BDF',async({page,context})=>{
  test.setTimeout(600000);
  const inputs=path.resolve('tests/inverse_history/radau/inputs');
  const output=process.env.OPENSWING_RUN_OUTPUT||'test-results/radau-position';await mkdir(output,{recursive:true});
  const source=await readFile(path.join(inputs,'rigid.asw'),'utf8');
  const saved=JSON.parse(await readFile(path.join(inputs,'step-checkpoint.json'),'utf8'));
  const errors=[],external=[],started=Date.now();
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(/^https?:/.test(r.url())&&!/^http:\/\/(127\.0\.0\.1|localhost):/.test(r.url()))external.push(r.url());});
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled({timeout:180000});
  await page.locator('#file').setInputFiles({name:'rigid.asw',mimeType:'text/plain',buffer:Buffer.from(source)});
  await expect(page.locator('#model-name')).toHaveText('Guided rigid-body demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled({timeout:180000});
  await page.locator('#mode').selectOption('time');await page.locator('#tab-time').click();
  await page.locator('#time-checkpoint-settings').evaluate(e=>e.open=true);
  await page.locator('#time-checkpoint-file').setInputFiles({name:'position-checkpoint.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(saved))});
  await expect(page.locator('#time-continue-order')).toHaveValue('5');
  await page.locator('#time-continue-duration').fill('.02');await page.locator('#time-continue-step').fill('.02');
  await context.setOffline(true);await page.locator('#time-continue').click();
  await continued(page,360000);
  const result=JSON.parse(await download(page,'#export-json'));
  await writeFile(path.join(output,'result.json'),JSON.stringify(result)+'\n');
  expect(result.accepted_steps).toBe(1);expect(result.rejected_steps).toBe(0);expect(result.snapshots).toHaveLength(2);
  expect(result.snapshots[0].restart.accepted_method).toEqual(saved.accepted_method);
  expect(result.snapshots[1].restart.accepted_method.scheme).toBe('openswing-so3-position-defect-radau-iia-3-v1');
  expect(result.checkpoint_validation.discrete_replayed).toBe(true);mechanics(result);
  const modules=Object.keys(result.software_provenance.modules).sort();
  expect(modules).toEqual((await readdir('openswing')).filter(n=>n.endsWith('.py')).sort());
  for(const name of modules)expect(createHash('sha256').update(await readFile('openswing/'+name)).digest('hex')).toBe(result.software_provenance.modules[name]);
  await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
  await page.locator('#time-quantity').selectOption('inverse.actual|power.1|position_earth.x');
  await expect(page.locator('#time-unit')).toContainText('Achieved');
  await expect(page.locator('#time-summary')).toContainText('1 accepted steps');
  expect(await page.locator('#time-plot polyline').count()).toBeGreaterThan(0);
  const csv=await download(page,'#time-csv');await writeFile(path.join(output,'history.csv'),csv);
  const rows=csv.trim().split('\n').map(line=>line.match(/"(?:[^"]|"")*"/g).map(cell=>cell.slice(1,-1).replaceAll('""','"')));
  const actual=rows[0].findIndex(label=>label.startsWith('Achieved')&&label.includes('E1'));
  const residual=rows[0].findIndex(label=>label.startsWith('Target residual')&&label.includes('E1'));
  expect(actual).toBeGreaterThan(0);expect(residual).toBeGreaterThan(0);
  for(const row of rows.slice(1)){
    const t=Number(row[0]);expect(Math.abs(Number(row[actual])-(-10*t+.2*t*t-t**3/15))).toBeLessThan(1e-8);
    expect(Math.abs(Number(row[residual]))).toBeLessThan(1e-8);
  }
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#time-plot').screenshot({path:path.join(output,'mobile-position.png')});
  // Continue the actual browser endpoint with BDF2, keeping its Radau producer record.
  await page.locator('#time-scrub').fill('1');await page.locator('#time-checkpoint-use').click();
  await page.locator('#time-continue-order').selectOption('2');await page.locator('#time-continue-duration').fill('.02');
  await page.locator('#time-continue').click();
  await continued(page,180000);
  await page.locator('#workspace-tab-output').click();
  const branched=JSON.parse(await download(page,'#export-json'));await writeFile(path.join(output,'branched.json'),JSON.stringify(branched)+'\n');
  expect(branched.accepted_steps).toBe(2);expect(branched.retained_steps).toBe(1);expect(branched.snapshots).toHaveLength(3);
  expect(branched.snapshots.slice(0,2).map(s=>s.restart.accepted_method)).toEqual(result.snapshots.map(s=>s.restart.accepted_method));
  expect(branched.snapshots[2].restart.accepted_method.kind).toBe('bdf');mechanics(branched);
  expect(errors).toEqual([]);expect(external).toEqual([]);
  await writeFile(path.join(output,'status.json'),JSON.stringify({status:'PASS',seconds:(Date.now()-started)/1000,
    offline:true,viewport:390,source_sha256:result.software_provenance.modules,errors,external},null,2)+'\n');
});
