import test from 'node:test';
import assert from 'node:assert/strict';
import {vortexOverlay,vortexColors} from '../web/vortex-overlay.js';

const c=Math.cos(Math.PI/6),s=Math.sin(Math.PI/6);
const frame={body_to_earth:[[c,0,s],[0,1,0],[-s,0,c]],position_earth:[2,-3,.127]};
const plane={flag:1,normal_body:[-s,0,c],offset:.127};
const data={bound_segments:[[[0,-.762,0],[0,0,0]],[[0,0,0],[0,.762,0]]],
  wake_direction:[Math.cos(.2),0,Math.sin(.2)],frozen:false};
const near=(actual,expected)=>{
  assert.equal(actual.length,expected.length);
  for(let i=0;i<actual.length;i++)assert.ok(Math.abs(actual[i]-expected[i])<2e-14,`${actual} != ${expected}`);
};

test('ground off keeps the existing real vortex overlay and does not mutate inputs',()=>{
  const original=structuredClone(data);
  const plain=vortexOverlay(data,3);
  assert.deepEqual(vortexOverlay(data,3,null,{...plane,flag:0}),plain);
  assert.equal(plain.length,2);
  assert.equal(plain[0].color,vortexColors.bound);
  assert.equal(plain[1].color,vortexColors.wake);
  vortexOverlay(data,3,frame,plane);
  assert.deepEqual(data,original);
});

for(const flag of [1,-1])for(const frozen of [false,true]) {
  test(`${flag===1?'solid':'free'} images reflect the entire ${frozen?'frozen':'current'} wake in Earth view`,()=>{
    const source={...data,frozen,wake_direction:frozen?[1,0,0]:data.wake_direction};
    const before=structuredClone({source,frame,plane});
    const [bound,wake,imageBound,imageWake]=vortexOverlay(source,2,frame,{...plane,flag});
    assert.equal(imageBound.kind,'vortex-image-bound');
    assert.equal(imageWake.kind,'vortex-image-wake');
    assert.equal(imageBound.color,vortexColors.imageBound);
    assert.equal(imageWake.color,vortexColors.imageWake);
    assert.equal(imageBound.overlay,true);
    assert.equal(imageWake.overlay,true);
    // Independent Earth-space geometry: the ground is simply Z=0. Reflect
    // both ends of every drawn segment, not only each wake's starting point.
    for(const [real,image] of [[bound,imageBound],[wake,imageWake]]) {
      assert.equal(image.segments.length,real.segments.length);
      real.segments.forEach((segment,i)=>segment.forEach(([x,y,z],j)=>near(image.segments[i][j],[x,y,-z])));
    }
    const leg=wake.segments[0],reflected=imageWake.segments[0];
    assert.ok(Math.abs(leg[1][2]-leg[0][2])>.1,'fixture must detect an unchanged image-ray direction');
    near(reflected[1].map((v,i)=>v-reflected[0][i]),leg[1].map((v,i)=>(i===2?-1:1)*(v-leg[0][i])));
    assert.deepEqual({source,frame,plane},before);
  });
}

test('body-view image points have opposite signed plane distance and preserve tangential position',()=>{
  const dot=p=>p.reduce((sum,v,i)=>sum+v*plane.normal_body[i],0);
  const objects=vortexOverlay(data,4,null,plane);
  for(const [real,image] of [[objects[0],objects[2]],[objects[1],objects[3]]]) {
    real.segments.forEach((segment,i)=>segment.forEach((p,j)=>{
      const reflected=image.segments[i][j],distance=dot(p)+plane.offset;
      near([dot(reflected)+plane.offset],[-distance]);
      near(reflected.map((v,k)=>v+distance*plane.normal_body[k]),p.map((v,k)=>v-distance*plane.normal_body[k]));
    }));
  }
});
