import test from 'node:test';
import assert from 'node:assert/strict';
import {weightRecords,editWeight,deleteWeight,appendWeight,massDisplayUnits} from '../web/mass-data.js';

const source='Name\nAircraft\nEnd\nWeight\n# Nbeam t X Y Z Mg\n* 2 3 4 5 9.81\n+ 1 0 0 0 2\n! pilot\n  5, 2.0, 1D0, -2, 0, 10   ! keep pilot note\n! payload\n  5 3 1 2 3 20\nEnd\nBeam 5\nWeight\nt x\n0 0\n10 10\nEnd\n';
test('weight editing reads scaled optional records and keeps names, comments and unrelated source',()=>{
  const {records}=weightRecords(source);assert.equal(records.length,2);assert.equal(records[0].label,'pilot');
  assert.deepEqual(records[0].values.slice(0,6),[5,5,3,-8,0,100.10000000000001]);
  assert.equal(records[0].values[11],0);
  const edited=editWeight(source,0,{5:198.2}),rows=weightRecords(edited).records;
  assert.ok(Math.abs(rows[0].values[5]-198.2)<1e-12);assert.deepEqual(rows[1].values,records[1].values);
  const changes=edited.split('\n').filter((line,i)=>line!==source.split('\n')[i]);assert.equal(changes.length,1);
  assert.match(changes[0],/^  5, 2.0, 1D0, -2, 0,/);assert.match(changes[0],/! keep pilot note$/);
  assert.equal(editWeight(source,0,{5:records[0].values[5]}),source);
});
test('optional inertias preserve omitted zero values even under adders',()=>{
  const s='Weight\n+ 0 0 0 0 0 4 5 6 7 8 9\n2 0 0 0 0 10 ! mass\nEnd\n';
  const edited=editWeight(s,0,{11:30}),row=weightRecords(edited).records[0];
  assert.equal(row.values[11],30);assert.deepEqual(row.values.slice(6,11),[0,0,0,0,0]);assert.match(edited,/! mass/);
});
test('zero multipliers are isolated around the edited row without changing the next mass',()=>{
  const s='Weight\r\n* 1 1 1 1 0\r\n+ 0 0 0 0 5\r\n2 0 0 0 0 10 ! fixed\r\n2 1 0 0 0 20\r\nEnd\r\n';
  const edited=editWeight(s,0,{5:7}),rows=weightRecords(edited).records;
  assert.equal(rows[0].values[5],7);assert.equal(rows[1].values[5],5);assert.match(edited,/! fixed\r\n/);
  assert.ok(edited.includes('2 1 0 0 0 20\r\n'));assert.equal(edited.replaceAll('\r\n','').includes('\n'),false);
});
test('delete retains annotations and add keeps prior Weight blocks byte for byte',()=>{
  const deleted=deleteWeight(source,0);assert.match(deleted,/! pilot/);assert.match(deleted,/! keep pilot note/);
  assert.equal(weightRecords(deleted).records.length,1);
  const added=appendWeight(source,{beam:5,t:1,position:[2,3,4]});assert.ok(added.startsWith(source));
  const row=weightRecords(added).records.at(-1);assert.deepEqual(row.values.slice(0,6),[5,1,2,3,4,0]);
  assert.equal(weightRecords(deleteWeight(added,2)).records.length,2);
});
test('mass and inertia convert from force-weighted ASW values to SI without assuming pounds are mass',()=>{
  const units=massDisplayUnits({constants:[32.18],si:{M:14.5939029372,L:.3048}});
  assert.equal(units.massLabel,'kg');assert.equal(units.lengthLabel,'m');
  assert.ok(Math.abs(165*units.factor(5)-74.82889946047234)<1e-10);
  assert.equal(units.factor(2),.3048);assert.equal(units.factor(1),1);
  assert.ok(Math.abs(units.factor(11)-14.5939029372*.3048**2/32.18)<1e-12);
  const input=massDisplayUnits({constants:[10],si:null});assert.equal(input.factor(5),.1);assert.equal(input.massLabel,'input M');
});
test('Fortran exponent spellings, negative static weights, and empty files are retained',()=>{
  const s='Weight\n1 2.1-6 1D+1 0 0 -6.2832+00\nEnd';
  const row=weightRecords(s).records[0];assert.equal(row.values[1],2.1e-6);assert.equal(row.values[5],-6.2832);
  assert.match(editWeight(s,0,{5:3}),/2.1-6 1D\+1 0 0  +3/);
  assert.equal(weightRecords('Name\nWeight\nEnd\n').records.length,0);
  assert.throws(()=>editWeight(s,0,{5:NaN}));assert.throws(()=>editWeight(s,0,{0:1.5}));
});
