import test from 'node:test';
import assert from 'node:assert/strict';
import {frequencySampleLabel,frequencyPlaybackPhase,frequencyPlaybackNote,frequencyMotionSummary} from '../web/frequency-playback.js';

test('model-time animation differentiates to the harmonic angular-rate amplitude',()=>{
  const amplitude=.2,dt=.00001;
  for(const frequency of [.2,1,10]){
    const omega=2*Math.PI*frequency;
    const angle=time=>amplitude*Math.cos(frequencyPlaybackPhase(90,time*1000,omega,'model')*Math.PI/180);
    // Center the derivative away from the clock's initial-time boundary.
    const t=1/frequency,rate=(angle(t+dt)-angle(t-dt))/(2*dt);
    assert.ok(Math.abs(rate+omega*amplitude)<omega*amplitude*1e-6);
    assert.ok(Math.abs(frequencyPlaybackPhase(17,1000/frequency,omega,'model')-17)<1e-10);
  }
});

test('inspection has an explicit frequency-independent clock and warning',()=>{
  for(const frequency of [.2,1,10]){
    assert.equal(frequencyPlaybackPhase(0,1000,2*Math.PI*frequency,'inspection'),90);
    assert.equal(frequencyPlaybackPhase(0,4000,2*Math.PI*frequency,'inspection'),0);
  }
  assert.match(frequencyPlaybackNote(2*Math.PI,'inspection'),/Visible turning speed is not the physical angular rate/);
  assert.equal(frequencyPlaybackPhase(20,1000,0,'model'),20);
  assert.match(frequencyPlaybackNote(0,'model'),/static/);
});

test('sample labels expose both frequency conventions with matching unit assumptions',()=>{
  const model={units:{T:[1,'s']}};
  assert.equal(frequencySampleLabel(2*Math.PI,'cycles',model),'1 Hz · 6.28319 rad/s');
  assert.equal(frequencySampleLabel(2*Math.PI,'radians',model),'6.28319 rad/s · 1 Hz');
  assert.equal(frequencySampleLabel(0,'cycles',model),'0 Hz · 0 rad/s');
  assert.equal(frequencySampleLabel(2*Math.PI,'cycles'),'1 cycles/T · 6.28319 rad/T');
  assert.match(frequencyPlaybackNote(2*Math.PI,'model',model),/Real-time playback · 1 second per cycle/);
  assert.match(frequencyPlaybackNote(2*Math.PI,'model'),/1 input T per wall-clock second/);
});

test('animation motion summary distinguishes rate and angle and applies display amplitude',()=>{
  const frame={rates_body:{real:[0,0,.003],imag:[0,0,.004]},attitude_rad:{real:[0,0,0],imag:[0,0,.001]}};
  const model={units:{T:[1,'s']}},before=JSON.stringify(frame);
  assert.equal(frequencyMotionSummary({frame},2,'radians',model),'Aircraft-frame amplitudes at input ×2: body yaw rate 0.01 rad/s · heading angle 0.002 rad.');
  assert.equal(frequencyMotionSummary({frame},2,'degrees',model),'Aircraft-frame amplitudes at input ×2: body yaw rate 0.572958 °/s · heading angle 0.114592 °.');
  assert.match(frequencyMotionSummary({frame},0,'degrees'),/body yaw rate 0 °\/T · heading angle 0 °/);
  assert.equal(frequencyMotionSummary({},1),'');
  assert.equal(frequencyMotionSummary({frame},NaN),'');
  assert.equal(frequencyMotionSummary({frame},-1),'');
  assert.equal(JSON.stringify(frame),before);
});
