import test from 'node:test';
import assert from 'node:assert/strict';
import {quiescentCondition} from '../web/quiescent-settings.js';
import {STILL_AIR_NUMERICS,selectedNumerics,stillAirModalRequest,sourceFrequencyRequest,
  assertSourceFrequencyRequest,assertStillAirIdentity} from '../web/numerical-policy.js';

const condition=factor=>quiescentCondition({density:10,position_earth:[0,0,0],attitude:[0,0,0],
  gravity_magnitude:0,body_added_mass_factor:factor});
test('still-air modes and frequency requests retain the selected body coefficient',()=>{
  assert.deepEqual(selectedNumerics('aswing-still-air'),STILL_AIR_NUMERICS);
  for(const factor of [1,2]){
    const modal=stillAirModalRequest({action:'modes',mode:'modes',source:'body',panels:4,
      numerics:STILL_AIR_NUMERICS,modes:{frame:'fixed',vacuum:false,quiescent_density:10}},condition(factor));
    assert.equal(modal.condition,null);assert.equal(modal.modes.quiescent_body_added_mass_factor,factor);
    const request=sourceFrequencyRequest({action:'frequency',mode:'frequency',source:'body',panels:4,
      numerics:STILL_AIR_NUMERICS,frequency:{frame:'fixed',frequencies:[1,4],inputs:[{kind:'initial'}]}},STILL_AIR_NUMERICS,condition(factor));
    assertSourceFrequencyRequest(request,STILL_AIR_NUMERICS);
    assert.equal(request.frequency.quiescent_body_added_mass_factor,factor);
  }
});
test('saved body states reject a coefficient mismatch without changing old surface identities',()=>{
  const packet={format:'openswing-equilibrium',version:1,positions:[],identity:{...STILL_AIR_NUMERICS,quiescent_density:10},launch:{quiescent_density:10}};
  assertStillAirIdentity(packet,10);
  packet.identity.quiescent_body_added_mass_factor=2;packet.launch.quiescent_body_added_mass_factor=2;
  assertStillAirIdentity(packet,10,2);
  assert.throws(()=>assertStillAirIdentity(packet,10,1),/coefficient/);
});
test('invalid body choices cannot silently become the default convention',()=>{
  for(const value of [true,false,0,1.5,3,NaN,'2',null])assert.throws(()=>condition(value),/fuselage/);
});
