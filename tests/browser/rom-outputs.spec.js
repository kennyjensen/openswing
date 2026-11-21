import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

async function download(page,id){const event=page.waitForEvent('download');await page.locator(id).click();return readFile(await(await event).path(),'utf8');}

test('physical ROM outputs retain rate lift, direct terms, station identity and saved selections offline',async({page,context})=>{
  test.setTimeout(480000);
  const study=JSON.parse(await readFile('docs/validation/rom-outputs.json','utf8'));
  const native=study.cases.find(c=>c.spec.kind==='rigid'&&c.spec.panels===4&&!c.spec.frozen);
  for(const [file,wanted] of Object.entries(study.source_sha256))expect(createHash('sha256').update(await readFile(file)).digest('hex'),file).toBe(wanted);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles({name:'rom-sections.asw',mimeType:'text/plain',buffer:Buffer.from(native.source)});
  await expect(page.locator('#model-name')).toHaveText('Normal section loads');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await expect(page.locator('#node-table tbody tr')).toHaveCount(5);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#speed').fill('30');await page.locator('#alpha').fill('0');
  await page.locator('#controls input[data-control="1"]').fill('3');
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-count').fill('4');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await context.setOffline(true);await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  const modes=JSON.parse(await download(page,'#export-json'));
  expect(modes.rom_output_catalog.stations.strips).toHaveLength(4);
  await page.locator('#rom-settings').evaluate(e=>e.open=true);
  await page.locator('#rom-modes').selectOption(['0','1','2','3']);
  await page.locator('#rom-inputs').selectOption([{label:'Flap 1'},{label:'Uniform gust · Earth z'}]);
  await page.locator('#rom-outputs').fill('');
  await page.locator('#rom-physical-settings').evaluate(e=>e.open=true);
  for(const item of native.outputs){
    const spec=item.selector;
    await page.locator('#rom-physical-field').selectOption(`${spec.group}.${spec.key}`);
    await page.locator('#rom-physical-beam').selectOption(String(spec.beam));
    await page.locator('#rom-physical-station').selectOption(String(spec.index));
    await page.locator('#rom-physical-add').click();
  }
  await expect(page.locator('#rom-physical-selected li')).toHaveCount(12);
  await page.locator('#rom-physical-add').click();
  await expect(page.locator('#rom-physical-note')).toHaveText('This output is already selected.');
  await expect(page.locator('#rom-physical-selected li')).toHaveCount(12);
  const fieldValues=await page.locator('#rom-physical-field option').evaluateAll(rows=>rows.map(r=>r.value));
  expect(fieldValues).not.toContain('sections.shell_shear_stress');
  await page.locator('#rom-frequencies').fill('0, 3, 25');
  await page.locator('#rom-initial-settings').evaluate(e=>e.open=true);
  await page.locator('#rom-initial-profiles').fill(JSON.stringify([{kind:'initial',name:'circulation',state:{circulation:[0,1,2,3].map(i=>.2*Math.sin((i+.5)*Math.PI/4))}}]));
  await page.locator('#rom-initial-times').fill('0, 0.05, 0.2');
  await page.locator('#rom-build').click();
  await expect(page.locator('#runtime-status')).toHaveText('Reduced model generated',{timeout:240000});
  await expect(page.locator('#error')).toBeHidden();
  const result=JSON.parse(await download(page,'#rom-json'));
  expect(result.outputs.map(o=>o.selector)).toEqual(native.outputs.map(o=>o.selector));
  for(const [k,sample] of result.samples.entries())for(const part of ['real','imag'])for(let j=0;j<12;j++)for(let i=0;i<2;i++){
    const wanted=native.reference[part][k][j][i];
    expect(Math.abs(sample.reduced[part][j][i]-wanted)/Math.max(1,Math.abs(wanted))).toBeLessThan(2e-6);
  }
  expect(result.initial_responses[0].converged).toBe(true);
  await page.locator('#rom-output').selectOption('1');await page.locator('#rom-input').selectOption('1');
  await expect(page.locator('#rom-unit')).toContainText('input F/L / input L/T');
  await expect(page.locator('#rom-comparison tbody tr')).toHaveCount(3);
  await expect(page.locator('#rom-plot svg')).toBeVisible();
  await expect(page.locator('#rom-legacy')).toBeEnabled();
  const legacy=await download(page,'#rom-legacy');expect(legacy).toContain('OpenSwing strips.f_aero');expect(legacy).toContain('N/m');
  const text=await download(page,'#rom-text');expect(text).toContain('"selector"');expect(text).toContain('D_rate 12 2');
  await page.locator('#rom-settings').screenshot({path:'test-results/rom-physical-outputs.png'});
  await page.locator('#project-settings').evaluate(e=>e.open=true);
  await page.locator('#project-solution-name').fill('Physical ROM outputs');await page.locator('#project-save-solution').click();
  await expect(page.locator('#project-status')).toContainText('Computed solution saved.');
  await page.locator('#rom-physical-selected li button').first().click();
  await expect(page.locator('#rom-json')).toBeDisabled();await expect(page.locator('#rom-physical-selected li')).toHaveCount(11);
  await page.locator('#project-load-solution').click();
  await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');
  await expect(page.locator('#rom-physical-selected li')).toHaveCount(12);
  expect(JSON.parse(await download(page,'#rom-json'))).toEqual(result);
  expect(JSON.parse(await download(page,'#export-json'))).toEqual(modes);
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#rom-physical-settings').screenshot({path:'test-results/rom-physical-mobile.png'});
  await writeFile('test-results/rom-physical-values.json',JSON.stringify({outputs:result.outputs,samples:result.samples,initial:result.initial_responses[0].samples},null,2)+'\n');
  expect(errors).toEqual([]);
});

