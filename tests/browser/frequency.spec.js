import { test, expect } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';
import { frequencyGeometry, complexGain } from '../../web/frequency-results.js';

test('harmonic geometry uses physical input amplitude and exp positive i phase without mutating data',()=>{
  const result={base:{geometry:[{index:1,quads:[],axis:[[[0,0,0],[0,2,0]]]}],attachments:[],modal_base:{body_to_earth:[[0,-1,0],[1,0,0],[0,0,1]],position_earth:[10,20,30]}},samples:[{responses:[{output:{
    geometry:[{quads:{real:[],imag:[]},axis:{real:[[[0,0,0],[0,.002,0]]],imag:[[[0,0,0],[0,-.003,0]]]}}],
    earth_geometry:[{quads:{real:[],imag:[]},axis:{real:[[[0,0,0],[-.002,0,0]]],imag:[[[0,0,0],[.003,0,0]]]}}],attachments:[],earth_attachments:[]}}]},{responses:[]}]};
  const before=JSON.stringify(result),body=frequencyGeometry(result,0,0,Math.PI/2,2),earth=frequencyGeometry(result,0,0,Math.PI/2,2,true);
  expect(body.beams[0].axis[0][1][1]).toBeCloseTo(2.006,14);
  expect(earth.beams[0].axis[0][1][0]).toBeCloseTo(7.994,14);
  expect(frequencyGeometry(result,1,0,0,1)).toBeNull();expect(JSON.stringify(result)).toBe(before);
  expect(complexGain({real:0,imag:-2}).phase).toBe(-90);
  expect(complexGain({real:0,imag:0})).toEqual({real:0,imag:0,magnitude:0,db:null,phase:null});
});

async function prepare(page,file,name){
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles(file);await expect(page.locator('#model-name')).toHaveText(name);
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#alpha').fill('0');await page.locator('#speed').fill('10');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-count').fill('5');
}
async function saved(page){const event=page.waitForEvent('download');await page.locator('#export-json').click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}

test('Bode oscillator runs offline in WASM with direct loads, phase, physical amplitude and immutable exports',async({page,context})=>{
  test.setTimeout(220000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:original.call(this,type,...args);};});
  await prepare(page,'examples/forced-oscillator.asw','Forced spring-mass demonstrator');
  await page.locator('#frequency-inputs').selectOption('controls');await page.locator('#frequency-start').fill('1');await page.locator('#frequency-end').fill('100');
  await context.setOffline(true);await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:160000});
  await expect(page.locator('#error')).toBeHidden();const result=await saved(page);
  expect(result.analysis).toBe('frequency_response');expect(result.inputs.map(c=>c.name)).toEqual(['power.1']);
  for(const s of result.samples){
    const d=s.responses[0].output.nodes.at(-1).displacement,w=s.omega,re=500-2*w*w,im=10*w,den=re*re+im*im;
    expect(d.real[1]).toBeCloseTo(re/den,10);expect(d.imag[1]).toBeCloseTo(-im/den,10);
    expect(s.responses[0].output.operating['power.1'].real).toBeCloseTo(1,10);
    expect(s.diagnostics.backward_errors[0]).toBeLessThan(1e-10);
  }
  await page.locator('#frequency-group').selectOption('nodes');
  await page.locator('#frequency-quantity').selectOption({label:'displacement y [input L]'});
  await expect(page.locator('#frequency-gain-plot svg')).toBeVisible();await expect(page.locator('#frequency-phase-plot svg')).toBeVisible();
  await page.locator('#frequency-gain').selectOption('db');await page.locator('#frequency-gain-plot circle[data-frequency="2"]').click();
  await expect(page.locator('#frequency-sample')).toHaveValue('2');
  await expect(page.locator('#frequency-detail')).toContainText('ω=10.0000');
  const csvEvent=page.waitForEvent('download');await page.locator('#frequency-csv').click();const csv=await readFile(await(await csvEvent).path(),'utf8');
  expect(csv).toContain('omega [rad/T]');expect(csv).toContain('phase [deg]');expect(csv.trim().split('\n')).toHaveLength(6);
  await page.locator('#frequency-view').selectOption('earth');await page.locator('#frequency-amplitude').fill('10');await page.locator('#frequency-phase').fill('90');
  await expect(page.locator('#geometry-label')).toHaveText('EARTH FRAME · LINEAR HARMONIC RESPONSE');
  await page.locator('#frequency-play').click();await expect.poll(()=>page.locator('#frequency-phase').inputValue()).not.toBe('90');await page.locator('#frequency-play').click();
  expect(await saved(page)).toEqual(result);
  await page.locator('#pane-frequency').screenshot({path:'test-results/bode-oscillator.png'});
  await page.locator('#viewport').scrollIntoViewIfNeeded();
  const drawing=await page.locator('#viewport canvas').evaluate(canvas=>({renderer:canvas.dataset.renderer,png:canvas.toDataURL()}));expect(drawing.renderer).toBe('canvas2d');
  await writeFile('test-results/bode-geometry.png',Buffer.from(drawing.png.split(',')[1],'base64'));
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  await page.locator('#workspace-tab-settings').click();
  await page.locator('#frequency-count').fill('7');await expect(page.locator('#export-json')).toBeDisabled();
  await page.locator('#workspace-tab-plots').click();await expect(page.locator('#frequency-transport')).toBeHidden();
  expect(errors).toEqual([]);
});

