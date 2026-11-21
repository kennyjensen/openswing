import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

test('literal ST-3 composite models reproduce complete dense dimensions and physical modes offline',async({page,context},info)=>{
 test.setTimeout(600000);
 const bytes=await readFile('docs/validation/dense-staircase.json'),study=JSON.parse(bytes);
 const baseline=JSON.parse(await readFile('docs/validation/isae-st3.json'));
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await context.setOffline(true);
 const cases=[];
 for(const [name,panels,gravity] of [['0_3_90',16,9.81],['p15_0',16,9.81],['m15_0',16,9.81],['0_3_90',32,0],['m15_0',8,0]]){
  const expected=study.runs.find(r=>r.identity.specification.name===name&&r.identity.specification.panels===panels&&r.identity.specification.gravity===gravity&&r.identity.specification.speed===0).result;
  const source=`3 - Structure/CASE - ST3 Low aspect ratio/Vaccum_anaysis/[${name}].asw`;
  const path=`.reference/isae-validation/${baseline.provenance.revision}/${source}`;
  const text=await readFile(path,'utf8');expect(createHash('sha256').update(text).digest('hex')).toBe(baseline.provenance.sources[source].sha256);
  await page.locator('#file').setInputFiles(path);await expect(page.locator('#editor')).toHaveValue(text);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#panels').fill(String(panels));await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-vacuum').check();
  await page.locator('#modal-frame').selectOption('fixed');await page.locator('#modal-count').fill('10');
  await page.locator('#modal-method').selectOption('dense');await page.locator('#modal-shift-real').fill('-.1');await page.locator('#modal-shift-imag').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill(String(gravity));
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:150000});
  await expect(page.locator('#error')).toBeHidden();const dl=page.waitForEvent('download');await page.locator('#export-json').click();
  const result=JSON.parse(await readFile(await(await dl).path(),'utf8'));
  expect(result.software_provenance.modules).toEqual(study.modules);expect(result.vacuum).toBe(true);
  expect(result.base.gravity_body).toEqual([0,0,gravity ? -gravity : 0]);expect(result.diagnostics.base_residual).toBeLessThan(1e-8);
  expect(result.diagnostics.finite_dimension).toBe(expected.searches[0].diagnostics.finite_dimension);
  for(const target of expected.matches[0].modes){
   const candidates=result.modes.filter(m=>m.eigenvalue[1]>0).sort((a,b)=>Math.abs(a.frequency-target.frequency_Hz)-Math.abs(b.frequency-target.frequency_Hz));
   const actual=candidates[0];expect(Math.abs(actual.frequency-target.frequency_Hz)).toBeLessThan(2e-6);
   expect(actual.right_backward_error).toBeLessThan(1e-9);expect(actual.left_backward_error).toBeLessThan(1e-9);
   const native=expected.searches[0].roots[target.root_index].shape;
   const a=[],b=[];for(let j=0;j<actual.output.nodes.length;j++){
    const node=actual.output.nodes[j];for(let k=0;k<6;k++){
     const field=k<3?node.displacement:node.rotation;a.push([field.real[k%3],field.imag[k%3]]);b.push([native.real[j][k],native.imag[j][k]]);
    }
   }
   let real=0,imag=0,aa=0,bb=0;for(let j=0;j<a.length;j++){
    real+=a[j][0]*b[j][0]+a[j][1]*b[j][1];imag+=a[j][0]*b[j][1]-a[j][1]*b[j][0];aa+=a[j][0]**2+a[j][1]**2;bb+=b[j][0]**2+b[j][1]**2;
   }
   expect((real*real+imag*imag)/(aa*bb)).toBeGreaterThan(1-2e-8);
  }
  cases.push({name,panels,gravity,result});
 }
 expect(errors).toEqual([]);
 await writeFile(info.outputPath('dense-staircase-browser.json'),JSON.stringify({status:'PASS',kernelModules:study.modules,
  study_sha256:createHash('sha256').update(bytes).digest('hex'),cases,offline:true,complete_dimensions_verified:true},null,2)+'\n');
});
