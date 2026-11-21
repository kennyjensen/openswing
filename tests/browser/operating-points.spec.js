import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';

async function exported(page,selector,json=true){
  const event=page.waitForEvent('download');await page.locator(selector).click();
  const content=await readFile(await(await event).path(),'utf8');
  return json?JSON.parse(content):content;
}
async function ready(page){await expect(page.locator('#runtime-status')).toHaveText('Configuration ready');await expect(page.locator('#solve')).toBeEnabled();}
async function setup(page,context){
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await ready(page);
  await context.setOffline(true);await page.locator('#tab-operating-points').click();
}

test('steady polars solve offline, preserve repeated points, inspect, export and restore inputs on mobile',async({page,context},testInfo)=>{
  test.setTimeout(180000);const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await setup(page,context);
  await page.locator('#operating-points-initialization').selectOption('previous');
  await page.locator('#operating-points-values').fill('-2, 0, 5, 5');
  await page.locator('#operating-points-run').click();
  await expect(page.locator('#operating-points-status')).toContainText('4/4 points converged');
  await expect(page.locator('#operating-points-table tbody tr')).toHaveCount(4);
  const sweep=await exported(page,'#operating-points-json');
  await writeFile(testInfo.outputPath('rigid-polar.json'),JSON.stringify(sweep,null,2));
  expect(sweep.request.action).toBe('operating_points');expect(sweep.request.panels).toBe(4);
  expect(sweep.points.map(p=>p.condition.alpha)).toEqual([-2,0,5,5]);
  expect(sweep.points.map(p=>p.actual_condition.alpha)).toEqual([-2,0,5,5]);
  expect(sweep.points[2].result.CL).toBeCloseTo(sweep.points[3].result.CL,10);
  expect(sweep.initialization).toBe('previous');
  expect(sweep.points.map(p=>p.initialization.source_index)).toEqual([null,0,1,2]);
  for(const [i,point] of sweep.points.slice(1).entries()){
    const initialization=point.result.circulation_solver.initialization;
    expect(initialization.initial_circulation).toEqual(sweep.points[i].result.strips.map(s=>s.circulation));
    expect(initialization.seed_attempt.accepted||initialization.cold_fallback).toBe(true);
    expect(point.initialization.cold_fallback).toBe(initialization.cold_fallback);
    if(initialization.cold_fallback)await expect(page.locator('#operating-points-table tbody tr').nth(i+1)).toContainText('independent retry');
  }
  expect(sweep.points[3].result.circulation_solver.initialization.seed_attempt.accepted).toBe(true);
  // The zero-lift -> 5 degree step used to reject subnormal circulation seeds.
  expect(sweep.points[2].result.circulation_solver.initialization.seed_attempt.accepted).toBe(true);
  expect(sweep.points[2].initialization.cold_fallback).toBe(false);
  await expect(page.locator('#operating-points-table tbody tr').nth(1)).toContainText('Point 1');
  expect(sweep.points.every(p=>p.converged&&p.result.residual<1e-7)).toBe(true);
  expect(sweep.software_provenance.modules['operating_points.py']).toMatch(/^[a-f0-9]{64}$/);
  const csv=await exported(page,'#operating-points-csv',false);expect(csv.trim().split('\r\n')).toHaveLength(5);
  expect(csv).toContain('"actual_alpha_deg"');
  await page.locator('#operating-points-table tbody tr').nth(2).getByRole('button').click();
  const selected=await exported(page,'#export-json');
  expect(selected.CL).toBe(sweep.points[2].result.CL);
  expect(selected.request.initial_circulation).toEqual(sweep.points[1].result.strips.map(s=>s.circulation));
  await expect(page.locator('#alpha')).toHaveValue('5');
  await expect(page.locator('#result-state')).toContainText('steady point 3/4');
  await page.locator('#project-settings').evaluate(e=>e.open=true);
  await page.locator('#project-solution-name').fill('Polar point at five degrees');
  await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Computed solution saved.');
  await page.locator('#project-case-name').fill('Steady polar inputs');
  const project=await exported(page,'#project-export-current');
  expect(project.cases[0].configuration.fields['operating-points-values']).toBe('-2, 0, 5, 5');
  expect(project.cases[0].configuration.fields['operating-points-initialization']).toBe('previous');
  await page.locator('#operating-points-initialization').selectOption('cold');
  await page.locator('#operating-points-values').fill('1,3');
  await expect(page.locator('#operating-points-results')).toBeHidden();
  await page.locator('#project-file').setInputFiles({name:'polar.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});
  await expect(page.locator('#project-status')).toContainText('Project opened.');await page.locator('#project-load').click();
  await expect(page.locator('#project-status')).toContainText('Loaded Steady polar inputs.');
  await expect(page.locator('#operating-points-values')).toHaveValue('-2, 0, 5, 5');
  await expect(page.locator('#operating-points-initialization')).toHaveValue('previous');
  await page.locator('#mode').selectOption('mounted');
  await page.locator('#structural-equations').selectOption('aswing-coupled');
  await page.locator('#operating-points-values').fill('2,4');
  await page.locator('#operating-points-run').click();
  await expect(page.locator('#operating-points-status')).toContainText('2/2 points converged');
  const mounted=await exported(page,'#operating-points-json');
  expect(mounted.request.numerics.structural_operator).toBe('drela-steady-coupled-v1');
  expect(mounted.points.every(p=>p.result.numerics.structural_operator==='drela-steady-coupled-v1')).toBe(true);
  expect(mounted.points[1].result.equilibrium_initialization.initialization).toBe('saved physical equilibrium');
  await writeFile(testInfo.outputPath('mounted-polar.json'),JSON.stringify(mounted,null,2));
  await page.screenshot({path:testInfo.outputPath('steady-polar-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
  await page.locator('#operating-points-plot-CL').scrollIntoViewIfNeeded();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  expect(await page.locator('#operating-points-plot-CL').evaluate(c=>c.width>0&&c.getContext('2d').getImageData(0,0,c.width,c.height).data.some(v=>v>0))).toBe(true);
  await page.screenshot({path:testInfo.outputPath('steady-polar-mobile.png')});
  expect(errors).toEqual([]);await expect(page.locator('#error')).toBeHidden();
  await page.setViewportSize({width:1440,height:1000});
  delete project.cases[0].configuration.fields['operating-points-initialization'];
  await page.locator('#project-file').setInputFiles({name:'older-polar.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});
  await expect(page.locator('#project-status')).toContainText('Project opened.');await page.locator('#project-load').click();
  await expect(page.locator('#project-status')).toContainText('Loaded Steady polar inputs.');
  await expect(page.locator('#operating-points-initialization')).toHaveValue('cold');
});

test('failed points stay visible and cancelled or stale sequences cannot replace current results',async({page,context},testInfo)=>{
  test.setTimeout(180000);await setup(page,context);
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#speed').fill('400');await page.locator('#operating-points-values').fill('0,1,2');
  await page.locator('#operating-points-run').click();
  await expect(page.locator('#operating-points-status')).toContainText('0/3 points converged; 3 failed');
  const failed=await exported(page,'#operating-points-json');
  expect(failed.points.every(p=>!p.converged&&p.error.message.includes('Mach'))).toBe(true);
  await expect(page.locator('#operating-points-table tbody tr')).toHaveCount(3);
  await expect(page.locator('#operating-points-table tbody button')).toHaveCount(0);
  await writeFile(testInfo.outputPath('failed-polar.json'),JSON.stringify(failed,null,2));
  await page.locator('#speed').fill('30');await expect(page.locator('#operating-points-results')).toBeHidden();
  await page.locator('#operating-points-values').fill('1,,2');await page.locator('#operating-points-run').click();
  await expect(page.locator('#operating-points-error')).toContainText('missing');
  await page.locator('#operating-points-values').fill(Array.from({length:40},(_,i)=>i%6).join(','));
  await page.locator('#operating-points-run').click();await expect(page.locator('#cancel')).toBeVisible();
  await page.locator('#alpha').fill('7');
  await expect(page.locator('#runtime-status')).toHaveText('Inputs changed; run the steady sequence again');
  await expect(page.locator('#operating-points-results')).toBeHidden();
  await expect(page.locator('#operating-points-run')).toBeEnabled();
  await page.locator('#operating-points-run').click();await expect(page.locator('#cancel')).toBeVisible();
  // The cancellation restarts the runtime; local files are fetched again.
  await context.setOffline(false);await page.locator('#cancel').click();await ready(page);
  await expect(page.locator('#operating-points-results')).toBeHidden();
  await context.setOffline(true);await page.locator('#operating-points-values').fill('1');
  await page.locator('#operating-points-run').click();
  await expect(page.locator('#operating-points-status')).toContainText('1/1 points converged');
});