test('physical node, section and global ROM selections match a loaded spring offline',async({page,context})=>{
  test.setTimeout(300000);
  const study=JSON.parse(await readFile('docs/validation/rom-outputs.json','utf8'));
  const native=study.cases.find(c=>c.spec.kind==='mechanical'&&!c.spec.units);
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('instrumented-oscillator');
  await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await expect(page.locator('#node-table tbody tr')).toHaveCount(5);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
  await page.locator('#powers input[data-power="1"]').fill('5');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-count').fill('2');
  await context.setOffline(true);await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  await page.locator('#rom-settings').evaluate(e=>e.open=true);
  await page.locator('#rom-outputs').fill('');await page.locator('#rom-physical-settings').evaluate(e=>e.open=true);
  for(const {selector:s} of native.outputs){
    await page.locator('#rom-physical-field').selectOption(`${s.group}.${s.key}${s.component==null?'':'.'+s.component}`);
    if(s.group==='global')await expect(page.locator('#rom-physical-location')).toBeHidden();
    else{
      await page.locator('#rom-physical-beam').selectOption(String(s.beam));
      await page.locator('#rom-physical-station').selectOption(String(s.index));
    }
    await page.locator('#rom-physical-add').click();
  }
  await page.locator('#rom-frequencies').fill('0, 10, 50');await page.locator('#rom-build').click();
  await expect(page.locator('#runtime-status')).toHaveText('Reduced model generated',{timeout:180000});
  const result=JSON.parse(await download(page,'#rom-json'));
  expect(result.outputs.map(o=>o.selector)).toEqual(native.outputs.map(o=>o.selector));
  expect(result.output_base[0]).toBeCloseTo(.01,10);expect(result.output_base[2]).toBeCloseTo(.005,10);
  for(const [k,sample] of result.samples.entries())for(const part of ['real','imag'])for(let j=0;j<6;j++){
    const wanted=native.reference[part][k][j][0];
    for(const kind of ['full','reduced'])expect(Math.abs(sample[kind][part][j][0]-wanted)/Math.max(1,Math.abs(wanted))).toBeLessThan(2e-6);
  }
  await expect(page.locator('#rom-legacy')).toBeEnabled();
  await page.locator('#rom-output').selectOption('3');await expect(page.locator('#rom-unit')).toContainText('input F / file engine setting');
  await page.locator('#rom-settings').screenshot({path:'test-results/rom-physical-spring.png'});
  await page.locator('#speed').fill('12');await expect(page.locator('#rom-build')).toBeDisabled();
  await expect(page.locator('#rom-physical-selected li')).toHaveCount(0);
});
