// Execution held with the existing Node/browser test hold.
import test from 'node:test';
import assert from 'node:assert/strict';
import {structureExportRows,structureSampleDescription,structureMissingDescription} from '../web/structure-results.js';

test('CSV keeps distributed gravity on intervals and blanks endpoint rows',()=>{
  const result={structure:{strain_source:'source_discrete_constitutive'},elements:[{
    t:1.5,t0:1,t1:2,distributed_gravity:{normal:-3,force_per_length:[0,0,-3],sample_location:'interval mean load; physical midpoint normal'},
    endpoint_traces:[{t:1,side:'right',force_local:[0,0,2]},{t:2,side:'left',force_local:[0,0,-1]}],
  }]};
  const before=structuredClone(result),rows=structureExportRows(result);
  assert.equal(rows.length,3);assert.equal(rows[0].distributed_gravity.normal,-3);
  for(const row of rows.slice(1))assert.equal(row.distributed_gravity,undefined);
  assert.deepEqual(result,before);
  assert.deepEqual(rows.slice(1).map(r=>r.force_local),[[0,0,2],[0,0,-1]]);
});

test('normal-load caption distinguishes force per length from constitutive components',()=>{
  const text=structureSampleDescription({strain_source:'source_discrete_constitutive'},4,'distributed_gravity.normal');
  assert.match(text,/per material length/);assert.match(text,/physical midpoint normal/);
  assert.match(text,/Concentrated weights and support reactions are separate/);
  assert.doesNotMatch(text,/constitutive estimates/);
});

test('older or unsupported results report unavailable loads instead of missing shell data',()=>{
  const text=structureMissingDescription('distributed_gravity.normal',3,3);
  assert.match(text,/3 of 3 samples unavailable/);assert.match(text,/Other policies and older saved results/);
  assert.doesNotMatch(text,/Cshell|Atshell/);
  assert.equal(structureMissingDescription('distributed_gravity.normal',0,3),'');
  assert.match(structureMissingDescription('shell.shear_stress',1,3),/Atshell/);
});
