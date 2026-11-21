import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';

const saved=JSON.parse(await readFile(new URL('../data/daedalus-frame-response.json',import.meta.url),'utf8'));
// Synthetic display data in the saved response schema. These are chosen
// coordinates for unit/axis assertions, not additional physical solutions.
function fixture(gaps=false){
  const result=structuredClone(saved.results.free);
  const frequency=gaps?[.1,.2,.4,.6,1,2,10]:[.1,.2,1,2,10];
  const magnitude=gaps?[.2,0,.4,null,1,2,6]:[.2,.3,1,3,6];
  result.samples=frequency.map((f,i)=>{
    const point=structuredClone(result.samples[0]);point.frequency=f;point.omega=2*Math.PI*f;
    if(magnitude[i]===null){point.converged=false;point.responses=[{converged:false,error:'Synthetic missing sample.'}];return point;}
    const angle=gaps?30:45*(i-2),native=magnitude[i]*Math.PI/180;
    const value={real:[0,0,native*Math.cos(angle*Math.PI/180)],imag:[0,0,native*Math.sin(angle*Math.PI/180)]};
    point.responses[0].output.frame.rates_body=value;
    point.responses[0].output.operating['rates.z']={real:value.real[2],imag:value.imag[2]};
    return point;
  });
  return {result,model:saved.model_metadata,frequency,magnitude};
}

async function mount(page,data=fixture()){
  await page.addInitScript(()=>{
    window.fixtureWorkerAttempts=0;
    window.Worker=class{constructor(){window.fixtureWorkerAttempts++;throw Error('No worker or solver in Bode rendering fixture.');}};
  });
  await page.route('**/frequency-axes-fixture.json',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(data)}));
  await page.route('**/frequency-axes-fixture',route=>route.fulfill({contentType:'text/html',body:`<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><script type="module">
    import '/web/style.css';
    import {plotColors} from '/web/plot-colors.js';
    import {frequencySettings,frequencyTransport,frequencyPane,createFrequencyResults} from '/web/frequency-results.js';
    document.documentElement.style.setProperty('--plot-color',plotColors[0]);
    document.body.innerHTML='<div hidden>'+frequencySettings+frequencyTransport+'</div>'+frequencyPane;
    document.querySelector('#pane-frequency').hidden=false;
    window.fixture=await(await fetch('/frequency-axes-fixture.json')).json();window.original=JSON.stringify(fixture.result);window.exports=[];
    window.view=createFrequencyResults(()=>{},()=>{},(name,text)=>exports.push({name,text}),()=>fixture.model);
    view.setResult(fixture.result);window.ready=true;
  </script></body></html>`}));
  await page.goto('/frequency-axes-fixture');await page.waitForFunction(()=>window.ready);
  await page.locator('#frequency-group').selectOption('frame');
  const yaw=await page.locator('#frequency-quantity option').evaluateAll(es=>es.find(e=>e.textContent.startsWith('Yaw rate r'))?.value);
  expect(yaw).toBeDefined();await page.locator('#frequency-quantity').selectOption(yaw);
}

