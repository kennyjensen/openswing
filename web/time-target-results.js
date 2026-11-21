import {actuatorTargets} from './time-actuators.js';
const byQuantity=new Map(actuatorTargets.map(target=>[target.quantity,target]));

// Match saved rows by ownership, never by array position. Keep solver-reported
// angular errors: subtracting displayed principal angles can add a spurious turn.
export function actuatorHistoryQuantities(rows=[]){
  return rows.flatMap(({variable,quantity})=>{
    const target=byQuantity.get(quantity);if(!target)return [];
    const owner=variable.replace('control.','F').replace('power.','E');
    return [['target','Target',target.target_unit],['actual','Achieved',target.target_unit],['normalized_residual','Target residual','dimensionless']].map(([field,label,unit])=>[
      `inverse.${field}|${variable}|${quantity}`,`${label} ${target.label} · ${owner}`,unit,
    ]);
  });
}
export function actuatorHistoryValue(snapshot,key){
  const [field,variable,quantity]=key.slice('inverse.'.length).split('|');
  if(!['target','actual','normalized_residual'].includes(field))return null;
  const value=snapshot.operating_constraints?.find(row=>row.variable===variable&&row.quantity===quantity)?.[field];
  return Number.isFinite(value)?value:null;
}

// Forcing labels may contain dots (explicit Earth-vector extensions); each
// label is one literal JSON key, not a nested object path.
export function forcingHistoryValue(snapshot,key){
  const value=snapshot.forcing_values?.[key.slice('forcing_values.'.length)];
  return Number.isFinite(value)?value:null;
}

export function timeInitializationSummary(trajectory,first=trajectory?.snapshots?.[0]){
  const report=trajectory?.initialization,phase=first?.initial_phase??'';
  if(trajectory?.request?.action==='resume_time'||phase.startsWith('checkpoint'))return 'Checkpoint continuation: the saved physical state is retained before the next time inputs.';
  if(phase==='history_transition_right_limit'||trajectory?.launch_transition?.kind==='held_physical_state_right_limit')return 'Saved-equilibrium history launch: snapshot 0 is the completed right state after applying the initial history. The original before-input snapshot is retained separately; the saved physical state is held while actuator settings and initial rates are completed.';
  if(report?.source==='cold inverse-history equilibrium'||phase==='cold_inverse_history')return 'Cold inverse-history initialization: the initial frame state and local velocities are held; elastic shape and actuator settings are solved with the initial time targets.';
  if(report?.source==='saved steady equilibrium'||phase.startsWith('saved_equilibrium'))return 'Saved-equilibrium launch: the saved setup is retained; new time inputs apply after the initial snapshot.';
  return report?.source?`Initialization: ${report.source}.`:'';
}
