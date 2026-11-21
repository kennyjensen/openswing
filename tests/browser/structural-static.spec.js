import {test,expect} from '@playwright/test';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const sha=b=>createHash('sha256').update(b).digest('hex');
const ready=async p=>{await expect(p.locator('#solve')).toBeEnabled();await expect(p.locator('#error')).toBeHidden();};
async function download(p,id='#export-json'){const event=p.waitForEvent('download');await p.locator(id).click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}
async function run(p){await p.locator('#solve').click();await expect(p.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});await ready(p);}
async function load(p,name,panels){
  const path=`examples/isae-st3-static-${name}.asw`,source=await readFile(path,'utf8');
  await p.locator('#file').setInputFiles(path);await expect(p.locator('#editor')).toHaveValue(source);await ready(p);
  await expect(p.locator('#mode')).toHaveValue('structural');
  await p.locator('#panels').fill(String(panels));await p.locator('#panels').press('Tab');await ready(p);
  return source;
}

test('literal signed static models solve offline, preserve physics, reject negative-mass dynamics and round-trip saved solutions',async({page,context},info)=>{
  test.setTimeout(600000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const baselineBytes=await readFile('docs/validation/isae-st3-static.json'),baseline=JSON.parse(baselineBytes);
  const modules={};for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py')))modules[n]=sha(await readFile('openswing/'+n));
  await page.goto('/');await ready(page);await context.setOffline(true);
  const cases=[];
  for(const name of ['0_3_90','p15_0','m15_0']){
    const source=await load(page,name,64);
    await expect(page.locator('#speed')).toBeHidden();await expect(page.locator('#atmosphere-settings')).toBeHidden();
    // An unused flight input must neither block nor enter a structural solve.
    await page.locator('#speed').evaluate(e=>e.value='');
    await run(page);const result=await download(page);
    expect(result.analysis).toBe('structural_static');expect(result.request.source).toBe(source);expect(result.request.condition).toBeNull();
    expect(result.condition).toBeNull();expect(result.strips).toEqual([]);expect(result.atmosphere).toBeUndefined();
    expect(result.mass_properties.physical).toBe(false);expect(result.mass_properties.cg).toBeNull();expect(result.equilibrium_state.launch).toBeUndefined();
    expect(result.software_provenance.modules).toEqual(modules);expect(result.residual).toBeLessThan(1e-8);
    const key=baseline.archived_final_weights.find(r=>r.name===name).native_key;
    const old=baseline.runs.find(r=>r.key===key).result.result;
    let position=0,rotation=0;
    for(let i=0;i<old.nodes.length;i++)for(let j=0;j<3;j++){
      position=Math.max(position,Math.abs(result.nodes[i].position[j]-old.nodes[i].position[j]));
      for(let k=0;k<3;k++)rotation=Math.max(rotation,Math.abs(result.nodes[i].rotation[j][k]-old.nodes[i].rotation[j][k]));
    }
    expect(position).toBeLessThan(2e-8);expect(rotation).toBeLessThan(2e-8);
    await expect(page.locator('#mass')).toHaveText('—');await expect(page.locator('#plot svg')).toBeVisible();
    cases.push({name,result,maximum_position_difference:position,maximum_rotation_difference:rotation});
  }
  await page.locator('#project-settings').evaluate(e=>e.open=true);
  await page.locator('#project-solution-name').fill('Signed static couple');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Computed solution saved.');
  const project=await download(page,'#project-export');expect(project.solutions[0].kind).toBe('structural');expect(project.solutions[0].data).toEqual(cases.at(-1).result);
  await page.locator('#static-gravity-mode').selectOption('custom');await page.locator('#static-gravity-z').fill('0');await run(page);
  const zero=await download(page);expect(zero.max_displacement).toBeLessThan(1e-12);expect(zero.gravity_body).toEqual([0,0,0]);
  await page.evaluate(()=>{window.reopenActions=[];const post=Worker.prototype.postMessage;Worker.prototype.postMessage=function(p,...rest){window.reopenActions.push(p.request?.action);return post.call(this,p,...rest);};});
  await page.locator('#project-load-solution').click();await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');await ready(page);
  expect(await download(page)).toEqual(cases.at(-1).result);
  expect((await page.evaluate(()=>window.reopenActions)).filter(a=>!['inspect','distribution','discard_frequency'].includes(a))).toEqual([]);
  await page.screenshot({path:info.outputPath('structural-static-desktop.png'),fullPage:true});
  await page.locator('#mode').selectOption('mounted');await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis stopped');
  await expect(page.locator('#error')).toContainText('Point weights must be nonnegative');
  expect(errors).toEqual([]);
  const report={status:'PASS',offline:true,cases,zero_gravity:zero,saved_solution_round_trip:true,negative_mass_aerodynamic_rejection:true,kernelModules:modules,baseline_sha256:sha(baselineBytes),test_sha256:sha(await readFile(import.meta.filename))};
  await writeFile(info.outputPath('structural-static-browser.json'),JSON.stringify(report,null,2)+'\n');
});

test('mobile structural controls and plots work without airflow fields',async({page,context},info)=>{
  test.setTimeout(240000);await page.setViewportSize({width:390,height:844});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await context.setOffline(true);await page.locator('#workspace-tab-settings').click();
  await load(page,'p15_0',16);await expect(page.locator('#structural-settings')).toBeVisible();await expect(page.locator('#speed')).toBeHidden();
  await run(page);await expect(page.locator('#plot svg')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  await page.screenshot({path:info.outputPath('structural-static-mobile.png'),fullPage:true});
  await page.locator('#workspace-tab-output').click();await expect(page.locator('#pane-report')).toContainText('STRUCTURAL STATIC');
  expect(errors).toEqual([]);
  await writeFile(info.outputPath('structural-static-mobile.json'),JSON.stringify({status:'PASS',offline:true,viewport:{width:390,height:844},test_sha256:sha(await readFile(import.meta.filename))},null,2)+'\n');
});
