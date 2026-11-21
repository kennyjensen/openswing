// Reassess retained worker output; never start a browser or a solver.
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {gunzipSync} from 'node:zlib';
import {equalPhysical} from './isae_time_browser_compare.mjs';

const base='artifacts/isae/ua-time-source-mechanics-20261102/browser';
const prior='artifacts/isae/ua1-stall-20261102-r1/n160-part001/trajectory.json.gz';
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const read=async name=>JSON.parse(await readFile(name,'utf8'));
const plan=await read(base+'/plan.json');
assert.equal((await read(base+'/original-execution.json')).exit_code,1);
assert.match((await read(base+'/failure.json')).message,/deep-equal/);
const inputs={};
for(const name of ['plan.json','original-execution.json','failure.json','failed-driver.mjs','warmup.json',
    'part0.json.gz','part1.json.gz','checkpoint0.json'])inputs[base+'/'+name]=hash(await readFile(base+'/'+name));
const targets=await readFile(prior);assert.equal(hash(targets),plan.target_sha256);inputs[prior]=hash(targets);
const expected=JSON.parse(gunzipSync(targets)).snapshots.slice(0,17);
for(const [name,value] of Object.entries(plan.module_sha256)){
  assert.equal(hash(await readFile('openswing/'+name)),value);
  assert.equal(hash(await readFile('dist/kernel/'+name)),value);
}
assert.equal(hash(await readFile('dist'+plan.worker_url)),plan.worker_sha256);
const scales={force:.5*1.225*100*200000,moment:.5*1.225*100*200000**2,
  CL:1,CDp:1,circulation_rate:10,local_velocity:10,local_rates:10,time:1};
let previous=null,maxResidual=0;const differences={};
const flatten=value=>Array.isArray(value)?value.flat(Infinity):[value];
for(let part=0;part<2;part++){
  const raw=JSON.parse(gunzipSync(await readFile(`${base}/part${part}.json.gz`)));
  assert.equal(raw.converged,true);assert.equal(raw.accepted_steps,8);assert.equal(raw.rejected_steps,0);
  assert.equal(raw.snapshots.length,9);assert.deepEqual(raw.software_provenance.modules,plan.module_sha256);
  if(previous){
    for(const key of ['force','circulation_rate','frame'])equalPhysical(raw.snapshots[0][key],previous[key],key);
    equalPhysical(raw.snapshots[0].strips.map(s=>s.circulation),previous.strips.map(s=>s.circulation),'circulation');
  }
  for(let i=0;i<raw.snapshots.length;i++){
    const a=raw.snapshots[i],b=expected[part*8+i];
    assert.ok(Math.abs(a.time-b.time)<1e-12);assert.ok(a.residual<1e-10);
    maxResidual=Math.max(maxResidual,a.residual);
    if(i)assert.equal(a.order,2);
    for(const [key,scale] of Object.entries(scales)){
      const av=flatten(a[key]),bv=flatten(b[key]);assert.equal(av.length,bv.length);
      for(let j=0;j<av.length;j++){
        assert.ok(Number.isFinite(av[j])&&Number.isFinite(bv[j]));
        differences[key]=Math.max(differences[key]??0,Math.abs(av[j]-bv[j])/scale);
      }
    }
    assert.equal(a.strips.length,b.strips.length);
    for(let j=0;j<a.strips.length;j++)differences.circulation=Math.max(differences.circulation??0,
      Math.abs(a.strips[j].circulation-b.strips[j].circulation)/10);
    for(const key of ['position_earth','velocity_origin_body','body_to_earth','rates_body']){
      const av=flatten(a.frame[key]),bv=flatten(b.frame[key]);assert.equal(av.length,bv.length);
      for(let j=0;j<av.length;j++)differences['frame/'+key]=Math.max(differences['frame/'+key]??0,
        Math.abs(av[j]-bv[j])/Math.max(1,Math.abs(bv[j])));
    }
  }
  previous=raw.snapshots.at(-1);
}
const maxDifference=Math.max(...Object.values(differences));assert.ok(maxDifference<plan.physical_difference_limit);
const sources={};
for(const name of ['scripts/assess-source-time-mechanics-browser.mjs','scripts/isae_time_browser_compare.mjs',
    'tests/source-time-browser-join.test.mjs'])sources[name]=hash(await readFile(name));
const report={passed:true,numerical_reexecution:false,original_driver_exit_code:1,
  reason:'Exact finite numeric comparison treats signed zero as the same physical state; every nonzero value remains exact at the continuation join.',
  steps:16,unique_states:17,rejected_steps:0,maxResidual,maxDifference,differences,
  input_sha256:inputs,assessment_source_sha256:sources,module_sha256:plan.module_sha256,
  physical_difference_limit:plan.physical_difference_limit,registered_pass_count_change:0};
await writeFile(base+'/assessment.json',JSON.stringify(report,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({passed:true,steps:16,unique_states:17,maxDifference,maxResidual,numerical_reexecution:false}));
