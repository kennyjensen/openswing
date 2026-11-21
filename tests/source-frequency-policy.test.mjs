import {test} from 'node:test';
import assert from 'node:assert/strict';
import {VACUUM_NUMERICS,STILL_AIR_NUMERICS,MOVING_VACUUM_NUMERICS,sourceFrequencyRequest,
  numericalRequest,assertSourceFrequencyRequest,assertVacuumInputs,assertStillAirInputs,assertMovingVacuumInputs} from '../web/numerical-policy.js';

const initial={kind:'initial',name:'Released spring',state:{beam_fields:[{beam:1,displacement:[[1,0,0,0],[3,0,.001,0]]}]}};
const pose={position_earth:[1,2,3],attitude:[4,5,6],gravity_magnitude:0,rates:[0,0,0],acceleration:[0,0,0],angular_acceleration:[0,0,0]};
const frame={velocity:[2,3,4],position:pose.position_earth,attitude:pose.attitude,gravity_magnitude:0,
  motion:{rates:[0,0,0],acceleration:[0,0,0],angular_acceleration:[0,0,0]}};
const raw=()=>({action:'frequency',mode:'frequency',source:'literal',panels:4,condition:pose,
  strut_mode:'bilateral',operating_constraints:[],derivatives:undefined,frequency_spacing:'log',retain_frequency:true,
  frequency:{frame:'fixed',frequencies:[1,2,3],inputs:[initial],initial_shift:.2,step:1e-5,matrices:true}});

for(const policy of [VACUUM_NUMERICS,STILL_AIR_NUMERICS,MOVING_VACUUM_NUMERICS]){
  test(`frequency mapping retains operator, medium and pose: ${policy.structural_operator}`,()=>{
    const request=raw(),before=structuredClone(request),still=policy===STILL_AIR_NUMERICS;
    const mapped=sourceFrequencyRequest(request,policy,still?{speed:0,density:1.225,position_earth:pose.position_earth,
      attitude:pose.attitude,gravity_magnitude:0}:pose,frame);
    assert.deepEqual(request,before);assert.equal(mapped.condition,null);assert(!('modes' in mapped));
    assert.equal(mapped.frequency.vacuum,!still);assert.deepEqual(mapped.frequency.position,pose.position_earth);
    assert.deepEqual(mapped.frequency.inputs,[initial]);assert.equal(mapped.frequency_spacing,'log');
    assert.deepEqual(numericalRequest(mapped,policy),{...mapped,numerics:policy});
    if(still)assert.equal(mapped.frequency.quiescent_density,1.225);
    else assert(!('quiescent_density' in mapped.frequency));
    for(const change of [{structural_operator:'midpoint-v1'},{count:10},{controller:{}},{inputs:['control.1']},{inputs:[{kind:'gust'}]}]){
      assert.throws(()=>assertSourceFrequencyRequest({...mapped,frequency:{...mapped.frequency,...change}},policy));
    }
    const session={...policy,format:'openswing-live-frequency',version:1,id:'test'};
    assert.doesNotThrow(()=>numericalRequest({action:'extend_frequency',source:'literal',session,frequencies:[4]},policy));
    assert.throws(()=>numericalRequest({action:'extend_frequency',source:'literal',session,frequencies:[4]},undefined),/do not match/);
  });
}

test('moving frequency supports canonical frame forcing and keeps exact motion',()=>{
  for(const motion of ['prescribed','free','mixed']){
    const r=raw();Object.assign(r.frequency,{frame:motion,inputs:[motion==='prescribed'?'acceleration.y':'target.force.y']});
    if(motion==='mixed')r.frequency.load_targets={'force.y':0};
    const out=sourceFrequencyRequest(r,MOVING_VACUUM_NUMERICS,pose,frame);
    assert.equal(out.frequency.frame,motion);assert.deepEqual(out.frequency.motion,frame.motion);
    assert.doesNotThrow(()=>numericalRequest(out,MOVING_VACUUM_NUMERICS));
    assert.throws(()=>numericalRequest(out,VACUUM_NUMERICS));
  }
});

test('source frequency workbench catches incompatible frame or airflow inputs before dispatch',()=>{
  const fields={mode:'frequency','frequency-frame':'fixed','frequency-inputs':'initial','modal-vacuum':true,
    'modal-quiescent':false,'modal-quiescent-density':'1.225','feedback-enabled':false,'gravity-mode':'file',
    'attitude-bank':'0','attitude-elevation':'0','attitude-heading':'0',
    ...Object.fromEntries(['moving-velocity','rates','acceleration','angular_acceleration','position-earth'].flatMap(kind=>['x','y','z'].map(axis=>[`${kind}-${axis}`,'0'])))};
  assert.doesNotThrow(()=>assertVacuumInputs(fields));assert.doesNotThrow(()=>assertMovingVacuumInputs(fields));
  assert.doesNotThrow(()=>assertStillAirInputs({...fields,'modal-vacuum':false,'modal-quiescent':true}));
  for(const check of [assertVacuumInputs,assertMovingVacuumInputs]){
    assert.throws(()=>check({...fields,'frequency-inputs':'all'}));
    assert.throws(()=>check({...fields,'frequency-inputs':'frame'}));
    assert.throws(()=>check({...fields,'feedback-enabled':true}));
  }
  assert.throws(()=>assertVacuumInputs({...fields,'frequency-frame':'free'}));
});
