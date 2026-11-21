import {timePhase} from './time-timeline.js';

// This is a display index, never a physical snapshot or restart record.
export const indexedTimeQuantities=['CL','CD','CDi','CDi_near','efficiency','CLi','CYi','Cm','max_displacement','residual'];
export function timeHistoryEntry(snapshot){
  return {time:snapshot.time,step:Number.isFinite(snapshot.step)?snapshot.step:null,
    forcing_side:typeof snapshot.forcing_side==='string'?snapshot.forcing_side:null,
    input_transition:!!snapshot.input_transition,phase:timePhase({step:snapshot.step,
      input_transition:snapshot.input_transition,forcing_side:snapshot.forcing_side,
      initial_phase:typeof snapshot.initial_phase==='string'?snapshot.initial_phase:undefined}),
    has_checkpoint:!!snapshot.restart,has_accuracy:!!snapshot.accuracy,
    internal_steps:snapshot.step>0?(snapshot.accuracy?.internal_steps??1):0,
    values:indexedTimeQuantities.map(key=>Number.isFinite(snapshot[key])?snapshot[key]:null)};
}

export function validTimeHistoryEntry(entry,time){
  return entry!==null&&typeof entry==='object'&&!Array.isArray(entry)
    &&Object.is(entry.time,time)&&(entry.step===null||Number.isFinite(entry.step))
    &&(entry.forcing_side===null||typeof entry.forcing_side==='string')
    &&typeof entry.input_transition==='boolean'&&typeof entry.phase==='string'
    &&typeof entry.has_checkpoint==='boolean'&&typeof entry.has_accuracy==='boolean'
    &&Number.isFinite(entry.internal_steps)&&entry.internal_steps>=0
    &&Array.isArray(entry.values)&&entry.values.length===indexedTimeQuantities.length
    &&entry.values.every(value=>value===null||Number.isFinite(value));
}
