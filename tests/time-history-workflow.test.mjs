import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createTimeHistoryWriter,openTimeHistoryArchive} from '../web/time-history-archive.js';
import {archiveTrajectory,timeHistory,copyTimeHistory,archivedTimeHistory} from '../web/time-history-source.js';
import {joinTimeHistory} from '../web/time-history-continuation.js';
import {serializableTimeSolution} from '../web/time-history-project.js';
import {exportTimeHistory} from '../web/time-history-export.js';
import {distributionAccumulator,distributionHistory} from '../web/distribution-history.js';

function fixture(){
  const context={method:{order:2},setup:{forcing:'original'}},changed={method:{order:5},setup:{forcing:'changed'}};
  const snapshot=(time,step,CL,extra={})=>({time,step,CL,residual:0,strips:[{beam:1,t:0,force:[CL,0,0]}],
    restart:{state:{time,vector:[CL,-0,2]},older:{time:time-.025,internal:true},accepted_method:{previous2:{time:time-.04,hidden:true},unknown:{retain:['old',false]}}},...extra});
  const parent={analysis:'time_response',end_time:.1,start_time:0,duration:.1,accepted_steps:1,rejected_steps:0,
    restart_context:context,forcing:{breaks:[.1]},software_provenance:{fingerprint:'old'},snapshots:[
      snapshot(0,0,-0),snapshot(.1,.1,1,{forcing_side:'left',accuracy:{internal_steps:2}}),
      snapshot(.1,0,2,{input_transition:{side:'after'},forcing_side:'right'})]};
  const segment={...parent,start_time:.1,end_time:.2,duration:.1,software_provenance:{fingerprint:'new'},restart_context:changed,
    snapshots:[snapshot(.1,0,1),snapshot(.1,0,3,{input_transition:{side:'after'},forcing_side:'right'}),snapshot(.2,.1,4,{accuracy:{internal_steps:4}})]};
  return {parent,segment};
}
function fileHandle(){
  let pieces=[],closed=false,aborted=false;
  return {async createWritable(){return {async write(bytes){pieces.push(bytes.slice());},async close(){closed=true;},async abort(){aborted=true;}};},
    async getFile(){assert.ok(closed&&!aborted);return new Blob(pieces);},get aborted(){return aborted;}};
}
async function stored(trajectory){
  const handle=fileHandle(),writer=await createTimeHistoryWriter(await handle.createWritable(),{chunkSize:2});
  const {snapshots,...metadata}=trajectory;await writer.append(snapshots);await writer.finish(metadata);
  return archiveTrajectory(await openTimeHistoryArchive(await handle.getFile()));
}
async function physical(trajectory){const result=[];for await(const snapshot of timeHistory(trajectory).scan())result.push(snapshot);return result;}

test('archive continuation matches the full array branch, including internal method records and input jumps',async()=>{
  const {parent,segment}=fixture(),archived=await stored(parent),before=structuredClone({parent,segment});
  const legacy=await joinTimeHistory(parent,1,segment),result=await joinTimeHistory(archived,1,segment);
  const {snapshots,...metadata}=legacy;
  assert.deepEqual(result,metadata);assert.deepEqual(await physical(result),snapshots);
  assert.equal(timeHistory(result).count,4);assert.equal(result.accepted_steps,2);assert.equal(result.retained_steps,1);assert.equal(result.internal_steps,6);
  assert.deepEqual(result.history_sources,[{start_snapshot:0,end_snapshot:2,software_provenance:{fingerprint:'old'}},{start_snapshot:2,end_snapshot:4,software_provenance:{fingerprint:'new'}}]);
  assert.deepEqual(timeHistory(result).times,[0,.1,.1,.2]);
  assert.equal((await timeHistory(result).checkpoint(1)).context.setup.forcing,'original');
  assert.equal((await timeHistory(result).checkpoint(2)).context.setup.forcing,'changed');
  assert.equal((await timeHistory(result).checkpoint(1)).accepted_method.previous2.hidden,true);
  assert.deepEqual({parent,segment},before);
});

