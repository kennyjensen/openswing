import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
async function ready(page){await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#distribution-preview')).toBeEnabled();await expect(page.locator('#project-add')).toBeEnabled();}
async function download(page,id='#project-export'){const event=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}
async function open(page){await page.goto('/');await ready(page);await page.locator('#project-settings').evaluate(e=>e.open=true);}
async function save(page,name){await page.locator('#project-case-name').fill(name);await page.locator('#project-add').click();await expect(page.locator('#project-status')).toContainText('New case saved.');await ready(page);}
async function select(page,name){await page.locator('#project-cases').selectOption({label:name});await expect(page.locator('#project-status')).toContainText('Case selected.');}
async function load(page,name){await select(page,name);await page.locator('#project-load').click();await expect(page.locator('#project-status')).toHaveText(`Loaded ${name}. Run analysis to compute new results.`);await ready(page);}
async function inputFile(page,project){await page.locator('#project-file').setInputFiles({name:'project.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});}
async function oscillator(page){await page.locator('#example').selectOption('instrumented-oscillator');await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');await ready(page);
  await page.locator('#node-file').setInputFiles({name:'nodes.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({format:'openswing-mesh',version:1,panels:{default:4,beams:{'1':{count:4,spacing:'uniform'}}}}))});await expect(page.locator('#node-table tbody tr')).toHaveCount(5);await ready(page);
  await page.locator('#mode').selectOption('mounted');await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
}
async function solve(page){await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:240000});await expect(page.locator('#error')).toBeHidden();await ready(page);}

test('saved projects restore exact editable cases, loaded trim and analytical Bode response after reload',async({page,context})=>{
  test.setTimeout(600000);const errors=[];page.on('pageerror',e=>errors.push(e.message));await open(page);await oscillator(page);
  await page.locator('#operating-settings').evaluate(e=>e.open=true);await page.locator('#add-constraint').click();await page.locator('.constraint-variable').selectOption('power.1');await page.locator('.constraint-quantity').selectOption('user');await page.locator('.constraint-row input').fill('.01');await page.locator('[data-custom="residual_scale"]').fill('.01');
  await solve(page);const trim=await download(page,'#export-json');expect(trim.operating_values['power.1']).toBeCloseTo(5,7);expect(trim.sensors[1].displacement_body[1]).toBeCloseTo(.01,9);
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);await page.locator('#equilibrium-use').click();
  // Inactive analysis settings must survive too, including tables and all mixed-frame axes.
  await page.locator('#time-forcing').evaluate(e=>{e.value='time +E1\n0 0\n.1 2\n.2 0\n';e.dispatchEvent(new Event('input'));});
  await page.locator('#time-frame').selectOption('mixed',{force:true});await page.locator('[data-time-load="My"]').selectOption('load',{force:true});await page.locator('[data-time-target="My"]').evaluate(e=>e.value='1.25');
  await page.locator('#modal-frame').selectOption('mixed',{force:true});await page.locator('#modal-load-Mz').selectOption('load',{force:true});await page.locator('#modal-target-Mz').evaluate(e=>e.value='-.75');
  await page.locator('#frequency-count').evaluate(e=>e.value='3');await page.locator('#frequency-spacing').selectOption('linear',{force:true});await page.locator('#frequency-start').evaluate(e=>e.value='0');await page.locator('#frequency-end').evaluate(e=>e.value='20');await page.locator('#frequency-inputs').selectOption('controls',{force:true});
  await page.locator('#altitude-unit').selectOption('304.8');await page.locator('#altitude').fill('1.75');await page.locator('#density-mode').selectOption('custom');await page.locator('#density').fill('1.225');
  await save(page,'Loaded trim');const a=(await download(page)).cases[0].configuration;expect(a.equilibrium.enabled).toBe(true);expect(a.fields['time-target:My']).toBe('1.25');expect(a.fields['modal-target-Mz']).toBe('-.75');
  await page.locator('#example').selectOption('rectangular');await ready(page);await page.locator('#clear-constraints').click();await page.locator('#equilibrium-clear').click();await page.locator('#speed').fill('44');await save(page,'Wing');
  const project=await download(page);await inputFile(page,project);await expect(page.locator('#project-status')).toContainText('Project opened.');expect(await page.locator('#model-name').textContent()).toBe('Rectangular research wing');
  await load(page,'Loaded trim');await expect(page.locator('#equilibrium-enable')).toBeChecked();await expect(page.locator('#export-json')).toBeDisabled();await page.locator('#project-update').click();await expect(page.locator('#project-status')).toContainText('Case updated.');expect((await download(page)).cases[0].configuration).toEqual(a);
  await page.locator('#project-undo-load').click();await expect(page.locator('#project-status')).toHaveText('Previous workbench inputs restored.');await ready(page);await expect(page.locator('#speed')).toHaveValue('44');await expect(page.locator('#model-name')).toHaveText('Rectangular research wing');
  await page.reload();await ready(page);await page.locator('#project-settings').evaluate(e=>e.open=true);expect((await download(page)).cases).toHaveLength(2);await load(page,'Loaded trim');await page.locator('#project-update').click();await expect(page.locator('#project-status')).toContainText('Case updated.');expect((await download(page)).cases[0].configuration).toEqual(a);
  await context.setOffline(true);await page.locator('#mode').selectOption('frequency');await solve(page);const f=await download(page,'#export-json');expect(f.request.frequency.initial_state).toEqual(a.equilibrium.state);expect(f.request.panels).toEqual(a.mesh);expect(f.request.operating_constraints).toEqual(a.constraints);
  for(const row of f.samples){const d=row.responses[0].output.sensors[1].displacement_body,w=row.omega,re=500-2*w*w,im=10*w,den=re*re+im*im;expect(d.real[1]).toBeCloseTo(re/den,9);expect(d.imag[1]).toBeCloseTo(-im/den,9);}
  await page.locator('#project-settings').screenshot({path:'test-results/projects.png'});await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.locator('#project-settings').screenshot({path:'test-results/projects-mobile.png'});expect(errors).toEqual([]);
});

test('project failures and pending edits preserve the current workspace and saved cases',async({page})=>{
  test.setTimeout(240000);await open(page);await oscillator(page);await save(page,'Spring');const project=await download(page),source=await page.locator('#editor').inputValue();
  for(const modify of [p=>p.version=99,p=>p.cases[0].configuration.fields.unrecognized='x',p=>p.cases[0].configuration.fields.mode='unknown']){
    const bad=structuredClone(project);modify(bad);await inputFile(page,bad);await expect(page.locator('#error')).toBeVisible();expect(await download(page)).toEqual(project);expect(await page.locator('#editor').inputValue()).toBe(source);await page.locator('#close-error').click();
  }
  await page.locator('#tab-editor').click();await page.locator('#editor').fill(source+'\n! unapplied draft\n');await page.locator('#project-load').click();await expect(page.locator('#project-status')).toContainText('apply ASW');expect(await page.locator('#editor').inputValue()).toContain('unapplied draft');await page.locator('#apply').click();await ready(page);
  await page.locator('#tab-nodes').click();await page.locator('#node-count').fill('8');await page.locator('#project-load').click();await expect(page.locator('#project-status')).toContainText('node drafts');await page.locator('#node-apply').click();await ready(page);
  const before=await page.locator('#editor').inputValue();const bad=structuredClone(project);bad.cases[0].configuration.source='Not an ASW model';await inputFile(page,bad);await expect(page.locator('#project-status')).toContainText('Project opened.');await page.locator('#project-load').click();await expect(page.locator('#error')).toBeVisible();expect(await page.locator('#editor').inputValue()).toBe(before);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#project-undo').click();await expect(page.locator('#project-status')).toContainText('Previous project restored.');expect(await download(page)).toEqual(project);
  // A user edit while inspect is in flight must defeat the stale case load.
  await page.evaluate(()=>{const send=Worker.prototype.postMessage;Worker.prototype.postMessage=function(data,...rest){if(data.request?.action==='inspect')setTimeout(()=>send.call(this,data,...rest),1000);else send.call(this,data,...rest);};});
  await page.locator('#project-load').click();await expect(page.locator('#runtime-status')).toHaveText('Checking saved case…');await page.locator('#speed').fill('27');await expect(page.locator('#project-status')).toContainText('Inputs changed');await expect(page.locator('#speed')).toHaveValue('27');expect(await page.locator('#editor').inputValue()).toBe(before);
});

test('browser persistence prevents lost updates between tabs and supports durable undo',async({page,context})=>{
  test.setTimeout(240000);await open(page);const other=await context.newPage();await open(other);await save(page,'First tab');
  await other.locator('#speed').fill('47');await other.locator('#project-case-name').fill('Second tab');await other.locator('#project-add').click();await expect(other.locator('#project-status')).toContainText('Another tab changed');await expect(other.locator('#speed')).toHaveValue('47');
  await other.locator('#project-reload').click();await expect(other.locator('#project-status')).toContainText('Saved project reloaded.');await save(other,'Second tab');expect((await download(other)).cases).toHaveLength(2);
  await page.locator('#project-reload').click();await expect(page.locator('#project-status')).toContainText('Saved project reloaded.');await page.locator('#project-delete').click();await expect(page.locator('#project-status')).toContainText('Case removed.');expect((await download(page)).cases).toHaveLength(1);
  await page.reload();await ready(page);await page.locator('#project-settings').evaluate(e=>e.open=true);await page.locator('#project-undo').click();await expect(page.locator('#project-status')).toContainText('Previous project restored.');expect((await download(page)).cases).toHaveLength(2);await other.close();
});

test('a failed application after model inspection rolls back the full previous workspace',async({page})=>{
  test.setTimeout(240000);await open(page);await oscillator(page);await page.locator('#operating-settings').evaluate(e=>e.open=true);await page.locator('#add-constraint').click();await page.locator('.constraint-variable').selectOption('power.1');await page.locator('.constraint-quantity').selectOption('force.y');await save(page,'Spring target');
  const project=await download(page),bad=structuredClone(project);bad.cases[0].configuration.constraints[0].quantity='unsupported.target';
  await page.locator('#example').selectOption('rectangular');await ready(page);await page.locator('#clear-constraints').click();await page.locator('#speed').fill('34');await page.locator('#alpha').fill('17');const before=(await download(page,'#project-export-current')).cases[0].configuration;
  await inputFile(page,bad);await expect(page.locator('#project-status')).toContainText('Project opened.');await page.locator('#project-load').click();await expect(page.locator('#project-status')).toContainText('constraint quantity');await ready(page);
  expect((await download(page,'#project-export-current')).cases[0].configuration).toEqual(before);expect((await download(page)).cases[0].configuration.constraints[0].quantity).toBe('unsupported.target');
  await page.locator('#project-undo').click();await expect(page.locator('#project-status')).toContainText('Previous project restored.');await page.locator('#project-load').click();await expect(page.locator('#project-status')).toContainText('Loaded Spring target.');await ready(page);await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');
});
