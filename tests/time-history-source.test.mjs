import {test} from 'node:test';
import assert from 'node:assert/strict';
import {archiveTrajectory,timeHistory,archivedTimeHistory} from '../web/time-history-source.js';
import {timeHistoryEntry,indexedTimeQuantities} from '../web/time-history-index.js';
import {createHistorySelection} from '../web/time-history-selection.js';
import {createTimeHistoryWriter,openTimeHistoryArchive} from '../web/time-history-archive.js';
import {checkpointAt} from '../web/time-checkpoint.js';

const context={method:{order:2},setup:{forcing:'retained'}};
const snapshots=[
  {time:0,step:0,CL:-0,residual:1e-12,restart:{state:{time:0,vector:[1,-0,3]},older:null}},
  {time:.1,step:.1,CL:1,residual:2e-12,forcing_side:'left',restart:{state:{time:.1,vector:[2,-0,3]},older:{time:.03,internal:true}}},
  {time:.1,step:0,CL:2,residual:3e-12,input_transition:{side:'after'},restart_context:{...context,method:{order:5}},restart:{state:{time:.1,vector:[3,-0,3]},older:null}},
];
const metadata={analysis:'time_response',restart_context:context};
function fakeArchive(indexed=true){
  const reads=[];return {reads,snapshotCount:snapshots.length,metadata:()=>structuredClone(metadata),times:()=>snapshots.map(s=>s.time),
    index:()=>indexed?snapshots.map(timeHistoryEntry):null,async readSnapshot(index){reads.push(index);return structuredClone(snapshots[index]);}};
}

test('memory results retain their shape and use the same scalar index',async()=>{
  const trajectory={...metadata,snapshots},source=timeHistory(trajectory);
  assert.strictEqual(timeHistory(trajectory),source);assert.equal(source.archived,false);
  assert.equal(archivedTimeHistory(trajectory),false);assert.deepEqual(Object.keys(trajectory),['analysis','restart_context','snapshots']);
  assert.strictEqual(source.peek(1),snapshots[1]);assert.strictEqual(await source.read(1),snapshots[1]);
  assert.deepEqual(await source.prepare(),snapshots.map(timeHistoryEntry));
  const values=await source.series('CL',()=>{throw Error('Index should be used');});
  assert.deepEqual(values,[-0,1,2]);assert.ok(Object.is(values[0],-0));
});

test('archive opens and plots indexed quantities without reading physical history',async()=>{
  const archive=fakeArchive(),trajectory=archiveTrajectory(archive),source=timeHistory(trajectory);
  assert.equal(Object.hasOwn(trajectory,'snapshots'),false);assert.equal(archivedTimeHistory(trajectory),true);
  assert.deepEqual(await source.prepare(),snapshots.map(timeHistoryEntry));
  assert.deepEqual(await source.series('CL',()=>999),[-0,1,2]);assert.deepEqual(archive.reads,[]);
  assert.equal(source.peek(1),null);const selected=await source.read(1);source.pin(1,selected);
  assert.deepEqual(checkpointAt(trajectory,1),checkpointAt({...metadata,snapshots},1));
  for await(const ignored of source.scan()){};
  assert.strictEqual(source.peek(1),selected,'Plot scans must not evict the selected physical state');
  const checkpoint=await source.checkpoint(2);assert.equal(checkpoint.context.method.order,5);
  checkpoint.state.vector[0]=999;assert.equal((await source.checkpoint(2)).state.vector[0],3);
});

test('legacy archives build a complete index once without retaining the physical array',async()=>{
  const archive=fakeArchive(false),source=timeHistory(archiveTrajectory(archive)),progress=[];
  assert.deepEqual(await source.prepare({onProgress:(done,total)=>progress.push([done,total])}),snapshots.map(timeHistoryEntry));
  assert.deepEqual(archive.reads,[0,1,2]);assert.deepEqual(progress,[[3,3]]);
  assert.deepEqual(await source.series('CL',()=>999),[-0,1,2]);assert.deepEqual(archive.reads,[0,1,2]);
  assert.equal(source.peek(0),null);
});

test('non-indexed series scan exact physical values and retain at most four series',async()=>{
  const archive=fakeArchive(),source=timeHistory(archiveTrajectory(archive));
  const fn=s=>s.restart.state.vector[0];
  assert.deepEqual(await source.series('node.x',fn),[1,2,3]);assert.equal(archive.reads.length,3);
  await source.series('node.x',()=>999);assert.equal(archive.reads.length,3);
  for(let i=0;i<4;i++)await source.series('other'+i,fn);
  assert.equal(archive.reads.length,15);await source.series('node.x',fn);assert.equal(archive.reads.length,18);
});

