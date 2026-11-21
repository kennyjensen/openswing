import {test} from 'node:test';
import assert from 'node:assert/strict';
import {shareTimeHistoryMetadata} from '../web/time-history-metadata.js';
import {checkpointAt} from '../web/time-checkpoint.js';

function segment(offset=0,forcing='time +Az\n'+Array.from({length:64},(_,i)=>`${i/100} ${i/1000}\n`).join('')){
  const setup={forcing,condition:{speed:10,alpha:9,reference:[0,-0,0]},extension:{enabled:false,label:'literal metadata'}};
  const context={method:{order:2},setup:structuredClone(setup)};
  return {analysis:'time_response',restart_context:context,snapshots:[0,1].map(i=>({time:offset+i,residual:0,
    restart_context:structuredClone(context),restart:{state:{time:offset+i,value:i},older:i?{time:offset,value:0}:null,
      options:{order:2},next_step:1,forcing_side:i?'left':'right',
      accepted_method:{kind:'bdf',previous:{time:offset+i-1},previous2:{time:offset+i-2},coefficients:[1.5,-2,.5],
        accepted_inputs:{setup:structuredClone(setup),method:{order:2},opaque:{references:[['literal',99]],values:['not a storage format']}}}}}))};
}

test('within and across segments share exact metadata without changing JSON or the inputs',()=>{
  const raw=segment(),copy=structuredClone(raw),first=shareTimeHistoryMetadata(raw);
  assert.deepStrictEqual(raw,copy);assert.deepStrictEqual(first,raw);assert.equal(JSON.stringify(first),JSON.stringify(raw));
  const a=first.snapshots[0].restart.accepted_method.accepted_inputs;
  assert.strictEqual(a,first.snapshots[1].restart.accepted_method.accepted_inputs);
  assert.strictEqual(a.setup,first.restart_context.setup);
  assert.strictEqual(first.snapshots[0].restart_context,first.restart_context);
  const nextRaw=segment(2),next=shareTimeHistoryMetadata(nextRaw,first);
  assert.strictEqual(next.restart_context,first.restart_context);
  assert.strictEqual(next.snapshots[0].restart.accepted_method.accepted_inputs,a);
  assert.deepStrictEqual(next,nextRaw);assert.equal(JSON.stringify(next),JSON.stringify(nextRaw));
  assert.notStrictEqual(next.snapshots[0].restart.state,first.snapshots[0].restart.state);
});

test('branching, input changes, historical method details and key order stay distinct',()=>{
  const first=shareTimeHistoryMetadata(segment());
  const raw=segment(2,'time +Az\n0 1\n1 -1\n'+'# retained text\n'.repeat(32));
  const prior=raw.snapshots[0].restart.accepted_method;
  prior.kind='historical-radau';prior.internal_stage={time:2.5,state:[1,2,3]};
  const next=shareTimeHistoryMetadata(raw,first);
  assert.notStrictEqual(next.restart_context,first.restart_context);
  assert.deepStrictEqual(next,raw);assert.strictEqual(next.snapshots[0].restart.accepted_method.internal_stage,prior.internal_stage);
  const reordered=segment(4);reordered.restart_context={setup:reordered.restart_context.setup,method:reordered.restart_context.method};
  const other=shareTimeHistoryMetadata(reordered,first);
  assert.notStrictEqual(other.restart_context,first.restart_context);
  assert.equal(JSON.stringify(other),JSON.stringify(reordered));
});

test('signed zero is not merged into positive zero, and values are never rounded',()=>{
  const first=shareTimeHistoryMetadata(segment());
  const raw=segment(2);raw.restart_context.setup.condition.reference[1]=0;
  raw.snapshots[0].restart.accepted_method.accepted_inputs.setup.condition.speed=10+Number.EPSILON*8;
  const next=shareTimeHistoryMetadata(raw,first);
  assert.notStrictEqual(next.restart_context,first.restart_context);
  assert.ok(Object.is(first.restart_context.setup.condition.reference[1],-0));
  assert.ok(Object.is(next.restart_context.setup.condition.reference[1],0));
  assert.equal(next.snapshots[0].restart.accepted_method.accepted_inputs.setup.condition.speed,10+Number.EPSILON*8);
  assert.deepStrictEqual(next,raw);
});

test('standalone checkpoint extraction still owns independent metadata',()=>{
  const result=shareTimeHistoryMetadata(segment()),before=structuredClone(result),saved=checkpointAt(result,1);
  saved.context.setup.condition.speed=999;
  saved.accepted_method.accepted_inputs.setup.condition.reference[0]=777;
  saved.state.value=555;
  assert.deepStrictEqual(result,before);
  assert.equal(saved.accepted_method.accepted_inputs.setup.condition.speed,10);
  assert.equal(saved.context.setup.condition.reference[0],0);
});

test('legacy parent results can seed sharing; independent new histories have independent pools',()=>{
  const old=segment(),result=shareTimeHistoryMetadata(segment(2),old);
  assert.strictEqual(result.restart_context.setup,old.restart_context.setup);
  const independent=shareTimeHistoryMetadata(segment(2));
  assert.notStrictEqual(independent.restart_context,result.restart_context);
  for(const value of [null,undefined,{},[],{analysis:'rigid_steady'}, {analysis:'time_response',snapshots:[]}])assert.strictEqual(shareTimeHistoryMetadata(value),value);
});

test('opaque unsupported values and cycles are left untouched instead of coerced',()=>{
  for(const edit of [s=>s.extra=undefined,s=>s.extra=NaN,s=>s.extra=Infinity,
    s=>s.extra=()=>0,s=>s.extra=Array(3),s=>s.extra=s,
    s=>Object.defineProperty(s,'hidden',{value:2}),
    s=>s.extra=Object.assign(Object.create(null),{x:1}),
    s=>Object.defineProperty(s,'getter',{get(){throw Error('Do not evaluate');},enumerable:true})]){
    const raw=segment();edit(raw.restart_context);
    const shared=shareTimeHistoryMetadata(raw);
    assert.strictEqual(shared.restart_context,raw.restart_context);
  }
});

test('bounded cache eviction never drops a metadata field or alters a prior history',()=>{
  let previous=shareTimeHistoryMetadata(segment(0,'a'.repeat(800000))),original=previous;
  for(let i=1;i<=6;i++){
    const raw=segment(i,String(i).repeat(800000)),next=shareTimeHistoryMetadata(raw,previous);
    assert.deepStrictEqual(next,raw);previous=next;
  }
  assert.equal(original.restart_context.setup.forcing,'a'.repeat(800000));
  const huge=segment(9,'x'.repeat(4*1024*1024+1)),large=shareTimeHistoryMetadata(huge,previous);
  assert.strictEqual(large.restart_context,huge.restart_context);
  assert.deepStrictEqual(large,huge);
});
