import {test} from 'node:test';
import assert from 'node:assert/strict';
import {gzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {createTimeHistoryWriter,openTimeHistoryArchive} from '../web/time-history-archive.js';
import {encodeHistoryJSON,decodeHistoryJSON} from '../web/time-history-codec.js';
import {checkpointAt} from '../web/time-checkpoint.js';

function fixture(){
  const context={method:{order:2,maximum_step:.02},setup:{forcing:'0 0\n.02 .1\n'.repeat(50)}};
  const state=(time,force=0)=>({time,position:[1,-0,2],commands:{F3:force},extra:'retained'.repeat(50)});
  const initial=state(0),before=state(.02),after=state(.02,.1),internal=state(.015),seed=state(.01);
  const options={gravity:[0,0,-9.81],unknown:{enabled:false,value:null},extension:'options'.repeat(50)};
  const accepted={kind:'bdf',previous:initial,previous2:internal,seed,
    accepted_inputs:context,endpoint:{state:before,options},
    literal:{format:'openswing-time-result',version:99,references:[['user data',10]]}};
  const snapshots=[
    {time:0,CL:-0,restart:{state:initial,older:null,options}},
    {time:.02,CL:.3,input_transition:{side:'before'},restart:{state:before,older:initial,options,accepted_method:accepted}},
    {time:.02,CL:.4,input_transition:{side:'after'},restart_context:{...context,method:{order:5}},
      restart:{state:after,older:null,options,accepted_method:{kind:'historic-radau',stages:[seed,internal],unknown:['retain',false,null]}}},
  ];
  const metadata={analysis:'time_response',restart_context:context,unknown:JSON.parse('{"__proto__":{"safe":true},"constructor":"literal","negative_zero":-0}')};
  return {snapshots,metadata};
}
function memorySink(){
  const pieces=[];let closed=0,aborted=0;
  return {async write(x){pieces.push(x.slice());},async close(){closed++;},async abort(){aborted++;},
    blob(){return new Blob(pieces);},get closed(){return closed;},get aborted(){return aborted;}};
}
async function saved(options={}){
  const data=fixture(),sink=memorySink(),writer=await createTimeHistoryWriter(sink,{chunkSize:2,...options});
  const original=structuredClone(data);await writer.append(data.snapshots);
  const summary=await writer.finish(data.metadata);assert.deepEqual(data,original);
  return {...data,blob:sink.blob(),summary,sink};
}

test('all fields, signed zero, same-time transitions and internal method states round-trip',async()=>{
  const {blob,snapshots,metadata,summary,sink}=await saved();
  assert.deepEqual(summary,{format:'openswing-time-history',version:1,snapshots:3,chunks:2,bytes:blob.size});
  assert.equal(sink.closed,1);assert.equal(sink.aborted,0);
  const archive=await openTimeHistoryArchive(blob);
  assert.deepEqual(archive.metadata(),metadata);assert.deepEqual(archive.times(),[0,.02,.02]);
  const actual=[];for await(const snapshot of archive.snapshots())actual.push(snapshot);
  assert.deepEqual(actual,snapshots);
  for(let i=0;i<snapshots.length;i++)assert.deepEqual(checkpointAt({...metadata,snapshots:actual},i),checkpointAt({...metadata,snapshots},i));
  assert.equal(actual[1].restart.accepted_method.previous2.time,.015);
  assert.equal(actual[2].restart.accepted_method.kind,'historic-radau');
  assert.ok(Object.is(actual[0].CL,-0));assert.ok(Object.is(actual[1].restart.state.position[1],-0));
  assert.equal(Object.getPrototypeOf(archive.metadata().unknown),Object.prototype);
  assert.equal(Object.prototype.safe,undefined);
  assert.deepEqual(await archive.verify(),{snapshots:3,chunks:2});
});

test('random access reads only its chunk, and selected copies cannot corrupt the cache',async()=>{
  const {blob,snapshots,metadata}=await saved();const ranges=[];
  const archive=await openTimeHistoryArchive({size:blob.size,slice(a,b){ranges.push([a,b]);return blob.slice(a,b);}});
  assert.equal(archive.statistics.recordsRead,1);
  const before=ranges.length,selected=await archive.readSnapshot(2);
  assert.equal(ranges.length,before+1);assert.equal(archive.statistics.recordsRead,2);
  selected.restart.state.position[0]=999;const copy=archive.metadata();copy.restart_context.method.order=99;
  assert.deepEqual(await archive.readSnapshot(2),snapshots[2]);assert.deepEqual(archive.metadata(),metadata);
  assert.equal(ranges.length,before+1);
  await archive.readSnapshot(0);await archive.readSnapshot(2);
  assert.equal(archive.statistics.recordsRead,4,'one chunk cache, not an ever-growing history');
  assert.deepEqual(await Promise.all([archive.readSnapshot(1),archive.readSnapshot(2)]),snapshots.slice(1));
  for(const index of [-1,3,.5,NaN,'0'])await assert.rejects(archive.readSnapshot(index),/out of range/);
});

test('writes commit only on finish and reject further or overlapping writes',async()=>{
  const sink=memorySink(),data=fixture(),writer=await createTimeHistoryWriter(sink,{chunkSize:1});
  const pending=writer.append(data.snapshots);await assert.rejects(writer.append([]),/serial/);await pending;
  await assert.rejects(openTimeHistoryArchive(sink.blob()),/Invalid or incomplete/);
  await writer.finish(data.metadata);await assert.rejects(writer.append([]),/open/);
  await assert.rejects(writer.finish(data.metadata),/open/);await writer.abort();assert.equal(sink.aborted,0);
});

test('sink failures abort once and cannot publish a valid archive',async()=>{
  const data=fixture(),sink=memorySink();let writes=0;
  const writer=await createTimeHistoryWriter({...sink,write:async bytes=>{if(++writes===2)throw Error('disk full');await sink.write(bytes);}});
  await assert.rejects(writer.append(data.snapshots),/disk full/);assert.equal(sink.aborted,1);
  await assert.rejects(writer.finish(data.metadata),/open/);
  await assert.rejects(openTimeHistoryArchive(sink.blob()),/Invalid or incomplete/);
});

test('unsupported values fail explicitly without invoking accessors or toJSON',async()=>{
  let invoked=0;
  const getter=Object.defineProperty({},'x',{enumerable:true,get(){invoked++;return 1;}});
  const cycle={};cycle.self=cycle;
  const hidden=Object.defineProperty({},'x',{value:1});
  const sparse=Array(2),symbol={[Symbol('x')]:1},nonplain=new Date();
  for(const value of [undefined,NaN,Infinity,1n,()=>1,getter,cycle,hidden,sparse,symbol,nonplain,{toJSON(){invoked++;return 1;}}]){
    const sink=memorySink(),writer=await createTimeHistoryWriter(sink);
    await assert.rejects(writer.append([{time:0,extra:value}]));assert.equal(sink.aborted,1);
  }
  assert.equal(invoked,0);
});

test('nonmonotone times and oversized single states fail rather than being omitted',async()=>{
  for(const snapshots of [[{time:1},{time:0}],[{time:Infinity}],[{time:'1'}],[{time:0,extra:'x'.repeat(16*1024*1024)}]]){
    const sink=memorySink(),writer=await createTimeHistoryWriter(sink);
    await assert.rejects(writer.append(snapshots));assert.equal(sink.aborted,1);
  }
  const writer=await createTimeHistoryWriter(memorySink());
  await assert.rejects(writer.finish(fixture().metadata),/Finish history/);
});

test('pooling cannot hide excessive expanded depth and time accessors are never invoked',async()=>{
  let state={payload:'x'.repeat(250)};for(let i=0;i<76;i++)state={n:state};
  const writer=await createTimeHistoryWriter(memorySink());
  await assert.rejects(writer.append([{time:0,restart:{state}}]),/structural/);
  let invoked=0;
  const snapshot=Object.defineProperty({},'time',{enumerable:true,get(){invoked++;return 0;}});
  const second=await createTimeHistoryWriter(memorySink());
  await assert.rejects(second.append([snapshot]));assert.equal(invoked,0);
});

test('large batches split into bounded records without dropping data',async()=>{
  const sink=memorySink(),writer=await createTimeHistoryWriter(sink);
  const snapshots=Array.from({length:3},(_,time)=>({time,unpooled:'x'.repeat(6*1024*1024)}));
  await writer.append(snapshots);const result=await writer.finish({analysis:'time_response'});
  assert.equal(result.chunks,2);const archive=await openTimeHistoryArchive(sink.blob());
  for(let i=0;i<3;i++)assert.deepEqual(await archive.readSnapshot(i),snapshots[i]);
});

test('truncation, modified index, bad magic and compressed-data corruption reject',async()=>{
  const {blob}=await saved(),bytes=new Uint8Array(await blob.arrayBuffer());
  for(const end of [0,8,bytes.length-1,bytes.length-56])await assert.rejects(openTimeHistoryArchive(new Blob([bytes.subarray(0,end)])));
  for(const index of [0,bytes.length-56,bytes.length-1]){
    const damaged=bytes.slice();damaged[index]^=1;await assert.rejects(openTimeHistoryArchive(new Blob([damaged])));
  }
  const damaged=bytes.slice();damaged[20]^=127;
  const archive=await openTimeHistoryArchive(new Blob([damaged]));await assert.rejects(archive.readSnapshot(0));
});

// Construct files independently to test reader validation, not just a writer /
// reader that might agree on the same erroneous encoding.
function handmade({packet,editManifest=()=>{},plainBytes}={}){
  const chunk=Buffer.from(JSON.stringify(packet??{format:'openswing-time-result',version:1,
    result:{analysis:'time_response',snapshots:[{time:0}]},values:[],references:[]}));
  const root=Buffer.from('{"analysis":"time_response"}'),compressed=[gzipSync(chunk),gzipSync(root)];
  const records=[{kind:'snapshots',offset:8,bytes:compressed[0].length,plain_bytes:plainBytes??chunk.length,
    sha256:createHash('sha256').update(chunk).digest('hex'),first:0,count:1,times:[0]},
  {kind:'metadata',offset:8+compressed[0].length,bytes:compressed[1].length,plain_bytes:root.length,sha256:createHash('sha256').update(root).digest('hex')}];
  const manifest={format:'openswing-time-history',version:1,snapshots:1,records};editManifest(manifest);
  const encoded=Buffer.from(JSON.stringify(manifest)),footer=Buffer.alloc(56);footer.write('OSWEND01');
  footer.writeBigUInt64LE(BigInt(8+compressed[0].length+compressed[1].length),8);footer.writeBigUInt64LE(BigInt(encoded.length),16);
  createHash('sha256').update(encoded).digest().copy(footer,24);
  return new Blob([Buffer.from('OSWHST01'),...compressed,encoded,footer]);
}

test('independent archive opens; forged offsets, counts, limits, versions and hashes reject',async()=>{
  const valid=await openTimeHistoryArchive(handmade());assert.deepEqual(await valid.readSnapshot(0),{time:0});
  for(const editManifest of [m=>m.version=2,m=>m.snapshots=2,m=>m.records[0].offset=9,
    m=>m.records[0].count=129,m=>m.records[0].plain_bytes=17*1024*1024,
    m=>m.records[0].first=1,m=>m.records[0].times=[],m=>m.records[1].kind='snapshots'])
    await assert.rejects(openTimeHistoryArchive(handmade({editManifest})));
  const wrongHash=await openTimeHistoryArchive(handmade({editManifest:m=>m.records[0].sha256='0'.repeat(64)}));
  await assert.rejects(wrongHash.readSnapshot(0),/checksum/);
  const oversized=await openTimeHistoryArchive(handmade({plainBytes:20}));
  await assert.rejects(oversized.readSnapshot(0),/declared size/);
  const wrongTime=await openTimeHistoryArchive(handmade({editManifest:m=>m.records[0].times=[1]}));
  await assert.rejects(wrongTime.readSnapshot(0),/Invalid/);
});

test('malformed reference targets and prototype writes reject before exposing any state',async()=>{
  for(const path of [['snapshots',0,'__proto__'],['snapshots',0,'missing'],['snapshots',0,'time']]){
    const packet={format:'openswing-time-result',version:1,
      result:JSON.parse('{"analysis":"time_response","snapshots":[{"time":0,"__proto__":null}]}'),
      values:[{poison:true}],references:[[path,0]]};
    const archive=await openTimeHistoryArchive(handmade({packet}));await assert.rejects(archive.readSnapshot(0),/Invalid compact/);
  }
  assert.equal(Object.prototype.poison,undefined);
});

test('display index is optional, versioned, and checked against physical values when read',async()=>{
  const entry={time:0,step:null,forcing_side:null,input_transition:false,phase:'Computed state',has_checkpoint:false,has_accuracy:false,internal_steps:0,values:Array(10).fill(null)};
  const valid=await openTimeHistoryArchive(handmade({editManifest:m=>Object.assign(m.records[0],{preview_version:1,preview:[entry]})}));
  assert.deepEqual(valid.index(),[entry]);assert.deepEqual(await valid.readSnapshot(0),{time:0});
  const changed=structuredClone(entry);changed.values[0]=9;
  const wrong=await openTimeHistoryArchive(handmade({editManifest:m=>Object.assign(m.records[0],{preview_version:1,preview:[changed]})}));
  await assert.rejects(wrong.readSnapshot(0),/display index/);
  const future=await openTimeHistoryArchive(handmade({editManifest:m=>Object.assign(m.records[0],{preview_version:99,preview:{unknown:true}})}));
  assert.equal(future.index(),null);assert.deepEqual(await future.readSnapshot(0),{time:0});
  await assert.rejects(openTimeHistoryArchive(handmade({editManifest:m=>Object.assign(m.records[0],{preview_version:1,preview:[]} )})));
});

test('lossless JSON rejects numeric overflow, invalid UTF-8, excessive depth and byte size',()=>{
  assert.ok(Object.is(decodeHistoryJSON(encodeHistoryJSON(-0)),-0));
  assert.throws(()=>decodeHistoryJSON(new TextEncoder().encode('1e999')),/non-finite/);
  assert.throws(()=>decodeHistoryJSON(new Uint8Array([0xff])));
  let deep=0;for(let i=0;i<82;i++)deep=[deep];assert.throws(()=>encodeHistoryJSON(deep),/structural/);
  assert.throws(()=>encodeHistoryJSON('ééé',6),/byte limit/);
});
