import test from 'node:test';
import assert from 'node:assert/strict';
import {VACUUM_NUMERICS,STILL_AIR_NUMERICS,MOVING_VACUUM_NUMERICS,
  vacuumModalRequest,stillAirModalRequest,movingVacuumModalRequest,
  movingVacuumTimeRequest,airflowDynamicRequest,sourceFrequencyRequest,
  assertMovingTimeRequest} from '../web/numerical-policy.js';

const pose={position_earth:[0,0,0],attitude:[0,0,0],gravity_magnitude:0,
  rates:[0,0,0],acceleration:[0,0,0],angular_acceleration:[0,0,0]};
const still={speed:0,density:1.2,position_earth:pose.position_earth,attitude:pose.attitude,gravity_magnitude:0};
const frame={velocity:[0,0,0],position:[0,0,0],attitude:[0,0,0],gravity_magnitude:0,
  motion:{rates:[0,0,0],acceleration:[0,0,0],angular_acceleration:[0,0,0]}};
const request=(action,mode)=>({action,mode:action,source:'literal',strut_mode:mode,
  [action]:{frame:'fixed',vacuum:true}});

for(const mode of ['bilateral','wire']){
  test(`source modal and frequency mappings preserve ${mode} law`,()=>{
    for(const policy of [VACUUM_NUMERICS,STILL_AIR_NUMERICS,MOVING_VACUUM_NUMERICS]){
      const r=request('modes',mode),isStill=policy===STILL_AIR_NUMERICS;
      if(isStill)Object.assign(r.modes,{vacuum:false,quiescent_density:1.2});
      const before=structuredClone(r);
      const mapped=isStill?stillAirModalRequest(r,still):policy===VACUUM_NUMERICS?
        vacuumModalRequest(r,pose):movingVacuumModalRequest(r,frame);
      assert.equal(mapped.strut_mode,mode);assert.deepEqual(r,before);
      const frequency={...r,action:'frequency',mode:'frequency',frequency:{...r.modes,
        frequencies:[1,10],inputs:[{kind:'initial',state:{}}]}};
      delete frequency.modes;
      assert.equal(sourceFrequencyRequest(frequency,policy,isStill?still:pose,frame).strut_mode,mode);
    }
  });
  test(`source cold time and airflow mappings preserve ${mode} law`,()=>{
    const r=request('time',mode);r.time={frame:'free',duration:.1,dt:.01};
    assert.equal(movingVacuumTimeRequest(r,frame).strut_mode,mode);
    for(const action of ['modes','frequency','time']){
      const flow=request(action,mode);flow.condition={speed:23,alpha:0};
      flow[action]={frame:action==='time'?'free':'fixed',
        ...(action==='time'?{duration:.1,dt:.01}:action==='frequency'?{inputs:['power.1']}: {})};
      assert.equal(airflowDynamicRequest(flow).strut_mode,mode);
    }
  });
}

test('invalid brace laws and saved-setup overrides are never silently discarded',()=>{
  for(const value of [null,'unknown',false,{},[]]){
    assert.throws(()=>vacuumModalRequest(request('modes',value),pose),/Strut mode/);
    const r=request('time',value);r.time={frame:'free',duration:.1,dt:.01};
    assert.throws(()=>movingVacuumTimeRequest(r,frame),/Strut mode/);
  }
  for(const airflow of [false,true])for(const action of ['launch_time','resume_time']){
    assert.throws(()=>assertMovingTimeRequest({action,mode:'time',source:'literal',strut_mode:'wire',
      time:{duration:.1,dt:.01}},{airflow}),/saved physical setup/);
  }
});
