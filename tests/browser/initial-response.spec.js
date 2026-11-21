import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
async function saved(page,id='#export-json'){await expect(page.locator(id)).toBeEnabled();const event=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}
async function prepare(page,source){
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#file').setInputFiles(source);
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#alpha').fill('0');await page.locator('#speed').fill('10');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-spacing').selectOption('linear');await page.locator('#frequency-start').fill('0');await page.locator('#frequency-end').fill('30');await page.locator('#frequency-count').fill('4');
  await page.locator('#frequency-initial-settings').evaluate(e=>e.open=true);
}

test('initial spectra run offline with physical profiles, derivative boundary terms and spectral units',async({page,context})=>{
  test.setTimeout(240000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:original.call(this,type,...args);};});
  await prepare(page,'examples/instrumented-oscillator.asw');await page.locator('#frequency-inputs').selectOption('initial');
  await page.locator('#frequency-initial-file').setInputFiles('examples/initial-spring.json');
  const profiles=await saved(page,'#frequency-initial-save');expect(profiles).toHaveLength(2);
  await context.setOffline(true);await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged');
  const result=await saved(page);expect(result.inputs).toHaveLength(2);
  for(const sample of result.samples){const w=sample.omega,re=500-2*w*w,im=10*w,den=re*re+im*im;
    const q=sample.responses[0].output.nodes.at(-1).displacement;
    expect(q.real[1]).toBeCloseTo(.002*(10*re+2*w*im)/den,11);
    expect(q.imag[1]).toBeCloseTo(.002*(2*w*re-10*im)/den,11);
  }
  await page.locator('#frequency-group').selectOption('nodes');await page.locator('#frequency-quantity').selectOption({label:'displacement y [input L]'});
  await expect(page.locator('#frequency-unit')).toContainText('One-sided initial-state spectrum');await expect(page.locator('#frequency-unit')).toContainText('input L · input T');
  await expect(page.locator('#frequency-gain-plot circle')).toHaveCount(4);await expect(page.locator('#frequency-transport')).toBeHidden();
  await expect(page.locator('#geometry-label')).toContainText('BASE · INITIAL-STATE SPECTRUM');
  await expect(page.locator('#viewport canvas')).toHaveAttribute('data-renderer','canvas2d');
  const event=page.waitForEvent('download');await page.locator('#frequency-csv').click();const file=await event;
  expect(file.suggestedFilename()).toBe('openswing-initial-spectrum.csv');const csv=await readFile(await file.path(),'utf8');
  expect(csv).toContain('X(s) / profile amplitude');expect(csv).toContain('Laplace damping [1/T]');expect(csv).toContain('input L · input T');
  await page.locator('#frequency-input').selectOption('1');await page.locator('#frequency-display').selectOption('broken_loop');
  await expect(page.locator('#frequency-unit')).toContainText('no matching aircraft response');await expect(page.locator('#frequency-gain-plot circle')).toHaveCount(0);
  await page.locator('#frequency-display').selectOption('response');await page.screenshot({path:'test-results/initial-spectrum-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#frequency-unit').scrollIntoViewIfNeeded();await page.screenshot({path:'test-results/initial-spectrum-mobile.png'});
  await page.locator('#frequency-initial').fill('[{"kind":"initial","state":{"nodes":[{"beam":1,"t":0,"displacement":[0,0.002,0]}]}}]');
  await expect(page.locator('#export-json')).toBeDisabled();await page.locator('#solve').click();await expect(page.locator('#error p')).toContainText('violates algebraic or hidden');
  expect(errors).toEqual([]);
});

test('initial response remains available when a simultaneous periodic input has a DC pole',async({page})=>{
  test.setTimeout(200000);const source=await readFile('examples/guided-body.asw','utf8')+'\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\n';
  await prepare(page,{name:'rigid.asw',mimeType:'text/plain',buffer:Buffer.from(source)});
  await page.locator('#frequency-inputs').selectOption('controls');await page.locator('#frequency-frame').selectOption('free');
  await page.locator('#frequency-end').fill('2');await page.locator('#frequency-count').fill('3');await page.locator('#frequency-initial-shift').fill('.7');
  await page.locator('#frequency-initial').fill('[{"kind":"initial","name":"Velocity release","state":{"frame":{"velocity_origin_body":[1,0,0]}}}]');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Frequency response finished with gaps');
  const result=await saved(page);expect(result.samples[0].resolved_inputs).toBe(1);
  await page.locator('#frequency-sample').selectOption('0');await expect(page.locator('#frequency-detail')).toContainText('Unavailable:');
  await page.locator('#frequency-input').selectOption('1');await page.locator('#frequency-group').selectOption('frame');await page.locator('#frequency-quantity').selectOption({label:'position earth x [input L]'});
  await expect(page.locator('#frequency-summary')).toContainText('3/3 frequencies resolved');await expect(page.locator('#frequency-gain-plot circle')).toHaveCount(3);
  await expect(page.locator('#frequency-detail')).not.toContainText('Unavailable:');await expect(page.locator('#frequency-sample option:checked')).not.toContainText('unavailable');
  expect(result.samples[0].responses[1].output.frame.position_earth.real[0]).toBeCloseTo(1/.7**2,7);
  await page.locator('#frequency-initial-shift').fill('0');await page.locator('#solve').click();await expect(page.locator('#error p')).toContainText('no ordinary Fourier integral');
});
