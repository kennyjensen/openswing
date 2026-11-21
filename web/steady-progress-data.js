import {sameConfiguration,validateConfiguration,validateJSON} from './project-data.js';
import {sameNumerics,assertNumericalIdentity} from './numerical-policy.js';

const plain=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const fail=message=>{throw new Error(message);};
const operators=new Set(['midpoint-v1','drela-steady-zero-offset-v1','drela-steady-section-v1','drela-steady-coupled-v1','drela-moving-airflow-v1']);

export function steadyRequest(request) {
  // Match the JSON sent to the worker, preserving every defined setting.
  const base=JSON.parse(JSON.stringify(request,(_key,value)=>{
    if(typeof value==='number'&&!Number.isFinite(value))fail('Solve settings must be finite.');
    return value;
  }));
  if(!plain(base)||base.action!=='solve'||!['mounted','structural'].includes(base.mode))
    fail('Select structural static or mounted equilibrium for a resumable solve.');
  if(!operators.has(base.numerics?.structural_operator??'midpoint-v1'))fail('These equations do not support resumable equilibrium.');
  if(['initial_state','controller','derivatives'].some(key=>base[key]!=null))
    fail('Resumable solves require feedback and derivatives off, and no enabled initial equilibrium.');
  if(Object.hasOwn(base,'continuation'))fail('Expected solve settings without an embedded continuation job.');
  const constraints=base.operating_constraints??[],pairs={};
  for(const axis of ['x','y','z']){
    pairs[`acceleration.${axis}`]=`force.${axis}`;
    pairs[`angular_acceleration.${axis}`]=`moment.${axis}`;
  }
  if(!Array.isArray(constraints)||constraints.some(c=>!plain(c)||!Object.hasOwn(pairs,c.variable)||pairs[c.variable]!==c.quantity)||new Set(constraints.map(c=>c.variable)).size!==constraints.length)
    fail('Use Run analysis for trim targets. Resumable solves support prescribed conditions or acceleration/net-load targets.');
  if(typeof base.source!=='string'||!base.source.trim())fail('A resumable solve needs its ASW source.');
  validateJSON(base);return base;
}

export function validateSteadyCheckpoint(packet) {
  validateJSON(packet);
  if(!plain(packet)||packet.format!=='openswing-static-continuation'||packet.version!==1
      ||!plain(packet.context)||!plain(packet.context.coordinates)||!plain(packet.context.identity)
      ||!Number.isSafeInteger(packet.context.coordinates.size)||packet.context.coordinates.size<1
      ||!Array.isArray(packet.coordinates)||packet.coordinates.length!==packet.context.coordinates.size
      ||!packet.coordinates.every(Number.isFinite)||!Array.isArray(packet.hinge_charts)||!packet.hinge_charts.every(Number.isFinite)
      ||!Number.isFinite(packet.load_fraction)||!(packet.load_fraction>0&&packet.load_fraction<1)
      ||!Number.isFinite(packet.next_increment)||!(packet.next_increment>0&&packet.next_increment<=1)
      ||!Number.isSafeInteger(packet.accepted_load_steps)||packet.accepted_load_steps<1
      ||!Number.isSafeInteger(packet.rejected_load_attempts)||packet.rejected_load_attempts<0
      ||!Number.isFinite(packet.physical_residual)||packet.physical_residual<0
      ||typeof packet.sha256!=='string'||!/^[a-f0-9]{64}$/.test(packet.sha256))
    fail('Load an unfinished OpenSwing equilibrium-progress file. This is not a time checkpoint or a converged equilibrium.');
  // The kernel verifies the checksum, complete context and physical residual.
  return structuredClone(packet);
}

export function validateSteadyProgress(value) {
  validateJSON(value);
  const keys=['format','version','configuration','request','checkpoint'];
  if(!plain(value)||value.format!=='openswing-equilibrium-progress'||value.version!==1
      ||Object.keys(value).length!==keys.length||keys.some(k=>!Object.hasOwn(value,k)))
    fail('Load a version-1 OpenSwing equilibrium-progress JSON file.');
  const configuration=validateConfiguration(value.configuration),request=steadyRequest(value.request),checkpoint=validateSteadyCheckpoint(value.checkpoint);
  if(configuration.source!==request.source||configuration.fields.mode!==request.mode
      ||!sameConfiguration(configuration.mesh,request.panels)||!sameNumerics(configuration.numerics,request.numerics))
    fail('Saved solve settings and case configuration do not match.');
  assertNumericalIdentity(request.numerics,checkpoint.context.identity);
  return {format:value.format,version:1,configuration,request,checkpoint};
}

export function progressRecord(configuration,request,result) {
  if(result?.continuation_status!=='pending'||result.converged!==false||result.equilibrium_state!=null)
    fail('Only an unfinished accepted load step can be saved as solve progress.');
  const {continuation,...base}=request;
  return validateSteadyProgress({format:'openswing-equilibrium-progress',version:1,
    configuration,request:base,checkpoint:result.checkpoint});
}

export function nextSteadyRequest(request,saved=null) {
  const base=steadyRequest(request);
  if(saved&&!sameConfiguration(base,saved.request))
    fail('Solve inputs changed. Restore saved solve settings before resuming, or start a new resumable solve.');
  return {...base,continuation:{max_load_steps:1,...(saved?{checkpoint:structuredClone(saved.checkpoint)}:{})}};
}
