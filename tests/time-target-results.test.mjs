import test from 'node:test';
import assert from 'node:assert/strict';
import {actuatorHistoryQuantities,actuatorHistoryValue,forcingHistoryValue,timeInitializationSummary} from '../web/time-target-results.js';

test('history display keys bind actuator and target independently of residual row order',()=>{
  const rows=[{variable:'power.1',quantity:'velocity_earth.y'},{variable:'control.2',quantity:'rates.x'}];
  const quantities=actuatorHistoryQuantities(rows);
  assert.equal(quantities.length,6);
  assert.equal(quantities[0][1],'Target velocity_earth.y · E1');
  assert.equal(quantities[0][2],'input L/T');
  assert.equal(quantities[3][2],'rad/input T');
  const snapshot={operating_constraints:[
    {variable:'acceleration.y',quantity:'force.y',target:0,actual:0,normalized_residual:0},
    {variable:'control.2',quantity:'rates.x',target:Math.PI/2,actual:Math.PI/2,normalized_residual:0},
    {variable:'power.1',quantity:'velocity_earth.y',target:.008,actual:.008000000001,normalized_residual:1e-12},
  ]};
  assert.deepEqual(quantities.map(q=>actuatorHistoryValue(snapshot,q[0])),[.008,.008000000001,1e-12,Math.PI/2,Math.PI/2,0]);
  assert.equal(actuatorHistoryValue({operating_constraints:[]},quantities[0][0]),null);
  assert.equal(actuatorHistoryValue({},quantities[0][0]),null);
  assert.equal(actuatorHistoryValue({operating_constraints:[{...snapshot.operating_constraints[2],actual:Infinity}]},quantities[1][0]),null);
});
test('periodic display retains achieved principal angle and reported residual instead of subtracting a turn',()=>{
  const quantities=actuatorHistoryQuantities([{variable:'power.1',quantity:'attitude.heading'}]);
  const snapshot={operating_constraints:[{variable:'power.1',quantity:'attitude.heading',target:180,actual:-180,normalized_residual:0}]};
  assert.deepEqual(quantities.map(q=>actuatorHistoryValue(snapshot,q[0])),[180,-180,0]);
  assert.equal(quantities[2][2],'dimensionless');
  assert.deepEqual(actuatorHistoryQuantities([{variable:'power.1',quantity:'unknown.future'}]),[]);
});
test('cold, saved launch and checkpoint histories receive source-specific wording',()=>{
  const cold={initialization:{source:'cold inverse-history equilibrium'},snapshots:[{initial_phase:'cold_inverse_history'}]};
  const label=timeInitializationSummary(cold);
  assert.match(label,/Cold inverse-history initialization/);assert.match(label,/frame state.*held/);assert.doesNotMatch(label,/Saved-equilibrium launch/);
  assert.equal(timeInitializationSummary({snapshots:cold.snapshots}),label);
  assert.match(timeInitializationSummary({initialization:{source:'saved steady equilibrium'}}),/Saved-equilibrium launch.*after the initial snapshot/);
  assert.match(timeInitializationSummary({snapshots:[{initial_phase:'saved_equilibrium_disturbance_before_time_inputs'}]}),/Saved-equilibrium launch/);
  assert.match(timeInitializationSummary({...cold,snapshots:[{initial_phase:'checkpoint_before_next_inputs'}]}),/^Checkpoint continuation/);
  assert.equal(timeInitializationSummary({initialization:{source:'future initializer'}}),'Initialization: future initializer.');
  assert.match(timeInitializationSummary({...cold,request:{action:'resume_time'}}),/^Checkpoint continuation/);
  assert.equal(timeInitializationSummary(null),'');assert.equal(timeInitializationSummary({}),'');
});

test('explicit Earth-vector input series read literal dotted forcing labels',()=>{
  const snapshot={forcing_values:{'velocity_earth.y':.008,'rates_earth.z':.2,'Wx':90,'A[1]':5}};
  assert.equal(forcingHistoryValue(snapshot,'forcing_values.velocity_earth.y'),.008);
  assert.equal(forcingHistoryValue(snapshot,'forcing_values.rates_earth.z'),.2);
  assert.equal(forcingHistoryValue(snapshot,'forcing_values.Wx'),90);
  assert.equal(forcingHistoryValue(snapshot,'forcing_values.A[1]'),5);
  assert.equal(forcingHistoryValue(snapshot,'forcing_values.acceleration_earth.x'),null);
  assert.equal(forcingHistoryValue({},'forcing_values.velocity_earth.y'),null);
});