test('nested archive branches and undo copies retain complete older states independently of the selected state',async()=>{
  const {parent,segment}=fixture(),first=await joinTimeHistory(await stored(parent),1,segment),undo=copyTimeHistory(first);
  assert.ok(archivedTimeHistory(undo));assert.deepEqual(await physical(undo),await physical(first));
  const later={...segment,start_time:.2,end_time:.3,snapshots:[segment.snapshots[2],{...segment.snapshots[2],time:.3,restart:{...segment.snapshots[2].restart,state:{time:.3,vector:[5,-0,2]}}}]};
  const second=await joinTimeHistory(first,3,later);
  assert.equal(timeHistory(second).count,5);assert.equal(timeHistory(undo).count,4);
  const selected=await timeHistory(second).read(4);timeHistory(second).pin(4,selected);
  assert.equal(timeHistory(undo).peek(4),null);assert.deepEqual(await timeHistory(undo).read(3),segment.snapshots[2]);
  await assert.rejects(joinTimeHistory(first,0,later),/selected time/);
});

test('small archive-backed results materialize for existing JSON projects without changing the live history',async()=>{
  const {parent}=fixture(),trajectory=await stored(parent),solution={kind:'time',data:trajectory,view:{snapshot:'1'}};
  const result=await serializableTimeSolution(solution);
  assert.deepEqual(result,{...solution,data:parent});assert.equal(archivedTimeHistory(result.data),false);
  assert.equal(archivedTimeHistory(solution.data),true);assert.equal(Object.hasOwn(solution.data,'snapshots'),false);
  assert.strictEqual(await serializableTimeSolution({kind:'modes'}).then(x=>x.kind),'modes');
});

test('complete-history export preserves all states, root metadata and saved workbench inputs',async()=>{
  const {parent}=fixture();parent.request={action:'time',source:'fixture ASW',omitted:undefined};
  const handle=fileHandle(),progress=[],workbench={format:'openswing-workbench-history',version:1,configuration:{source:'fixture ASW'}};
  const result=await exportTimeHistory(parent,{workbench,picker:async options=>{assert.equal(options.suggestedName,'openswing-time.oswh');return handle;},onProgress:(done,total)=>progress.push([done,total])});
  assert.equal(result.snapshots,3);assert.deepEqual(progress,[[3,3]]);
  const reader=await openTimeHistoryArchive(await handle.getFile());
  assert.deepEqual(reader.metadata().openswing_workbench,workbench);
  assert.deepEqual(reader.metadata().request,{action:'time',source:'fixture ASW'});
  assert.deepEqual(await physical(archiveTrajectory(reader)),parent.snapshots);
  assert.ok(Object.hasOwn(parent.request,'omitted'),'Export must not mutate the original request');
});

test('picker cancellation performs no writes and failed exports abort instead of publishing a partial file',async()=>{
  const {parent}=fixture(),cancel=new DOMException('Cancelled','AbortError');
  await assert.rejects(exportTimeHistory(parent,{picker:async()=>{throw cancel;}}),{name:'AbortError'});
  const handle=fileHandle(),original=handle.createWritable;
  handle.createWritable=async()=>{const sink=await original();sink.write=async()=>{throw Error('disk full');};return sink;};
  await assert.rejects(exportTimeHistory(parent,{picker:async()=>handle}),/disk full/);assert.equal(handle.aborted,true);
});

test('streamed distribution reduction matches the existing array result exactly',async()=>{
  const {parent}=fixture(),trajectory=await stored(parent),value=row=>row.force[0],accumulator=distributionAccumulator('strips',1,value);let index=0;
  for await(const snapshot of timeHistory(trajectory).scan())accumulator.add(snapshot,index++);
  assert.deepEqual(accumulator.result(),distributionHistory(parent.snapshots,'strips',1,value));
});
