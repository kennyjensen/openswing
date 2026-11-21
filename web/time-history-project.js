import {timeHistory,archivedTimeHistory} from './time-history-source.js';
import {PROJECT_LIMIT} from './project-data.js';
import {encodeHistoryJSON} from './time-history-codec.js';

// Existing JSON projects retain their existing bounds. Small archive-backed
// histories can still be saved there; large ones stay complete in .oswh files.
export async function serializableTimeSolution(solution){
  if(solution.kind!=='time'||!archivedTimeHistory(solution.data))return solution;
  const data={...solution.data,snapshots:[]};let bytes=encodeHistoryJSON(data,PROJECT_LIMIT).length,values=0;
  const count=value=>{
    if(++values>2000000)throw new Error('This history exceeds the JSON project limit. Use Save complete history to retain every state.');
    if(value!==null&&typeof value==='object')for(const child of Object.values(value))count(child);
  };
  count(data);
  for await(const snapshot of timeHistory(solution.data).scan()){
    count(snapshot);bytes+=encodeHistoryJSON(snapshot,PROJECT_LIMIT).length+1;
    if(bytes>PROJECT_LIMIT)throw new Error('This history exceeds the JSON project limit. Use Save complete history to retain every state.');
    data.snapshots.push(snapshot);
  }
  return {...solution,data};
}
