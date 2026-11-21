// Input changes may have two physical snapshots at the same clock value.
export const acceptedTimeSteps=snapshots=>snapshots.filter(s=>Number.isFinite(s.step)&&s.step>0).length;
export function timePhase(snapshot){
  if(snapshot.input_transition)return 'After input change';
  if(snapshot.forcing_side==='left')return 'Before input change';
  if(snapshot.initial_phase?.startsWith('checkpoint'))return 'Saved state before next inputs';
  return snapshot.step===0?'Initial state':'Computed state';
}
export function timePlotSegments(snapshots,values,breakTimes){
  const breaks=new Set(breakTimes),segments=[];
  let current=[];
  for(let i=0;i<snapshots.length;i++){
    const s=snapshots[i],before=snapshots[i-1],value=values[i];
    const changed=!!s.input_transition||(before&&breaks.has(before.time)&&before.forcing_side!=='right');
    if(current.length&&(!Number.isFinite(value)||changed)){segments.push(current);current=[];}
    if(Number.isFinite(value))current.push([s.time,value]);
  }
  if(current.length)segments.push(current);
  return segments;
}
