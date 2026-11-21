// Exact finite physical values. Signed zeros represent the same state after JSON.
import assert from 'node:assert/strict';

export function equalPhysical(a,b,path='state'){
  assert.equal(typeof a,typeof b,path);
  if(typeof a==='number'){
    assert.ok(Number.isFinite(a)&&Number.isFinite(b),path+' must be finite');
    assert.ok(a===b,path+' changed');
  }else if(a===null||b===null||typeof a!=='object'){
    assert.equal(a,b,path);
  }else{
    assert.equal(Array.isArray(a),Array.isArray(b),path);
    if(Array.isArray(a))assert.equal(a.length,b.length,path);
    assert.deepEqual(Object.keys(a).sort(),Object.keys(b).sort(),path);
    for(const key of Object.keys(a))equalPhysical(a[key],b[key],path+'/'+key);
  }
}
