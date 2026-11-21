import {timeHistory,archivedTimeHistory,attachTimeHistory} from './time-history-source.js';
import {continuedHistorySources} from './solution-data.js';

export async function joinTimeHistory(parent,index,segment){
  const previous=timeHistory(parent),tail=timeHistory(segment);
  if(!Number.isInteger(index)||index<0||index>=previous.count)throw new Error('Invalid continuation snapshot.');
  if(previous.times[index]!==tail.times[0])throw new Error('Continuation does not start at the selected time.');
  const oldEntries=(await previous.prepare()).slice(0,index+1),newEntries=(await tail.prepare()).slice(1),entries=[...oldEntries,...newEntries];
  const steps=rows=>rows.filter(row=>row.step>0).length;
  const output={...segment,history_sources:continuedHistorySources(parent,index,segment,previous.count,tail.count),
    retained_steps:steps(oldEntries),start_time:entries[0].time,duration:segment.end_time-entries[0].time,accepted_steps:steps(entries)};
  if(entries.some(entry=>entry.has_accuracy))output.internal_steps=entries.reduce((total,entry)=>total+entry.internal_steps,0);
  output.history_breaks=[...new Set([...(parent.history_breaks??parent.forcing?.breaks??[]).filter(t=>t>=output.start_time&&t<=previous.times[index]),
    ...(segment.forcing?.breaks??[]).filter(t=>t>=previous.times[index]&&t<=segment.end_time)])].sort((a,b)=>a-b);
  const prefix=snapshot=>({...snapshot,restart_context:snapshot.restart_context??parent.restart_context});
  if(!archivedTimeHistory(parent)&&!archivedTimeHistory(segment)){
    output.snapshots=[...parent.snapshots.slice(0,index+1).map(prefix),...segment.snapshots.slice(1)];return output;
  }
  delete output.snapshots;
  return attachTimeHistory(output,{snapshotCount:entries.length,times:()=>entries.map(entry=>entry.time),index:()=>entries,
    async readSnapshot(i){return i<=index?prefix(await previous.read(i)):tail.read(i-index);}});
}
