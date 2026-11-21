import { test, expect } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';
import { modeGeometry } from '../../web/mode-results.js';
import { surfaceColors } from '../../web/plot-colors.js';

test('complex mode geometry transforms the loaded base and preserves saved arrays',()=>{
  const result={base:{geometry:[{index:1,quads:[],axis:[[[0,0,0],[0,2,0]]]}],attachments:[],modal_base:{body_to_earth:[[0,-1,0],[1,0,0],[0,0,1]],position_earth:[10,20,30]}},modes:[{output:{
    geometry:[{quads:{real:[],imag:[]},axis:{real:[[[0,0,0],[0,0,2]]],imag:[[[0,0,0],[0,0,1]]]}}],
    earth_geometry:[{quads:{real:[],imag:[]},axis:{real:[[[1,0,0],[1,0,2]]],imag:[[[0,0,0],[0,0,1]]]}}],attachments:[],earth_attachments:[]}}]};
  const before=JSON.stringify(result),r=modeGeometry(result,0,Math.PI/2,2,true);
  expect(r.beams[0].axis[0][0]).toEqual([10,20,30]);
  expect(r.beams[0].axis[0][1][0]).toBeCloseTo(8,12);
  expect(r.beams[0].axis[0][1][2]).toBeCloseTo(30-2/Math.sqrt(6),12);
  expect(JSON.stringify(result)).toBe(before);
});

test('coupled modes solve offline, display complex loads, animate and export without changing the base',async({page,context})=>{
  test.setTimeout(220000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
    const original=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:original.call(this,type,...args);};
  });
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles('examples/heave-pitch.asw');await expect(page.locator('#model-name')).toHaveText('Heave and pitch research wing');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#alpha').fill('0');await page.locator('#speed').fill('50');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-count').fill('8');
  await context.setOffline(true);
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:160000});
  await expect(page.locator('#error')).toBeHidden();await expect(page.locator('#modal-roots svg')).toBeVisible();
  let dl=page.waitForEvent('download');await page.locator('#export-json').click();
  const resultText=await readFile(await(await dl).path(),'utf8');
  await writeFile('test-results/coupled-result.json',resultText);const result=JSON.parse(resultText);
  expect(result.analysis).toBe('eigenmodes');expect(result.diagnostics.method).toBe('full_shift_invert');
  expect(result.diagnostics.finite_dimension).toBeNull();expect(result.modes).toHaveLength(8);
  expect(result.diagnostics.arnoldi.factorizations).toBe(1);expect(result.diagnostics.integrator_deflation.count).toBe(0);
  expect(result.modes.filter(m=>m.eigenvalue[0]>.5)).toHaveLength(2);
  expect(result.diagnostics.base_residual).toBeLessThan(1e-8);
  const unstable=result.modes.findIndex(m=>m.eigenvalue[0]>0&&m.eigenvalue[1]>0);
  await page.locator('#modal-select').selectOption(String(unstable));await expect(page.locator('#modal-detail')).toContainText('unstable');
  await page.locator('#modal-beam').selectOption('2');await page.locator('#modal-quantity').selectOption('strips.force.2');
  await expect(page.locator('#modal-plot polyline')).toHaveCount(2);
  dl=page.waitForEvent('download');await page.locator('#modal-output-csv').click();
  const csv=await readFile(await(await dl).path(),'utf8');expect(csv).toContain('Aerodynamic strip force z imaginary');expect(csv.split('\n').length).toBeGreaterThan(4);
  await page.locator('#modal-view').selectOption('earth');await expect(page.locator('#geometry-label')).toContainText('EARTH FRAME · SCALED LINEAR MODE');
  await page.locator('#modal-phase').fill('90');await page.locator('#modal-amplitude').fill('3');
  await page.locator('#modal-play').click();await expect(page.locator('#modal-play')).toHaveText('Pause');
  await expect.poll(()=>page.locator('#modal-phase').inputValue()).not.toBe('90');await page.locator('#modal-play').click();
  await page.locator('#modal-phase').fill('0');await expect(page.locator('#modal-phase-label')).toHaveText('0°');
  dl=page.waitForEvent('download');await page.locator('#export-json').click();
  expect(JSON.parse(await readFile(await(await dl).path(),'utf8'))).toEqual(result);
  await page.locator('#tab-report').click();await expect(page.locator('#pane-report')).toContainText('Coefficients are frozen');
  await page.locator('#tab-modes').click();await page.locator('#pane-modes').screenshot({path:'test-results/modal-results.png'});
  await page.locator('#viewport').scrollIntoViewIfNeeded();
  // The first beam uses Daedalus red; body beams also consume a palette slot.
  expect(surfaceColors[0]).toBe('#ff0000');
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  const drawing=await page.locator('#viewport canvas').evaluate(canvas=>{
    const context=canvas.getContext('2d'),pixels=context.getImageData(0,0,canvas.width,canvas.height).data;
    let aircraft=0;for(let i=0;i<pixels.length;i+=4)if(pixels[i]>200&&pixels[i+1]<100&&pixels[i+2]<100&&pixels[i+3]>200)aircraft++;
    return {aircraft,renderer:canvas.dataset.renderer,png:canvas.toDataURL()};
  });
  expect(drawing.renderer).toBe('canvas2d');expect(drawing.aircraft).toBeGreaterThan(250);
  await writeFile('test-results/modal-canvas-stats.json',JSON.stringify({phase_degrees:0,surface_color:surfaceColors[0],renderer:drawing.renderer,red_surface_pixels:drawing.aircraft,minimum_exclusive:250}));
  await writeFile('test-results/modal-canvas.png',Buffer.from(drawing.png.split(',')[1],'base64'));
  await page.locator('#viewport').screenshot({path:'test-results/modal-geometry.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  await page.getByRole('tab',{name:'Settings',exact:true}).click();
  await page.locator('#modal-count').fill('6');await expect(page.locator('#export-json')).toBeDisabled();
  await page.getByRole('tab',{name:'Plots',exact:true}).click();await expect(page.locator('#mode-transport')).toBeHidden();
  expect(errors).toEqual([]);
});

