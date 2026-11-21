import {validateConfiguration,validateJSON} from './project-data.js';
import {validateEquilibriumPacket,checkpointRecord} from './saved-state-data.js';
import {sourceNumerics,vacuumNumerics,stillAirNumerics,movingVacuumNumerics,airflowNumerics,numericalMode,numericalModeLabel,sameNumerics,assertNumericalIdentity,assertVacuumRequest,assertStillAirRequest,assertStillAirIdentity,assertMovingVacuumRequest,assertMovingTimeRequest,movingVacuumFrame,assertSourceFrequencyRequest,assertAirflowRequest} from './numerical-policy.js';
const plain=x=>x!==null&&typeof x==='object'&&!Array.isArray(x)&&Object.getPrototypeOf(x)===Object.prototype;
const fail=message=>{throw new Error(message);};
const kinds={rigid:'rigid_steady',mounted:['mounted_static','constrained_static'],structural:'structural_static',time:'time_response',modes:'eigenmodes',frequency:'frequency_response'};
const digestPattern=/^[a-f0-9]{64}$/;
export function canonicalJSON(value){
  const order=x=>Array.isArray(x)?x.map(order):plain(x)?Object.fromEntries(Object.keys(x).sort().map(k=>[k,order(x[k])])):x;
  return JSON.stringify(order(value));
}
function content(solution){return Object.fromEntries(['kind','configuration','data','auxiliary','view','provenance'].map(k=>[k,solution[k]]));}
export async function solutionChecksum(solution){
  return digest(content(solution));
}
async function digest(value){
  const bytes=new TextEncoder().encode(canonicalJSON(value));
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
}
export const kernelFingerprint=p=>digest({modules:p.modules,runtime:p.runtime});
export function portableResult(result){
  const copy=structuredClone(result);
  // UI requests may own an omitted optional property (for example derivatives:
  // undefined). Retain exactly the request sent as JSON to the worker.
  if(copy?.request)copy.request=JSON.parse(JSON.stringify(copy.request));
  // A frequency handle identifies a live worker object, not a portable model.
  if(copy)delete copy.frequency_session;
  return copy;
}
// Half-open snapshot ranges preserve the origin of retained states when a
// continuation uses a newer kernel. Adjacent equal sources share one range.
export function continuedHistorySources(parent,index,segment,parentCount=parent.snapshots.length,segmentCount=segment.snapshots.length){
  const sources=parent.history_sources??[{start_snapshot:0,end_snapshot:parentCount,software_provenance:parent.software_provenance??null}];
  const retained=sources.filter(s=>s.start_snapshot<=index).map(s=>({...structuredClone(s),end_snapshot:Math.min(s.end_snapshot,index+1)}));
  const next={start_snapshot:index+1,end_snapshot:index+segmentCount,software_provenance:structuredClone(segment.software_provenance??null)};
  if(next.end_snapshot>next.start_snapshot){
    const last=retained.at(-1);
    if(last&&canonicalJSON(last.software_provenance)===canonicalJSON(next.software_provenance))last.end_snapshot=next.end_snapshot;
    else retained.push(next);
  }
  return retained;
}
export function validateSolution(value){
  validateJSON(value);
  if(!plain(value)||Object.keys(value).some(k=>!['id','name','created_at','kind','configuration','data','auxiliary','view','provenance','checksum'].includes(k)))fail('Invalid saved solution record.');
  if(typeof value.id!=='string'||!/^[a-zA-Z0-9_-]{1,100}$/.test(value.id))fail('Invalid solution identifier.');
  if(typeof value.name!=='string'||!value.name.trim()||value.name.length>160)fail('Invalid solution name.');
  if(typeof value.created_at!=='string'||!Number.isFinite(Date.parse(value.created_at)))fail('Invalid solution creation date.');
  if(!Object.hasOwn(kinds,value.kind))fail('Unsupported saved analysis kind.');
  const configuration=validateConfiguration(value.configuration),d=value.data;
  if(!plain(d)||!([kinds[value.kind]].flat().includes(d.analysis))||!plain(d.request)||d.request.source!==configuration.source)fail('Saved solution and its ASW calculation request do not match.');
  if(!sameNumerics(configuration.numerics,d.request.numerics)||!sameNumerics(configuration.numerics,d.numerics))fail('Saved solution, calculation request and configuration numerical settings do not match.');
  const sourceVacuum=vacuumNumerics(configuration.numerics),sourceStillAir=stillAirNumerics(configuration.numerics),sourceMoving=movingVacuumNumerics(configuration.numerics),sourceAirflow=airflowNumerics(configuration.numerics),sourceSteady=sourceAirflow&&value.kind==='mounted',sourceTime=(sourceMoving||sourceAirflow)&&value.kind==='time',sourceModal=sourceVacuum||sourceStillAir||((sourceMoving||sourceAirflow)&&!sourceTime&&!sourceSteady);
  const sourceFrequency=sourceModal&&value.kind==='frequency';
  if(sourceNumerics(configuration.numerics)&&!(sourceSteady?configuration.fields.mode==='mounted'&&d.request.mode==='mounted'&&d.request.action==='solve':sourceFrequency?configuration.fields.mode==='frequency'&&d.request.mode==='frequency'&&d.request.action==='frequency':sourceTime?configuration.fields.mode==='time'&&['time','launch_time','resume_time'].includes(d.request.action):value.kind===numericalMode(configuration.numerics)&&d.request.mode===numericalMode(configuration.numerics)&&d.request.action===(sourceModal?'modes':'solve')))fail(`The selected ASWING saved solution requires ${numericalModeLabel(configuration.numerics)}.`);
  if(sourceFrequency){
    assertSourceFrequencyRequest(d.request,configuration.numerics);
    if(d.frame_mode!==configuration.fields['frequency-frame']||d.frame_mode!==d.request.frequency.frame)
      fail('Saved source frequency frame does not match its configuration.');
  }
  if(sourceAirflow){
    assertAirflowRequest(d.request);
    if(d.structural_operator!==configuration.numerics.structural_operator||d.fluid!=null||d.base?.fluid!=null)
      fail('Saved source airflow result has incompatible equations, fluid or feedback settings.');
    const controller=sourceSteady?d.request.controller:sourceTime?d.restart_context?.setup?.controller:d.request[sourceFrequency?'frequency':'modes']?.controller;
    if(canonicalJSON(d.controller?.definition??null)!==canonicalJSON(controller??null))
      fail('Saved source airflow controller does not match its request or restart setup.');
    if(sourceSteady&&canonicalJSON(d.equilibrium_state?.launch?.controller??null)!==canonicalJSON(controller??null))
      fail('Saved source steady controller does not match its time-launch setup.');
    if(sourceTime){
      const original=d.request.action==='time'?d.request.time.controller:d.request.action==='launch_time'
        ?d.request.equilibrium_state?.launch?.controller:d.request.checkpoint?.context?.setup?.controller;
      if(canonicalJSON(controller??null)!==canonicalJSON(original??null))
        fail('Saved source airflow restart controller does not match its original setup.');
    }
    if(!sourceTime&&!sourceSteady){
      const options=d.request[sourceFrequency?'frequency':'modes'],prefix=sourceFrequency?'frequency':'modal';
      if(d.vacuum!==false||d.frame_mode!==options.frame||options.frame!==configuration.fields[`${prefix}-frame`])
        fail('Saved source airflow frame or medium does not match its configuration.');
    }
  }
  if(sourceVacuum){
    if(!sourceFrequency)assertVacuumRequest(d.request);
    if(d.vacuum!==true||d.frame_mode!=='fixed'||d.controller!=null||d.fluid!=null)fail('Saved ASWING vacuum result has incompatible flow, frame or controller settings.');
    if(d.structural_operator!==configuration.numerics.structural_operator)fail('Saved result structural equations do not match its numerical settings.');
  }
  if(sourceStillAir){
    if(!sourceFrequency)assertStillAirRequest(d.request);
    const density=d.request[sourceFrequency?'frequency':'modes'].quiescent_density;
    if(d.vacuum!==false||d.frame_mode!=='fixed'||d.controller!=null||d.condition!=null
        ||d.structural_operator!==configuration.numerics.structural_operator
        ||Number(configuration.fields['modal-quiescent-density'])!==density
        ||d.fluid?.kind!=='quiescent'||d.fluid.density!==density
        ||d.base?.fluid?.kind!=='quiescent'||d.base.fluid.density!==density)
      fail('Saved ASWING still-air result has incompatible density, flow, frame or controller settings.');
  }
  if(sourceMoving&&!sourceTime){
    if(!sourceFrequency)assertMovingVacuumRequest(d.request);
    const prefix=sourceFrequency?'frequency':'modal',options=d.request[sourceFrequency?'frequency':'modes'],fields=configuration.fields,expected=movingVacuumFrame(fields);
    if(d.vacuum!==true||d.fluid!=null||d.base?.fluid!=null||d.controller!=null||d.condition!=null
        ||d.frame_mode!==options.frame||options.frame!==fields[`${prefix}-frame`]
        ||d.structural_operator!==configuration.numerics.structural_operator
        ||Object.entries(expected).some(([key,value])=>canonicalJSON(options[key])!==canonicalJSON(value)))
      fail('Saved moving vacuum result, request and configuration frame motion do not match.');
    const targets={};
    if(options.frame==='mixed')for(const kind of ['F','M'])for(const axis of ['x','y','z'])
      if(fields[`${prefix}-load-${kind}${axis}`]==='load')targets[`${kind==='F'?'force':'moment'}.${axis}`]=Number(fields[`${prefix}-target-${kind}${axis}`]);
    if(canonicalJSON(options.load_targets??{})!==canonicalJSON(targets))fail('Saved moving vacuum frame load targets do not match the configuration.');
  }
  if(sourceTime){
    assertMovingTimeRequest(d.request,{airflow:sourceAirflow});
    assertNumericalIdentity(configuration.numerics,d.restart_context?.identity);
    if((!sourceAirflow&&d.controller!=null)||d.fluid!=null||(sourceAirflow?!plain(d.restart_context?.setup?.condition):d.condition!=null||d.restart_context?.setup?.condition!==null)
        ||(!sourceAirflow&&d.restart_context.setup.controller!=null)||(d.restart_context.setup.actuator_constraints??[]).length)
      fail('Saved source time result contains incompatible flow, feedback or actuator setup.');
    const options=d.request.time,fields=configuration.fields;
    if(!['prescribed','free','mixed'].includes(d.frame_mode)||d.frame_mode!==d.restart_context.setup.frame)
      fail('Saved moving vacuum time frame and restart setup do not match.');
    if(sourceMoving&&d.request.action==='time'&&Object.entries(movingVacuumFrame(fields)).some(([key,v])=>canonicalJSON(options[key])!==canonicalJSON(v)))
      fail('Saved cold time motion and configuration do not match.');
    if(d.request.action!=='resume_time'){
      if((options.frame??'prescribed')!==fields['time-frame']||d.frame_mode!==(options.frame??'prescribed'))fail('Saved time frame and configuration do not match.');
      const targets={};
      if(fields['time-frame']==='mixed')for(const kind of ['F','M'])for(const axis of ['x','y','z'])
        if(fields[`time-load:${kind}${axis}`]==='load')targets[`${kind==='F'?'force':'moment'}.${axis}`]=Number(fields[`time-target:${kind}${axis}`]);
      if(canonicalJSON(options.load_targets??{})!==canonicalJSON(targets))fail('Saved time frame targets and configuration do not match.');
    }
    for(const snapshot of d.snapshots??[]){
      if(snapshot.structural_operator!==configuration.numerics.structural_operator)fail('Saved time snapshot equations do not match its policy.');
      // Dynamic snapshots own a checkpoint and its context, not a steady
      // equilibrium packet. Preserve the accepted state and method as emitted.
      const checkpoint=checkpointRecord(snapshot.restart,snapshot.restart_context??d.restart_context);
      if(sourceAirflow&&canonicalJSON(checkpoint.context.setup.controller??null)!==canonicalJSON(d.restart_context.setup.controller??null))
        fail('Saved source airflow snapshot controller does not match its restart setup.');
      assertNumericalIdentity(configuration.numerics,checkpoint.context.identity);
      assertNumericalIdentity(configuration.numerics,checkpoint.accepted_method?.accepted_inputs?.identity);
      if(snapshot.equilibrium_state!==undefined){validateEquilibriumPacket(snapshot.equilibrium_state);assertNumericalIdentity(configuration.numerics,snapshot.equilibrium_state.identity);}
    }
  }
  if(sourceNumerics(configuration.numerics)&&(sourceModal?d.base?.structural_operator:d.structural_operator)!==configuration.numerics.structural_operator)fail('Saved result structural equations do not match its numerical settings.');
  if(Object.hasOwn(d,'frequency_session'))fail('A saved solution cannot contain a live frequency session.');
  if(typeof d.converged!=='boolean')fail('Saved solution is missing its convergence status.');
  if(value.kind!=='frequency'&&!d.converged)fail('Only completed primary analyses can be archived.');
  const base=['modes','frequency'].includes(value.kind)?d.base:value.kind==='time'?d.snapshots?.[0]:d;
  if(!plain(base)||!plain(base.mass_properties)||!Array.isArray(base.limitations))fail('Saved solution is missing its physical base result.');
  if(base.equilibrium_state!==undefined){validateEquilibriumPacket(base.equilibrium_state);assertNumericalIdentity(configuration.numerics,base.equilibrium_state.identity);}
  else if(sourceNumerics(configuration.numerics)&&!sourceTime)fail('ASWING saved solution is missing its equilibrium identity.');
  if(sourceStillAir){
    const options=d.request[sourceFrequency?'frequency':'modes'];
    const factor=options.quiescent_body_added_mass_factor??1;
    assertStillAirIdentity(base.equilibrium_state,options.quiescent_density,factor);
    if(base.equilibrium_state.identity.quiescent_body_added_mass_factor!==undefined
        ||options.quiescent_body_added_mass_factor!==undefined){
      if(Number(configuration.fields['body-added-mass']??1)!==factor
          ||(d.fluid?.body_added_mass_factor??1)!==factor
          ||(base.fluid?.body_added_mass_factor??1)!==factor)
        fail('Still-air body coefficient does not match the configuration and result.');
    }
  }
  if(sourceNumerics(configuration.numerics)&&!sourceModal&&!sourceTime&&!sourceSteady&&base.equilibrium_state.launch!==undefined)fail('ASWING static saved solutions cannot contain a dynamic launch.');
  if(['rigid','mounted','structural'].includes(value.kind)&&(!Array.isArray(d.strips)||!Number.isFinite(d.residual)))fail('Incomplete saved steady result.');
  if(base.mass_properties.physical===false&&value.kind!=='structural')fail('Signed static loads cannot be stored as a physical dynamic or aerodynamic result.');
  if(value.kind==='time'&&(!Array.isArray(d.snapshots)||!d.snapshots.length||!plain(d.restart_context)||d.snapshots.some(s=>!Number.isFinite(s.time)||!Number.isFinite(s.residual))))fail('Incomplete saved time history.');
  if(value.kind==='time')for(const snapshot of d.snapshots){
    if(snapshot.restart?.version!=null)checkpointRecord(snapshot.restart,snapshot.restart_context??d.restart_context);
  }
  if(d.history_sources!==undefined){
    if(value.kind!=='time'||!Array.isArray(d.history_sources)||!d.history_sources.length)fail('Invalid retained-history provenance.');
    let end=0;
    for(const s of d.history_sources){if(!plain(s)||s.start_snapshot!==end||!Number.isInteger(s.end_snapshot)||s.end_snapshot<=end||s.end_snapshot>d.snapshots.length||!(s.software_provenance===null||plain(s.software_provenance)))fail('Invalid retained-history provenance.');end=s.end_snapshot;}
    if(end!==d.snapshots.length)fail('Incomplete retained-history provenance.');
  }
  if(value.kind==='modes'&&(!Array.isArray(d.modes)||!plain(d.diagnostics)))fail('Incomplete saved modal result.');
  if(value.kind==='frequency'&&(!Array.isArray(d.samples)||!d.samples.length||!Array.isArray(d.inputs)||!plain(d.diagnostics)))fail('Incomplete saved frequency result.');
  if(!plain(value.auxiliary)||Object.keys(value.auxiliary).some(k=>!['rom','stability','flow','comparison'].includes(k)))fail('Invalid saved supplementary results.');
  if((sourceStillAir||sourceMoving||sourceAirflow)&&['rom','stability','flow'].some(key=>value.auxiliary[key]!=null))fail('These ASWING modal results do not support ROM, stability-sweep or flow-survey supplements.');
  if(!plain(value.view)||Object.values(value.view).some(v=>typeof v!=='string'&&typeof v!=='boolean'&&!(Array.isArray(v)&&v.every(x=>typeof x==='string'))))fail('Invalid saved result-view settings.');
  const p=value.provenance;
  if(!plain(p)||p.format!=='openswing-kernel-provenance'||p.version!==1||!digestPattern.test(p.fingerprint)||!plain(p.modules)||!Object.keys(p.modules).length||Object.entries(p.modules).some(([name,hash])=>!/^\w+\.py$/.test(name)||!digestPattern.test(hash))||!plain(p.runtime)||['pyodide','python','numpy','scipy'].some(k=>typeof p.runtime[k]!=='string'||!p.runtime[k]))fail('Saved solution is missing its numerical-kernel provenance.');
  if(canonicalJSON(p)!==canonicalJSON(d.software_provenance))fail('Saved result provenance does not match its archive.');
  if(typeof value.checksum!=='string'||!digestPattern.test(value.checksum))fail('Invalid saved solution checksum.');
  return structuredClone({...value,name:value.name.trim(),configuration});
}
export async function sealSolution(value){
  const copy=structuredClone(value);copy.data=portableResult(copy.data);copy.checksum=await solutionChecksum(copy);return validateSolution(copy);
}
export async function verifySolution(value){
  const copy=validateSolution(value);
  if(await solutionChecksum(copy)!==copy.checksum)fail('Saved solution checksum mismatch. The stored calculation or context was changed.');
  if(await kernelFingerprint(copy.provenance)!==copy.provenance.fingerprint)fail('Saved numerical-kernel fingerprint does not match its source and runtime record.');
  for(const s of copy.data.history_sources??[])if(s.software_provenance&&await kernelFingerprint(s.software_provenance)!==s.software_provenance.fingerprint)fail('Retained-history numerical fingerprint mismatch.');
  return copy;
}
export function validateSolutionList(values){
  if(!Array.isArray(values)||values.length>200)fail('A project supports at most 200 saved solutions.');
  const out=values.map(validateSolution),ids=new Set(),names=new Set();
  for(const s of out){if(ids.has(s.id)||names.has(s.name))fail('Solution names and identifiers must be unique.');ids.add(s.id);names.add(s.name);}
  return out;
}