// Recover a plotted coordinate from two labeled grid ticks. This checks the
// renderer against native fixture values without using its plotAxis helper.
async function coordinates(page,selector,index,comparison=false){
  return page.locator(selector).evaluate((svg,{index,comparison})=>{
    const circle=svg.querySelector(`circle[data-frequency="${index}"]`);
    const decode=axis=>{
      const log=axis==='x'?document.querySelector('#frequency-axis').value==='log':
        (comparison?svg.dataset.axisScale==='log':svg.dataset.yScale==='log');
      let ticks;
      if(comparison){
        ticks=[...svg.querySelectorAll(`path.grid-major[data-axis="${axis}"]`)].map(e=>{
          const numbers=e.getAttribute('d').match(/[-+]?\d*\.?\d+(?:e[-+]?\d+)?/gi).map(Number);
          return {value:Number(e.dataset.tickValue),position:numbers[axis==='x'?0:1]};
        });
      }else{
        ticks=[...svg.querySelectorAll(`text[data-axis="${axis}"]`)].map(e=>({value:Number(e.dataset.value),
          position:Number(e.getAttribute(axis==='x'?'x':'y'))-(axis==='y'?4:0)}));
      }
      const first=ticks[0],last=ticks.at(-1),p=Number(circle.getAttribute(axis==='x'?'cx':'cy'));
      const fraction=(p-first.position)/(last.position-first.position);
      return log?10**(Math.log10(first.value)+fraction*(Math.log10(last.value)-Math.log10(first.value))):first.value+fraction*(last.value-first.value);
    };
    return {x:decode('x'),y:decode('y')};
  },{index,comparison});
}
async function csv(page,comparison=false){
  await page.locator(comparison?'#frequency-compare-csv':'#frequency-csv').click();
  return page.evaluate(()=>window.exports.at(-1).text);
}
const close=(actual,expected)=>expect(Math.abs(actual-expected)).toBeLessThan(2e-11*Math.max(1,Math.abs(expected)));
const paths=async(page,selector)=>page.locator(selector).evaluateAll(es=>es.map(e=>(e.getAttribute('d').match(/M/g)||[]).length));

test('Bode defaults show decade grids and exactly one native frequency/angular conversion',async({page})=>{
  const data=fixture();await mount(page,data);
  await expect(page.locator('#frequency-units')).toHaveValue('cycles');await expect(page.locator('#frequency-angle-units')).toHaveValue('degrees');
  await expect(page.locator('#frequency-gain')).toHaveValue('absolute');
  await expect(page.locator('#frequency-gain-plot svg')).toHaveAttribute('data-x-scale','log');
  await expect(page.locator('#frequency-gain-plot svg')).toHaveAttribute('data-y-scale','log');
  await expect(page.locator('#frequency-phase-plot svg')).toHaveAttribute('data-y-scale','linear');
  for(const tick of [.1,1,10])await expect(page.locator(`#frequency-gain-plot text[data-axis="x"][data-value="${tick}"]`)).toHaveText(String(tick));
  const minor=await page.locator('#frequency-gain-plot path.plot-grid-minor').evaluateAll(es=>({vertical:es.filter(e=>e.getAttribute('d').includes('V')).length,horizontal:es.filter(e=>e.getAttribute('d').includes('H')).length}));
  expect(minor.vertical).toBeGreaterThan(0);expect(minor.horizontal).toBeGreaterThan(0);
  for(let i=0;i<data.frequency.length;i++){
    const xy=await coordinates(page,'#frequency-gain-plot svg',i);close(xy.x,data.frequency[i]);close(xy.y,data.magnitude[i]);
    const phase=await coordinates(page,'#frequency-phase-plot svg',i);close(phase.y,45*(i-2));
  }
  const originalCSV=await csv(page);
  await page.locator('#frequency-angle-units').selectOption('radians');await page.locator('#frequency-units').selectOption('radians');
  for(let i=0;i<data.frequency.length;i++){
    const xy=await coordinates(page,'#frequency-gain-plot svg',i);close(xy.x,2*Math.PI*data.frequency[i]);close(xy.y,data.magnitude[i]*Math.PI/180);
  }
  await page.locator('#frequency-gain').selectOption('linear');await expect(page.locator('#frequency-gain-plot svg')).toHaveAttribute('data-y-scale','linear');
  close((await coordinates(page,'#frequency-gain-plot svg',2)).y,Math.PI/180);
  await page.locator('#frequency-gain').selectOption('db');await expect(page.locator('#frequency-gain-plot svg')).toHaveAttribute('data-y-scale','linear');
  close((await coordinates(page,'#frequency-gain-plot svg',2)).y,20*Math.log10(Math.PI/180));
  await page.locator('#frequency-angle-units').selectOption('degrees');close((await coordinates(page,'#frequency-gain-plot svg',2)).y,0);
  await page.locator('#frequency-axis').selectOption('linear');await expect(page.locator('#frequency-gain-plot svg')).toHaveAttribute('data-x-scale','linear');
  close((await coordinates(page,'#frequency-gain-plot svg',2)).x,2*Math.PI);
  expect(await csv(page)).toBe(originalCSV);
  expect(await page.evaluate(()=>JSON.stringify(fixture.result))).toBe(await page.evaluate(()=>window.original));
  // A positive native frequency can underflow only when displayed in cycles.
  // It remains a valid angular-frequency point and must not poison SVG paths.
  await page.evaluate(()=>{const result=structuredClone(fixture.result);result.samples[0].omega=Number.MIN_VALUE;view.setResult(result);});
  await page.locator('#frequency-gain').selectOption('absolute');
  await page.locator('#frequency-axis').selectOption('log');
  await page.locator('#frequency-units').selectOption('cycles');
  await expect(page.locator('#frequency-gain-plot circle[data-frequency="0"]')).toHaveCount(0);
  await expect(page.locator('#frequency-gain-plot circle')).toHaveCount(data.frequency.length-1);
  expect(await page.locator('#frequency-gain-plot svg').evaluate(e=>e.outerHTML)).not.toMatch(/NaN|Infinity/);
  await page.locator('#frequency-units').selectOption('radians');
  await expect(page.locator('#frequency-gain-plot circle[data-frequency="0"]')).toHaveCount(1);
  await expect(page.locator('#frequency-gain-plot circle')).toHaveCount(data.frequency.length);
  expect(await page.locator('#frequency-gain-plot svg').evaluate(e=>e.outerHTML)).not.toMatch(/NaN|Infinity/);
  expect(await page.evaluate(()=>window.fixtureWorkerAttempts)).toBe(0);
});

