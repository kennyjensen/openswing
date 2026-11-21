import test from 'node:test';
import assert from 'node:assert/strict';
import {distributionHistory,envelopeCSV,historyCSV,sectionColumns,stripColumns,shoulderColumns,atPath} from '../web/distribution-history.js';
const freeze=o=>{if(o&&typeof o==='object'){Object.values(o).forEach(freeze);Object.freeze(o);}return o;};
const row=(t,value)=>({beam:1,t,t0:t-.25,t1:t+.25,strain:[0,value,0]});
const snap=(time,values)=>({time,step:.1,forcing_side:'right',elements:values.map((v,i)=>row(i+.5,v))});
const extract=r=>r.strain?.[1];
const parse=text=>text.trimEnd().split('\n').map(line=>[...line.matchAll(/"((?:[^"]|"")*)"(?:,|$)/g)].map(m=>m[1].replaceAll('""','"')));

test('signed sampled extrema retain earliest tied snapshot and event side without mutating states',()=>{
  const states=freeze([snap(0,[2,-3]),{...snap(.1,[-4,1]),forcing_side:'left'},snap(.1,[-4,5])]);
  const h=distributionHistory(states,'elements',1,extract);
  assert.equal(h.stations[0].min.value,-4);assert.equal(h.stations[0].min.index,1);assert.equal(h.stations[0].min.side,'left');
  assert.equal(h.stations[1].max.value,5);assert.equal(h.peak.index,2);assert.equal(h.peak.station,1);
  const csv=parse(envelopeCSV(h,1,'strain.1','dimensionless'));
  assert.equal(csv.length,3);assert.deepEqual(csv[1].slice(9),['-4','1','0.1','0.1','left','2','0','0','0.1','right']);
});
test('envelopes describe sampled analytic waves, not a continuous-time bound',()=>{
  const times=[0,.25,.5,.75],stations=[.1,.4,.9];
  const states=freeze(times.map(time=>({time,elements:stations.map(t=>row(t,2*t*Math.sin(2*Math.PI*(time+.05))))})));
  const h=distributionHistory(states,'elements',1,extract);
  for(let j=0;j<stations.length;j++){
    assert.equal(h.stations[j].max.index,1);assert.equal(h.stations[j].min.index,3);
    assert.ok(Math.abs(h.stations[j].max.value-2*stations[j]*Math.cos(Math.PI/10))<1e-14);
    assert.ok(h.stations[j].max.value<2*stations[j]);
  }
});
test('null, absent, nonfinite and nonnumeric values remain gaps, including all-missing stations',()=>{
  const states=[snap(0,[null,undefined,0]),snap(1,[Infinity,NaN,-0]),snap(2,['2',null,3])];
  const h=distributionHistory(states,'elements',1,extract);
  assert.equal(h.missing,6);assert.equal(h.stations[0].count,0);assert.equal(h.stations[1].max,null);assert.equal(h.stations[2].min.value,0);
  const csv=parse(envelopeCSV(h,1,'strain.1','dimensionless'));assert.deepEqual(csv[1].slice(9),Array(10).fill(''));
});
test('coincident stations remain distinct and incompatible material grids are rejected',()=>{
  const a={time:0,elements:[row(1,2),row(1,-2)]},b={time:1,elements:[row(1,3),row(1,-5)]};
  const h=distributionHistory(freeze([a,b]),'elements',1,extract);
  assert.equal(h.stations.length,2);assert.equal(h.stations[0].min.value,2);assert.equal(h.stations[1].min.value,-5);
  const changed=structuredClone(b);changed.elements[1].t0+=.01;
  assert.throws(()=>distributionHistory([a,changed],'elements',1,extract),/different material station grid/);
  assert.throws(()=>distributionHistory([a,{time:1,elements:[row(1,0)]}],'elements',1,extract),/different material station grid/);
  assert.throws(()=>distributionHistory([{time:NaN,elements:[]}],'elements',1,extract),/finite time/);
});
test('aerodynamic density uses each state’s current length and preserves force impulses separately',()=>{
  const states=freeze([1,2,4].map((length,time)=>({time,strips:[{beam:3,t:1,length,force:[0,0,8]}],body_shoulders:[{beam:3,t:1,force:[0,0,-5*time]}]})));
  const h=distributionHistory(states,'strips',3,r=>r.force[2]/r.length);
  assert.equal(h.stations[0].min.value,2);assert.equal(h.stations[0].min.index,2);assert.equal(h.stations[0].max.value,8);
  const impulse=distributionHistory(states,'body_shoulders',3,r=>r.force[2]);assert.equal(impulse.peak.value,-10);
});
test('snapshot-specific physical stress conversion does not turn missing metadata into zero',()=>{
  const states=[2,3,null].map((factor,time)=>({time,structure:{factor},elements:[{...row(.5,0),stress:4}]}));
  const h=distributionHistory(states,'elements',1,(r,s)=>s.structure.factor===null?null:r.stress*s.structure.factor);
  assert.equal(h.stations[0].min.value,8);assert.equal(h.stations[0].max.value,12);assert.equal(h.stations[0].count,2);
});
test('history tables include every state and beam with raw quantities, ordinals and event metadata',()=>{
  const states=[snap(0,[.002,-.001]),snap(.1,[.004,-.003])];
  states[0].elements.push({...row(1,.008),beam:-2});states[1].elements.push({...row(1,.016),beam:-2});
  states[0].elements[0].shell={shear_status:'missing, "shell"'};
  const lines=parse(historyCSV(freeze(states),'elements',sectionColumns));
  assert.equal(lines.length,7);assert.equal(lines[1][0],'0');assert.equal(lines[4][0],'1');
  const col=name=>lines[0].indexOf(name);
  assert.equal(lines[2][col('beam_station_index (0-based)')],'1');assert.equal(lines[3][col('beam_station_index (0-based)')],'0');
  assert.equal(lines[3][col('beam')],'-2');assert.equal(lines[6][col('strain_s')],'0.016');
  assert.equal(lines[1][col('shear_status')],'missing, "shell"');assert.equal(lines[2][col('torsional_shear_stress [F/L^2]')],'');
  for(const [field,columns] of [['strips',stripColumns],['body_shoulders',shoulderColumns]]){
    const data=parse(historyCSV([{time:2,[field]:[{beam:1,t:.5,force:[1,2,3]}]}],field,columns));
    assert.equal(data[1][data[0].indexOf(field==='strips'?'F_z [F]':'Fz [F]')],'3');
  }
  assert.equal(atPath({},'shell.axial_strain'),undefined);
});
