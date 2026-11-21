import {test,expect} from '@playwright/test';
import {readFile,writeFile,readdir} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';

const cold=process.env.OPENSWING_COLD_EQUILIBRIUM==='1';
test(`full ${cold?'cold':'saved'} Daedalus reuses output fields and exports its complete response offline`,async({page,context},info)=>{
  test.setTimeout(1800000);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  let last=0;
  await page.exposeFunction('influenceProgress',row=>{
    if(Date.now()-last>10000){console.log(JSON.stringify(row));last=Date.now();}
  });
  await page.addInitScript(()=>{
    const original=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:original.call(this,type,...args);};
  });
  const kernelModules={},served=new Set();
  if(process.env.OPENSWING_KERNEL){
    const root=path.resolve(process.env.OPENSWING_KERNEL,'openswing');
    const names=(await readdir(root)).filter(name=>name.endsWith('.py'));
    const sources=new Map();
    for(const name of names){
      const bytes=await readFile(path.join(root,name));sources.set(name,bytes);
      kernelModules[name]=createHash('sha256').update(bytes).digest('hex');
    }
    await context.route('**/kernel/**',async route=>{
      const name=new URL(route.request().url()).pathname.split('/').pop();
      if(name==='sources.json'){
        names.forEach(name=>served.add(name));
        return route.fulfill({contentType:'application/json',body:JSON.stringify({format:'openswing-kernel-sources',version:1,
          sources:names.map(name=>[name,sources.get(name).toString('utf8')])})});
      }
      if(name==='manifest.json')return route.fulfill({contentType:'application/json',body:JSON.stringify(names)});
      if(!names.includes(name))throw new Error('Unexpected kernel module '+name);
      served.add(name);
      await route.fulfill({contentType:'text/plain',body:sources.get(name)});
    });
  }
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('dae');
  await expect(page.locator('#model-name')).toHaveText('Daedalus HPA');
  await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#panels')).toHaveValue('48');
  await page.locator('#speed').fill('30');await page.locator('#alpha').fill('5');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('.1');
  await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-count').fill('2');
  if(!cold){
    await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);
    await page.locator('#equilibrium-file').setInputFiles('tests/fixtures/dae-geometry-equilibrium.json');
    await expect(page.locator('#equilibrium-enable')).toBeChecked();
  }
  await page.evaluate(()=>{
    window.influenceMessages=[];
    new MutationObserver(()=>{
      const row={ms:performance.now(),text:document.querySelector('#runtime-status').textContent};
      window.influenceMessages.push(row);window.influenceProgress(row);
    }).observe(document.querySelector('#runtime-status'),{childList:true,subtree:true});
  });
  await context.setOffline(true);
  const start=performance.now(),wall=Date.now();await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:1500000});
  const seconds=(performance.now()-start)/1000,wallSeconds=(Date.now()-wall)/1000;
  const event=page.waitForEvent('download');await page.locator('#export-json').click();
  const result=JSON.parse(await readFile(await(await event).path(),'utf8'));
  expect(result.diagnostics.applied_load_linearization.method).toContain('retained applied-load C/Q/D');
  expect(result.diagnostics.applied_load_linearization.rows).toBe(6);
  expect(result.diagnostics.applied_load_linearization.cached_bytes).toBeLessThanOrEqual(2*1024**2);
  expect(result.diagnostics.applied_load_linearization.base_residual_moment_term).toBe(true);
  expect(result.diagnostics.applied_load_linearization.exact_internal_load_zeros).toBe(true);
  expect(result.diagnostics.applied_load_linearization.applications).toBe(8);
  expect(result.diagnostics.applied_load_linearization.fallback).toBeNull();
  const structural=result.diagnostics.state_linearization.geometry_assembly;
  expect(structural.structural_fallback).toBeNull();
  expect(structural.structural_geometry.method).toContain('retained section C');
  expect(structural.structural_geometry.columns).toBe(1650);
  expect(structural.local_groups).toBe(18);
  expect(structural.original_local_groups).toBe(24);
  expect(structural.local_geometry_matrix_fallback).toBeNull();
  expect(structural.local_geometry_matrix.method).toBe('retained sparse local geometry Jacobian');
  expect(structural.local_geometry_matrix.columns).toBe(1650);
  expect(structural.local_geometry_matrix.direction_evaluations).toBe(2);
  expect(structural.local_geometry_matrix.applications).toBe(105);
  expect(structural.local_geometry_matrix.cached_bytes).toBeLessThanOrEqual(32*1024**2);
  expect(result.converged).toBe(true);expect(result.samples.map(s=>s.omega)).toEqual([.1,100]);
  expect(result.inputs).toHaveLength(4);expect(result.diagnostics.full_dimension).toBe(5167);
  expect(result.diagnostics.loaded_matrices_reused).toBe(false);
  expect(result.diagnostics.output_linearization.method).toContain('retained full moving-source derivatives');
  expect(result.diagnostics.output_linearization.field_rows).toBe(3243);
  expect(result.diagnostics.output_linearization.cached_bytes).toBeLessThanOrEqual(128*1024**2);
  expect(result.diagnostics.output_linearization.fallback).toBeNull();
  expect(result.diagnostics.harmonic_structure.beam_equations_eliminated).toBe(1650);
  expect(result.diagnostics.harmonic_structure.beam_reduced_dimension).toBe(3517);
  expect(result.diagnostics.state_linearization.equilibrium_columns_reused).toBe(cold?0:result.diagnostics.state_layout.network_size);
  expect(result.diagnostics.state_linearization.direct_mechanical_columns).toBe(1650);
  expect(result.diagnostics.state_linearization.mechanical_column_groups).toBe(0);
  expect(result.diagnostics.structural_output_linearization.method).toBe('retained analytic section C matrix');
  expect(result.diagnostics.structural_output_linearization.rows).toBe(4050);
  expect(result.diagnostics.structural_output_linearization.cached_bytes).toBeLessThanOrEqual(32*1024**2);
  expect(result.diagnostics.structural_output_linearization.rate_and_input_terms).toBe('zero');
  expect(result.diagnostics.structural_output_linearization.fallback).toBeNull();
  const rank=result.base.equilibrium_initialization;
  if(cold){
    expect(rank.initialization).toBe('undeformed load continuation');
  }else{
    expect(rank.rank_check).toBe('sparse inverse-norm certificate');
    expect(rank.column_scaled_reciprocal_condition).toBeNull();
    expect(rank.column_scaled_reciprocal_condition_lower_bound).toBeGreaterThan(1e-10);
  }
  for(const sample of result.samples){
    expect(sample.responses).toHaveLength(4);
    expect(sample.diagnostics.factor_dimensions).toEqual([1867,1867,1867,1867]);
    expect(sample.diagnostics.beam_equations_eliminated).toEqual([1650,1650,1650,1650]);
    for(const residual of sample.diagnostics.scaled_residuals)expect(residual).toBeLessThanOrEqual(1e-7);
    for(const response of sample.responses)expect(response.state.real).toHaveLength(5167);
  }
  await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
  await expect(page.locator('#frequency-gain-plot svg')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  const download=page.waitForEvent('download');await page.locator('#frequency-csv').click();
  expect((await readFile(await(await download).path(),'utf8')).trim().split('\n')).toHaveLength(3);
  expect(errors).toEqual([]);
  const messages=await page.evaluate(()=>window.influenceMessages);
  if(!cold)expect(messages.some(row=>row.text.includes('checking constraint independence'))).toBe(true);
  expect(messages.some(row=>row.text.includes('full constraint check'))).toBe(false);
  expect(messages.some(row=>row.text.includes('preparing reusable beam factors'))).toBe(true);
  if(process.env.OPENSWING_KERNEL){
    expect(served.size).toBe(Object.keys(kernelModules).length);
    expect(result.software_provenance.modules).toEqual(kernelModules);
  }
  await writeFile(info.outputPath('full-dae.json'),JSON.stringify({seconds,wallSeconds,messages,result,kernelModules,served:[...served],
    cold,qualification:`${cold?'Cold equilibrium':'Saved-equilibrium'} launch, full 48-interval mesh, two endpoint frequencies and four inputs. Software viewer. Candidate kernel can be supplied by local request routing. This is correctness/UI validation; a native accuracy study may run concurrently, so this is not a performance comparison.`}));
  console.log(JSON.stringify({seconds,wallSeconds}));
});