test('zero and missing samples break log gain/phase while linear magnitude retains zeros',async({page})=>{
  await mount(page,fixture(true));
  await expect(page.locator('#frequency-gain-plot circle')).toHaveCount(5);
  await expect(page.locator('#frequency-gain-plot circle[data-frequency="1"]')).toHaveCount(0);
  await expect(page.locator('#frequency-gain-plot circle[data-frequency="3"]')).toHaveCount(0);
  expect(await paths(page,'#frequency-gain-plot path.plot-line')).toEqual([3]);
  expect(await paths(page,'#frequency-phase-plot path.plot-line')).toEqual([3]);
  const originalCSV=await csv(page);expect(originalCSV).toContain('Synthetic missing sample.');
  await page.locator('#frequency-gain').selectOption('linear');await expect(page.locator('#frequency-gain-plot circle')).toHaveCount(6);
  close((await coordinates(page,'#frequency-gain-plot svg',1)).y,0);expect(await paths(page,'#frequency-gain-plot path.plot-line')).toEqual([2]);
  await page.locator('#frequency-gain').selectOption('db');expect(await paths(page,'#frequency-gain-plot path.plot-line')).toEqual([3]);
  expect(await csv(page)).toBe(originalCSV);
  await page.evaluate(()=>{const result=structuredClone(fixture.result);result.samples[0].omega=0;result.samples[0].frequency=0;view.setResult(result);});
  await expect(page.locator('#frequency-axis')).toHaveValue('linear');
  await page.locator('#frequency-axis').selectOption('log');await expect(page.locator('#frequency-unit')).toContainText('Zero frequency is omitted');
  await expect(page.locator('#frequency-gain-plot circle[data-frequency="0"]')).toHaveCount(0);
  await page.locator('#frequency-axis').selectOption('linear');await expect(page.locator('#frequency-gain-plot circle[data-frequency="0"]')).toHaveCount(1);
  expect(await page.evaluate(()=>window.fixtureWorkerAttempts)).toBe(0);
});

