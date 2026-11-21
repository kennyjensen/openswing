import test from 'node:test';
import assert from 'node:assert/strict';
import {frameSettingHelp,constrainedRateHelp,rateLabel,rateDefinition,controlInputLabel,baseMotionNote,baseConditionSummary} from '../web/frequency-frame-help.js';

const yaw={group:'operating',key:'rates.z',component:null,display:'response'};
test('fixed response explains constrained body rates without changing data',()=>{
  const result={frame_mode:'fixed',samples:[{response:{real:0,imag:0}}]},before=JSON.stringify(result);
  assert.match(constrainedRateHelp(result,yaw),/yaw rate is constrained to zero/);
  assert.match(constrainedRateHelp(result,{group:'frame',key:'rates_body',component:0}),/roll rate/);
  assert.match(frameSettingHelp('fixed'),/loads and elastic deformation can still respond/);
  assert.equal(JSON.stringify(result),before);
  assert.match(constrainedRateHelp(result,{group:'frame'}),/no Flight frame outputs were computed/);
  assert.match(constrainedRateHelp(result,{group:'frame'}),/Other output groups use the saved result immediately/);
});
test('free motion and unrelated physical zeros receive no constrained-zero claim',()=>{
  for(const result of [{frame_mode:'free'},{frame_mode:'mixed',frame_load_targets:{'moment.z':0}}])
    assert.equal(constrainedRateHelp(result,yaw),'');
  for(const selection of [{group:'global',key:'Cn'},{group:'nodes',key:'rates',component:2},{...yaw,display:'broken_loop'}])
    assert.equal(constrainedRateHelp({frame_mode:'fixed'},selection),'');
  assert.equal(constrainedRateHelp(null,yaw),'');
});
test('recorded mixed constraints distinguish solved yaw from a prescribed axis',()=>{
  const explanation=constrainedRateHelp({frame_mode:'mixed',frame_load_targets:{'moment.x':0}},yaw);
  assert.match(explanation,/prescribes yaw acceleration/);assert.doesNotMatch(explanation,/constrained to zero/);
  assert.match(constrainedRateHelp({frame_mode:'prescribed'},yaw),/run a new analysis/);
  assert.match(frameSettingHelp('free'),/does not establish a steady-flight trim/);
});
test('angular velocity labels distinguish aircraft and local elastic motion',()=>{
  for(const [i,axis] of ['x','y','z'].entries()){
    assert.equal(rateLabel('operating','rates.'+axis,null),rateLabel('frame','rates_body',i));
    assert.equal(rateLabel('frame','rates_body',i),`${['Roll','Pitch','Yaw'][i]} angular velocity Ω_${axis} · body ${axis}`);
    assert.equal(rateLabel('nodes','rates',i),`Elastic angular velocity ω_${axis} · body ${axis}`);
    assert.match(rateDefinition('frame','rates_body',i),new RegExp('ASWING W'+axis));
    assert.match(rateDefinition('nodes','rates',i),/relative to the aircraft frame/);
  }
  assert.equal(rateLabel('frame','rates_body',3),null);
  assert.equal(rateLabel('nodes','rates',3),null);
  assert.equal(rateDefinition('nodes','rotation',2),'');
});
test('control labels use declared beam metadata without guessing aircraft function',()=>{
  const model={distributions:[{name:'Rudder',properties:['dCLdF3']},{name:'Rudder',properties:['dCMdF3']},{name:'Other',properties:['dCLdF30']},{name:'Stab',properties:['dCLdF2']}]};
  assert.equal(controlInputLabel({name:'control.3'},model),'control.3 · Rudder');
  assert.equal(controlInputLabel({name:'control.2'},model),'control.2 · Stab');
  assert.equal(controlInputLabel({name:'control.1'},model),'control.1');
  assert.equal(controlInputLabel({name:'power.1'},model),'power.1');
  assert.equal(controlInputLabel({name:'control.3'},null),'control.3');
});
test('accelerating-base qualification follows the recorded flag without inventing a threshold',()=>{
  assert.match(baseMotionNote({base:{modal_base:{kinematically_steady:false}}}),/accelerating state.*steady trim/);
  assert.equal(baseMotionNote({base:{modal_base:{kinematically_steady:true}}}),'');
  assert.equal(baseMotionNote({base:{}}),'');
});

test('base summary separates fixed motion, steady motion and unknown trim',()=>{
  const result={frame_mode:'free',base:{modal_base:{kinematically_steady:false}}};
  assert.match(baseConditionSummary(result),/accelerating.*steady trim/);
  result.base.modal_base.kinematically_steady=true;
  assert.match(baseConditionSummary(result),/steady in the recorded flight frame/);
  result.frame_mode='fixed';
  assert.match(baseConditionSummary(result),/held fixed.*trim is not established/);
  assert.match(baseConditionSummary({frame_mode:'free',base:{}}),/not reported/);
  assert.equal(baseConditionSummary(null),'');
});

test('base summary reports physical weight using actual gravity, not the lift-target multiplier',()=>{
  const result={frame_mode:'free',base:{modal_base:{kinematically_steady:true},
    mass_properties:{mass:10},gravity_body:[0,6,-8],atmosphere:{gravity_magnitude:32.18,load_factor:3},
    reference_flow:{speed:22},earth_state:{flight_path:0}}};
  const model={units:{F:[1,'lb'],L:[1,'ft'],T:[1,'s']}};
  const before=JSON.stringify(result);
  assert.match(baseConditionSummary(result,model),/Weight 100 lb/);
  assert.match(baseConditionSummary(result,model),/airspeed 22 ft\/s.*Flight path 0°/);
  assert.equal(JSON.stringify(result),before);
  result.base.gravity_body=[0,0,0];assert.match(baseConditionSummary(result,model),/Weight 0 lb/);
  result.base.mass_properties.physical=false;assert.doesNotMatch(baseConditionSummary(result,model),/Weight/);
  delete result.base.mass_properties.physical;delete result.base.gravity_body;
  assert.match(baseConditionSummary(result,{units:{F:[2,'lb']}}),/Weight 321.8 input F/);
  delete result.base.mass_properties;assert.doesNotMatch(baseConditionSummary(result,model),/Weight/);
});