test('cancellation discards partial scans and never caches a shortened series',async()=>{
  const archive=fakeArchive(),source=timeHistory(archiveTrajectory(archive)),controller=new AbortController();
  await assert.rejects(source.series('cancelled',s=>{controller.abort();return s.CL;},{signal:controller.signal}),{name:'AbortError'});
  assert.deepEqual(await source.series('cancelled',s=>s.CL),[-0,1,2]);
  assert.deepEqual(archive.reads,[0,0,1,2]);
  const legacy=fakeArchive(false),old=timeHistory(archiveTrajectory(legacy)),signal=AbortSignal.abort();
  await assert.rejects(old.prepare({signal}),{name:'AbortError'});assert.deepEqual(legacy.reads,[]);
  assert.equal((await old.prepare()).length,3);
});

test('display entries preserve event side and omit full checkpoints',()=>{
  const entries=snapshots.map(timeHistoryEntry);
  assert.equal(entries[1].phase,'Before input change');assert.equal(entries[2].phase,'After input change');
  assert.equal(entries[1].time,entries[2].time);assert.ok(entries.every(entry=>!Object.hasOwn(entry,'restart')));
  assert.ok(entries.every(entry=>entry.values.length===indexedTimeQuantities.length));
  assert.equal(timeHistoryEntry({time:0,initial_phase:123}).phase,'Computed state');
});

test('current writer index survives reopening and is checked against physical states',async()=>{
  const pieces=[],writer=await createTimeHistoryWriter({async write(bytes){pieces.push(bytes);},async close(){},async abort(){}},{chunkSize:2});
  await writer.append(snapshots);await writer.finish(metadata);
  const reader=await openTimeHistoryArchive(new Blob(pieces));assert.deepEqual(reader.index(),snapshots.map(timeHistoryEntry));
  assert.equal(reader.statistics.recordsRead,1);
  const source=timeHistory(archiveTrajectory(reader));assert.deepEqual(await source.series('CL',()=>999),[-0,1,2]);
  assert.equal(reader.statistics.recordsRead,1);
  for(let i=0;i<3;i++)assert.deepEqual(await source.read(i),snapshots[i]);
});

function deferredSource(){
  const calls=[],resolvers=new Map(),pins=[];
  return {calls,pins,peek:()=>null,pin:(index,snapshot)=>pins.push([index,snapshot]),
    read(index){calls.push(index);return new Promise((resolve,reject)=>resolvers.set(index,{resolve,reject}));},
    finish(index){resolvers.get(index).resolve({time:index,physical:'complete'});},
    fail(index){resolvers.get(index).reject(Error('read failed'));}};
}
const turn=()=>new Promise(resolve=>setImmediate(resolve));

test('rapid selection reads only the in-flight state and newest request, never commits a stale state',async()=>{
  const source=deferredSource(),commits=[],controller=createHistorySelection((s,i)=>commits.push([s,i]));
  const a=controller.select(source,1),b=controller.select(source,2),c=controller.select(source,3);
  assert.deepEqual(source.calls,[1]);assert.equal(await b,false);
  source.finish(1);await turn();assert.deepEqual(source.calls,[1,3]);assert.equal(await a,false);assert.deepEqual(commits,[]);
  source.finish(3);assert.equal(await c,true);assert.deepEqual(commits,[[{time:3,physical:'complete'},3]]);
  assert.deepEqual(source.pins,[[3,{time:3,physical:'complete'}]]);
});

test('trajectory replacement and pause cancel stale selection without poisoning later reads',async()=>{
  const source=deferredSource(),other=deferredSource(),commits=[],controller=createHistorySelection((s,i)=>commits.push(i));
  const a=controller.select(source,1);controller.cancel();const b=controller.select(other,0);
  source.finish(1);await turn();assert.equal(await a,false);assert.deepEqual(commits,[]);
  other.finish(0);assert.equal(await b,true);assert.deepEqual(commits,[0]);
  const c=controller.select(other,2);controller.cancel();other.fail(2);assert.equal(await c,false);
  const d=controller.select(other,3);other.fail(3);await assert.rejects(d,/read failed/);
  const e=controller.select(other,4);other.finish(4);assert.equal(await e,true);
});

test('an already loaded physical state selects immediately and supersedes an in-flight read',async()=>{
  const slow=deferredSource(),memory=timeHistory({...metadata,snapshots}),commits=[];
  const controller=createHistorySelection((s,i)=>commits.push([s,i]));
  const first=controller.select(slow,10),next=controller.select(memory,2);
  assert.equal(commits.length,1);assert.strictEqual(commits[0][0],snapshots[2]);assert.equal(await next,true);
  slow.finish(10);assert.equal(await first,false);assert.equal(commits.length,1);
});
