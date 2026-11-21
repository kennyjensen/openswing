import test from 'node:test';
import assert from 'node:assert/strict';
import {totalForcesMarkup,flightOutputValues,outputNumber,renderFlightOutput} from '../web/total-forces.js';

const model={reference:[[10,2,8]],controls:[2,3],distributions:[{name:'Stab',properties:['dCLdF2']},{name:'Rudder',properties:['dCLdF3']}]};
test('total forces keeps every coefficient and diagnostic exactly once in compact cells',()=>{
  for(const id of ['cl','cy','cd','cdi','cdp','roll','pitch','yaw','efficiency','mach','out-alpha','out-beta','out-p','out-q','out-r',
    'cdi-near','cdbody','cdam','cdeng','residual','stalled','mass','deflection','output-controls','trefftz-note','circulation-note'])
    assert.equal(totalForcesMarkup.split(`id="${id}"`).length-1,1);
  assert.match(totalForcesMarkup,/<details class="output-extra"><summary>Additional results/);
  assert.equal(totalForcesMarkup.includes('result-hero'),false);
});
test('display precision is compact and avoids misleading negative zero or missing zeros',()=>{
  assert.equal(outputNumber(.828612345), '0.8286');assert.equal(outputNumber(-.000001), '0.0000');
  assert.equal(outputNumber(0), '0.0000');assert.equal(outputNumber(5,3), '5.000');
  for(const value of [null,undefined,NaN,Infinity])assert.equal(outputNumber(value),'—');
});
test('reported conditions and rates use solved values and documented stability axes',()=>{
  const condition={alpha:0,beta:0,speed:99,rates:[0,0,0],controls:{2:0,3:0}};
  const result={operating_values:{alpha:30,beta:4,speed:20,'rates.x':1,'rates.y':2,'rates.z':3,'control.2':-1.51,'control.3':.2}};
  const before=JSON.stringify({condition,result,model}),v=flightOutputValues(result,condition,model);
  assert.equal(v.alpha,30);assert.equal(v.beta,4);
  assert.ok(Math.abs(v.rates[0]-(-Math.sqrt(3)/2-1.5)/5)<1e-12);
  assert.equal(v.rates[1],.1);assert.ok(Math.abs(v.rates[2]-(.5-3*Math.sqrt(3)/2)/5)<1e-12);
  assert.deepEqual(v.controls,[{index:2,label:'Stab (F2)',value:-1.51},{index:3,label:'Rudder (F3)',value:.2}]);
  assert.equal(JSON.stringify({condition,result,model}),before);
  assert.deepEqual(flightOutputValues(result,{...condition,speed:0},null).rates,[null,null,null]);
  assert.deepEqual(flightOutputValues(null,condition,model).controls,[]);
});
test('time response frame rates and controller actuator values take precedence over requested inputs',()=>{
  const condition={alpha:0,beta:0,speed:10,controls:{2:0,3:0}},result={frame:{rates_body:[-1,2,-3]},feedback:{actuators:{F2:1.3}}};
  const values=flightOutputValues(result,condition,model);
  assert.deepEqual(values.rates,[.4,.2,1.2]);assert.equal(values.controls[0].value,1.3);
});
test('control labels are escaped, file settings are not mislabeled degrees, and reset clears values',()=>{
  const previous=globalThis.document,nodes={};globalThis.document={getElementById:id=>nodes[id]??=( {} )};
  try{
    renderFlightOutput({},{alpha:5,beta:0,speed:20,controls:{2:-1.51}},{...model,distributions:[{name:'<script>',properties:['dCLdF2']}]});
    assert.equal(nodes['out-alpha'].textContent,'5.000');assert.equal(nodes['output-controls'].hidden,false);
    assert.match(nodes['output-controls'].innerHTML,/&lt;script&gt;/);assert.match(nodes['output-controls'].innerHTML,/-1.51/);
    assert.equal(nodes['output-controls'].innerHTML.includes(' deg'),false);
    renderFlightOutput(null,null,model);assert.equal(nodes['out-alpha'].textContent,'—');assert.equal(nodes['output-controls'].hidden,true);
    assert.equal(nodes['output-controls'].innerHTML,'');
  }finally{globalThis.document=previous;}
});
