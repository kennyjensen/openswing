import test from 'node:test';
import assert from 'node:assert/strict';
import {parseActuatorTargets,actuatorTargets} from '../web/time-actuators.js';

test('actuator targets convert angular units and preserve raw force and lift targets',()=>{
  const model={controls:[2],engine_controls:[{index:1},{index:3}]};
  assert.deepEqual(parseActuatorTargets('# inverse targets\ne1 ax .2\nF2 My -3e2\nE3 Gz 90 ! torque',model),[
    {variable:'power.1',quantity:'acceleration.x',target:.2},
    {variable:'control.2',quantity:'moment.y',target:-300},
    {variable:'power.3',quantity:'angular_acceleration.z',target:Math.PI/2},
  ]);
  assert.deepEqual(parseActuatorTargets('F2 L 20\nE1 Ar -.4',model),[
    {variable:'control.2',quantity:'lift',target:20},{variable:'power.1',quantity:'radial_acceleration',target:-.4},
  ]);
  assert.deepEqual(parseActuatorTargets(''),[]);
});

test('inverse targets reject invalid values, duplicate ownership and undeclared actuators',()=>{
  for(const text of ['E1 Ax NaN','E1 Ax Infinity','E1 Ax 1e999','E1 Ax 0x10','E0 Ax 0','E1 UX 10','E1 Ax 0 extra','E1 Ax 0\nE1 Ay 0','E1 Ax 0\nE2 Ax 0'])
    assert.throws(()=>parseActuatorTargets(text));
  assert.throws(()=>parseActuatorTargets('F2 L 0',{controls:[1],engine_controls:[]}),/not declared/);
});

// The frozen Python catalog is an independently captured authoritative schema;
// this catches omitted labels, wrong canonical units and accidental new aliases.
const catalog=JSON.parse(await (await import('node:fs/promises')).readFile(new URL('./fixtures/time-history-catalog.json',import.meta.url),'utf8'));
test('all staged kernel history labels preserve quantity and canonical units',()=>{
  assert.equal(catalog.length,25);
  for(const entry of catalog){
    const value=entry.label==='V'?12.5:entry.periodic?-179.5:.25;
    const [row]=parseActuatorTargets(`E7 ${entry.label.toLowerCase()} ${value}`,{controls:[],engine_controls:[7]});
    assert.deepEqual(row,{variable:'power.7',quantity:entry.quantity,target:value*entry.factor});
    const metadata=actuatorTargets.find(x=>x.quantity===entry.quantity);
    assert.equal(metadata.table_unit,entry.table_unit,entry.label);
    assert.equal(metadata.target_unit,entry.target_unit,entry.label);
    assert.equal(metadata.semantics,entry.semantics,entry.label);
  }
});
test('body angular labels convert degrees; Earth vector extensions stay radians',()=>{
  assert.deepEqual(parseActuatorTargets('E1 Wx 180\nE2 rates_earth.x 3.141592653589793\nE3 Gz 90\nE4 angular_acceleration_earth.z .5'),[
    {variable:'power.1',quantity:'rates.x',target:Math.PI},
    {variable:'power.2',quantity:'rates_earth.x',target:Math.PI},
    {variable:'power.3',quantity:'angular_acceleration.z',target:Math.PI/2},
    {variable:'power.4',quantity:'angular_acceleration_earth.z',target:.5},
  ]);
  assert.deepEqual(parseActuatorTargets('F2 Ez -90\nE1 RX -4\nE3 velocity_earth.x -10'),[
    {variable:'control.2',quantity:'attitude.heading',target:-90},
    {variable:'power.1',quantity:'position_earth.x',target:-4},
    {variable:'power.3',quantity:'velocity_earth.x',target:-10},
  ]);
});
test('principal angle and airspeed domains match kernel boundaries without changing values',()=>{
  for(const label of ['A','Ex','Ez']){
    for(const value of [-180,180])assert.equal(parseActuatorTargets(`E1 ${label} ${value}`)[0].target,value);
    for(const value of [-180.0001,180.0001])assert.throws(()=>parseActuatorTargets(`E1 ${label} ${value}`),/principal range/);
  }
  for(const label of ['B','Ey','Ga']){
    for(const value of [-89.999,89.999])assert.equal(parseActuatorTargets(`E1 ${label} ${value}`)[0].target,value);
    for(const value of [-90,90,180])assert.throws(()=>parseActuatorTargets(`E1 ${label} ${value}`),/nonsingular range/);
  }
  for(const value of [0,-1,-0])assert.throws(()=>parseActuatorTargets(`E1 V ${value}`),/positive/);
  assert.equal(parseActuatorTargets('E1 V 1e-9')[0].target,1e-9);
});
test('history errors retain row location and reject ambiguous ownership and unsupported aliases',()=>{
  assert.throws(()=>parseActuatorTargets('# note\nE1 V 0'),/row 2: V.*positive/);
  assert.throws(()=>parseActuatorTargets('E1 RX 0\nE2 rx 1'),/row 2: each time actuator/);
  assert.throws(()=>parseActuatorTargets('E1 RX 0\nE1 RY 1'),/row 2: each time actuator/);
  for(const label of ['UX','UY','UZ','IAS','heading','attitude.heading','alpha','V[1]','__proto__','constructor'])
    assert.throws(()=>parseActuatorTargets(`E1 ${label} 1`),/unsupported target/);
  for(const value of ['NaN','Infinity','1e999','0x10','true'])assert.throws(()=>parseActuatorTargets(`E1 Wx ${value}`),/finite value/);
  assert.throws(()=>parseActuatorTargets('F2 RX 0',{controls:[1],engine_controls:[]}),/not declared/);
});
