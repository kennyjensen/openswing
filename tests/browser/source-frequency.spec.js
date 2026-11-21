import {test,expect} from '@playwright/test';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {parseProject} from '../../web/project-data.js';
import {verifySolution} from '../../web/solution-data.js';

async function finish(page,label='Analysis converged'){
  await expect(page.locator('#runtime-status')).toHaveText(new RegExp(`^(${label}|Analysis stopped|Frequency refinement stopped)$`),{timeout:300000});
  if(await page.locator('#error').isVisible())throw new Error(await page.locator('#error').innerText());
  await expect(page.locator('#runtime-status')).toHaveText(label);
}
async function exported(page,id){const event=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}
const complex=(re,im)=>({re,im});
const divide=(a,b)=>complex((a.re*b.re+a.im*b.im)/(b.re*b.re+b.im*b.im),(a.im*b.re-a.re*b.im)/(b.re*b.re+b.im*b.im));

test('built offline source response preserves matrices, fluid, saved policy and physical spectra',async({page,context})=>{
  test.setTimeout(900000);
  const errors=[],outputs=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  for(const selection of ['aswing-moving-vacuum','aswing-vacuum','aswing-still-air']){
    const moving=selection==='aswing-moving-vacuum',wet=selection==='aswing-still-air',count=moving?14:4;
    // Source files are local upload inputs; all numerical packages are already cached.
    await page.locator('#file').setInputFiles(moving?'examples/source-moving-vacuum-check.asw':'examples/source-still-air-check.asw');
    await expect(page.locator('#solve')).toBeEnabled();
    await page.locator('#mode').selectOption('frequency');
    await page.locator('#tab-nodes').click();
    await page.locator('#node-spacing').selectOption('uniform');await page.locator('#node-count').fill(String(count));
    await page.locator('#node-apply').click();await expect(page.locator('#node-status')).toContainText(`${count+1} nodes`);
    await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
    await page.locator('#frequency-frame').selectOption(moving?'prescribed':'fixed');
    await page.locator('#structural-equations').selectOption(selection);await expect(page.locator('#solve')).toBeEnabled();
    await page.locator('#frequency-start').fill('1');await page.locator('#frequency-end').fill('15');await page.locator('#frequency-count').fill('3');
    await page.locator('#frequency-spacing').selectOption('linear');
    if(moving){await expect(page.locator('#frequency-inputs')).toHaveValue('frame');}
    else{
      await expect(page.locator('#frequency-inputs')).toHaveValue('initial');
      await page.locator('#frequency-initial-settings').evaluate(e=>e.open=true);
      const profile=Array.from({length:5},(_,j)=>[1+j/2,0,0,.001*Math.sin(j*Math.PI/8)]);
      await page.locator('#frequency-initial').fill(JSON.stringify([{kind:'initial',name:'Released shear',state:{beam_fields:[{beam:1,displacement:profile}]}}]));
      await page.locator('#frequency-initial-shift').fill('.3');
    }
    if(wet){await expect(page.locator('#modal-quiescent-density')).toBeVisible();await page.locator('#modal-quiescent-density').fill('1.225');}
    await context.setOffline(true);
    await page.locator('#solve').click();await finish(page);
    let out=await exported(page,'#export-json');
    expect(out.numerics.structural_operator).toBe(wet?'drela-fixed-still-air-v1':moving?'drela-moving-vacuum-v1':'drela-fixed-vacuum-v1');
    expect(out.condition).toBeNull();expect(out.base.structural_operator).toBe(out.structural_operator);
    expect(out.frequency_session.structural_operator).toBe(out.structural_operator);
    expect(out.vacuum).toBe(!wet);expect(out.diagnostics.matrix_storage.includes('sparse')).toBe(moving);
    const input=moving?out.inputs.findIndex(c=>c.name==='acceleration.y'):0;
    expect(input).toBeGreaterThanOrEqual(0);
    const check=result=>{
      for(const sample of result.samples){
        const tip=sample.responses[input].output.nodes.at(-1).displacement,w=sample.omega;
        if(moving){expect(tip.real[1]).toBeCloseTo(-3/(100-3*w*w),8);expect(Math.abs(tip.imag[1])).toBeLessThan(1e-9);}
        else{
          // Uniform shear endpoint-average dispersion: omega=2*sqrt(GKn/mu)/h*tan(pi/(4*N)).
          const mu=2+(wet?Math.PI*1.225/4:0),pole=4*Math.sqrt(800/mu)*Math.tan(Math.PI/16);
          const q=divide(complex(.0003,.001*w),complex(.09-w*w+pole*pole,.6*w));
          expect(tip.real[2]).toBeCloseTo(q.re,9);expect(tip.imag[2]).toBeCloseTo(q.im,9);
        }
      }
    };
    check(out);
    await page.locator('#frequency-refinement').evaluate(e=>e.open=true);await page.locator('#frequency-add-values').fill('2, 4');
    await page.locator('#frequency-add-list').click();await finish(page,'Frequency refinement complete');
    const refined=await exported(page,'#export-json');check(refined);
    expect(refined.frequency_refinement.linearization_reused).toBe(true);
    for(const old of out.samples)expect(refined.samples.find(s=>s.omega===old.omega)).toEqual(old);
    out=refined;
    await page.locator('#project-settings').evaluate(e=>e.open=true);
    await page.locator('#project-solution-name').fill(selection);await page.locator('#project-save-solution').click();
    await expect(page.locator('#project-status')).toContainText('Saved');
    const project=parseProject(JSON.stringify(await exported(page,'#project-export')));
    const saved=project.solutions.find(s=>s.name===selection);expect(saved).toBeTruthy();await verifySolution(saved);
    expect(saved.data.samples).toEqual(out.samples);expect(saved.data.frequency_session).toBeUndefined();
    outputs.push({selection,result:out,solution:saved});
    // Return to the ordinary UI before changing the next model; clear initial profiles explicitly.
    await page.locator('#structural-equations').selectOption('midpoint');await expect(page.locator('#solve')).toBeEnabled();
    await page.locator('#frequency-initial-settings').evaluate(e=>e.open=true);await page.locator('#frequency-initial').fill('[]');
  }
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  expect(errors).toEqual([]);
  await mkdir('artifacts/isae/source-frequency-20261030',{recursive:true});
  await writeFile('artifacts/isae/source-frequency-20261030/browser.json',JSON.stringify({status:'PASS',errors,outputs},null,2)+'\n');
});

