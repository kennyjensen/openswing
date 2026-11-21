// One interface for existing in-memory results and immutable archive readers.
// Only scalar display entries and a bounded number of scalar series are cached.
import {checkpointRecord} from './saved-state-data.js';
import {indexedTimeQuantities,timeHistoryEntry} from './time-history-index.js';

const sources=new WeakMap(),backends=new WeakMap();
const cancelled=signal=>{if(signal?.aborted)throw new DOMException('History read cancelled.','AbortError');};
const yieldToUI=()=>new Promise(resolve=>setTimeout(resolve,0));

function createSource(trajectory,archive=null){
  const snapshots=archive?null:trajectory.snapshots,count=archive?.snapshotCount??snapshots.length;
  let entries=archive?.index?.()??(snapshots?snapshots.map(timeHistoryEntry):null),preparing=null,pinned=null;
  const times=archive?archive.times():entries.map(entry=>entry.time),cache=new Map();
  function check(index){if(!Number.isInteger(index)||index<0||index>=count)throw new RangeError('History snapshot index is out of range.');}
  async function read(index){check(index);return archive?archive.readSnapshot(index):snapshots[index];}
  async function *scan({signal,onProgress=()=>{}}={}){
    for(let i=0;i<count;i++){
      cancelled(signal);const snapshot=await read(i);cancelled(signal);yield snapshot;
      if((i+1)%32===0||i===count-1){onProgress(i+1,count);await yieldToUI();}
    }
  }
  async function prepare({onProgress=()=>{},signal}={}){
    cancelled(signal);
    if(entries)return entries;
    if(!preparing)preparing=(async()=>{
      const next=[];for await(const snapshot of scan({onProgress,signal}))next.push(timeHistoryEntry(snapshot));
      entries=next;return entries;
    })().finally(()=>{preparing=null;});
    return preparing;
  }
  return {
    count,times,archived:!!archive,read,scan,prepare,
    peek(index){return snapshots?.[index]??(pinned?.index===index?pinned.snapshot:null);},
    pin(index,snapshot){check(index);if(archive)pinned={index,snapshot};},
    async checkpoint(index){const snapshot=await read(index);return checkpointRecord(snapshot.restart,snapshot.restart_context??trajectory.restart_context);},
    async series(key,value,{signal,onProgress=()=>{}}={}){
      cancelled(signal);
      const indexed=indexedTimeQuantities.indexOf(key);
      if(indexed>=0){const rows=await prepare({onProgress,signal});cancelled(signal);return rows.map(row=>row.values[indexed]);}
      if(cache.has(key)){const found=cache.get(key);cache.delete(key);cache.set(key,found);return found;}
      const values=[];
      for await(const snapshot of scan({signal,onProgress})){
        const raw=value(snapshot);values.push(Number.isFinite(raw)?raw:null);
      }
      cancelled(signal);cache.set(key,values);
      while(cache.size>4)cache.delete(cache.keys().next().value);
      return values;
    },
  };
}

export function timeHistory(trajectory){
  if(!trajectory)return null;
  let source=sources.get(trajectory);
  if(!source){
    if(!Array.isArray(trajectory.snapshots)||!trajectory.snapshots.length)throw new Error('No computed time snapshots.');
    source=createSource(trajectory);sources.set(trajectory,source);
  }
  return source;
}

export function archiveTrajectory(archive){
  return attachTimeHistory(archive.metadata(),archive);
}

export function copyTimeHistory(trajectory){
  const copy=structuredClone(trajectory);
  if(copy?.request)copy.request=JSON.parse(JSON.stringify(copy.request));
  if(sources.get(trajectory)?.archived)attachTimeHistory(copy,backends.get(trajectory));
  return copy;
}

export function attachTimeHistory(metadata,reader){
  sources.set(metadata,createSource(metadata,reader));backends.set(metadata,reader);return metadata;
}

export const archivedTimeHistory=trajectory=>!!sources.get(trajectory)?.archived;