test('gust families export separate complex input columns and reject empty sine ranges',async({page})=>{
  test.setTimeout(220000);
  await prepare(page,'examples/rectangular.asw','Rectangular research wing');await page.locator('#frequency-inputs').selectOption('gust');
  await page.locator('#frequency-count').fill('3');await page.locator('#frequency-spacing').selectOption('linear');await page.locator('#frequency-start').fill('0');await page.locator('#frequency-end').fill('10');
  await page.locator('#frequency-gust-settings').evaluate(e=>e.open=true);await page.locator('#frequency-parity').selectOption('sine');
  await page.locator('#solve').click();await expect(page.locator('#error')).toContainText('Sine gusts need');
  await page.locator('#frequency-span-mode').fill('1');await page.locator('#frequency-parity').selectOption('both');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:160000});
  const result=await saved(page);expect(result.inputs).toHaveLength(3);expect(result.inputs.map(c=>c.name)).toEqual(['gust cosine n=0','gust cosine n=1','gust sine n=1']);
  for(const s of result.samples){expect(s.responses).toHaveLength(3);expect(s.responses[0].output.global.CL.real).toBeGreaterThan(.2);expect(Math.abs(s.responses[2].output.global.CL.real)).toBeLessThan(1e-9);}
  await page.locator('#frequency-input').selectOption('2');await page.locator('#frequency-group').selectOption('global');await page.locator('#frequency-quantity').selectOption({label:'Cl [dimensionless]'});
  await expect(page.locator('#frequency-gain-plot svg')).toBeVisible();
  await page.locator('#frequency-sample').selectOption('2');await expect(page.locator('#frequency-detail')).toContainText('refine the spatial mesh');
});

test('free-flight DC integrators produce explicit gaps and retain finite-frequency physical motion',async({page})=>{
  test.setTimeout(180000);
  const source=`Name\nFree rigid thrust benchmark\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.80665 1.225 340.294\nEnd\nReference\n2 1 2\nEnd\nGround\n1 0 0\nEnd\nWeight\n1 0 0 0 0 9.80665 0 0 0 0 0 19.6133 29.41995 39.2266\nEnd\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\nBeam 1\nRigid reference beam\nt y\n0 0\n2 2\nEnd\n`;
  await prepare(page,{name:'rigid.asw',mimeType:'text/plain',buffer:Buffer.from(source)},'Free rigid thrust benchmark');
  await page.locator('#frequency-inputs').selectOption('controls');await page.locator('#frequency-frame').selectOption('free');
  await page.locator('#frequency-spacing').selectOption('linear');await page.locator('#frequency-start').fill('0');await page.locator('#frequency-end').fill('2');await page.locator('#frequency-count').fill('3');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Frequency response finished with gaps',{timeout:140000});
  await expect(page.locator('#error')).toBeHidden();const result=await saved(page);expect(result.converged).toBe(false);expect(result.samples[0].responses).toHaveLength(0);
  for(const s of result.samples.slice(1))expect(s.responses[0].output.frame.position_earth.real[0]).toBeCloseTo(-1/s.omega**2,8);
  await page.locator('#frequency-group').selectOption('frame');await page.locator('#frequency-quantity').selectOption({label:'position earth x [input L]'});
  await expect(page.locator('#frequency-gain-plot circle')).toHaveCount(2);
  await page.locator('#frequency-sample').selectOption('0');await expect(page.locator('#frequency-detail')).toContainText('Unavailable:');await expect(page.locator('#frequency-transport')).toBeHidden();
  await expect(page.locator('#geometry-label')).toContainText('RESPONSE UNAVAILABLE');
});
