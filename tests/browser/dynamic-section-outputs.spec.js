import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
const saved=async(page,id='#export-json',json=true)=>{const event=page.waitForEvent('download');await page.locator(id).click();const text=await readFile(await(await event).path(),'utf8');return json?JSON.parse(text):text;};
const csv=text=>text.trimEnd().split('\n').map(line=>[...line.matchAll(/"((?:[^"]|"")*)"(?:,|$)/g)].map(m=>m[1].replaceAll('""','"')));
const keys=['cm','f_aero','f_reac','da_eff'];
async function prepare(page,file,speed){
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#file').setInputFiles(file);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#speed').fill(String(speed));await page.locator('#alpha').fill('0');await page.locator('#beta').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
}

test('complex modal section loads and incidence retain physical normalization and missing body values offline',async({page,context})=>{
  test.setTimeout(240000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await prepare(page,'examples/heave-pitch.asw',40);await page.locator('#mode').selectOption('modes');await page.locator('#modal-count').fill('8');
  await context.setOffline(true);await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  const result=await saved(page),index=result.modes.findIndex(m=>m.eigenvalue[1]>1),mode=result.modes[index];expect(index).toBeGreaterThanOrEqual(0);
  const root=result.base.nodes.find(n=>n.beam===2&&n.t===0).index,theta=mode.output.nodes[root].rotation;
  for(const s of mode.output.strips.filter(s=>s.beam===2)){
    expect(s.da_eff.real).toBeCloseTo(theta.real[1],8);expect(s.da_eff.imag).toBeCloseTo(theta.imag[1],8);
    const [re,im]=mode.eigenvalue,g=s.circulation;
    expect(s.f_aero.real).toBeCloseTo(1.225*((40+re)*g.real-im*g.imag),6);
    expect(s.f_aero.imag).toBeCloseTo(1.225*((40+re)*g.imag+im*g.real),6);
  }
  await page.locator('#modal-select').selectOption(String(index));await page.locator('#modal-beam').selectOption('2');
  for(const key of keys){
    await page.locator('#modal-quantity').selectOption('strips.'+key);await expect(page.locator('#modal-plot polyline')).toHaveCount(2);await expect(page.locator('#modal-unit')).toContainText('Complex perturbation');
    const rows=csv(await saved(page,'#modal-output-csv',false)),strips=mode.output.strips.filter(s=>s.beam===2).sort((a,b)=>a.t-b.t);
    expect(rows).toHaveLength(strips.length+1);for(const [i,s] of strips.entries()){expect(Number(rows[i+1][4])).toBe(s[key].real);expect(Number(rows[i+1][5])).toBe(s[key].imag);}
    if(key==='da_eff')expect(rows[0][4]).toContain('[rad]');
  }
  await page.locator('#pane-modes').screenshot({path:'test-results/dynamic-section-modes.png'});
  await page.locator('#modal-beam').selectOption('1');await expect(page.locator('#modal-plot')).toContainText('No values available');
  expect(await saved(page)).toEqual(result);await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);expect(errors).toEqual([]);
});

test('section Bode and initial spectra preserve units, rate feedthrough, CSV and mixed body/lifting selection offline',async({page,context})=>{
  test.setTimeout(260000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  // Radius zero makes the leading body strip physically inert. It exercises
  // selection when lifting-only quantities are absent on the first strip.
  let source=await readFile('examples/section-outputs.asw','utf8');
  source=source.replace('Beam 1','Beam 2').replace('Ground\n1 0 0','Ground\n2 0 0').replace('Weight\n1 0','Weight\n2 0');
  source+='\nGround\n1 0 0\nEnd\nBeam 1\nZero-radius body\nt x radius\n0 4 0\n1 5 0\nEnd\n';
  // Model beam order follows its source order, so put the body first.
  const marker=source.indexOf('Beam 1'),body=source.slice(marker);source=source.slice(0,marker);const first=source.indexOf('Beam 2');source=source.slice(0,first)+body+source.slice(first);
  await prepare(page,{name:'mixed-sections.asw',mimeType:'text/plain',buffer:Buffer.from(source)},30);await page.locator('[data-control="1"]').fill('3');
  await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-spacing').selectOption('linear');await page.locator('#frequency-start').fill('0');await page.locator('#frequency-end').fill('6');await page.locator('#frequency-count').fill('3');
  await page.locator('#frequency-gust-settings').evaluate(e=>e.open=true);await page.locator('#frequency-wave').selectOption('uniform');
  await page.locator('#frequency-initial-settings').evaluate(e=>e.open=true);
  const gamma=Array.from({length:4},(_,i)=>.2*Math.sin((i+.5)*Math.PI/4));await page.locator('#frequency-initial').fill(JSON.stringify([{kind:'initial',name:'elliptic circulation',state:{circulation:gamma}}]));
  await context.setOffline(true);await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  const result=await saved(page);expect(result.inputs).toHaveLength(3);expect(result.samples[0].responses[0].output.strips[0].beam).toBe(1);
  await page.locator('#frequency-group').selectOption('strips');
  for(const [key,unit] of [['cm','dimensionless'],['f_aero','input F/L'],['f_reac','input F/L'],['da_eff','rad']]){
    await page.locator('#frequency-quantity').selectOption({label:`${key.replaceAll('_',' ')} [${unit}]`});await page.locator('#frequency-station').selectOption('4');
    await expect(page.locator('#frequency-unit')).toContainText('Complex perturbation');await expect(page.locator('#frequency-gain-plot svg')).toBeVisible();
    const rows=csv(await saved(page,'#frequency-csv',false)),header=rows[0];
    const ri=header.findIndex(h=>h.startsWith('real [')),ii=header.findIndex(h=>h.startsWith('imag ['));expect(ri).toBeGreaterThan(-1);
    for(let j=0;j<3;j++){const value=result.samples[j].responses[0].output.strips[4][key];expect(Number(rows[j+1][ri])).toBe(value.real);expect(Number(rows[j+1][ii])).toBe(value.imag);}
  }
  await page.locator('#frequency-input').selectOption('2');await page.locator('#frequency-quantity').selectOption({label:'f aero [input F/L]'});await page.locator('#frequency-station').selectOption('4');
  await expect(page.locator('#frequency-unit')).toContainText('input T');await expect(page.locator('#frequency-unit')).toContainText('initial-value subtraction');
  for(const sample of result.samples){const s=sample.responses[2].output.strips[4],g=s.circulation,w=sample.omega;
    expect(s.f_aero.real).toBeCloseTo(1.225*(30*g.real-w*g.imag-gamma[0]),7);expect(s.f_aero.imag).toBeCloseTo(1.225*(30*g.imag+w*g.real),7);
  }
  const ticks=await page.locator('#frequency-gain-plot text[x="75"]').allTextContents();expect(new Set(ticks).size).toBe(5);
  await page.locator('#pane-frequency').screenshot({path:'test-results/dynamic-section-frequency.png'});
  await page.locator('#frequency-station').selectOption('0');await expect(page.locator('#frequency-gain-plot')).toContainText('No magnitude values available');
  expect(await saved(page)).toEqual(result);await page.locator('#frequency-station').selectOption('4');await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.locator('#pane-frequency').screenshot({path:'test-results/dynamic-section-frequency-mobile.png'});expect(errors).toEqual([]);
});
