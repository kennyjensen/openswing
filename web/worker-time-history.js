import {attachTimeHistory} from './time-history-source.js';
import {timeHistoryEntry,validTimeHistoryEntry} from './time-history-index.js';

// Compressed reports stay outside the expanded JavaScript object graph.
// The existing history interface loads one complete report when selected.
export async function decodeTimeSnapshot(blob){
  if(typeof DecompressionStream!=='function')throw new Error('This browser needs gzip decompression support for time-response histories.');
  const text=await new Response(blob.stream().pipeThrough(new DecompressionStream('gzip'))).text();
  const snapshot=JSON.parse(text);
  if(!snapshot||typeof snapshot!=='object'||Array.isArray(snapshot)||!Number.isFinite(snapshot.time))
    throw new Error('Reading time response: invalid snapshot.');
  return snapshot;
}

export async function indexTimeSnapshot(blob){
  return timeHistoryEntry(await decodeTimeSnapshot(blob));
}

export function restoreWorkerTimeHistory(result){
  if(!result?.snapshot_storage)return result;
  const {snapshot_storage:storage,...metadata}=result;
  const {records,entries}=storage;
  if(storage.format!=='openswing-worker-time-history'||storage.version!==1
      ||metadata.analysis!=='time_response'||!Array.isArray(records)||!records.length
      ||!Array.isArray(entries)||entries.length!==records.length
      ||records.some(record=>!(record instanceof Blob))
      ||entries.some((entry,i)=>!validTimeHistoryEntry(entry,entry?.time)||!Number.isFinite(entry.time)
        ||i>0&&entry.time<entries[i-1].time))throw new Error('Invalid worker time history.');
  let cachedIndex=-1,cached;
  return attachTimeHistory(metadata,{
    snapshotCount:records.length,times:()=>entries.map(entry=>entry.time),index:()=>entries,
    async readSnapshot(index){
      if(!Number.isInteger(index)||index<0||index>=records.length)throw new RangeError('Time snapshot index out of range.');
      if(index!==cachedIndex){
        const snapshot=await decodeTimeSnapshot(records[index]);
        if(snapshot.time!==entries[index].time)throw new Error('Time snapshot and display index disagree.');
        cached=snapshot;cachedIndex=index;
      }
      return structuredClone(cached);
    },
  });
}
