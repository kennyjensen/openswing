import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {solutionChecksum} from '../../web/solution-data.js';
const text=async(page,id)=>{const d=page.waitForEvent('download');await page.locator(id).click();return readFile(await(await d).path(),'utf8');};
const data=async(page,id='#export-json')=>JSON.parse(await text(page,id));
const parseCSV=text=>{const rows=text.trimEnd().split('\n').map(line=>[...line.matchAll(/"((?:[^"]|"")*)"(?:,|$)/g)].map(m=>m[1].replaceAll('""','"')));return rows.slice(1).map(row=>Object.fromEntries(rows[0].map((h,i)=>[h,row[i]])));};
async function ready(page){await expect(page.locator('#solve')).toBeEnabled();}
async function open(page,context){
  await page.goto('/');await ready(page);await context.setOffline(true);
  await page.locator('#file').setInputFiles('.reference/isae-sa2/SA_2.asw');await ready(page);
  await page.locator('#speed').fill('49.9');await page.locator('#alpha').fill('10.5');await page.locator('#beta').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#density-mode').selectOption('custom');await page.locator('#density').fill('1.2256');
}
async function panels(page,n){await page.locator('#panels').fill(String(n));await page.locator('#panels').press('Tab');await ready(page);}
async function solve(page,label='Analysis converged'){await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText(label,{timeout:180000});return data(page);}
const importProject=async(page,p)=>{await page.locator('#project-file').setInputFiles({name:'airflow.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(p))});await expect(page.locator('#project-status')).toContainText('Project opened.');await page.locator('#project-load-solution').click();await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');};

test('force-point airflow exposes tip growth, preserves archive gaps and locates invalid local Mach offline',async({page,context})=>{
  test.skip(!existsSync('.reference/isae-sa2/SA_2.asw'),'Fetch SA-2 references first.');test.setTimeout(300000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));await open(page,context);
  const reference=JSON.parse(await readFile('docs/validation/sa2-tip.json','utf8'));
  for(const n of [100,200]){
    await panels(page,n);const result=await solve(page);
    const expected=reference.cases.find(c=>c.panels===n&&!c.frozen).inferred_original_speed_tip_Mach;
    expect(result.lifting_airflow.maximum.normal_mach).toBeCloseTo(expected,7);
    for(const s of result.strips){
      expect(s.normal_mach).toBeCloseTo(s.normal_speed/result.lifting_airflow.sound_speed,12);
      const v=s.relative_velocity,sx=Math.sign(s.t)*.8801/Math.hypot(.8801,1.2446),sy=1.2446/Math.hypot(.8801,1.2446);
      const along=v[0]*sx+v[1]*sy;
      expect(s.normal_speed).toBeCloseTo(Math.hypot(v[0]-along*sx,v[1]-along*sy,v[2]),7);
    }
    await page.locator('#tab-loading').click();await page.locator('#plot-quantity').selectOption('normal_mach');
    await expect(page.locator('#plot-title')).toHaveText('Local section-normal Mach');await expect(page.locator('#plot svg')).toBeVisible();
    expect(await page.locator('#plot .plot-line').getAttribute('d')).not.toMatch(/NaN|undefined/);
    const csv=await text(page,'#csv');expect(csv).toContain('Mach_normal');expect(csv).toContain('V_normal [L/T]');
    expect(csv).toContain('force_point_x [L]');
  }
  await page.locator('#pane-loading').screenshot({path:'test-results/section-airflow-desktop.png'});
  await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText('LIFTING FORCE-POINT AIRFLOW');
  await expect(page.locator('#pane-report')).toContainText('Maximum normal Mach 0.806986');
  await page.locator('#project-settings').evaluate(e=>e.open=true);await page.locator('#project-solution-name').fill('Airflow record');
  await page.locator('#project-save-solution').click();await expect(page.locator('#project-status')).toContainText('Computed solution saved.');
  const original=await data(page,'#project-export'),old=structuredClone(original),solution=old.solutions[0];
  delete solution.data.lifting_airflow;
  for(const s of solution.data.strips)for(const key of ['normal_mach','normal_speed','relative_velocity','velocity_position'])delete s[key];
  solution.checksum=await solutionChecksum(solution);
  await importProject(page,old);await page.locator('#tab-loading').click();await page.locator('#plot-quantity').selectOption('normal_mach');
  await expect(page.locator('#plot')).toContainText('unavailable in the selected result');
  await importProject(page,original);await page.locator('#tab-loading').click();await page.locator('#plot-quantity').selectOption('vz');
  await expect(page.locator('#plot svg')).toBeVisible();await expect(page.locator('#plot-unit')).toContainText('input L/T');
  await panels(page,400);await page.locator('#solve').click();
  await expect(page.locator('#error')).toContainText('Maximum M_perp=1.619776',{timeout:120000});
  await expect(page.locator('#error')).toContainText('body force point');await expect(page.locator('#export-json')).toBeDisabled();
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.screenshot({path:'test-results/section-airflow-mobile.png'});expect(errors).toEqual([]);
});

test('computed time states expose local Mach histories and all-state velocity CSV',async({page,context})=>{
  test.skip(!existsSync('.reference/isae-sa2/SA_2.asw'),'Fetch SA-2 references first.');test.setTimeout(240000);
  await open(page,context);await panels(page,4);await page.locator('#alpha').fill('0');await page.locator('#mode').selectOption('mounted');
  const steady=await solve(page);await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);await page.locator('#equilibrium-use').click();
  await page.locator('#mode').selectOption('time');await page.locator('#time-duration').fill('.02');await page.locator('#time-step').fill('.01');
  const result=await solve(page,'Time integration converged');expect(result.snapshots.length).toBe(3);
  for(const s of result.snapshots){expect(s.lifting_airflow.samples).toBe(4);expect(s.lifting_airflow.maximum.normal_mach).toBeCloseTo(steady.lifting_airflow.maximum.normal_mach,10);}
  await page.locator('#tab-loading').click();await page.locator('#plot-quantity').selectOption('normal_mach');await page.locator('#plot-scope').selectOption('overlay');
  await expect(page.locator('#plot .distribution-trace')).toHaveCount(3);await page.locator('#plot-scope').selectOption('envelope');
  // A constant horizontal SVG path has a zero-height bounding box. Check its
  // geometry and visible point markers, rather than Playwright's box heuristic.
  await expect(page.locator('#plot path.distribution-max')).toHaveAttribute('d',/^M[\d.]+ [\d.]+h0L/);
  await expect(page.locator('#plot circle.distribution-max')).toHaveCount(4);
  await expect(page.locator('#plot circle.distribution-max').first()).toBeVisible();
  await page.locator('#pane-loading').screenshot({path:'test-results/section-airflow-history.png'});
  const csv=await text(page,'#plot-history-csv');
  expect(csv).toContain('"V_relative_z [L/T]"');expect(csv).toContain('"Mach_normal"');expect(csv.trim().split('\n')).toHaveLength(13);
  for(const row of parseCSV(csv)){
    const sample=result.snapshots[Number(row['snapshot_index (0-based)'])].strips[Number(row['beam_station_index (0-based)'])];
    expect(Number(row.Mach_normal)).toBe(sample.normal_mach);
    expect(Number(row['V_normal [L/T]'])).toBe(sample.normal_speed);
    for(const [i,axis] of ['x','y','z'].entries()){
      expect(Number(row[`V_relative_${axis} [L/T]`])).toBe(sample.relative_velocity[i]);
      expect(Number(row[`force_point_${axis} [L]`])).toBe(sample.velocity_position[i]);
    }
  }
  const envelope=parseCSV(await text(page,'#plot-envelope-csv'));expect(envelope).toHaveLength(4);
  for(const [j,row] of envelope.entries()){
    const values=result.snapshots.map(s=>s.strips[j].normal_mach);
    expect(row.quantity).toBe('normal_mach');expect(row.unit).toBe('Mach');
    expect(Number(row.min_value)).toBe(Math.min(...values));expect(Number(row.max_value)).toBe(Math.max(...values));
    expect(Number(row.available_snapshots)).toBe(3);
  }
});