test('saved source frequency results restore in the built workbench without recalculation',async({page,context})=>{
  test.setTimeout(300000);
  const captured=JSON.parse(await readFile('artifacts/isae/source-frequency-20261030/browser.json','utf8'));
  const project={format:'openswing-project',version:2,name:'Source frequency checks',selected:null,cases:[],
    solutions:captured.outputs.map(o=>o.solution),selected_solution:null};
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await context.setOffline(true);
  await page.locator('#project-file').setInputFiles({name:'source-frequency.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});
  await page.locator('#project-settings').evaluate(e=>e.open=true);
  for(const entry of captured.outputs){
    await page.locator('#project-solutions').selectOption(entry.solution.id);
    await page.locator('#project-load-solution').click();
    await expect(page.locator('#project-status')).toContainText(`Opened ${entry.selection}.`);
    if(await page.locator('#error').isVisible())throw new Error(await page.locator('#error').innerText());
    await expect(page.locator('#structural-equations')).toHaveValue(entry.selection);
    await expect(page.locator('#mode')).toHaveValue('frequency');
    expect((await exported(page,'#export-json')).samples).toEqual(entry.solution.data.samples);
    await page.locator('#frequency-refinement').evaluate(e=>e.open=true);
    await expect(page.locator('#frequency-add-list')).toBeDisabled();
    if(entry.selection==='aswing-still-air')await expect(page.locator('#modal-quiescent-density')).toBeVisible();
  }
  expect(errors).toEqual([]);
  await writeFile('artifacts/isae/source-frequency-20261030/browser-restore.json',JSON.stringify({status:'PASS',restored:captured.outputs.map(o=>o.selection),errors})+'\n');
});
