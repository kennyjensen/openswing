import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {distributionSegments} from '../web/distribution-spline.js';

// Reference samples come from the native Distribution/SciPy implementation,
// including left-sided jump endpoints. No solver or browser is needed here.
const cases=JSON.parse(readFileSync(new URL('./fixtures/distribution-spline.json',import.meta.url),'utf8'));
for(const c of cases)test('live spline agrees with native '+c.policy+' '+c.name,()=>{
  const actual=distributionSegments(c.points,c.report,c.policy);
  assert.equal(actual.length,c.expected.length);
  let error=0;
  c.expected.forEach((s,j)=>s.t.forEach((t,i)=>{
    const index=actual[j].t.findIndex(x=>Math.abs(x-t)<1e-12);
    if(index<0)throw new Error('Missing reference station '+t);
    error=Math.max(error,Math.abs(actual[j].values[index]-s.values[i])/(1+Math.abs(s.values[i])));
  }));
  assert.ok(error<2e-12,'Maximum relative display error '+error);
});

test('invalid rows hide the live curve and singleton rigid overrides stay constant',()=>{
  const report={domain:[-5,5],mirrored:true};
  for(const rows of [[],[[0,1]],[[0,''],[1,2]],[[0,1],[2,2],[1,3]],[[0,1],[0,2],[1,3]]])assert.deepEqual(distributionSegments(rows,report),[]);
  assert.deepEqual(distributionSegments([[1,0]],{...report,rigid_zero:true}),[{t:[-5,5],values:[0,0],extrapolated:false}]);
});
