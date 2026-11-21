import {test} from 'node:test';
import assert from 'node:assert/strict';
import {equalPhysical} from '../scripts/isae_time_browser_compare.mjs';

test('signed zeros survive JSON continuation as the same physical value',()=>{
  const state={attitude:[0,-0,0],force:[2,3,4]};
  equalPhysical(state,JSON.parse(JSON.stringify(state)));
});
test('one ULP of nonzero circulation is rejected',()=>{
  assert.throws(()=>equalPhysical({gamma:[1]},{gamma:[1+Number.EPSILON]}));
});
test('missing fields and changed shapes are rejected',()=>{
  assert.throws(()=>equalPhysical({frame:[0,0,0]},{}));
  assert.throws(()=>equalPhysical([0],[0,0]));
});
test('nonfinite physical states are rejected, including matching nonfinite values',()=>{
  for(const value of [NaN,Infinity,-Infinity])assert.throws(()=>equalPhysical([value],[value]));
});
