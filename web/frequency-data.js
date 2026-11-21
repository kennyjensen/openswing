import {feedbackUnit} from './feedback-results.js';
import {sensorFields} from './sensor-results.js';

// Display conversion only. Saved responses and CSV retain their native units.
export function displayResponseUnit(unit,angleUnits='radians'){
  return angleUnits==='degrees'&&/^rad(?=\/|\s|$)/.test(unit)
    ? {unit:unit.replace(/^rad/,'deg'),scale:180/Math.PI} : {unit,scale:1};
}

export function complexGain(value){
  if(!value||!Number.isFinite(value.real)||!Number.isFinite(value.imag))return null;
  const magnitude=Math.hypot(value.real,value.imag);
  return {...value,magnitude,db:magnitude>0?20*Math.log10(magnitude):null,phase:magnitude>0?Math.atan2(value.imag,value.real)*180/Math.PI:null};
}
export const unitFor=(group,key,controller)=>{
  if(group==='feedback')return feedbackUnit(controller,key);
  if(group==='sensors')return sensorFields.find(f=>f[0]===key)?.[2]??'file units';
  if(group==='global')return key.startsWith('C')?'dimensionless':key.includes('moment')?'input F·L':'input F';
  if(group==='operating')return key.startsWith('power.')?'file engine setting':key.startsWith('control.')?'file flap setting':key.startsWith('angular_acceleration.')?'rad/T²':key.startsWith('acceleration.')?'L/T²':key.startsWith('rates.')?'rad/T':key.startsWith('position_earth.')?'input L':key==='speed'?'L/T':'deg';
  if(group==='strips'&&['cm','f_aero','f_reac','da_eff','length','normal_speed','normal_mach','relative_velocity'].includes(key))return {cm:'dimensionless',f_aero:'input F/L',f_reac:'input F/L',da_eff:'rad',length:'input L',normal_speed:'L/T',normal_mach:'dimensionless',relative_velocity:'L/T'}[key];
  if(group==='sections'&&key==='moment_axes')return 'input F·L';
  if(group==='sections'&&key==='distributed_gravity_normal')return 'input F/L';
  return {displacement:'input L',rotation:'rad',velocity:'L/T',rates:'rad/T',force:'input F',moment:'input F·L',force_local:'input F',moment_local:'input F·L',circulation:'L²/T',cl:'dimensionless',apparent_force:'input F',strain:'dimensionless',curvature_change:'1/L',axial_strain_tension:'dimensionless',shell_strain:'dimensionless',shell_shear_stress:'F/L²',velocity_origin_body:'L/T',rates_body:'rad/T',position_earth:'input L',attitude_rad:'rad'}[key]??'file units';
};

