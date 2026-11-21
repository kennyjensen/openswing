import test from 'node:test';
import assert from 'node:assert/strict';
import {linearValue,linearLoadingSamples,linearStructureSamples,linearShoulderSamples,spanRange} from '../web/linear-span.js';
import {modeGeometry,modeDisplayScale} from '../web/mode-results.js';
import {frequencyGeometry} from '../web/frequency-results.js';

const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-10,`${a} != ${b}`);
const complex=(real,imag=0)=>({real,imag});

test('linear span values include equilibrium and share the geometry phase convention',()=>{
  for(const [phase,expected] of [[0,11],[Math.PI/2,-3],[Math.PI,-1],[3*Math.PI/2,13]]){
    const v=linearValue(5,complex(3,4),{phase,scale:2});close(v.value,expected);
    assert.deepEqual([v.lower,v.upper],[-5,15]);
  }
  for(const delta of [null,complex(null),complex(1,NaN)])assert.equal(linearValue(5,delta,{phase:0,scale:1}).value,null);
  assert.equal(linearValue(null,complex(0),{phase:0,scale:1}).value,null);
  close(linearValue(5,complex(3,4),{phase:2,scale:0}).value,5);
});

test('strip response uses beam/station identity, unit conversion and the length derivative',()=>{
  const rows=[{beam:1,t:0,cl:1,force:[0,0,12],length:3,da_eff:.1},{beam:2,t:0,cl:5}],
    output={strips:[{beam:2,t:0,cl:complex(2)},{beam:1,t:0,cl:complex(3,4),force:complex([0,0,6],[0,0,3]),length:complex(.5,.25),da_eff:complex(.02,.01)}]},
    before=JSON.stringify({rows,output}),linear={output,phase:0,scale:2};
  assert.deepEqual(linearLoadingSamples(rows,linear,'cl').map(s=>s.value),[7,9]);
  close(linearLoadingSamples(rows,linear,'fz')[0].value,4+2*(6/3-12*.5/9));
  close(linearLoadingSamples(rows,linear,'da_eff')[0].value,.14*180/Math.PI);
  const r0=spanRange(linearLoadingSamples(rows,linear,'cl'));
  linear.phase=Math.PI/2;
  close(linearLoadingSamples(rows,linear,'cl')[0].value,-7);
  assert.deepEqual(spanRange(linearLoadingSamples(rows,linear,'cl')),r0);
  assert.equal(JSON.stringify({rows,output}),before);
  assert.equal(linearLoadingSamples(rows,{...linear,output:{strips:[]}},'cl')[0].value,null);
  const historical={output:{strips:[{beam:1,t:0,force:complex([0,0,6],[0,0,0])}]},phase:0,scale:1};
  assert.equal(linearLoadingSamples(rows,historical,'fz')[0].value,null);
});

test('signed section output and absolute bounds retain physical strain/stress semantics',()=>{
  const rows=[{beam:1,t:1,t0:0,t1:2,axial_strain_tension:0,curvature_change:[0,0,0],
    strain:[0,0,0],moment_axes:[1,2,3],shell:{c:2,n:3,axial_strain:0,axial_strain_bound:0,shear_stress:0}}];
  const output={sections:[{beam:1,t:1,axial_strain_tension:complex(.001),curvature_change:complex([.002,0,.003],[0,0,0]),
    strain:complex([0,.001,0],[0,.002,0]),shell_strain:complex(.001),shell_shear_stress:complex(4),moment_axes:complex([4,5,6],[1,2,3])}]};
  const before=JSON.stringify({rows,output}),state={output,phase:0,scale:1};
  const val=key=>linearStructureSamples(rows,state,key)[0];
  close(val('shell.axial_strain_bound').value,.013);
  close(val('shell.axial_strain').value,.001);
  close(val('moment_axes.1').value,7);
  close(linearStructureSamples(rows,state,'strain.1',1e6)[0].value,1000);
  const range=spanRange([val('shell.axial_strain_bound')]);
  state.phase=Math.PI;
  close(val('shell.axial_strain_bound').value,.013);
  close(val('shell.axial_strain').value,-.001);
  close(val('shell.shear_stress').value,-4);
  close(val('shell.shear_stress_abs').value,4);
  assert.deepEqual(spanRange([val('shell.axial_strain_bound')]),range);
  state.phase=Math.PI/2;close(val('shell.axial_strain_bound').value,0);
  const sample=val('strain.1');assert.equal(sample.t0,0);assert.equal(sample.t1,2);close(sample.value,-.002);
  assert.equal(val('distributed_gravity.normal').value,null);
  assert.equal(JSON.stringify({rows,output}),before);
});

test('shoulder impulses keep their material positions and full-cycle force limits',()=>{
  const rows=[{beam:2,t:3,force:[0,0,10]}],linear={phase:Math.PI/2,scale:2,output:{body_shoulders:[{beam:2,t:3,force:complex([0,0,3],[0,0,4])}]}};
  const [s]=linearShoulderSamples(rows,linear,2);assert.equal(s.t,3);close(s.value,2);assert.deepEqual(spanRange([s]),[0,20]);
});

test('span and aircraft use identical forced amplitude and body/Earth mode normalization',()=>{
  const shape=multiplier=>[{index:1,axis:complex([[[3*multiplier,0,0]]],[[[4*multiplier,0,0]]]),quads:complex([],[])}];
  const output={geometry:shape(1),earth_geometry:shape(2),attachments:[],earth_attachments:[],strips:[{beam:1,t:0,cl:complex(3,4)}]},
    base={geometry:[{index:1,axis:[[[1,0,0]]],quads:[]}],attachments:[],modal_base:{body_to_earth:[[1,0,0],[0,1,0],[0,0,1]],position_earth:[0,0,0]}},
    result={base,modes:[{output}],inputs:[{kind:'control'}],samples:[{responses:[{output}]}]},before=JSON.stringify(result);
  for(const phase of [0,Math.PI/2,Math.PI]){
    const forced=frequencyGeometry(result,0,0,phase,2);
    const c=linearLoadingSamples([{beam:1,t:0,cl:1}],{output,phase,scale:2},'cl')[0];
    close(forced.beams[0].axis[0][0][0],c.value);
    for(const earth of [false,true]){
      const mode=modeGeometry(result,0,phase,.1,earth),scale=modeDisplayScale(output,.1,earth);
      close(mode.scale,scale);close(scale,earth?.01:.02);
      const v=linearValue(0,complex(3,4),{phase,scale});
      close((mode.beams[0].axis[0][0][0]-1)/(earth?2:1),v.value);
    }
  }
  result.inputs[0].kind='initial';assert.equal(frequencyGeometry(result,0,0,0,1),null);result.inputs[0].kind='control';
  assert.equal(JSON.stringify(result),before);
});
