import {loadingQuantities,loadingValue} from './loading-data.js';

const finite=Number.isFinite;
const get=(row,path)=>path.split('.').reduce((v,k)=>v?.[k],row);
const component=(delta,index)=>index===undefined?delta:delta&&{real:delta.real?.[index],imag:delta.imag?.[index]};
const pair=delta=>finite(delta?.real)&&finite(delta?.imag);

// The same exp(+i phase) convention and display scale as the aircraft geometry.
// Keep saved equilibrium/results immutable. Missing derivatives are not zeros.
export function linearValue(base,delta,{phase,scale}){
  if(!finite(base)||!pair(delta)||!finite(phase)||!finite(scale))return {value:null};
  const amplitude=Math.abs(scale)*Math.hypot(delta.real,delta.imag);
  return {value:base+scale*(delta.real*Math.cos(phase)-delta.imag*Math.sin(phase)),
    lower:base-amplitude,upper:base+amplitude};
}
function absolute(value){
  if(!finite(value.value))return value;
  return {value:Math.abs(value.value),lower:value.lower<=0&&value.upper>=0?0:Math.min(Math.abs(value.lower),Math.abs(value.upper)),
    upper:Math.max(Math.abs(value.lower),Math.abs(value.upper))};
}
function scaled(value,scale){
  if(!finite(value.value))return {value:null};
  return {value:value.value*scale,lower:Math.min(value.lower*scale,value.upper*scale),upper:Math.max(value.lower*scale,value.upper*scale)};
}
function rowsByStation(rows){return new Map((rows??[]).map(row=>[`${row.beam}:${row.t}`,row]));}
export function spanRange(samples){
  const values=samples.flatMap(row=>[row.lower,row.upper]).filter(finite);
  return values.length?[Math.min(0,...values),Math.max(0,...values)]:null;
}

export function linearLoadingSamples(rows,linear,quantity){
  const q=loadingQuantities[quantity],deltas=rowsByStation(linear.output?.strips);
  return rows.map(row=>{
    const delta=deltas.get(`${row.beam}:${row.t}`);
    let perturbation=component(delta?.[q.path],q.component);
    if(q.axis!==undefined){
      const force=component(delta?.force,q.axis),length=delta?.length;
      // d(F/l) = dF/l - F dl/l²; dividing an animated force by the
      // equilibrium length would omit extension of the strip.
      perturbation=pair(force)&&pair(length)&&row.length>0&&finite(row.force?.[q.axis])?
        Object.fromEntries(['real','imag'].map(k=>[k,force[k]/row.length-row.force[q.axis]*length[k]/row.length**2])):null;
    }
    if(pair(perturbation))perturbation={real:perturbation.real*(q.scale??1),imag:perturbation.imag*(q.scale??1)};
    return {t:row.t,...linearValue(loadingValue(row,quantity),perturbation,linear)};
  });
}

export function linearStructureSamples(rows,linear,key,scale=1){
  const deltas=rowsByStation(linear.output?.sections);
  return rows.map(row=>{
    const delta=deltas.get(`${row.beam}:${row.t}`),[field,index]=key.split('.');
    const value=(base,d)=>linearValue(base,d,linear);
    let sample;
    if(key==='shell.axial_strain_bound'){
      // A bound is a sum of absolute signed contributions, not a signed
      // sinusoid (in particular about a zero-strain equilibrium).
      const terms=[value(row.axial_strain_tension,delta?.axial_strain_tension),
        scaled(value(row.curvature_change?.[2],component(delta?.curvature_change,2)),row.shell?.c),
        scaled(value(row.curvature_change?.[0],component(delta?.curvature_change,0)),-row.shell?.n)].map(absolute);
      sample=finite(row.shell?.axial_strain_bound)&&terms.every(t=>finite(t.value))?
        {value:terms.reduce((a,t)=>a+t.value,0),lower:0,upper:terms.reduce((a,t)=>a+t.upper,0)}:{value:null};
    }else if(field==='shell'){
      const strain=index==='axial_strain';
      sample=value(row.shell?.[strain?'axial_strain':'shear_stress'],delta?.[strain?'shell_strain':'shell_shear_stress']);
      if(index==='shear_stress_abs')sample=absolute(sample);
    }else{
      const d=field==='distributed_gravity'?delta?.distributed_gravity_normal:component(delta?.[field],index===undefined?undefined:Number(index));
      sample=value(get(row,key),d);
    }
    return {t:row.t,t0:row.t0,t1:row.t1,...scaled(sample,scale)};
  });
}

export function linearShoulderSamples(rows,linear,axis){
  const deltas=rowsByStation(linear.output?.body_shoulders);
  return rows.map(row=>({t:row.t,...linearValue(row.force?.[axis],component(deltas.get(`${row.beam}:${row.t}`)?.force,axis),linear)}));
}
