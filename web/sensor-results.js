const $=id=>document.getElementById(id);
export const sensorFields=[
  ['speed','Airspeed','input L/T'],['alpha','Flow alpha','deg'],['beta','Flow beta','deg'],
  ['bank','Sensor bank','deg'],['elevation','Sensor elevation','deg'],['heading','Sensor heading','deg'],
  ['air_velocity_sensor','Air velocity in sensor axes','input L/T',['V','β','α']],
  ['acceleration_sensor','Specific force (a − g)','input L/T²',['V','β','α']],
  ['angular_acceleration_sensor','Absolute angular acceleration','rad/input T²',['V','β','α']],
  ['rates_sensor','Absolute rotation rate','rad/input T',['V','β','α']],
  ['position_earth','GPS position','input L',['X','Y','Z']],['velocity_earth','GPS velocity','input L/T',['X','Y','Z']],
  ['anchor_position_body','Anchor position in body axes','input L',['x','y','z']],
  ['anchor_velocity_body','Anchor relative velocity','input L/T',['x','y','z']],
  ['displacement_body','Anchor elastic displacement','input L',['x','y','z']],
  ['position_body','Pylon tip position in body axes','input L',['x','y','z']],
  ['force_local','Beam force at anchor','input F',['c','s','n']],['moment_local','Beam moment at anchor','input F·L',['c','s','n']],
  ['strain','Adjacent material strain','dimensionless',['c','s','n']],['curvature_change','Adjacent curvature change','rad/input L',['c','s','n']],
  ['circulation','Adjacent circulation','input L²/T'],['shell_strain','Adjacent signed shell strain','dimensionless'],
  ['shell_shear_stress','Adjacent shell shear stress','input F/L²'],
];
export const sensorQuantities=sensorFields.flatMap(([key,label,unit,axes])=>axes?axes.map((a,i)=>[`${key}.${i}`,`${label} ${a}`,unit]):[[key,label,unit]]);
const frameDependentFields=new Set(['alpha','beta','bank','air_velocity_sensor','acceleration_sensor','angular_acceleration_sensor','rates_sensor']);
export function sensorFieldAvailable(sensor,field){
  if(sensor?.axes_available===false&&frameDependentFields.has(field))return false;
  if(sensor?.v_axis_available===false&&['heading','elevation'].includes(field))return false;
  // Inspection rows and older saved results need not contain measured fields.
  return !Object.hasOwn(sensor??{},field)||sensor[field]!=null;
}
export function sensorAvailabilityDescription(base,complex=false){
  const axes=base?.axes_available===false?` Sensor frame unavailable: ${base.axes_unavailable_reason??'the recorded directions do not define a sensor frame'}.`:'';
  const singular=base?.attitude_singular?(base.v_axis_available===false?' Sensor attitude angles are undefined because the sensor V direction is unavailable.':complex?' Euler-angle perturbations are undefined at this vertical sensor attitude.':' Bank and heading are undefined at this vertical sensor attitude.'):'';
  const zeroFlow=base?.flow_singular===undefined?base?.axes_available!==false&&base?.speed!=null&&base?.alpha==null:base.flow_singular===true;
  return axes+singular+(zeroFlow?(complex?' Airspeed and flow-angle perturbations are undefined at zero airflow.':' Flow angles are undefined at zero airspeed.'):'');
}
export const sensorPane=`
<div id="pane-sensors" class="tab-pane sensor-pane" role="tabpanel" aria-labelledby="tab-sensors" hidden>
  <p id="sensor-summary" class="small muted">Sensor records in the ASW file define moving pitot/vane, inertial, GPS and structural measurements.</p>
  <div class="time-toolbar"><label>Sensor<select id="sensor-select" aria-label="Selected sensor"></select></label><button id="sensor-csv" disabled>Sensor CSV</button></div>
  <p id="sensor-detail" class="small muted"></p><div id="sensor-table" class="derivative-table-wrap"></div>
  <p class="small muted">Specific force is acceleration minus gravity: level flight reads upward g and free fall reads zero. Sensor axes follow the pylon. GPS and inertial outputs refer to its tip; body-relative motion and beam loads refer to its anchor. Load traces and strain/circulation sample locations are retained in JSON. <span id="sensor-strain-location-note">Strain/stress use the adjacent material midpoint.</span> Time history, Eigenmodes and Bode response also offer sensor quantities.</p>
</div>`;
export const sensorStrainDescription=base=>base?.strain_sample_location==='selected adjacent element constitutive average'?'Mechanical and shell axial strains use the selected adjacent constitutive interval, with averaged shell properties. Shell shear stress uses total anchor torque. Damped endpoint mechanical strains are unavailable.':base?.strain_sample_location==='one-sided sensor anchor section'?'Strain/stress use the one-sided sensor anchor section.':'Strain/stress use the adjacent material midpoint.';
const fmt=x=>Number.isFinite(x)?x.toPrecision(7):'—';
const get=(value,key)=>key.split('.').reduce((v,k)=>v?.[k],value);
const csv=row=>row.map(x=>'"'+String(x??'').replaceAll('"','""')+'"').join(',');
export function createSensorResults(getState,download,getModeIndex=()=>0){
  let identity=null,tag='',context=null;
  function current(){
    const state=getState();
    if(state.frequency){
      const input=Number($('frequency-input').value),sample=state.frequency.samples[Number($('frequency-sample').value)];
      return {rows:sample?.responses[input]?.output.sensors??[],base:state.frequency.base.sensors,
        complex:true,label:`Harmonic perturbation · ω=${fmt(sample?.omega)} rad/input T · ${state.frequency.inputs[input]?.name??''}`,
        normalization:`per unit ${state.frequency.inputs[input]?.unit??'input'}; independent of playback amplitude and phase`};
    }
    if(state.modal){
      const index=getModeIndex(),mode=state.modal.modes[index];
      return {rows:mode?.output.sensors??[],base:state.modal.base.sensors,complex:true,
        label:`Mode ${index+1} · complex sensor perturbation`,normalization:'per saved right eigenvector; independent of display scale and phase'};
    }
    return {rows:state.result?.sensors??[],base:state.result?.sensors,complex:false,
      label:state.trajectory?`Computed time state · t=${fmt(state.result?.time)} input T`:'Steady sensor measurements',normalization:'physical input units'};
  }
  function values(){
    const sensor=context.rows.find(s=>s.index===Number($('sensor-select').value));if(!sensor)return [];
    return sensorQuantities.map(([key,label,unit])=>{
      const [field,axis]=key.split('.'),v=sensor[field];
      const real=context.complex?(axis==null?v?.real:v?.real?.[axis]):get(sensor,key),imag=context.complex?(axis==null?v?.imag:v?.imag?.[axis]):null;
      return {key,label,unit,real,imag};
    });
  }
  function table(){
    $('sensor-table').replaceChildren();$('sensor-detail').textContent='';$('sensor-strain-location-note').textContent=sensorStrainDescription(null);if(!context.rows.length)return;
    const id=Number($('sensor-select').value),base=context.base?.find(s=>s.index===id);
    $('sensor-strain-location-note').textContent=sensorStrainDescription(base);
    $('sensor-detail').textContent=`Sensor ${id} · beam ${base.beam}, t=${fmt(base.t)} · ${base.flow_mode} airflow. ${base.load_trace?`Loads: ${base.load_trace} trace. Strain sample t=${fmt(base.strain_sample_t)}; circulation sample t=${fmt(base.circulation_sample_t)}.`:'Structural loads unavailable for a rigid-only solve.'}${sensorAvailabilityDescription(base,context.complex)}`;
    const table=document.createElement('table'),thead=document.createElement('thead'),header=document.createElement('tr');
    for(const name of ['Measurement','Unit',context.complex?'Real':'Value',...(context.complex?['Imaginary']:[])]){const th=document.createElement('th');th.textContent=name;header.append(th);}thead.append(header);table.append(thead);
    const body=document.createElement('tbody');
    for(const row of values()){
      const tr=document.createElement('tr');for(const value of [row.label,row.unit,fmt(row.real),...(context.complex?[fmt(row.imag)]:[])]){const td=document.createElement('td');td.textContent=value;tr.append(td);}body.append(tr);
    }
    table.append(body);$('sensor-table').append(table);
  }
  function render(){
    const next=current();if(next.rows===identity&&next.label===tag)return;identity=next.rows;tag=next.label;context=next;
    const selected=$('sensor-select').value;$('sensor-select').replaceChildren();
    for(const s of context.rows){const o=document.createElement('option');o.value=s.index;o.textContent=`Sensor ${s.index} · beam ${s.beam} · t=${fmt(s.t)}`;$('sensor-select').append(o);}
    if(context.rows.some(s=>String(s.index)===selected))$('sensor-select').value=selected;
    $('sensor-csv').disabled=!context.rows.length;
    $('sensor-summary').textContent=context.rows.length?`${context.label} · ${context.normalization}.`:'No sensor measurements in the current result. Add Sensor records to the ASW file, then run an analysis; a missing harmonic frequency has no sensor response.';
    table();
  }
  $('sensor-select').onchange=table;
  $('sensor-csv').onclick=()=>download('openswing-sensor.csv',[csv(['sensor','context','normalization','quantity','unit','real',...(context.complex?['imaginary']:[])]),...values().map(v=>csv([$('sensor-select').value,context.label,context.normalization,v.key,v.unit,v.real,...(context.complex?[v.imag]:[])]))].join('\n')+'\n','text/csv');
  return {render};
}
