import assert from 'node:assert/strict';
import test from 'node:test';
import {fourierWakeOptions,fourierWakeSummary} from '../web/fourier-wake.js';

test('only enabled rigid analyses request the optional diagnostic',()=>{
  assert.deepEqual(fourierWakeOptions('rigid',true),{fourier_wake_diagnostic:true});
  assert.deepEqual(fourierWakeOptions('rigid',false),{});
  for(const mode of ['mounted','structural','modes','frequency','time'])assert.deepEqual(fourierWakeOptions(mode,true),{});
  assert.throws(()=>fourierWakeOptions('rigid','true'),/on or off/);
});

test('reference results show the signed difference without replacing main values',()=>{
  const wake={CDi:.02,continuous_fourier:{available:true,CDi:.019,efficiency:.8}};
  const before=JSON.stringify(wake),text=fourierWakeSummary(wake);
  assert.match(text,/CDi = 0.019 \(-5% from discrete CDi\)/);
  assert.match(text,/efficiency = 0.8/);
  assert.match(text,/main coefficients retain/);
  assert.equal(JSON.stringify(wake),before);
});

test('missing, unsupported and exactly cancelled wakes never become invented zeros',()=>{
  assert.equal(fourierWakeSummary(null),'');
  assert.match(fourierWakeSummary({},true),/not returned.*Reload/);
  assert.match(fourierWakeSummary({continuous_fourier:{available:false,reason:'Ground images unsupported.'}}),/Ground images unsupported/);
  const text=fourierWakeSummary({CDi:0,continuous_fourier:{available:true,CDi:0,efficiency:null}});
  assert.match(text,/CDi = 0 \(difference 0\)/);
  assert.match(text,/efficiency = unavailable/);
  assert.doesNotMatch(text,/NaN|Infinity/);
  assert.match(fourierWakeSummary({CDi:1e-100,continuous_fourier:{available:true,CDi:2e-100,efficiency:0}}),/2e-100 \(\+100%/);
});
