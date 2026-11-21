import {historyTargets} from './time-history-targets.js';

const legacyTargets=[
  ...['x','y','z'].flatMap(a=>[
    ['F'+a,'force.'+a,1,'input F','input F'],['M'+a,'moment.'+a,1,'input F·L','input F·L'],
    ['A'+a,'acceleration.'+a,1,'input L/T²','input L/T²'],['G'+a,'angular_acceleration.'+a,Math.PI/180,'deg/input T²','rad/input T²'],
  ]),['L','lift',1,'input F','input F'],['Ar','radial_acceleration',1,'input L/T²','input L/T²'],
].map(([label,quantity,factor,table_unit,target_unit])=>Object.freeze({label,quantity,factor,table_unit,target_unit}));
export const actuatorTargets=Object.freeze([...legacyTargets,...historyTargets]);
const targets=new Map(actuatorTargets.map(t=>[t.label.toLowerCase(),t]));
const periodic=new Set(['reference.alpha','attitude.bank','attitude.heading']);
const openAngles=new Set(['reference.beta','attitude.elevation','flight_path']);

export const actuatorSettings=`
<details class="advanced" id="time-actuator-settings"><summary>Solve actuators from time targets</summary>
  <label class="field-label" for="time-actuators">One row: actuator, target, constant value / relative-table base</label>
  <textarea id="time-actuators" aria-label="Time actuator targets" spellcheck="false" placeholder="E1 Ax 0&#10;F1 My 0"></textarea>
  <p class="small muted">Use a declared F# flap or E# engine. Each actuator and target may appear once. Blank adds no inverse actuator targets.</p>
  <p class="small muted">Loads: Fx/Fy/Fz (input F), Mx/My/Mz (input F·L), L (lift at N=1, input F). Accelerations: Ax/Ay/Az and Ar (input L/T²), Gx/Gy/Gz (deg/input T²). An Ax/Ay/Az or Gx/Gy/Gz target requires that component to be solved from a net load in free or mixed motion.</p>
  <p class="small muted">Airflow: V (equivalent airspeed, input L/T), A (alpha, deg), B (beta, deg), at the body velocity reference including local Earth gust. V uses |relative velocity| × √(ρ/ρ₀); exact ASWING indicated-airspeed parity is unverified. Ga (climb angle, deg) uses stationary-air Earth velocity at that reference.</p>
  <p class="small muted">Motion: Wx/Wy/Wz (body angular-velocity components, deg/input T), RX/RY/RZ (body-origin Earth position, input L), Ex/Ey/Ez (bank/elevation/heading, deg). Angular velocity components are not Euler-angle rates. A, Ex and Ez use [−180, 180] degrees; B, Ey and Ga require (−90, 90) degrees. V must be positive. Multi-turn angle histories are not defined.</p>
  <details class="advanced"><summary>Explicit Earth-vector target names</summary><p class="small muted">These extensions use the full name with .x, .y or .z: velocity_earth (stationary-air velocity at the velocity reference, input L/T), rates_earth (angular velocity, rad/input T), acceleration_earth (absolute acceleration at the acceleration reference, input L/T²), angular_acceleration_earth (angular acceleration, rad/input T²). Example: E1 velocity_earth.y 0. Earth-vector angular units are radians.</p></details>
  <p class="small muted">Add a forcing column with the same target name to vary it over time. A + column adds to the row value above; an absolute column supplies the target directly. The solver finds actuator settings while retaining force balance and trajectory equations. A solved actuator cannot also have its own forcing column or feedback law. A target column and a controller command cannot share ownership.</p>
  <p class="small muted">Cold kinematic initialization holds the entered frame position, attitude, velocity and angular velocity, and solves the initial elastic shape and actuator settings from the initial targets. Incompatible initial targets are rejected. An ordinary saved-equilibrium launch preserves its initial physical state; new time inputs apply after that snapshot. For a supported saved-equilibrium history launch, snapshot 0 is the completed right state after applying the initial history; the original before-input snapshot is retained separately. The saved physical state is held while actuator settings and initial rates are completed. Supported initializations, transitions and continuations depend on the selected history.</p>
</details>`;

export function parseActuatorTargets(source,model=null){
  if(typeof source!=='string')throw new Error('Time actuator targets must be text.');
  const variables=new Set(),quantities=new Set(),rows=[];
  for(const [i,raw] of source.split(/\r?\n/).entries()){
    const text=raw.split(/[#!%]/,1)[0].trim();if(!text)continue;
    const fields=text.split(/\s+/),match=/^([FE])([1-9]\d*)$/i.exec(fields[0]);
    const prefix=`Time actuator row ${i+1}: `;
    if(fields.length!==3||!match||!/^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?$/.test(fields[2])||!Number.isFinite(Number(fields[2])))
      throw new Error(prefix+'enter an actuator, supported target and finite value, for example E1 Ax 0.');
    const target=targets.get(fields[1].toLowerCase());
    if(!target)throw new Error(prefix+`unsupported target ${fields[1]}; use a listed target label or explicit Earth-vector name.`);
    const kind=match[1].toUpperCase(),index=Number(match[2]),value=Number(fields[2]);
    if(!Number.isSafeInteger(index))throw new Error(prefix+'invalid actuator index.');
    if(target.quantity==='reference.equivalent_airspeed'&&value<=0)throw new Error(prefix+'V equivalent-airspeed target must be positive.');
    if(periodic.has(target.quantity)&&Math.abs(value)>180)throw new Error(prefix+`${target.label} requires the principal range [−180, 180] degrees; multi-turn histories are not defined.`);
    if(openAngles.has(target.quantity)&&Math.abs(value)>=90)throw new Error(prefix+`${target.label} requires the nonsingular range (−90, 90) degrees.`);
    if(model){
      const available=kind==='F'?model.controls:model.engine_controls.map(e=>typeof e==='number'?e:e.index);
      if(!available.includes(index))throw new Error(prefix+`${kind}${index} is not declared in this aircraft.`);
    }
    const variable=(kind==='F'?'control.':'power.')+index;
    if(variables.has(variable)||quantities.has(target.quantity))throw new Error(prefix+'each time actuator and target may appear only once.');
    variables.add(variable);quantities.add(target.quantity);
    rows.push({variable,quantity:target.quantity,target:value*target.factor});
  }
  return rows;
}
