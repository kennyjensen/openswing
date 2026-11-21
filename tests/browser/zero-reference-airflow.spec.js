import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';

const study=process.env.OPENSWING_ZERO_REFERENCE_STUDY || 'artifacts/isae/st4-airflow-zero-area-20261103';
const evidence=process.env.OPENSWING_ZERO_REFERENCE_EVIDENCE || study;
test.use({launchOptions:{executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-webgl','--js-flags=--max-old-space-size=192']}});
async function download(page,id){
  const event=page.waitForEvent('download');await page.locator(id).click();
  return readFile(await(await event).path(),'utf8');
}
async function solve(page){
  await expect(page.locator('#solve')).toBeEnabled();await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText(/^(Analysis converged|Analysis stopped)$/,{timeout:180000});
  await expect(page.locator('#error')).toBeHidden();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged');
}

test('zero Sref preserves dimensional airflow, modes and saved solutions offline',async({page,context})=>{
  test.setTimeout(360000);
  const input=JSON.parse(await readFile(`${study}/request.json`,'utf8'));
  const native=JSON.parse(await readFile(`${study}/result.json`,'utf8'));
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles({name:'7a_b17.asw',mimeType:'text/plain',buffer:Buffer.from(input.source)});
  await expect(page.locator('#editor')).toHaveValue(input.source);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('details').evaluateAll(nodes=>nodes.forEach(n=>n.open=true));
  await page.locator('#mode').selectOption('rigid');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');await page.locator('#beta').fill('1');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await context.setOffline(true);await solve(page);
  await expect(page.locator('#cl')).toHaveText('—');await expect(page.locator('#cd')).toHaveText('—');
  await expect(page.locator('#trefftz-note')).toContainText('Sref is zero');
  const rigid=JSON.parse(await download(page,'#export-json'));
  expect(rigid.CL).toBeNull();expect(rigid.CD).toBeNull();expect(rigid.coefficient_normalization.available).toBe(false);
  expect(Math.abs(rigid.force[1])).toBeGreaterThan(.01);expect(rigid.trefftz.available).toBe(true);

  await page.locator('#node-file').setInputFiles({name:'mesh.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({format:'openswing-mesh',version:1,panels:input.panels}))});
  await page.waitForFunction(()=>!document.querySelector('#node-file').value);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('modes');
  await page.locator('#structural-equations').selectOption('aswing-airflow');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#speed').fill('120');await page.locator('#beta').fill('0');
  await page.locator('#density-mode').selectOption('custom');await page.locator('#density').fill(String(input.condition.density));
  await page.locator('#gravity-magnitude').fill('9.81');await page.locator('#stall').check();await page.locator('#aero-lag').check();
  for(const [beam,count] of Object.entries(input.condition.circulation_modes || {})){
    await page.locator(`#circulation-modes input[data-circulation-beam="${beam}"]`).fill(String(count));
  }
  await page.locator('#modal-frame').selectOption('fixed');await page.locator('#modal-count').fill('16');
  await page.locator('#modal-method').selectOption('full_shift_invert');await page.locator('#modal-shift-real').fill('0');await page.locator('#modal-shift-imag').fill('300');
  await page.locator('#modal-step').fill('0.00001');await page.locator('#modal-rank').fill('0.000000001');await page.locator('#modal-matrices').uncheck();
  const started=Date.now();await solve(page);const seconds=(Date.now()-started)/1000;
  const bytes=await download(page,'#export-json'),result=JSON.parse(bytes);
  expect(result.structural_operator).toBe('drela-moving-airflow-v1');expect(result.vacuum).toBe(false);
  expect(result.request.source).toBe(input.source);expect(result.request.panels).toEqual(input.panels);
  for(const key of ['speed','alpha','beta','density','mach','gravity_magnitude','aero_lag','stall'])expect(result.request.condition[key]).toEqual(input.condition[key]);
  expect(result.base.residual).toBeLessThan(1e-8);expect(result.modes).toHaveLength(native.modes.length);
  expect(result.diagnostics.matrix_assembly.structured).toBe(true);
  if(Object.values(input.condition.circulation_modes || {}).some(count=>count>0)){
    expect(result.request.condition.circulation_modes).toEqual(input.condition.circulation_modes);
    const geometry=result.diagnostics.state_linearization.geometry_assembly;
    expect(geometry.local_groups).toBeLessThan(geometry.original_local_groups);
  }
  const unused=new Set(result.modes.map((_,i)=>i));let maximumPoleError=0;
  for(const ref of native.modes){
    const distance=i=>Math.hypot(...result.modes[i].eigenvalue.map((x,k)=>x-ref.eigenvalue[k]));
    const index=[...unused].sort((a,b)=>distance(a)-distance(b))[0];
    const error=distance(index)/(1+Math.hypot(...ref.eigenvalue));maximumPoleError=Math.max(error,maximumPoleError);
    expect(error).toBeLessThan(2e-7);unused.delete(index);
  }
  for(const mode of result.modes){
    expect(mode.output.global.CL).toBeNull();expect(mode.output.global.force).not.toBeNull();
    expect(mode.left_backward_error).toBeLessThan(1e-8);expect(mode.right_backward_error).toBeLessThan(1e-8);
  }
  await page.locator('#project-settings').evaluate(e=>e.open=true);
  await page.locator('#project-solution-name').fill('Zero-area airflow modes');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Computed solution saved.');
  const project=await download(page,'#project-export');
  await page.locator('#project-file').setInputFiles({name:'zero-area.json',mimeType:'application/json',buffer:Buffer.from(project)});
  await expect(page.locator('#project-status')).toContainText('Project opened.');await page.locator('#project-load-solution').click();
  await expect(page.locator('#project-status')).toContainText('Opened Zero-area airflow modes.');
  expect(await download(page,'#export-json')).toBe(bytes);
  expect(errors).toEqual([]);
  await writeFile(`${evidence}/browser.json`,JSON.stringify({status:'PASS',offline:true,seconds,maximumPoleError,errors,rigid,result,project_restore_exact:true})+'\n');
});