// Every trace refers to one independently solved input. No summation or shape
// normalization is implied by putting several transfer functions on a plot.
export function traceKey(s){return s.overlay?`overlay:${s.id}`:JSON.stringify([s.display??'response',s.inputName,s.group,s.key,s.component??null,s.station??null]);}
export function canonicalTrace(result,selection){
  if(selection.overlay)return selection;
  const s={display:'response',component:null,station:null,...selection};
  if(s.display==='broken_loop'){
    const match=result.inputs.find(c=>c.name===s.inputName)?.broken_loop_output;
    Object.assign(s,{group:match?.group??'',key:match?.key??'',component:match?.component??null,station:null});
  }
  return s;
}
export function frequencyValue(result,point,selection){
  const input=result.inputs.findIndex(c=>c.name===selection.inputName),response=point.responses?.[input];
  if(!response?.output)return {error:response?.error??point.error??'Response is unavailable.'};
  if(selection.display==='broken_loop'){
    const value=response.broken_loop;
    return value?.available?complexGain(value.value)??{error:'Broken-loop response is not finite.'}:{error:value?.error??'No matched broken-loop response.'};
  }
  let row=response.output[selection.group];if(Array.isArray(row))row=row[selection.station];
  const v=row?.[selection.key],real=selection.component==null?v?.real:v?.real?.[selection.component],imag=selection.component==null?v?.imag:v?.imag?.[selection.component];
  return complexGain({real,imag})??{error:'Selected output is unavailable or undefined at this sample.'};
}
export function frequencySeries(result,selection,unwrap=true){
  let last=null;
  return (selection.overlay?selection.samples:result.samples).map((point,index)=>{
    const value=selection.overlay?(complexGain(point)??{error:point.error??'External sample is unavailable.'}):frequencyValue(result,point,selection);
    if(value.phase==null){last=null;return {index,omega:point.omega,...value,phase:null};}
    if(unwrap&&last!=null)value.phase+=360*Math.round((last-value.phase)/360);
    last=value.phase;return {index,omega:point.omega,...value};
  });
}
export function traceInfo(result,selection){
  if(selection.overlay)return {selection,input:selection.input,unit:selection.unit,kind:selection.kind,label:`External · ${selection.label} → ${selection.targetLabel}`,station:selection.stationLabel,groupKey:JSON.stringify([selection.kind,selection.unit])};
  const s=canonicalTrace(result,selection),input=result.inputs.find(c=>c.name===s.inputName),initial=input?.kind==='initial',broken=s.display==='broken_loop';
  const unit=broken?'dimensionless':`${unitFor(s.group,s.key,result.controller)}${initial?' · input T':''} / (${input?.unit??'unknown input unit'})`;
  const kind=broken?'Broken loop · 1 − u/x':initial?'Initial-state spectrum':'Unit input transfer';
  let row=result.samples.find(p=>p.responses?.some(r=>r.output?.[s.group]))?.responses.find(r=>r.output?.[s.group])?.output?.[s.group];
  row=Array.isArray(row)?row[s.station]:null;
  const location=s.group==='nodes'?result.base.nodes?.find(n=>n.index===row?.index):row;
  const station=location?`${s.group==='sensors'?`Sensor ${location.index} · `:''}Beam ${location.beam} · t=${location.t}`:'';
  const axes=s.group==='sensors'?(sensorFields.find(f=>f[0]===s.key)?.[3]??[]):s.group==='sections'?['c','s','n']:['x','y','z'];
  const output=broken?(input?.broken_loop_output?.name??'unmatched response'):`${s.group} · ${s.key.replaceAll('_',' ')}${s.component==null?'':` ${axes[s.component]??s.component}`}`;
  const label=`${s.inputName} → ${output}${station?` · ${station}`:''}${initial?` · σ=${input.laplace_shift} /T`:''}`;
  return {selection:s,input,unit,kind,label,station,groupKey:JSON.stringify([kind,unit])};
}
const csv=row=>row.map(x=>'"'+String(x??'').replaceAll('"','""')+'"').join(',');
export function comparisonCSV(result,traces,unwrap=true){
  const header=['display','formula','input','input unit','output group','output','component','station index','station','response unit','omega [rad/T]','frequency [cycles/T]','Laplace damping [1/T]','real','imag','magnitude','gain [dB]','phase [deg]','phase convention','source','source label','source mapping','series id','status'];
  const rows=[csv(header)];
  for(const selection of traces){
    const info=traceInfo(result,selection),s=info.selection;
    for(const v of frequencySeries(result,s,unwrap))rows.push(csv([info.kind,s.display==='broken_loop'?'1 - u/x':info.input?.kind==='initial'?'X(s) / profile amplitude':'x/u',s.inputName,info.input?.unit,s.group,s.key,s.component,s.station,info.station,info.unit,v.omega,v.omega/(2*Math.PI),info.input?.laplace_shift??0,v.real,v.imag,v.magnitude,v.db,v.phase,unwrap?'unwrapped per trace; reset after gaps or zero':'wrapped ±180 degrees',s.overlay?'external':'computed',s.overlay?s.label:'',s.overlay?JSON.stringify(s.source):'',traceKey(s),v.error??(v.magnitude===0?'resolved zero; phase and dB undefined':'resolved')]));
  }
  return rows.join('\n')+'\n';
}
