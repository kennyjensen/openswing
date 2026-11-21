import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
import {solutionChecksum} from '../../web/solution-data.js';
const download=async(page,id,json=false)=>{const event=page.waitForEvent('download');await page.locator(id).click();const text=await readFile(await(await event).path(),'utf8');return json?JSON.parse(text):text;};
const parseCSV=text=>{const rows=text.trimEnd().split('\n').map(line=>[...line.matchAll(/"((?:[^"]|"")*)"(?:,|$)/g)].map(m=>m[1].replaceAll('""','"')));return rows.slice(1).map(row=>Object.fromEntries(rows[0].map((h,i)=>[h,row[i]])));};
const solve=async(page,label='Analysis converged')=>{await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText(label,{timeout:180000});return download(page,'#export-json',true);};

test('derived section loads retain physical units, saved-history samples and missing-field gaps offline',async({page,context})=>{
  test.setTimeout(300000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('section-outputs');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#speed').fill('30');await page.locator('#alpha').fill('0');await page.locator('#beta').fill('0');
  await page.locator('[data-control="1"]').fill('3');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await context.setOffline(true);
  const rigid=await solve(page),cm=-.025/Math.sqrt(1-(30/340.294)**2);
  for(const row of rigid.strips){expect(row.cm).toBeCloseTo(cm,12);expect(row.f_aero).toBeCloseTo(0,12);expect(row.f_reac).toBeCloseTo(-2.5*9.80665,12);expect(row.da_eff).toBe(0);}
  await page.locator('#tab-loading').click();
  for(const key of ['cm','f_aero','f_reac','da_eff']){
    await page.locator('#plot-quantity').selectOption(key);await expect(page.locator('#plot svg')).toBeVisible();
    await expect(page.locator('#plot-title')).not.toHaveText('');
    expect(await page.locator('#plot .plot-line').getAttribute('d')).not.toMatch(/NaN|undefined/);
  }
  await expect(page.locator('#plot-unit')).toContainText('deg');
  const csv=await download(page,'#csv');expect(csv).toContain('da_eff [rad]');expect(csv).toContain('f_reac [F/L]');
  await page.locator('#mode').selectOption('mounted');const steady=await solve(page);
  expect(steady.support_force[2]).toBeCloseTo(15*9.80665,7); // Distributed 5 kg plus separate 10 kg object.
  for(const row of steady.strips)expect(row.f_reac).toBeCloseTo(-2.5*9.80665,10);
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);await page.locator('#equilibrium-use').click();
  await page.locator('#mode').selectOption('time');await page.locator('#time-duration').fill('.02');await page.locator('#time-step').fill('.01');
  const history=await solve(page,'Time integration converged');expect(history.snapshots).toHaveLength(3);
  await page.locator('#tab-loading').click();await page.locator('#plot-quantity').selectOption('f_reac');await page.locator('#plot-scope').selectOption('envelope');
  await expect(page.locator('#plot circle.distribution-min')).toHaveCount(4);await expect(page.locator('#plot circle.distribution-min').first()).toBeVisible();
  const rows=parseCSV(await download(page,'#plot-history-csv'));expect(rows).toHaveLength(12);
  for(const row of rows){
    const sample=history.snapshots[Number(row['snapshot_index (0-based)'])].strips[Number(row['beam_station_index (0-based)'])];
    expect(Number(row.cm_quarter_chord)).toBe(sample.cm);
    for(const key of ['f_aero','f_reac'])expect(Number(row[`${key} [F/L]`])).toBe(sample[key]);
    expect(Number(row['da_eff [rad]'])).toBe(sample.da_eff);
    expect(Number(row['f_reac [F/L]'])).toBeCloseTo(-2.5*9.80665,9);
  }
  await page.locator('#pane-loading').screenshot({path:'test-results/section-outputs-history.png'});
  await page.locator('#project-settings').evaluate(e=>e.open=true);await page.locator('#project-solution-name').fill('Derived section loads');await page.locator('#project-save-solution').click();
  const original=await download(page,'#project-export',true),old=structuredClone(original),solution=old.solutions[0];
  for(const state of [solution.data,...solution.data.snapshots]){
    delete state.section_output_definitions;
    for(const row of state.strips??[])for(const key of ['cm','f_aero','f_reac','da_eff'])delete row[key];
  }
  solution.checksum=await solutionChecksum(solution);
  const restore=async project=>{await page.locator('#project-file').setInputFiles({name:'sections.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});await expect(page.locator('#project-status')).toContainText('Project opened');await page.locator('#project-load-solution').click();await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');};
  await restore(old);await page.locator('#tab-loading').click();await expect(page.locator('#plot')).toContainText('No values available');
  await restore(original);await page.locator('#tab-loading').click();await expect(page.locator('#plot svg')).toBeVisible();
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#pane-loading').screenshot({path:'test-results/section-outputs-mobile.png'});expect(errors).toEqual([]);
});

test('computed deformation exposes effective incidence in degrees while exports retain radians',async({page,context})=>{
  test.setTimeout(240000);await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('flexible');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('mounted');await page.locator('#speed').fill('30');await page.locator('#alpha').fill('5');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await context.setOffline(true);const result=await solve(page);
  expect(result.max_displacement).toBeGreaterThan(1);expect(Math.max(...result.strips.map(s=>Math.abs(s.da_eff)))).toBeGreaterThan(.001);
  await page.locator('#tab-loading').click();await page.locator('#plot-quantity').selectOption('da_eff');await expect(page.locator('#plot-unit')).toContainText('deg');
  const csv=(await download(page,'#csv')).trim().split('\n').map(row=>row.split(',')),index=csv[0].indexOf('da_eff [rad]');
  for(const [j,row] of csv.slice(1).entries())expect(Number(row[index])).toBe(result.strips[j].da_eff);
  await page.locator('#pane-loading').screenshot({path:'test-results/section-outputs-elastic.png'});
});
