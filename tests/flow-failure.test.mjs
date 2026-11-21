import test from 'node:test';
import assert from 'node:assert/strict';
import {failureOverlay} from '../web/flow-failure.js';

const diagnostic=()=>({kind:'section_normal_mach',maximum:{position:[1,2,3]},vortex_breakdown:{
  available:true,axes:'body',influence_geometry:'frozen jig',influence_receiver:[1,2,0],direction:[2,0,0],
  bound_sources:[{start:[0,1,0],end:[0,2,0]}],wake_sources:[{origin:[0,2,0]}],
}});

test('failure markers retain physical frozen sources and distinguish moved force receiver',()=>{
  const data=diagnostic(),before=structuredClone(data),objects=failureOverlay(data,4);
  assert.deepEqual(objects.find(o=>o.kind==='failure-bound').segments,[[[0,1,0],[0,2,0]]]);
  assert.deepEqual(objects.find(o=>o.kind==='failure-wake').segments,[[[0,2,0],[4,2,0]]]);
  for(const [kind,center] of [['failure-point',[1,2,3]],['failure-receiver',[1,2,0]]]) {
    for(const [a,b] of objects.find(o=>o.kind===kind).segments)assert.deepEqual(a.map((v,i)=>(v+b[i])/2),center);
  }
  assert(objects.every(o=>o.overlay)); // Neither renderer includes overlays in fit bounds.
  assert.deepEqual(data,before);
});

test('coincident current receiver gets one marker; unavailable sources retain force point',()=>{
  const data=diagnostic();data.vortex_breakdown.influence_receiver=[1,2,3];data.vortex_breakdown.influence_geometry='current';
  assert(!failureOverlay(data).some(o=>o.kind==='failure-receiver'));
  data.vortex_breakdown={available:false,reason:'Nonfinite attribution'};
  assert.deepEqual(failureOverlay(data).map(o=>o.kind),['failure-point']);
});

test('unrelated errors and nonfinite geometry cannot reach the renderer',()=>{
  assert.deepEqual(failureOverlay(null),[]);
  assert.deepEqual(failureOverlay({kind:'other'}),[]);
  const data=diagnostic();data.maximum.position=[NaN,0,0];assert.deepEqual(failureOverlay(data),[]);
  data.maximum.position=[1,2,3];data.vortex_breakdown.direction=[0,0,0];
  data.vortex_breakdown.bound_sources[0].start=[Infinity,1,0];
  const objects=failureOverlay(data,NaN);
  assert.deepEqual(objects.map(o=>o.kind),['failure-receiver','failure-point']);
  assert(objects.flatMap(o=>o.segments.flat(2)).every(Number.isFinite));
});

test('every rejected section is marked once, with the worst point larger',()=>{
  const data=diagnostic();
  data.rejected_sections=[
    {position:[1,2,3],influence_position:[1,2,0],normal_mach:2},
    {position:[1,-2,3],influence_position:[1,-2,0],normal_mach:1},
    {position:[1,0,3],normal_mach:.9},
    {position:[NaN,2,3],normal_mach:3},
  ];
  const before=structuredClone(data),objects=failureOverlay(data,4);
  const points=objects.find(o=>o.kind==='failure-point').segments;
  assert.equal(points.length,6);
  assert.equal(objects.find(o=>o.kind==='failure-receiver').segments.length,6);
  for(const [offset,center] of [[0,[1,2,3]],[3,[1,-2,3]]]) {
    for(const [a,b] of points.slice(offset,offset+3))assert.deepEqual(a.map((v,i)=>(v+b[i])/2),center);
  }
  assert(points[0][1][0]-points[0][0][0]>points[3][1][0]-points[3][0][0]);
  assert.deepEqual(data,before);
});
