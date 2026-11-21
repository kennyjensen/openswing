import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';

const fixture=JSON.parse(await readFile(new URL('../data/daedalus-frame-response.json',import.meta.url),'utf8'));
const rate=async(page,group)=>{
  await page.locator('#frequency-group').selectOption(group);
  const value=await page.locator('#frequency-quantity option').evaluateAll(options=>options.find(o=>o.textContent.startsWith('Yaw rate r'))?.value);
  expect(value).toBeDefined();await page.locator('#frequency-quantity').selectOption(value);
};

test('Bode defaults to free flight and 0.1–10 Hz without automatically solving',async({page})=>{
  await page.addInitScript(()=>{
    const context=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(kind,...args){return kind==='webgl2'?null:context.call(this,kind,...args);};
    window.frequencyRequests=[];
    const send=Worker.prototype.postMessage;
    Worker.prototype.postMessage=function(packet,...args){
      if(packet.request?.action==='frequency'){
        window.frequencyRequests.push(structuredClone(packet.request));
        queueMicrotask(()=>this.dispatchEvent(new MessageEvent('message',{data:{id:packet.id,error:'UI request captured; numerical solve intentionally not run.'}})));
        return;
      }
      return send.call(this,packet,...args);
    };
  });
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('dae');await expect(page.locator('#model-name')).toHaveText('Daedalus HPA');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('frequency');
  await expect(page.locator('#frequency-frame')).toHaveValue('free');
  await expect(page.locator('#frequency-start')).toHaveValue('0.1');await expect(page.locator('#frequency-end')).toHaveValue('10');
  await expect(page.locator('#frequency-start-unit')).toHaveText('Hz');
  await expect(page.getByRole('button',{name:'Use free-flight settings'})).toHaveCount(0);
  await page.locator('#frequency-inputs').selectOption('controls');
  await page.locator('#frequency-start').fill('.2');await page.locator('#frequency-end').fill('40');await page.locator('#frequency-count').fill('3');
  await page.locator('#frequency-frame').selectOption('fixed');
  await page.locator('#frequency-frame').selectOption('free');
  await expect(page.locator('#frequency-frame')).toHaveValue('free');
  await expect(page.locator('#frequency-inputs')).toHaveValue('controls');
  await expect(page.locator('#frequency-start')).toHaveValue('.2');await expect(page.locator('#frequency-end')).toHaveValue('40');await expect(page.locator('#frequency-count')).toHaveValue('3');
  expect(await page.evaluate(()=>window.frequencyRequests)).toEqual([]);
  await page.locator('#solve').click();await expect(page.locator('#error p')).toContainText('numerical solve intentionally not run');
  const requests=await page.evaluate(()=>window.frequencyRequests);expect(requests).toHaveLength(1);
  expect(requests[0].frequency.frame).toBe('free');expect(requests[0].frequency.inputs).toEqual(['control.2','control.3','power.1']);
  expect(requests[0].frequency.frequencies).toHaveLength(3);expect(requests[0].frequency.frequencies[0]).toBeCloseTo(.2*2*Math.PI,12);expect(requests[0].frequency.frequencies.at(-1)).toBeCloseTo(40*2*Math.PI,12);
});

