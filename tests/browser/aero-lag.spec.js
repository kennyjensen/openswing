import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
const data=async(page,id)=>{const d=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await d).path(),'utf8'));};
async function setup(page,source,speed='30'){
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles({name:'lag-check.asw',mimeType:'text/plain',buffer:Buffer.from(source)});
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#alpha').fill('0');await page.locator('#speed').fill(speed);
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#circulation-settings').evaluate(e=>e.open=true);
  await expect(page.locator('#aero-lag')).toBeChecked();
}
async function solve(page,text='Analysis converged'){
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText(text,{timeout:180000});
  await expect(page.locator('#error')).toBeHidden();return data(page,'#export-json');
}

test('lag option changes coupled modes and survives saved cases and time launch offline',async({page,context})=>{
  test.setTimeout(420000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await setup(page,await readFile('examples/heave-pitch.asw','utf8'),'50');
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-count').fill('8');await context.setOffline(true);
  const on=await solve(page);expect(on.diagnostics.finite_dimension).toBe(8);expect(on.base.aerodynamic_lag.enabled).toBe(true);
  await page.locator('#aero-lag').uncheck();await expect(page.locator('#export-json')).toBeDisabled();
  const off=await solve(page);expect(off.diagnostics.finite_dimension).toBe(4);expect(off.condition.aero_lag).toBe(false);
  expect(off.base.aerodynamic_lag.circulation).toBe('algebraic');expect(off.base.mass_properties.mass).toBeCloseTo(on.base.mass_properties.mass,10);
  expect(off.base.equilibrium_state.launch.condition.aero_lag).toBe(false);
  await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText('AERODYNAMIC LAG · DISABLED');
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);await page.locator('#equilibrium-use').click();
  await page.locator('#project-settings').evaluate(e=>e.open=true);
  await page.locator('#project-case-name').fill('Instantaneous circulation');await page.locator('#project-add').click();
  await expect(page.locator('#project-status')).toContainText('New case saved');
  await page.locator('#aero-lag').check();await page.locator('#project-load').click();
  await expect(page.locator('#project-status')).toContainText('Loaded Instantaneous circulation');await expect(page.locator('#aero-lag')).not.toBeChecked();
  // Saved time launch owns its physical setup even when the live inputs differ.
  await page.locator('#aero-lag').check();await page.locator('#mode').selectOption('time');
  await expect(page.locator('#equilibrium-status')).toContainText('Saved aerodynamic lag: disabled');
  await page.locator('#time-duration').fill('.02');await page.locator('#time-step').fill('.01');
  const history=await solve(page,'Time integration converged');expect(history.condition.aero_lag).toBe(false);
  for(const s of history.snapshots){expect(s.aerodynamic_lag.enabled).toBe(false);expect(s.circulation_rate_force).toEqual([0,0,0]);}
  await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText('AERODYNAMIC LAG · DISABLED');
  await page.locator('#circulation-settings').screenshot({path:'test-results/aero-lag-controls.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#equilibrium-status').scrollIntoViewIfNeeded();await page.screenshot({path:'test-results/aero-lag-mobile.png'});
  expect(errors).toEqual([]);
});

test('offline Bode gust response follows enabled and disabled section limits',async({page,context})=>{
  test.setTimeout(300000);
  let source=(await readFile('examples/rectangular.asw','utf8')).split('t dCLdF1')[0]+'End\n';
  source=source.replace('6 0 6 0','100000 0 100000 0').replace('6 .008','100000 .008').replaceAll('.008','0').replace('12 1 12','200000 1 200000');
  await setup(page,source);await page.locator('#mode').selectOption('frequency');
  await page.locator('#frequency-inputs').selectOption('gust');
  await page.locator('#frequency-gust-settings > summary').click();
  await page.locator('#frequency-wave').selectOption('uniform');
  await page.locator('#frequency-spacing').selectOption('linear');await page.locator('#frequency-start').fill('0');
  await page.locator('#frequency-end').fill('30');await page.locator('#frequency-count').fill('3');await context.setOffline(true);
  for(const lag of [true,false]){
    await page.locator('#aero-lag').setChecked(lag);const r=await solve(page);expect(r.base.aerodynamic_lag.enabled).toBe(lag);
    for(const s of r.samples){const v=s.responses[0].output.global.CL,k=s.omega/30;
      const real=2*Math.PI/30*(lag?(1+2*k*k)/(1+4*k*k):1),imag=lag?-2*Math.PI/30*k/(1+4*k*k):0;
      expect(Math.abs(v.real-real)).toBeLessThan(4e-5);expect(Math.abs(v.imag-imag)).toBeLessThan(4e-5);
    }
  }
  await expect(page.locator('#frequency-gain-plot svg')).toBeVisible();
});

test('older saved workbench cases restore the enabled lag default',async({page,context})=>{
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await context.setOffline(true);
  await page.locator('#project-settings').evaluate(e=>e.open=true);await page.locator('#project-case-name').fill('Legacy case');
  const project=await data(page,'#project-export-current');delete project.cases[0].configuration.fields['aero-lag'];
  await page.locator('#circulation-settings').evaluate(e=>e.open=true);await page.locator('#aero-lag').uncheck();
  await page.locator('#project-file').setInputFiles({name:'old-project.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});
  await expect(page.locator('#project-status')).toContainText('Project opened');await page.locator('#project-load').click();
  await expect(page.locator('#project-status')).toContainText('Loaded Legacy case');await expect(page.locator('#aero-lag')).toBeChecked();
  expect((await data(page,'#project-export-current')).cases[0].configuration.fields['aero-lag']).toBe(true);
  await expect(page.locator('#error')).toBeHidden();
});