test('vacuum modes preserve gravity overrides and report algebraic-only models clearly',async({page,context})=>{
  test.setTimeout(240000);
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-vacuum').check();
  // Complete finite classification is an explicit dense-method diagnostic.
  await expect(page.locator('#modal-method')).toHaveValue('full_shift_invert');
  await page.locator('#modal-method').selectOption('dense');
  await page.locator('#solve').click();await expect(page.locator('#error')).toContainText('No finite dynamic modes');
  const source=`Name\nVacuum oscillator\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.80665 1.225 340.294\nEnd\nReference\n2 1 2\nEnd\nGround\n1 0 0\nEnd\nWeight\n1 2 0 2 0 19.6133\nEnd\nBeam 1\nAxial spring\nt y EA tdeps\n0 0 1000 .02\n2 2 1000 .02\nEnd\n`;
  await page.locator('#file').setInputFiles({name:'oscillator.asw',mimeType:'text/plain',buffer:Buffer.from(source)});await expect(page.locator('#model-name')).toHaveText('Vacuum oscillator');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#modal-count').fill('2');await page.locator('#modal-method').selectOption('shift_invert');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged');await expect(page.locator('#error')).toBeHidden();
  await expect(page.locator('#cl')).toHaveText('—');await expect(page.locator('#modal-summary')).toContainText('Vacuum');
  const dl=page.waitForEvent('download');await page.locator('#export-json').click();const reducedText=await readFile(await(await dl).path(),'utf8');
  await writeFile('test-results/vacuum-reduced-result.json',reducedText);const r=JSON.parse(reducedText);
  expect(r.diagnostics.method).toBe('shift_invert');expect(r.base.gravity_body).toEqual([0,0,0]);expect(r.base.mass_properties.mass).toBeCloseTo(2,10);
  for(const m of r.modes){expect(m.eigenvalue[0]).toBeCloseTo(-2.5,6);expect(Math.abs(m.eigenvalue[1])).toBeCloseTo(Math.sqrt(250-6.25),6);}
  await context.setOffline(true);await page.locator('#modal-method').selectOption('full_shift_invert');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged');
  await expect(page.locator('#modal-summary')).toContainText('local search; total finite spectrum unclassified');
  const fullDownload=page.waitForEvent('download');await page.locator('#export-json').click();
  const fullText=await readFile(await(await fullDownload).path(),'utf8');await writeFile('test-results/vacuum-full-result.json',fullText);const full=JSON.parse(fullText);
  expect(full.diagnostics.method).toBe('full_shift_invert');expect(full.diagnostics.finite_dimension).toBeNull();expect(full.diagnostics.rank_tolerance).toBeNull();
  for(const m of full.modes){expect(m.eigenvalue[0]).toBeCloseTo(-2.5,6);expect(Math.abs(m.eigenvalue[1])).toBeCloseTo(Math.sqrt(250-6.25),6);expect(m.right_backward_error).toBeLessThan(1e-9);expect(m.left_backward_error).toBeLessThan(1e-9);}
  await page.locator('#pane-modes').screenshot({path:'test-results/descriptor-modes.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  await page.getByRole('tab',{name:'Plots',exact:true}).click();
  await page.locator('#pane-modes').screenshot({path:'test-results/descriptor-modes-mobile.png'});
});
