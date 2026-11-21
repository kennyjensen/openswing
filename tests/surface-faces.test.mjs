import test from 'node:test';
import assert from 'node:assert/strict';
import {surfaceFaces} from '../web/surface-faces.js';
import {vortexOverlay} from '../web/vortex-overlay.js';
import {trajectoryGeometry} from '../web/time-results.js';
import {modeGeometry} from '../web/mode-results.js';

function swept() {
  const c=Math.SQRT1_2;
  return {lifting:true,mirror_join:1,axis:[[[1,-1,0],[0,0,0]],[[0,0,0],[1,1,0]]],
    quads:[[[1,-1,0],[0,0,0],[c,c,0],[1+c,-1+c,0]],[[0,0,0],[1,1,0],[1+c,1-c,0],[c,-c,0]]]};
}
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-12,`${a} != ${b}`);
test('swept normal sections meet at the root without drawing either skin across it',()=>{
  const beam=swept(),original=structuredClone(beam),faces=surfaceFaces(beam);
  assert.equal(faces.length,2);
  assert.ok(faces[0].every(p=>p[1]<=1e-14));
  assert.ok(faces[1].every(p=>p[1]>=-1e-14));
  // Independently intersect the trailing edge x-y=sqrt(2) with y=0.
  for(const face of faces)near(Math.max(...face.filter(p=>Math.abs(p[1])<1e-14).map(p=>p[0])),Math.SQRT2);
  assert.deepEqual(beam,original);
});
test('root join follows rigid rotation and translation, including Earth views',()=>{
  const beam=swept(),transform=p=>[5-p[2],-7+p[0],12-p[1]];
  const moved={...beam,axis:beam.axis.map(s=>s.map(transform)),quads:beam.quads.map(q=>q.map(transform))};
  const expected=surfaceFaces(beam).map(q=>q.map(transform)),actual=surfaceFaces(moved);
  actual.flat(2).forEach((v,i)=>near(v,expected.flat(2)[i]));
});
test('unmarked geometry, bodies and open roots retain their supplied faces',()=>{
  const beam=swept();
  for(const b of [{...beam,mirror_join:undefined},{...beam,lifting:false},
    {...beam,axis:[beam.axis[0],[[0,.2,0],[1,1,0]]]}])assert.equal(surfaceFaces(b),b.quads);
});
test('vortex overlay preserves each horseshoe leg and applies the same Earth transform',()=>{
  const data={bound_segments:[[[1,0,0],[2,1,0]],[[3,1,0],[4,2,0]]],wake_direction:[.8,0,.6]},saved=structuredClone(data);
  const frame={body_to_earth:[[0,-1,0],[1,0,0],[0,0,1]],position_earth:[10,20,30]};
  const [bound,wake]=vortexOverlay(data,5,frame);
  assert.equal(bound.segments.length,2);assert.equal(wake.segments.length,4);
  assert.deepEqual(bound.segments[0],[[10,21,30],[9,22,30]]);
  assert.deepEqual(wake.segments[0],[[10,21,30],[10,25,33]]);
  assert.ok(bound.overlay&&wake.overlay);assert.deepEqual(data,saved);
});

test('streamwise display uses separate quads and preserves both saved representations',()=>{
  const beam=swept();beam.streamwise_quads=beam.quads.map((q,i)=>q.map((p,j)=>j<2?p:[p[0],i?1:-1,p[2]]));
  const saved=structuredClone(beam);
  assert.equal(surfaceFaces(beam,{streamwise:true}),beam.streamwise_quads);
  assert.notDeepEqual(surfaceFaces(beam),beam.streamwise_quads);
  assert.deepEqual(beam,saved);
  const old=swept();assert.deepEqual(surfaceFaces(old,{streamwise:true}),surfaceFaces(old));
});

test('time, modal and Bode geometry transform projected chords with the aircraft',()=>{
  const beam=swept();beam.streamwise_quads=structuredClone(beam.quads);
  const frame={body_to_earth:[[0,-1,0],[1,0,0],[0,0,1]],position_earth:[10,20,30]};
  const snapshot={frame,ground_plane:null};
  const earth=trajectoryGeometry([beam],[],snapshot,true).beams[0];
  assert.deepEqual(earth.streamwise_quads[0][0],[11,21,30]);
  const fill=(v,n)=>Array.isArray(v)?v.map(x=>fill(x,n)):n;
  const delta={quads:{real:fill(beam.quads,0),imag:fill(beam.quads,0)},
    axis:{real:fill(beam.axis,0),imag:fill(beam.axis,0)},
    streamwise_quads:{real:fill(beam.quads,2),imag:fill(beam.quads,3)}};
  const result={base:{geometry:[beam],attachments:[],modal_base:frame},
    modes:[{output:{geometry:[delta],earth_geometry:[delta],attachments:[],earth_attachments:[]}}]};
  const saved=structuredClone(result);
  // Bode uses the same physical-amplitude geometry path with normalize=false.
  const view=modeGeometry(result,0,Math.PI/2,.1,true,false);
  view.beams[0].streamwise_quads[0][0].forEach((v,i)=>near(v,[10.7,20.7,29.7][i]));
  assert.deepEqual(result,saved);
  delete delta.streamwise_quads;
  assert.equal(modeGeometry(result,0,0,1,false,false).beams[0].streamwise_quads,undefined);
});
