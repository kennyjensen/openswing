import {test} from 'node:test';
import assert from 'node:assert/strict';
import {structuralDerivativeOptions,structuralDerivativeSeries,structuralDerivativeCSV} from '../web/derivative-data.js';

const result={parameters:[{name:'alpha',unit:'rad'},{name:'power.1',unit:'file engine setting'}],
  node_order:[{beam:3,t:0},{beam:7,t:0}],
  element_order:[{beam:3,t:.5,t0:0,t1:1},{beam:7,t:.5,t0:0,t1:1},{beam:3,t:1.5,t0:1,t1:2}],
  section_output_fields:{shell_shear_stress:{label:'Signed torsional shear stress',unit:'input F / L^2',components:null},
    section_strain:{label:'Mechanical strain',unit:'dimensionless',components:['c','s','n']}},
  matrices:{positions:[[[1,2],[3,4],[5,6]],[[11,12],[13,14],[15,16]]],
    shell_shear_stress:[[null,null],[999,888],[250,500]],section_strain:[[[1,2],[3,4],[5,6]],[[9,9],[9,9],[9,9]],[[7,8],[9,10],[11,12]]]}};

test('beam filtering keeps material station and scalar/vector parameter columns aligned',()=>{
  const before=JSON.stringify(result);
  const stress=structuralDerivativeSeries(result,3,'shell_shear_stress',1);
  assert.deepEqual(stress.points.map(p=>p.value),[null,500]);
  assert.deepEqual(stress.points.map(p=>[p.t0,p.t,p.t1]),[[0,.5,1],[1,1.5,2]]);
  assert.deepEqual(structuralDerivativeSeries(result,3,'section_strain.1',0).points.map(p=>p.value),[3,9]);
  assert.deepEqual(structuralDerivativeSeries(result,7,'positions.2',1).points.map(p=>p.value),[16]);
  assert.equal(JSON.stringify(result),before);
});

test('distribution CSV retains all inputs, physical units, material locations and missing entries',()=>{
  const csv=structuralDerivativeCSV(structuralDerivativeSeries(result,3,'shell_shear_stress',0),result.parameters);
  const lines=csv.trim().split('\n');assert.equal(lines.length,3);
  assert.match(lines[0],/"alpha \/ \(rad\)","power.1 \/ \(file engine setting\)"/);
  assert.match(lines[1],/"input F \/ L\^2","material midpoint","",""$/);
  assert.match(lines[2],/"250","500"$/);assert.doesNotMatch(csv,/999|888|null|undefined/);
});

test('older saved derivatives retain nodal fields without inventing section data',()=>{
  const old={...result,section_output_fields:undefined};
  assert.equal(structuralDerivativeOptions(old).length,6);
  assert.equal(structuralDerivativeSeries(old,3,'shell_shear_stress',0),null);
  assert.deepEqual(structuralDerivativeSeries(old,3,'positions.2',0).points.map(p=>p.value),[5]);
});

test('source section plots and CSV retain their declared average and axes',()=>{
  const source=structuredClone(result);
  Object.assign(source.section_output_fields.section_strain,{sample_location:'element constitutive average',
    axes:'arithmetic average of endpoint c,s,n transforms; generally nonorthogonal'});
  const series=structuralDerivativeSeries(source,3,'section_strain.1',0);
  assert.equal(series.sampleLocation,'element constitutive average');
  assert.match(series.axes,/nonorthogonal/);
  const csv=structuralDerivativeCSV(series,source.parameters);
  assert.match(csv,/"element constitutive average"/);assert.doesNotMatch(csv,/material midpoint/);
  assert.deepEqual(series.points.map(p=>p.values),[[3,4],[9,10]]);
});
