import {test} from 'node:test';
import assert from 'node:assert/strict';
import {beamPlotControls,renderBeamDistribution,beamValueAt} from '../web/beam-distribution-plot.js';

test('span properties use labelled selectors and headings without export or history controls',()=>{
  for(const prefix of ['plot','structure']){
    const html=beamPlotControls({prefix,quantityOptions:'<option value="value">Value</option>'});
    for(const suffix of ['beam','quantity','title','unit'])assert.ok(html.includes('id="'+prefix+'-'+suffix+'"'));
    for(const removed of ['<button','CSV','Time distribution view','Current snapshot'])assert.equal(html.includes(removed),false);
    assert.match(html,/<label>Beam<select/);assert.match(html,/<label>Property<select/);
  }
});
test('the common chart preserves missing-value gaps and highlights stalled sections',()=>{
  const target={clientWidth:400};
  renderBeamDistribution(target,[{t:0,value:1},{t:1,value:null},{t:2,value:2,stalled:true}],{label:'Lift & load'});
  assert.match(target.innerHTML,/Lift &amp; load/);
  assert.match(target.innerHTML,/distribution-stalled/);
  const curve=target.innerHTML.match(/<path d="([^"]+)" class="plot-line"/)[1];
  assert.equal((curve.match(/M/g)||[]).length,2);assert.equal(curve.includes('L'),false);
  assert.equal(target.innerHTML.includes('NaN'),false);
});
test('section extents and concentrated impulses retain their physical plotting semantics',()=>{
  for(const [kind,segment] of [['sections','class="section-segment"'],['impulses','class="plot-line"']]){
    const target={clientWidth:400};
    renderBeamDistribution(target,[{t:1,t0:0,t1:2,value:-3}],{kind});
    assert.ok(target.innerHTML.includes(segment));assert.match(target.innerHTML,/<circle/);
    assert.equal(target.innerHTML.includes('NaN'),false);
  }
  const empty={};renderBeamDistribution(empty,[{t:1,value:null}]);
  assert.match(empty.textContent,/No values/);
});

test('hover values follow the drawn curve without bridging missing data or extrapolating',()=>{
  const samples=[{t:0,value:2},{t:2,value:6},{t:3,value:null},{t:4,value:10}];
  assert.deepEqual(beamValueAt(samples,1),{t:1,value:4});
  assert.deepEqual(beamValueAt(samples,2),{t:2,value:6});
  for(const t of [-1,2.5,3,3.5,5])assert.equal(beamValueAt(samples,t),null);
});

test('hover preserves interval values and selects actual concentrated forces',()=>{
  const sections=[{t:.5,t0:0,t1:1,value:3},{t:1.5,t0:1,t1:2,value:9}];
  assert.deepEqual(beamValueAt(sections,.9,'sections'),{t:.9,value:3});
  assert.deepEqual(beamValueAt(sections,1.1,'sections'),{t:1.1,value:9});
  assert.equal(beamValueAt(sections,3,'sections'),null);
  assert.equal(beamValueAt(sections,1.1,'impulses'),sections[1]);
});

test('hover converts pointer coordinates into chart units and clears on leave or empty data',()=>{
  const element=()=>({attributes:{},textContent:'',setAttribute(name,value){this.attributes[name]=String(value);},getComputedTextLength:()=>80});
  const parts=Object.fromEntries(['path','circle','rect','text'].map(tag=>[tag,element()]));
  const hover={...element(),querySelector:tag=>parts[tag]};
  const chart={querySelector:()=>hover,getScreenCTM:()=>({inverse:()=>({})}),createSVGPoint:()=>({matrixTransform(){return {x:(this.x-100)/2,y:(this.y-40)/2};}})};
  const target={clientWidth:400,querySelector:()=>chart};
  renderBeamDistribution(target,[{t:0,value:2},{t:2,value:6}],{unit:'N'});
  target.onpointermove({clientX:552,clientY:240});
  assert.equal(hover.attributes.visibility,'visible');assert.equal(parts.path.attributes.d,'M226 20V180');
  assert.equal(parts.text.textContent,'t = 1 · 4 N');assert.equal(parts.circle.attributes.cx,'226');
  target.onpointerleave();assert.equal(hover.attributes.visibility,'hidden');
  target.onpointerdown({clientX:552,clientY:240});assert.equal(hover.attributes.visibility,'visible');
  target.onpointermove({clientX:0,clientY:0});assert.equal(hover.attributes.visibility,'hidden');
  target.onpointerdown({clientX:552,clientY:240,pointerType:'touch'});
  target.onpointerleave({pointerType:'touch'});target.onpointercancel({pointerType:'touch'});
  assert.equal(hover.attributes.visibility,'visible');assert.equal(parts.text.textContent,'t = 1 · 4 N');
  target.onpointermove({clientX:0,clientY:0,pointerType:'touch'});assert.equal(hover.attributes.visibility,'visible');
  target.onpointerdown({clientX:706,clientY:240,pointerType:'touch'});assert.equal(parts.text.textContent,'t = 1.5 · 5 N');
  renderBeamDistribution(target,[{t:0,value:4},{t:2,value:8}],{unit:'N',range:[0,10]});
  assert.equal(hover.attributes.visibility,'visible');assert.equal(parts.text.textContent,'t = 1.5 · 7 N');
  renderBeamDistribution(target,[{t:0,value:4},{t:2,value:8}],{unit:'N',hoverKey:'another beam'});
  // The real SVG starts hidden; the saved touch position must not cross beams.
  assert.match(target.innerHTML,/beam-hover" visibility="hidden"/);
  renderBeamDistribution(target,[]);assert.equal(target.onpointermove,null);assert.equal(target.onpointerdown,null);
});

test('full-cycle limits hold the axes steady across animation phases',()=>{
  const target={clientWidth:400};
  renderBeamDistribution(target,[{t:0,value:2},{t:2,value:6}],{range:[-4,10]});
  const axis=target.innerHTML.match(/data-y-min="([^"]+)" data-y-max="([^"]+)"/)[0];
  renderBeamDistribution(target,[{t:0,value:-2},{t:2,value:0}],{range:[-4,10]});
  assert.ok(target.innerHTML.includes(axis));
});