test('comparison SVG/export shares selected log axes and units on desktop and mobile',async({page},info)=>{
  const data=fixture();await mount(page,data);
  await page.locator('#frequency-comparison').evaluate(e=>e.open=true);await page.locator('#frequency-compare-current').click();
  const gain='.frequency-comparison-svg [data-plot="magnitude"]',phase='.frequency-comparison-svg [data-plot="phase"]';
  await expect(page.locator(gain)).toHaveAttribute('data-axis-scale','log');await expect(page.locator(phase)).toHaveAttribute('data-axis-scale','linear');
  for(const value of [.1,1,10])await expect(page.locator(`${gain} path.grid-major[data-axis="x"][data-tick-value="${value}"]`)).toHaveCount(1);
  expect(await page.locator(`${gain} path.grid-minor[data-axis="x"]`).count()).toBeGreaterThan(0);
  expect(await page.locator(`${gain} path.grid-minor[data-axis="y"]`).count()).toBeGreaterThan(0);
  await expect(page.locator('.frequency-comparison-svg')).toContainText('deg/T');
  const main=await coordinates(page,'#frequency-gain-plot svg',2),comparison=await coordinates(page,gain,2,true);close(comparison.x,main.x);close(comparison.y,main.y);
  const originalCSV=await csv(page,true);
  await page.locator('#frequency-angle-units').selectOption('radians');await page.locator('#frequency-units').selectOption('radians');
  const native=await coordinates(page,gain,2,true);close(native.x,2*Math.PI);close(native.y,Math.PI/180);
  await expect(page.locator('.frequency-comparison-svg')).toContainText('rad/T');
  await page.locator('#frequency-gain').selectOption('db');await expect(page.locator('.frequency-comparison-svg [data-plot="db"]')).toHaveAttribute('data-axis-scale','linear');
  close((await coordinates(page,'.frequency-comparison-svg [data-plot="db"]',2,true)).y,20*Math.log10(Math.PI/180));
  expect(await csv(page,true)).toBe(originalCSV);
  await page.locator('#frequency-gain').selectOption('absolute');await page.locator('#frequency-angle-units').selectOption('degrees');await page.locator('#frequency-units').selectOption('cycles');
  await page.locator('.frequency-comparison-group button').click();
  const exported=await page.evaluate(()=>exports.at(-1).text);
  expect(exported).toContain('deg/T');expect(exported).toContain('f [cycles/input T]');expect(exported).toContain('grid-minor');expect(exported).not.toMatch(/NaN|Infinity/);
  const exportedShape=await page.evaluate(text=>{const doc=new DOMParser().parseFromString(text,'image/svg+xml');return {errors:doc.querySelectorAll('parsererror').length,
    gain:doc.querySelector('[data-plot="magnitude"]').getAttribute('data-axis-scale'),phase:doc.querySelector('[data-plot="phase"]').getAttribute('data-axis-scale'),
    ticks:[...doc.querySelectorAll('[data-plot="magnitude"] .grid-major[data-axis="x"]')].map(e=>Number(e.getAttribute('data-tick-value')))};},exported);
  expect(exportedShape.errors).toBe(0);expect(exportedShape.gain).toBe('log');expect(exportedShape.phase).toBe('linear');expect(exportedShape.ticks).toEqual(expect.arrayContaining([.1,1,10]));
  await page.locator('#pane-frequency').screenshot({path:info.outputPath('frequency-axes-desktop.png')});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await expect(page.locator('#frequency-gain-plot svg')).toBeVisible();
  expect(await page.locator('.frequency-comparison-chart').evaluate(e=>e.scrollWidth>e.clientWidth)).toBe(true);
  await page.locator('#pane-frequency').screenshot({path:info.outputPath('frequency-axes-mobile.png')});
  expect(await page.evaluate(()=>JSON.stringify(fixture.result))).toBe(await page.evaluate(()=>window.original));
  expect(await page.evaluate(()=>window.fixtureWorkerAttempts)).toBe(0);
});
