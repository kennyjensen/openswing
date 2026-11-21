import test from 'node:test';
import assert from 'node:assert/strict';
import {frameMotionRateCheck,yawMotionCheckText} from '../web/frequency-motion-check.js';

test('motion reconstruction removes translation and elastic deformation in a tilted frame',()=>{
  const c=Math.cos(.4),s=Math.sin(.4),R=[[c,0,s],[0,1,0],[-s,0,c]],omega=7;
  const points=[[4,2,1],[-3,5,0],[1,-4,3],[0,1,-5]],rotation=[[.03,-.05,.02],[-.04,.01,.07]];
  const transform=v=>R.map(row=>row.reduce((sum,a,k)=>sum+a*v[k],0));
  const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
  const elastic=rotation.map((_,part)=>points.map((p,i)=>p.map((v,j)=>(i+1)*(j+1)*.005*(part?-.5:1))));
  const world=rotation.map((rot,part)=>points.map((p,i)=>transform(elastic[part][i].map((v,j)=>v+cross(rot,p)[j])).map((v,j)=>v+(part+1)*(j+1))));
  const field=(r,i)=>({real:[r],imag:[i]});
  const output={geometry:[{index:7,quads:field(...elastic)}],earth_geometry:[{index:7,quads:field(...world)}]};
  const result={inputs:[{kind:'control'}],base:{modal_base:{kinematically_steady:true,attitude_rates_rad:[0,0,0],body_to_earth:R},geometry:[{index:7,quads:[points]}]}};
  const point={omega,responses:[{output}]},before=JSON.stringify({result,point});
  const check=frameMotionRateCheck(result,point);
  for(let i=0;i<3;i++){
    assert.ok(Math.abs(check.rates.real[i]+omega*rotation[1][i])<1e-13);
    assert.ok(Math.abs(check.rates.imag[i]-omega*rotation[0][i])<1e-13);
  }
  assert.ok(check.relativeDefect<1e-13);
  const plotted={real:-omega*rotation[1][2],imag:omega*rotation[0][2]};
  assert.match(yawMotionCheckText(result,point,0,plotted,'rad/T'),/Consistent complex rates/);
  assert.match(yawMotionCheckText(result,point,0,{real:plotted.imag,imag:plotted.real},'rad/T'),/complex rates differ/);
  assert.equal(JSON.stringify({result,point}),before);
  output.earth_geometry[0].quads.real[0][2][1]+=.5;
  assert.equal(frameMotionRateCheck(result,point),null);
  result.base.modal_base.kinematically_steady=false;
  assert.equal(frameMotionRateCheck(result,point),null);
});

test('initial spectra and incomplete or degenerate geometry are not reported as checks',()=>{
  const result={inputs:[{kind:'control'}],base:{modal_base:{kinematically_steady:true,attitude_rates_rad:[0,0,0],body_to_earth:[[1,0,0],[0,1,0],[0,0,1]]},geometry:[{index:1,axis:[[[0,0,0],[1,0,0],[2,0,0]]]}]}};
  const field={real:[[[0,0,0],[0,0,0],[0,0,0]]],imag:[[[0,0,0],[0,0,0],[0,0,0]]]};
  const point={omega:2,responses:[{output:{geometry:[{index:1,axis:field}],earth_geometry:[{index:1,axis:field}]}}]};
  assert.equal(frameMotionRateCheck(result,point),null);
  result.inputs[0].kind='initial';assert.equal(frameMotionRateCheck(result,point),null);
  assert.equal(frameMotionRateCheck(null,point),null);
  assert.equal(yawMotionCheckText(null,point,0,{real:0,imag:0},'rad/T'),'');
});
