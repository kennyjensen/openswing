import {test,expect} from '@playwright/test';
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {sealSolution} from '../../web/solution-data.js';
test.use({launchOptions:{executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,
  args:['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native',
    '--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']}});
async function download(page,id){
  const pending=page.waitForEvent('download');await page.locator(id).click();
  return readFile(await(await pending).path(),'utf8');
}
test('offline event completion displays both phases and counts actual steps when branching',async({page,context})=>{
  test.setTimeout(900000);
  const inputs=path.resolve('tests/inverse_history/events/inputs');
  const output=process.env.OPENSWING_RUN_OUTPUT||'test-results/history-events';await mkdir(output,{recursive:true});
  const source=await readFile(path.join(inputs,'rigid.asw'),'utf8');
  const saved=JSON.parse(await readFile(path.join(inputs,'left-checkpoint.json'),'utf8'));
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
  await page.locator('#time-checkpoint-file').setInputFiles({name:'left-checkpoint.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(saved))});
  await page.locator('#time-continue-duration').fill('.02');await context.setOffline(true);
  const retainedPath=process.env.OPENSWING_EVENT_RESULT;
  let retained=null;
  if(retainedPath){
    // Reopen the actual export through the public archive UI. This does not
    // claim another initial solve; the selected-state continuation below is new.
    retained=JSON.parse(await readFile(retainedPath,'utf8'));
    await page.locator('#project-settings').evaluate(e=>e.open=true);
    const project=JSON.parse(await download(page,'#project-export-current'));
    const solution=await sealSolution({id:'retained-event',name:'Retained input transition',
      created_at:new Date().toISOString(),kind:'time',configuration:project.cases[0].configuration,
      data:retained,auxiliary:{},view:{},provenance:retained.software_provenance});
    project.solutions=[solution];project.selected_solution=solution.id;
    await page.locator('#project-file').setInputFiles({name:'retained-event.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});
    await expect(page.locator('#project-status')).toContainText('Project opened.');
    await page.locator('#project-load-solution').click();
    await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');
  }else{
    await page.locator('#time-continue').click();
    await expect(page.locator('#runtime-status')).toHaveText('Time continuation converged',{timeout:720000});
  }
  const result=JSON.parse(await download(page,'#export-json'));
  if(retained)expect(result).toEqual(retained);
  await writeFile(path.join(output,'result.json'),JSON.stringify(result)+'\n');
  expect(result.accepted_steps).toBe(1);expect(result.rejected_steps).toBe(0);expect(result.snapshots).toHaveLength(3);
  expect(result.snapshots.map(s=>s.time)).toEqual([.06,.06,.08]);
  expect(result.snapshots[0].restart.accepted_method).toEqual(saved.accepted_method);
  for(const [i,force] of [[0,.8],[1,-.2],[2,-.2]])expect(Math.abs(result.snapshots[i].operating_values['power.1']-force)).toBeLessThan(1e-7);
  expect(result.snapshots[1].initial_phase).toBe('input_transition_right_limit');
  const modules=Object.keys(result.software_provenance.modules).sort();
  expect(modules).toEqual((await readdir('openswing')).filter(n=>n.endsWith('.py')).sort());
  for(const name of modules)expect(createHash('sha256').update(await readFile('openswing/'+name)).digest('hex')).toBe(result.software_provenance.modules[name]);
  await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
  await page.locator('#time-quantity').selectOption('actuator.power.1');
  await expect(page.locator('#time-summary')).toContainText('1 accepted steps');
  await page.locator('#time-scrub').fill('0');await expect(page.locator('#time-current')).toContainText('Before input change');
  await page.locator('#time-scrub').fill('1');await expect(page.locator('#time-current')).toContainText('After input change');
  const segments=await page.locator('#time-plot polyline').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('points').trim().split(/\s+/).length));
  expect(segments).toEqual([1,2]);
  const csv=await download(page,'#time-csv');await writeFile(path.join(output,'history.csv'),csv);
  const rows=csv.trim().split('\n').map(line=>line.match(/"(?:[^"]|"")*"/g).map(cell=>cell.slice(1,-1).replaceAll('""','"')));
  expect(rows[0][4]).toBe('snapshot phase');expect(rows.slice(1).map(row=>row[4])).toEqual(['Before input change','After input change','Computed state']);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#time-plot').screenshot({path:path.join(output,'mobile-force.png')});
  // Branch from the right phase. The retained prefix has two snapshots and
  // zero accepted steps; indexing it as one step would inflate the count.
  await page.locator('#time-checkpoint-use').click();await page.locator('#time-continue-duration').fill('.02');
  await page.locator('#time-continue').click();
  await expect(page.locator('#runtime-status')).toHaveText('Time continuation converged',{timeout:180000});
  await page.locator('#workspace-tab-output').click();
  const branched=JSON.parse(await download(page,'#export-json'));await writeFile(path.join(output,'branched.json'),JSON.stringify(branched)+'\n');
  expect(branched.accepted_steps).toBe(1);expect(branched.retained_steps).toBe(0);expect(branched.snapshots).toHaveLength(3);
  expect(branched.snapshots.filter(s=>s.input_transition)).toHaveLength(1);
  expect(branched.snapshots.slice(0,2).map(s=>s.restart.accepted_method)).toEqual(result.snapshots.slice(0,2).map(s=>s.restart.accepted_method));
  expect(Math.abs(branched.snapshots[2].operating_values['power.1']+.2)).toBeLessThan(1e-7);
  await page.locator('#workspace-tab-output').click();await expect(page.locator('#pane-report')).toContainText('1 accepted steps');
  expect(errors).toEqual([]);expect(external).toEqual([]);
  await writeFile(path.join(output,'status.json'),JSON.stringify({status:'PASS',seconds:(Date.now()-started)/1000,
    initial_origin:retainedPath?'retained_browser_export':'fresh_worker_solve',retained_file:retainedPath??null,
    initial_export_unchanged:retained?true:null,offline:true,viewport:390,source_sha256:result.software_provenance.modules,errors,external},null,2)+'\n');
});