test('recorded Daedalus fixed zeros and actual free yaw values render with their physical constraints',async({page})=>{
  // Exercise the actual served Bode component with saved native outputs. This
  // is a rendering regression, not a new browser numerical validation.
  await page.route('**/bode-frame-fixture.json',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(fixture)}));
  await page.route('**/bode-frame-fixture',route=>route.fulfill({contentType:'text/html',body:`<!doctype html><html><body><script type="module">
    import '/web/style.css';
    import {frequencySettings,frequencyTransport,frequencyPane,createFrequencyResults} from '/web/frequency-results.js';
    document.body.innerHTML=frequencySettings+frequencyTransport+frequencyPane;
    document.querySelector('#frequency-settings').hidden=false;document.querySelector('#pane-frequency').hidden=false;
    window.fixture=await(await fetch('/bode-frame-fixture.json')).json();window.original=JSON.stringify(fixture.results);window.exports=[];
    window.edits=0;let view;view=createFrequencyResults(()=>{},()=>{window.edits++;view.setResult(null);},(name,text)=>window.exports.push({name,text}),()=>fixture.model_metadata);
    window.loadResult=mode=>view.setResult(fixture.results[mode]);loadResult('fixed');window.ready=true;
  </script></body></html>`}));
  await page.goto('/bode-frame-fixture');await page.waitForFunction(()=>window.ready);
  await expect(page.locator('#frequency-base-condition')).toContainText('held fixed; steady-flight trim is not established');
  await expect(page.locator('#frequency-input')).toContainText('control.3 · Rudder');
  await page.locator('#frequency-group').selectOption('frame');
  await expect(page.locator('#frequency-quantity')).toBeDisabled();
  await expect(page.locator('#frequency-quantity')).toContainText('motion held fixed');
  await expect(page.locator('#frequency-frame-explanation')).toContainText('no Flight frame outputs');
  expect(await page.evaluate(()=>window.edits)).toBe(0);
  await rate(page,'operating');await expect(page.locator('#frequency-frame-explanation')).toContainText('yaw rate is constrained to zero');
  await expect(page.locator('#frequency-gain')).toHaveValue('absolute');
  await expect(page.locator('#frequency-gain-plot')).toContainText('Zero magnitude cannot be shown on a logarithmic axis');
  await expect(page.locator('#frequency-gain-plot svg')).toHaveCount(0);
  await expect(page.locator('#frequency-phase-plot')).toHaveText('No phase [deg] values available.');
  await page.locator('#frequency-gain').selectOption('linear');
  await expect(page.locator('#frequency-gain-plot svg')).toBeVisible();
  await expect(page.locator('#frequency-gain-plot svg')).toHaveAttribute('data-y-scale','linear');
  await expect(page.locator('#frequency-gain-plot circle')).toHaveCount(3);
  await page.locator('#frequency-gain').selectOption('absolute');
  await page.locator('#frequency-csv').click();
  const fixed=await page.evaluate(()=>window.exports.at(-1).text);
  expect(fixed).toContain('"rates.z"');
  expect(fixture.results.fixed.samples.every(s=>s.responses[0].output.operating['rates.z'].real===0&&s.responses[0].output.operating['rates.z'].imag===0)).toBe(true);
  await page.evaluate(()=>loadResult('free'));await rate(page,'frame');
  await expect(page.locator('#frequency-base-condition')).toContainText('Base motion: accelerating');
  await expect(page.locator('#frequency-frame-notice')).toBeHidden();
  await expect(page.locator('#frequency-base-condition')).toContainText('compute a steady trim');
  await expect(page.locator('#frequency-phase-plot svg')).toBeVisible();
  await page.locator('#frequency-csv').click();const free=await page.evaluate(()=>window.exports.at(-1).text);
  const rows=free.trim().split('\n').map(line=>line.slice(1,-1).split('","')),header=rows.shift(),re=header.findIndex(k=>k.startsWith('real [')),im=header.findIndex(k=>k.startsWith('imag ['));
  expect(rows).toHaveLength(3);
  for(const [i,row] of rows.entries()){
    const expected=fixture.results.free.samples[i].responses[0].output.frame.rates_body;
    expect(Number(row[re])).toBe(expected.real[2]);expect(Number(row[im])).toBe(expected.imag[2]);
    expect(Math.hypot(Number(row[re]),Number(row[im]))).toBeGreaterThan(0);
  }
  expect(await page.evaluate(()=>JSON.stringify(fixture.results))).toBe(await page.evaluate(()=>window.original));
  expect(await page.evaluate(()=>window.edits)).toBe(0);
  await page.evaluate(()=>loadResult('fixed'));await rate(page,'operating');
  await page.locator('#frequency-frame').selectOption('free');await expect(page.locator('#frequency-frame')).toHaveValue('free');
  await expect(page.locator('#frequency-frame-notice')).toBeHidden();await expect(page.locator('#frequency-summary')).toHaveText('Select frequency response, then run an analysis.');
  await expect(page.locator('#frequency-base-condition')).toBeHidden();
});
