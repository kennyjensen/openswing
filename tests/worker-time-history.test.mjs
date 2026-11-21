import {test} from 'node:test';
import assert from 'node:assert/strict';
import {gzipSync} from 'node:zlib';
import {readSolverReply} from '../web/solver-json.js';
import {restoreWorkerTimeHistory} from '../web/worker-time-history.js';
import {timeHistory,archivedTimeHistory} from '../web/time-history-source.js';
import {joinTimeHistory} from '../web/time-history-continuation.js';

function runtime(records){
  let index=0;const events=[],py={_module:{},async runPythonAsync(){
    events.push('compute');
    return {part_count:records.length,next_part(){
      const bytes=records[index++],heap=new Uint8Array(bytes.length+16);heap.set(bytes,16);py._module.HEAPU8=heap;
      return {address:16,byte_length:bytes.length,destroy(){heap.fill(0);events.push('release');}};
    },close(){events.push('close');},destroy(){events.push('destroy');}};
  }};return {py,events};
}
const rows=[
  {time:0,step:0,CL:-0,forcing_side:'right',fields:{unchanged:1e-100}},
  {time:.01,step:.01,CL:2,forcing_side:'left',fields:{unchanged:3}},
  {time:.01,step:0,CL:3,forcing_side:'right',input_transition:{},fields:{unchanged:4}},
];
const metadata={analysis:'time_response',start_time:0,end_time:.01,restart_context:{setup:{}}};
function packets(){
  return [new TextEncoder().encode(JSON.stringify({result:metadata,snapshot_count:rows.length,snapshot_encoding:'gzip-json-v1'})),
    ...rows.map((row,i)=>gzipSync(i===0?JSON.stringify(row).replace('"CL":0','"CL":-0.0'):JSON.stringify(row)))];
}
test('time reports cross the worker boundary once and stay compressed until selected',async()=>{
  const {py,events}=runtime(packets()),progress=[];
  const reply=await readSolverReply(py,'time',()=>{},(done,total)=>progress.push([done,total]));
  assert.equal(reply.result.snapshot_storage.records.length,3);
  assert.equal(Object.hasOwn(reply.result,'snapshots'),false);
  assert.deepEqual(events,['compute','release','release','release','release','close','destroy']);
  assert.deepEqual(progress.at(-1),[4,4]);
  const result=restoreWorkerTimeHistory(reply.result),source=timeHistory(result);
  assert.equal(archivedTimeHistory(result),true);assert.equal(source.count,3);
  assert.equal(Object.hasOwn(result,'snapshot_storage'),false);
  assert.equal(source.peek(0),null);
  assert.deepEqual(source.times,[0,.01,.01]);
  const entries=await source.prepare();
  assert.equal(entries[1].forcing_side,'left');assert.equal(entries[2].forcing_side,'right');
  assert.equal(Object.is(entries[0].values[0],-0),true);
  for(let i=0;i<rows.length;i++)assert.deepEqual(await source.read(i),rows[i]);
  const selected=await source.read(2);selected.fields.unchanged=999;
  assert.equal((await source.read(2)).fields.unchanged,4);
  assert.deepEqual(await source.series('CL',()=>999),[-0,2,3]);
});
test('an in-memory history can continue into compressed worker records without losing either branch',async()=>{
  const {py}=runtime(packets()),segment=restoreWorkerTimeHistory((await readSolverReply(py,'resume_time')).result);
  const parent={...metadata,snapshots:[{time:-.01,step:.01,CL:5},rows[0]]};
  const joined=await joinTimeHistory(parent,1,segment),source=timeHistory(joined);
  assert.equal(archivedTimeHistory(joined),true);
  assert.deepEqual(source.times,[-.01,0,.01,.01]);
  assert.deepEqual(await source.read(3),rows[2]);
  assert.deepEqual((await source.read(0)).restart_context,metadata.restart_context);
});
test('corrupt snapshot packets fail and release the worker buffer',async()=>{
  const records=packets();records[1]=gzipSync('null');
  const {py,events}=runtime(records);
  await assert.rejects(readSolverReply(py,'time'),/invalid snapshot/);
  assert.deepEqual(events.slice(-3),['release','close','destroy']);
  assert.throws(()=>restoreWorkerTimeHistory({...metadata,snapshot_storage:{version:1,format:'bad'}}),/Invalid worker/);
});
