import {test,expect} from '@playwright/test';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const sha=b=>createHash('sha256').update(b).digest('hex');
const ready=async p=>{await expect(p.locator('#solve')).toBeEnabled();await expect(p.locator('#error')).toBeHidden();};
async function download(p){const event=p.waitForEvent('download');await p.locator('#export-json').click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}
async function load(p,name,panels){
  const path=`examples/isae-st5-static-${name}.asw`,source=await readFile(path,'utf8');
  await p.locator('#file').setInputFiles(path);await expect(p.locator('#editor')).toHaveValue(source);await ready(p);
  await expect(p.locator('#mode')).toHaveValue('structural');
  await p.locator('#panels').fill(String(panels));await p.locator('#panels').press('Tab');await ready(p);return source;
}
async function run(p){await p.locator('#solve').click();await expect(p.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});await ready(p);}

test('literal distributed static joined wings solve offline and preserve all native nodes and section loads',async({page,context},info)=>{
  test.setTimeout(600000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const baselineBytes=await readFile('docs/validation/distributed-static.json'),baseline=JSON.parse(baselineBytes);
  const modules={};for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py')))modules[n]=sha(await readFile('openswing/'+n));
  await page.goto('/');await ready(page);await context.setOffline(true);const cases=[];
  for(const name of ['30lb_90_10','20lb_90_10','20lb_80_20']){
    const source=await load(page,name,64);await expect(page.locator('#speed')).toBeHidden();await expect(page.locator('#static-weight-note')).toContainText('Dmg');
    await run(page);const result=await download(page);expect(result.request.source).toBe(source);expect(result.request.condition).toBeNull();
    expect(result.analysis).toBe('structural_static');expect(result.software_provenance.modules).toEqual(modules);
    expect(result.mass_properties.physical).toBe(false);expect(result.mass_properties.signed_distributed_weights).toEqual([{beam:1,field:'Dmg'},{beam:2,field:'Dmg'}]);
    expect(result.mass_properties.cg).toBeNull();expect(result.equilibrium_state.launch).toBeUndefined();expect(result.residual).toBeLessThan(1e-8);
    const old=baseline.cases.find(c=>c.name==='JW_1_'+name).runs.find(r=>r.specification.panels===64).result;
    const differences={};
    for(const field of ['applied_force','applied_moment','support_force','support_moment','force_balance','moment_balance']){
      differences[field]=Math.max(...old[field].map((v,i)=>Math.abs(v-result[field][i])));expect(differences[field]).toBeLessThan(2e-8);
    }
    for(const [collection,fields] of [['nodes',['position','rotation']],['elements',['force','moment','strain','curvature_change']]]){
      expect(result[collection].length).toBe(old[collection].length);
      for(const field of fields){let maximum=0;for(let i=0;i<old[collection].length;i++){
        const a=old[collection][i][field].flat(Infinity),b=result[collection][i][field].flat(Infinity);
        expect(a.length).toBe(b.length);for(let j=0;j<a.length;j++)maximum=Math.max(maximum,Math.abs(a[j]-b[j]));
      }differences[collection+'.'+field]=maximum;expect(maximum).toBeLessThan(2e-8);}
    }
    await expect(page.locator('#plot-quantity')).toHaveValue('structure:moment_axes.0');await expect(page.locator('#plot svg')).toBeVisible();
    await page.locator('#plot-beam').selectOption('2');await expect(page.locator('#plot svg')).toBeVisible();
    cases.push({name,result,differences});
  }
  await page.screenshot({path:info.outputPath('distributed-static-desktop.png'),fullPage:true});
  await page.locator('#mode').selectOption('mounted');await page.locator('#solve').click();
  await expect(page.locator('#error')).toContainText('Distributed weights and centroidal inertias must be nonnegative');
  expect(errors).toEqual([]);
  await writeFile(info.outputPath('distributed-static-browser.json'),JSON.stringify({status:'PASS',offline:true,cases,kernelModules:modules,baseline_sha256:sha(baselineBytes),test_sha256:sha(await readFile(import.meta.filename)),negative_mass_rejected:true},null,2)+'\n');
});

test('distributed static controls and two-surface structural plots work on mobile',async({page,context},info)=>{
  test.setTimeout(240000);await page.setViewportSize({width:390,height:844});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await ready(page);await context.setOffline(true);await page.locator('#workspace-tab-settings').click();
  await load(page,'30lb_90_10',16);await expect(page.locator('#structural-settings')).toBeVisible();await run(page);
  await expect(page.locator('#plot svg')).toBeVisible();await page.locator('#plot-beam').selectOption('2');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  await page.screenshot({path:info.outputPath('distributed-static-mobile.png'),fullPage:true});
  await page.locator('#workspace-tab-output').click();await expect(page.locator('#pane-report')).toContainText('STRUCTURAL STATIC');
  expect(errors).toEqual([]);await writeFile(info.outputPath('distributed-static-mobile.json'),JSON.stringify({status:'PASS',offline:true,viewport:{width:390,height:844},test_sha256:sha(await readFile(import.meta.filename))},null,2)+'\n');
});
