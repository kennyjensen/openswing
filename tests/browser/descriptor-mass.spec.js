import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
async function saved(page){const event=page.waitForEvent('download');await page.locator('#export-json').click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}

test('loaded swept wing resolves modes and consistent initial spectra offline',async({page,context})=>{
  test.setTimeout(360000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:original.call(this,type,...args);};});
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#file').setInputFiles('examples/flexible.asw');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#alpha').fill('4');await page.locator('#speed').fill('30');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  // The standard pointwise circulation option exercises the unchanged UI defaults.
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-count').fill('6');await context.setOffline(true);
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:170000});
  const modes=await saved(page);expect(modes.base.max_displacement).toBeGreaterThan(.01);
  expect(modes.diagnostics.derivative_linearization.method).toContain('load coefficient');
  expect(modes.diagnostics.finite_dimension).toBeGreaterThan(30);expect(modes.modes).toHaveLength(6);
  const mode=modes.modes.find(v=>v.eigenvalue[1]>1);expect(mode).toBeTruthy();
  const scale=.001,nodes=modes.base.nodes.map(node=>{const output=mode.output.nodes[node.index];return {beam:node.beam,t:node.t,...Object.fromEntries(['displacement','rotation','velocity','rates'].map(key=>[key,output[key].real.map(v=>v*scale)]))};});
  const circulation=mode.output.strips.filter(v=>v.circulation).map(v=>v.circulation.real*scale);
  await page.locator('#modal-select').selectOption(String(mode.index));await page.locator('#viewport').screenshot({path:'test-results/descriptor-mass-wing-mode.png'});
  await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-inputs').selectOption('initial');await page.locator('#frequency-initial-settings').evaluate(e=>e.open=true);
  await page.locator('#frequency-initial').fill(JSON.stringify([{kind:'initial',name:'Loaded wing mode',state:{nodes,circulation}}]));
  await page.locator('#frequency-initial-shift').fill('100');await page.locator('#frequency-spacing').selectOption('linear');await page.locator('#frequency-start').fill('0');await page.locator('#frequency-end').fill('10');await page.locator('#frequency-count').fill('3');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:170000});
  const spectrum=await saved(page);expect(spectrum.diagnostics.initial_conditions.finite_dimension).toBe(modes.diagnostics.finite_dimension);
  for(const sample of spectrum.samples){
    const w=sample.omega,[real,imag]=mode.eigenvalue;
    for(let i=0;i<mode.right.real.length;i++){
      const vr=scale*mode.right.real[i],vi=scale*mode.right.imag[i],x=100-real,y1=w-imag,y2=w+imag;
      const expectedReal=.5*((vr*x+vi*y1)/(x*x+y1*y1)+(vr*x-vi*y2)/(x*x+y2*y2));
      const expectedImag=.5*((vi*x-vr*y1)/(x*x+y1*y1)+(-vi*x-vr*y2)/(x*x+y2*y2));
      expect(sample.responses[0].state.real[i]).toBeCloseTo(expectedReal,8);expect(sample.responses[0].state.imag[i]).toBeCloseTo(expectedImag,8);
    }
  }
  await expect(page.locator('#frequency-transport')).toBeHidden();await expect(page.locator('#geometry-label')).toContainText('BASE · INITIAL-STATE SPECTRUM');
  await page.locator('#frequency-group').selectOption('nodes');await page.locator('#frequency-quantity').selectOption({label:'displacement z [input L]'});
  await page.locator('#pane-frequency').screenshot({path:'test-results/descriptor-mass-wing-spectrum.png'});
  expect(errors).toEqual([]);
});
