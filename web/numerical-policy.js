// The absent policy is deliberately preserved for historical projects/checksums.
import {validateEquilibriumPacket,validateCheckpointPacket} from './saved-state-data.js';
export const DEFAULT_NUMERICS=Object.freeze({beam_interpolation:'natural-v1',structural_operator:'midpoint-v1'});
export const SOURCE_NUMERICS=Object.freeze({beam_interpolation:'drela-segspl-v1',structural_operator:'drela-steady-zero-offset-v1'});
export const SECTION_NUMERICS=Object.freeze({beam_interpolation:'drela-segspl-v1',structural_operator:'drela-steady-section-v1'});
export const COUPLED_NUMERICS=Object.freeze({beam_interpolation:'drela-segspl-v1',structural_operator:'drela-steady-coupled-v1'});
export const VACUUM_NUMERICS=Object.freeze({beam_interpolation:'drela-segspl-v1',structural_operator:'drela-fixed-vacuum-v1'});
export const STILL_AIR_NUMERICS=Object.freeze({beam_interpolation:'drela-segspl-v1',structural_operator:'drela-fixed-still-air-v1'});
export const MOVING_VACUUM_NUMERICS=Object.freeze({beam_interpolation:'drela-segspl-v1',structural_operator:'drela-moving-vacuum-v1'});
export const AIRFLOW_NUMERICS=Object.freeze({beam_interpolation:'drela-segspl-v1',structural_operator:'drela-moving-airflow-v1'});
const keys=['beam_interpolation','structural_operator'];
function assertStrutMode(request){
  if(request.strut_mode!==undefined&&!['bilateral','wire'].includes(request.strut_mode))
    throw new Error('Strut mode must be bilateral or wire.');
}
export function numericalSelection(value){
  if(value===undefined)return 'midpoint';
  if(value===null||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==2||keys.some(k=>!Object.hasOwn(value,k)))throw new Error('Numerical settings require a complete interpolation and structural-equation pair.');
  if(keys.every(k=>value[k]===DEFAULT_NUMERICS[k]))return 'midpoint';
  if(keys.every(k=>value[k]===SOURCE_NUMERICS[k]))return 'aswing';
  if(keys.every(k=>value[k]===SECTION_NUMERICS[k]))return 'aswing-section';
  if(keys.every(k=>value[k]===COUPLED_NUMERICS[k]))return 'aswing-coupled';
  if(keys.every(k=>value[k]===VACUUM_NUMERICS[k]))return 'aswing-vacuum';
  if(keys.every(k=>value[k]===STILL_AIR_NUMERICS[k]))return 'aswing-still-air';
  if(keys.every(k=>value[k]===MOVING_VACUUM_NUMERICS[k]))return 'aswing-moving-vacuum';
  if(keys.every(k=>value[k]===AIRFLOW_NUMERICS[k]))return 'aswing-airflow';
  throw new Error('Unsupported numerical settings pair.');
}
export function selectedNumerics(selection){
  if(selection==='midpoint')return undefined;
  if(selection==='aswing')return {...SOURCE_NUMERICS};
  if(selection==='aswing-section')return {...SECTION_NUMERICS};
  if(selection==='aswing-coupled')return {...COUPLED_NUMERICS};
  if(selection==='aswing-vacuum')return {...VACUUM_NUMERICS};
  if(selection==='aswing-still-air')return {...STILL_AIR_NUMERICS};
  if(selection==='aswing-moving-vacuum')return {...MOVING_VACUUM_NUMERICS};
  if(selection==='aswing-airflow')return {...AIRFLOW_NUMERICS};
  throw new Error('Unsupported structural-equation selection.');
}
export function sameNumerics(a,b){return numericalSelection(a)===numericalSelection(b);}
export function sourceNumerics(value){return numericalSelection(value)!=='midpoint';}
export function vacuumNumerics(value){return numericalSelection(value)==='aswing-vacuum';}
export function stillAirNumerics(value){return numericalSelection(value)==='aswing-still-air';}
export function movingVacuumNumerics(value){return numericalSelection(value)==='aswing-moving-vacuum';}
export function airflowNumerics(value){return numericalSelection(value)==='aswing-airflow';}
export function numericalMode(value){
  const selection=numericalSelection(value);
  return selection==='midpoint'?null:selection==='aswing-coupled'?'mounted':['aswing-vacuum','aswing-still-air','aswing-moving-vacuum','aswing-airflow'].includes(selection)?'modes':'structural';
}
export function numericalModeLabel(value){return airflowNumerics(value)?'mounted steady trim, coupled airflow modes, frequency or time response':numericalMode(value)==='mounted'?'mounted aeroelastic equilibrium':vacuumNumerics(value)?'fixed-frame vacuum eigenmodes':stillAirNumerics(value)?'fixed-frame still-air eigenmodes':movingVacuumNumerics(value)?'moving-frame vacuum eigenmodes or time response':'structural static analysis';}
export function selectionAllowsMode(selection,mode){if(selection==='aswing-airflow'&&mode==='mounted')return true;if(['aswing-moving-vacuum','aswing-airflow'].includes(selection))return ['modes','time','frequency'].includes(mode);if(['aswing-vacuum','aswing-still-air'].includes(selection))return ['modes','frequency'].includes(mode);const required=numericalMode(selectedNumerics(selection));return required===null||required===mode;}
export function structuralPolicyNote(selection){
  selectedNumerics(selection); // Reject unknown selections before displaying scope.
  if(selection==='midpoint')return '';
  if(selection==='aswing-airflow')return 'Steady trim, coupled airflow modes, frequency response and nonlinear time response · experimental. Steady trim solves operating targets, custom sensor equations and weighted redundant controls, including frame rates and accelerations, at zero local elastic rates; its saved equilibrium can launch time response with solved controls retained and trim targets released. Feedback controllers participate in steady trim and dynamic analyses. Steady stability/control derivatives can hold accelerations fixed or solve their free-flight response. Surface and fuselage beams use source section equations and moving-frame inertia. Stepped axes and inverse time-actuator targets are unsupported. Exact ASWING least-squares weight conventions remain unverified. Mesh/time refinement and archived ASWING validation remain necessary.';
  if(selection==='aswing-vacuum')return 'Fixed-frame vacuum eigenmodes and initial-disturbance spectra · experimental. Source section equations, endpoint-averaged inertia and material damping; physical nonnegative masses and damping times required. Earth attitude and gravity remain active. No airflow, moving frame, feedback, operating targets or time response. General discrete mass symmetry and archived ASWING agreement are unverified. Changing equations clears results and loaded equilibria.';
  if(selection==='aswing-still-air')return 'Fixed-frame still-air eigenmodes and initial-disturbance spectra · experimental. Set a positive fluid density; Earth pose and gravity remain active. Surface and fuselage beams use source section equations with endpoint-averaged real and apparent inertia. Fuselages retain the selected cylinder or printed ASWING coefficient. Stepped axes, engines, feedback, flight flow and nonlinear time response are unsupported. Archived ASWING agreement is unverified. Changing equations clears results and loaded equilibria.';
  if(selection==='aswing-moving-vacuum')return 'Vacuum eigenmodes, frequency response and nonlinear time response · experimental. Set body-origin velocity, motion, Earth pose and gravity for a cold run. Frequency inputs are frame loads, prescribed accelerations or initial disturbances. Saved launches and continuations retain their recorded setup. Linear responses use a frozen local model. No airflow, feedback or actuator targets. Archived ASWING agreement is unverified.';
  const joints='Rigid, pinned, roller and sprung joints are supported within the beam Euler-angle limits.';
  if(selection==='aswing-coupled')return `Mounted steady analysis: source section equations with existing steady aerodynamics. Operating targets can solve airspeed, incidence, sideslip, Earth pose, flap or engine settings together with deformation and circulation. Body rates and accelerations must remain prescribed at zero. Surface and fuselage beams and steady engines on their mounts are supported. ${joints} Custom sensor equations and weighted redundant controls share the coupled equilibrium. No stepped axes, derivatives or dynamics. Exact ASWING least-squares weight conventions remain unverified. Changing equations clears results and loaded equilibria. Historical ASWING load sampling and full agreement remain unverified.`;
  const scope=selection==='aswing-section'
    ?'Surface and fuselage beams, section and distributed CG offsets and finite shear are supported. Stepped axes, engines, airflow and dynamics are unsupported. Dynamic inertia and spin are unavailable.'
    :'Zero section and distributed CG offsets and rigid shear. Engines, airflow and dynamics are unsupported.';
  return `Structural static only: ${scope} ${joints} Changing equations clears results and loaded equilibria. Other analyses return to the existing equations. Archived ASWING agreement remains incomplete.`;
}
export function assertNumericalIdentity(numerics,identity){
  if(!identity){if(sourceNumerics(numerics))throw new Error('ASWING state is missing its numerical identity.');return;}
  const recorded={beam_interpolation:identity.beam_interpolation??DEFAULT_NUMERICS.beam_interpolation,
    structural_operator:identity.structural_operator??DEFAULT_NUMERICS.structural_operator};
  if(!sameNumerics(numerics,recorded))throw new Error('Saved state and configuration numerical settings do not match.');
}
const parseActions=new Set(['inspect','distribution','edit_distribution','canonical_asw','vortex_preview']);
export function assertVacuumInputs(fields,constraints=[],{modalSettings=true}={}){
  if(fields.mode==='frequency'&&modalSettings){
    assertSourceFrequencyFields(fields,false);
    if(fields['modal-vacuum']!==true||fields['modal-quiescent']!==false)throw new Error('Source vacuum frequency settings require vacuum on and still air off.');
    modalSettings=false;
  }
  for(const kind of ['rates','acceleration','angular_acceleration'])for(const axis of ['x','y','z']){
    const value=fields[`${kind}-${axis}`];
    if(typeof value!=='string'||!value.trim()||!Number.isFinite(Number(value))||Number(value)!==0)
      throw new Error('ASWING vacuum modes require zero body rates and accelerations. Set all motion inputs to zero before selecting these equations.');
  }
  if(fields['feedback-enabled']!==false)throw new Error('Disable feedback before selecting ASWING vacuum modes.');
  if(!Array.isArray(constraints)||constraints.length)throw new Error('Remove operating targets before selecting ASWING vacuum modes.');
  if(modalSettings&&(fields.mode!=='modes'||fields['modal-frame']!=='fixed'||fields['modal-ordinary-frame']!=='fixed'
      ||fields['modal-vacuum']!==true||fields['modal-quiescent']!==false))
    throw new Error('ASWING vacuum modes require fixed frame, vacuum on and still air off.');
}
export function assertVacuumRequest(request){
  assertStrutMode(request);
  const options=request.modes;
  const emptyObject=value=>value!==null&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).length===0;
  const allowed=new Set(['frame','count','shift','method','step','rank_tolerance','matrices','vacuum','tolerance',
    'continuation_steps','position','attitude','gravity_magnitude','initial_state','structured_base','controller','load_targets']);
  if(request.action!=='modes'||request.mode!=='modes'||!(request.condition===null||request.condition===undefined
      ||emptyObject(request.condition))
      ||!options||typeof options!=='object'||Array.isArray(options)||Object.keys(options).some(key=>!allowed.has(key))
      ||options.frame!=='fixed'||options.vacuum!==true
      ||options.controller!=null||(options.load_targets!=null&&!emptyObject(options.load_targets))
      ||(request.operating_constraints!=null&&(!Array.isArray(request.operating_constraints)||request.operating_constraints.length)))
    throw new Error('ASWING vacuum modes require a fixed frame, no FlightCondition, vacuum on and no controller or operating targets.');
}
export function vacuumModalRequest(request,condition){
  for(const key of ['rates','acceleration','angular_acceleration'])if(!Array.isArray(condition[key])||condition[key].length!==3
      ||condition[key].some(v=>typeof v!=='number'||!Number.isFinite(v)||v!==0))
    throw new Error('ASWING vacuum modes require zero body rates and accelerations.');
  for(const key of ['position_earth','attitude'])if(!Array.isArray(condition[key])||condition[key].length!==3
      ||condition[key].some(v=>typeof v!=='number'||!Number.isFinite(v)))throw new Error('Enter a finite Earth position and attitude.');
  if(condition.gravity_magnitude!==null&&!(Number.isFinite(condition.gravity_magnitude)&&condition.gravity_magnitude>=0))
    throw new Error('Enter a finite nonnegative gravity magnitude, or use file gravity.');
  const copy={...request,condition:null,modes:{...request.modes,position:condition.position_earth,
    attitude:condition.attitude,gravity_magnitude:condition.gravity_magnitude}};
  assertVacuumRequest(copy);
  if(request.derivatives!=null||request.controller!=null)
    throw new Error('ASWING vacuum modes do not support derivatives or controllers.');
  delete copy.derivatives;delete copy.controller;delete copy.operating_constraints;
  delete copy.modes.controller;return copy;
}
export function assertStillAirInputs(fields,constraints=[],{modalSettings=true}={}){
  if(fields.mode==='frequency'&&modalSettings){
    assertSourceFrequencyFields(fields,false);
    if(fields['modal-vacuum']!==false||fields['modal-quiescent']!==true)throw new Error('Source still-air frequency settings require still air on and vacuum off.');
    modalSettings=false;
  }
  for(const kind of ['rates','acceleration','angular_acceleration'])for(const axis of ['x','y','z']){
    const value=fields[`${kind}-${axis}`];
    if(typeof value!=='string'||!value.trim()||!Number.isFinite(Number(value))||Number(value)!==0)
      throw new Error('ASWING still-air modes require zero body rates and accelerations. Set all motion inputs to zero before selecting these equations.');
  }
  if(fields['feedback-enabled']!==false)throw new Error('Disable feedback before selecting ASWING still-air modes.');
  if(!Array.isArray(constraints)||constraints.length)throw new Error('Remove operating targets before selecting ASWING still-air modes.');
  const density=fields['modal-quiescent-density'];
  if(typeof density!=='string'||!density.trim()||!Number.isFinite(Number(density))||Number(density)<=0)
    throw new Error('Enter a positive finite still-air density in input M/L³ units.');
  if(modalSettings&&(fields.mode!=='modes'||fields['modal-frame']!=='fixed'||fields['modal-ordinary-frame']!=='fixed'
      ||fields['modal-vacuum']!==false||fields['modal-quiescent']!==true))
    throw new Error('ASWING still-air modes require fixed frame, still air on and vacuum off.');
}
export function assertStillAirIdentity(state,density,bodyFactor=1){
  validateEquilibriumPacket(state);assertNumericalIdentity(STILL_AIR_NUMERICS,state.identity);
  if(state.identity.quiescent_density!==density||(state.launch!==undefined&&state.launch.quiescent_density!==density))
    throw new Error('Saved still-air state and selected fluid density do not match.');
  const saved=state.identity.quiescent_body_added_mass_factor;
  if((saved!==undefined&&saved!==bodyFactor)||(state.launch?.quiescent_body_added_mass_factor!==undefined
      &&state.launch.quiescent_body_added_mass_factor!==bodyFactor))
    throw new Error('Saved still-air body coefficient and selected coefficient do not match.');
}
export function assertStillAirRequest(request){
  assertStrutMode(request);
  const options=request.modes;
  const requestKeys=new Set(['action','mode','source','panels','numerics','condition','modes','controller','derivatives',
    'gravity','initial_state','equilibrium_state','strut_mode','operating_constraints']);
  const allowed=new Set(['frame','count','shift','method','step','rank_tolerance','matrices','vacuum','quiescent_density',
    'quiescent_body_added_mass_factor','tolerance','continuation_steps','position','attitude','gravity_magnitude','initial_state','structured_base']);
  if(request.action!=='modes'||request.mode!=='modes'||request.condition!==null||Object.keys(request).some(key=>!requestKeys.has(key))
      ||!options||typeof options!=='object'||Array.isArray(options)||Object.keys(options).some(key=>!allowed.has(key))
      ||options.frame!=='fixed'||options.vacuum!==false
      ||typeof options.quiescent_density!=='number'||!Number.isFinite(options.quiescent_density)||options.quiescent_density<=0
      ||request.controller!=null||request.derivatives!=null||request.gravity!=null||request.initial_state!=null
      ||request.equilibrium_state!=null
      ||(request.operating_constraints!=null&&(!Array.isArray(request.operating_constraints)||request.operating_constraints.length)))
    throw new Error('ASWING still-air modes require fixed frame, positive fluid density, condition:null, vacuum off and no controller, motion or operating targets.');
  for(const key of ['position','attitude'])if(options[key]!==undefined&&(!Array.isArray(options[key])||options[key].length!==3||!options[key].every(v=>typeof v==='number'&&Number.isFinite(v))))
    throw new Error('Enter a finite Earth position and attitude.');
  if(options.gravity_magnitude!=null&&(typeof options.gravity_magnitude!=='number'||!Number.isFinite(options.gravity_magnitude)||options.gravity_magnitude<0))
    throw new Error('Enter a finite nonnegative gravity magnitude, or use file gravity.');
  if(options.quiescent_body_added_mass_factor!==undefined&&![1,2].includes(options.quiescent_body_added_mass_factor))
    throw new Error('Choose cylinder or printed ASWING fuselage apparent mass.');
  if(options.initial_state!=null)assertStillAirIdentity(options.initial_state,options.quiescent_density,options.quiescent_body_added_mass_factor??1);
}
export function stillAirModalRequest(request,condition){
  // The caller first validates live motion/feedback/targets, then constructs
  // this fresh quiescent condition. Ordinary flight data cannot enter the wire.
  const allowed=new Set(['speed','density','position_earth','attitude','gravity_magnitude','body_added_mass_factor']);
  if(!condition||typeof condition!=='object'||Array.isArray(condition)||Object.keys(condition).some(key=>!allowed.has(key))
      ||condition.speed!==0||typeof condition.density!=='number'||!Number.isFinite(condition.density)||condition.density<=0)
    throw new Error('ASWING still-air modes require an explicit zero-flow condition and positive fluid density.');
  if(request.derivatives!=null||request.controller!=null
      ||(request.operating_constraints!=null&&(!Array.isArray(request.operating_constraints)||request.operating_constraints.length)))
    throw new Error('ASWING still-air modes do not support derivatives, controllers or operating targets.');
  if(request.modes?.quiescent_density!==condition.density)
    throw new Error('Still-air modal and condition densities do not match.');
  for(const key of ['position_earth','attitude'])if(!Array.isArray(condition[key])||condition[key].length!==3
      ||condition[key].some(v=>typeof v!=='number'||!Number.isFinite(v)))throw new Error('Enter a finite Earth position and attitude.');
  const copy={...request,condition:null,modes:{...request.modes,position:condition.position_earth,
    attitude:condition.attitude,gravity_magnitude:condition.gravity_magnitude}};
  if(condition.body_added_mass_factor!==undefined){
    if(![1,2].includes(condition.body_added_mass_factor))throw new Error('Choose cylinder or printed ASWING fuselage apparent mass.');
    copy.modes.quiescent_body_added_mass_factor=condition.body_added_mass_factor;
  }
  delete copy.derivatives;delete copy.controller;delete copy.operating_constraints;
  assertStillAirRequest(copy);return copy;
}
const movingFrames=['fixed','prescribed','free','mixed'];
const finiteNumber=value=>typeof value==='number'&&Number.isFinite(value);
const finiteVector=value=>Array.isArray(value)&&value.length===3&&value.every(finiteNumber);
const plainObject=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
function assertMovingFrameTargets(frame,targets){
  if(!movingFrames.includes(frame))throw new Error('Choose fixed, prescribed, free or mixed frame motion.');
  if(targets==null)targets={};
  const keys=new Set(['force','moment'].flatMap(kind=>['x','y','z'].map(axis=>`${kind}.${axis}`)));
  if(!plainObject(targets)||Object.entries(targets).some(([key,value])=>!keys.has(key)||!finiteNumber(value)))
    throw new Error('Frame load targets must be finite force.x/y/z or moment.x/y/z values.');
  if(['fixed','prescribed'].includes(frame)&&Object.keys(targets).length)
    throw new Error('Fixed and prescribed frames cannot have load targets.');
  if(frame==='mixed'&&!Object.keys(targets).length)throw new Error('Mixed motion requires at least one force or moment target.');
}
export function assertMovingVacuumInputs(fields,constraints=[],{modalSettings=true}={}){
  if(fields.mode==='frequency'&&modalSettings){
    assertSourceFrequencyFields(fields,true);movingVacuumFrame(fields);
    if(fields['modal-vacuum']!==true||fields['modal-quiescent']!==false)throw new Error('Source moving frequency settings require vacuum on and still air off.');
    modalSettings=false;
  }
  for(const kind of ['moving-velocity','rates','acceleration','angular_acceleration'])for(const axis of ['x','y','z']){
    const value=fields[`${kind}-${axis}`];
    if(typeof value!=='string'||!value.trim()||!Number.isFinite(Number(value)))
      throw new Error('Enter finite body-origin velocity, rotation rates and acceleration components.');
  }
  if(fields['feedback-enabled']!==false)throw new Error('Disable feedback before selecting ASWING moving vacuum modes.');
  if(!Array.isArray(constraints)||constraints.length)throw new Error('Remove operating targets; use the modal frame load controls for moving vacuum modes.');
  if(fields.mode==='time'){
    if(typeof fields['time-actuators']!=='string'||fields['time-actuators'].trim())throw new Error('Moving vacuum time response does not support actuator targets.');
    if(!['prescribed','free','mixed'].includes(fields['time-frame']))throw new Error('Select prescribed, free or mixed time motion.');
    const targets={};
    if(fields['time-frame']==='mixed')for(const kind of ['F','M'])for(const axis of ['x','y','z']){
      const label=`${kind}${axis}`,selected=fields[`time-load:${label}`],value=fields[`time-target:${label}`];
      if(!['prescribed','load'].includes(selected))throw new Error('Select a prescribed acceleration or time load target for each axis.');
      if(selected==='load'){
        if(typeof value!=='string'||!value.trim()||!Number.isFinite(Number(value)))throw new Error('Enter finite time frame targets.');
        targets[`${kind==='F'?'force':'moment'}.${axis}`]=Number(value);
      }
    }
    assertMovingFrameTargets(fields['time-frame'],targets);movingVacuumFrame(fields);return;
  }
  if(modalSettings){
    if(fields.mode!=='modes'||fields['modal-vacuum']!==true||fields['modal-quiescent']!==false
        ||fields['modal-frame']!==fields['modal-ordinary-frame'])throw new Error('Moving vacuum modes require matching modal frames, vacuum on and still air off.');
    const targets={};
    if(fields['modal-frame']==='mixed')for(const kind of ['F','M'])for(const axis of ['x','y','z']){
      const key=`${kind}${axis}`,selection=fields[`modal-load-${key}`];
      if(!['prescribed','load'].includes(selection))throw new Error('Select a prescribed acceleration or load target for each mixed-frame axis.');
      if(selection==='load'){
        const value=fields[`modal-target-${key}`];
        if(typeof value!=='string'||!value.trim()||!Number.isFinite(Number(value)))throw new Error('Enter a finite modal frame load target.');
        targets[`${kind==='F'?'force':'moment'}.${axis}`]=Number(value);
      }
    }
    assertMovingFrameTargets(fields['modal-frame'],targets);
    movingVacuumFrame(fields);
  }
}
export function movingVacuumFrame(fields){
  const number=(key)=>{
    const value=fields[key];
    if(typeof value!=='string'||!value.trim()||!Number.isFinite(Number(value)))throw new Error('Enter finite moving-frame motion, Earth pose and gravity values.');
    return Number(value);
  };
  if(!['file','custom'].includes(fields['gravity-mode']))throw new Error('Select file or custom gravity.');
  const gravity=fields['gravity-mode']==='file'?null:number('gravity-magnitude');
  if(gravity!==null&&gravity<0)throw new Error('Gravity magnitude must be nonnegative.');
  return {velocity:['x','y','z'].map(axis=>number(`moving-velocity-${axis}`)),
    motion:Object.fromEntries(['rates','acceleration','angular_acceleration'].map(kind=>[kind,
      ['x','y','z'].map(axis=>number(`${kind}-${axis}`)*(kind==='acceleration'?1:Math.PI/180))])),
    position:['x','y','z'].map(axis=>number(`position-earth-${axis}`)),
    attitude:['bank','elevation','heading'].map(axis=>number(`attitude-${axis}`)),gravity_magnitude:gravity};
}
export function assertMovingVacuumRequest(request){
  assertStrutMode(request);
  const options=request.modes;
  const requestKeys=new Set(['action','mode','source','panels','numerics','condition','modes','loads','strut_mode']);
  const allowed=new Set(['frame','count','shift','method','step','rank_tolerance','matrices','vacuum','tolerance',
    'continuation_steps','position','attitude','gravity_magnitude','velocity','motion','initial_state','structured_base','load_targets']);
  if(request.action!=='modes'||request.mode!=='modes'||request.condition!==null
      ||Object.keys(request).some(key=>!requestKeys.has(key))||!plainObject(options)
      ||Object.keys(options).some(key=>!allowed.has(key))||options.vacuum!==true)
    throw new Error('Moving vacuum modes require condition:null, vacuum on and no airflow, controller or operating options.');
  assertMovingFrameTargets(options.frame,options.load_targets);
  for(const key of ['velocity','position','attitude'])if(options[key]!==undefined&&!finiteVector(options[key]))
    throw new Error('Moving vacuum velocity and Earth pose must be finite xyz vectors.');
  if(options.motion!=null){
    const names=['rates','acceleration','angular_acceleration'];
    if(!plainObject(options.motion)||Object.entries(options.motion).some(([key,value])=>!names.includes(key)||!finiteVector(value)))
      throw new Error('Moving vacuum motion requires finite rates, acceleration and angular_acceleration vectors.');
  }
  if(options.gravity_magnitude!=null&&(!finiteNumber(options.gravity_magnitude)||options.gravity_magnitude<0))
    throw new Error('Enter finite nonnegative gravity, or use file gravity.');
  if(options.initial_state!=null){validateEquilibriumPacket(options.initial_state);assertNumericalIdentity(MOVING_VACUUM_NUMERICS,options.initial_state.identity);}
}
export function movingVacuumModalRequest(request,frame){
  const names=['velocity','position','attitude','gravity_magnitude','motion'];
  if(!plainObject(frame)||Object.keys(frame).some(key=>!names.includes(key))||names.some(key=>!Object.hasOwn(frame,key)))
    throw new Error('Supply moving vacuum velocity, motion, Earth pose and gravity directly.');
  if(request.derivatives!=null||request.controller!=null||request.modes?.controller!=null
      ||(request.operating_constraints!=null&&(!Array.isArray(request.operating_constraints)||request.operating_constraints.length)))
    throw new Error('Moving vacuum modes do not support controllers, derivatives or arbitrary operating targets.');
  const copy={...request,condition:null,modes:{...request.modes,...frame}};
  delete copy.derivatives;delete copy.controller;delete copy.operating_constraints;
  delete copy.modes.controller;assertMovingVacuumRequest(copy);return copy;
}
const frequencyOnly=new Set(['frequencies','inputs','initial_shift','initial_rank_tolerance']);
const frequencyBase=new Set(['frame','step','matrices','vacuum','quiescent_density','quiescent_body_added_mass_factor','tolerance','continuation_steps',
  'position','attitude','gravity_magnitude','velocity','motion','initial_state','load_targets','controller']);
function frequencyModalRequest(request){
  if(request.action!=='frequency'||request.mode!=='frequency'||!plainObject(request.frequency)
      ||Object.keys(request.frequency).some(key=>!frequencyOnly.has(key)&&!frequencyBase.has(key)))
    throw new Error('Unsupported source frequency request.');
  if(request.retain_frequency!==undefined&&typeof request.retain_frequency!=='boolean')throw new Error('retain_frequency must be boolean.');
  if(request.frequency_spacing!==undefined&&!['linear','log'].includes(request.frequency_spacing))throw new Error('Unsupported frequency display spacing.');
  const copy={...request,action:'modes',mode:'modes',modes:Object.fromEntries(Object.entries(request.frequency).filter(([key])=>!frequencyOnly.has(key)))};
  delete copy.frequency;delete copy.frequency_spacing;delete copy.retain_frequency;return copy;
}
export function assertSourceFrequencyRequest(request,numerics){
  if(airflowNumerics(numerics)){assertAirflowRequest(request);return;}
  const modal=frequencyModalRequest(request),selection=numericalSelection(numerics);
  if(selection==='aswing-vacuum')assertVacuumRequest(modal);
  else if(selection==='aswing-still-air')assertStillAirRequest(modal);
  else if(selection==='aswing-moving-vacuum')assertMovingVacuumRequest(modal);
  else throw new Error('Select source dynamic equations for this response.');
  const inputs=request.frequency.inputs;
  if(!Array.isArray(inputs)||!inputs.length||inputs.some(input=>!(plainObject(input)&&input.kind==='initial')
      &&!(selection==='aswing-moving-vacuum'&&request.frequency.frame!=='fixed'&&typeof input==='string'&&/^(target\.|acceleration\.|angular_acceleration\.)/.test(input))))
    throw new Error('Source frequency inputs require initial disturbances or moving-frame loads and accelerations.');
}
export function sourceFrequencyRequest(request,numerics,condition,frame){
  const selection=numericalSelection(numerics),modal=frequencyModalRequest(request);
  modal.modes.vacuum=selection!=='aswing-still-air';
  if(selection==='aswing-still-air')modal.modes.quiescent_density=condition.density;
  const mapped=selection==='aswing-moving-vacuum'?movingVacuumModalRequest(modal,frame):
    selection==='aswing-still-air'?stillAirModalRequest(modal,condition):vacuumModalRequest(modal,condition);
  const copy={...mapped,action:'frequency',mode:'frequency',frequency:{...request.frequency,...mapped.modes}};
  delete copy.modes;delete copy.frequency.controller;
  for(const key of ['retain_frequency','frequency_spacing'])if(Object.hasOwn(request,key))copy[key]=request[key];
  assertSourceFrequencyRequest(copy,numerics);return copy;
}
function assertSourceFrequencyFields(fields,moving){
  const frame=fields['frequency-frame'],inputs=fields['frequency-inputs'];
  if(!(moving?movingFrames.includes(frame):frame==='fixed'))throw new Error('Select a supported source frequency frame. Fixed source policies require fixed frame.');
  if(!['initial',...(moving&&frame!=='fixed'?['frame']:[])].includes(inputs))throw new Error('Select initial disturbances, or moving-frame loads and accelerations.');
  const targets={};
  if(frame==='mixed')for(const kind of ['F','M'])for(const axis of ['x','y','z']){
    const label=`${kind}${axis}`,selection=fields[`frequency-load-${label}`],value=fields[`frequency-target-${label}`];
    if(!['load','prescribed'].includes(selection))throw new Error('Choose a frequency constraint for each axis.');
    if(selection==='load'){
      if(typeof value!=='string'||!value.trim()||!Number.isFinite(Number(value)))throw new Error('Enter finite frequency frame targets.');
      targets[`${kind==='F'?'force':'moment'}.${axis}`]=Number(value);
    }
  }
  assertMovingFrameTargets(frame,targets);
}
export function assertMovingTimeRequest(request,{airflow=false}={}){
  assertStrutMode(request);
  const action=request.action,options=request.time;
  if(!['time','launch_time','resume_time'].includes(action)||(request.mode!==undefined&&request.mode!=='time'))throw new Error('Moving vacuum time requests require a supported time action.');
  const top=new Set(['action','mode','source','numerics','time',...(airflow?['controller','derivatives','operating_constraints']:[]),...(action==='time'?['panels','condition','loads','initial_loads','strut_mode']:action==='launch_time'?['equilibrium_state']:['checkpoint'])]);
  const allowed=new Set(['duration','dt','order','tolerance','max_steps','forcing','accuracy']);
  if(action!=='resume_time')for(const key of ['frame','load_targets'])allowed.add(key);
  if(airflow&&action==='time')allowed.add('controller');
  if(airflow&&action!=='resume_time')allowed.add('actuator_constraints');
  if(action==='time')for(const key of airflow?['continuation_steps']:['velocity','motion','position','attitude','gravity_magnitude','continuation_steps'])allowed.add(key);
  if(action==='launch_time')for(const key of ['loads','disturbance','initial_difference_step','initial_rank_tolerance'])allowed.add(key);
  if(Object.keys(request).some(key=>!top.has(key))||!plainObject(options)||Object.keys(options).some(key=>!allowed.has(key)))
    throw new Error('Unsupported source time options; launch and continuation use the saved physical setup.');
  if(action==='time'&&airflow){
    if(!plainObject(request.condition))throw new Error('Source airflow time response requires a flight condition.');
  }else if(action==='time'){
    if(request.condition!==null)throw new Error('Moving vacuum cold time response requires condition:null.');
    const modal={action:'modes',mode:'modes',source:request.source,condition:null,modes:{frame:options.frame??'prescribed',vacuum:true,
      ...Object.fromEntries(['velocity','motion','position','attitude','gravity_magnitude','load_targets'].filter(key=>Object.hasOwn(options,key)).map(key=>[key,options[key]]))}};
    assertMovingVacuumRequest(modal);
  }else{
    const state=action==='launch_time'?validateEquilibriumPacket(request.equilibrium_state):validateCheckpointPacket(request.checkpoint);
    assertNumericalIdentity(airflow?AIRFLOW_NUMERICS:MOVING_VACUUM_NUMERICS,action==='launch_time'?state.identity:state.context.identity);
    const setup=action==='launch_time'?state.launch:state.context.setup;
    if(!plainObject(setup)||(airflow?!plainObject(setup.condition):setup.condition!=null)||(!airflow&&setup.controller!=null)||setup.quiescent_density!=null
        ||(setup.actuator_constraints!=null&&(!Array.isArray(setup.actuator_constraints)||setup.actuator_constraints.length)))
      throw new Error('Saved source dynamics setup has an incompatible medium, feedback or actuator targets.');
  }
  if(action!=='resume_time'){
    if(!['prescribed','free','mixed'].includes(options.frame??'prescribed'))throw new Error('Time frame must be prescribed, free or mixed.');
    assertMovingFrameTargets(options.frame??'prescribed',options.load_targets);
  }
  for(const key of ['duration','dt','tolerance']){
    const value=options[key],required=key==='duration'||(key==='dt'&&action!=='resume_time');
    if((required&&value==null)||(value!=null&&(!finiteNumber(value)||value<=0)))throw new Error(`Time ${key} must be positive and finite.`);
  }
  if(options.order!=null&&![1,2,5].includes(options.order))throw new Error('Time order must be 1, 2 or 5.');
  if(Object.hasOwn(options,'forcing')&&!(typeof options.forcing==='string'||(action==='resume_time'&&options.forcing===null)))throw new Error('Forcing must be an ASWING table string.');
}
export function movingVacuumTimeRequest(request,frame){
  if(request.controller!=null||request.derivatives!=null||request.time?.controller!=null
      ||(request.operating_constraints!=null&&(!Array.isArray(request.operating_constraints)||request.operating_constraints.length))
      ||(request.time?.actuator_constraints!=null&&(!Array.isArray(request.time.actuator_constraints)||request.time.actuator_constraints.length)))
    throw new Error('Moving vacuum time response has no feedback, actuator targets, arbitrary operating targets or aerodynamic options.');
  const copy={...request,time:{...request.time,...(request.action==='time'?frame:{})}};
  if(request.action==='time')copy.condition=null;
  delete copy.controller;delete copy.derivatives;delete copy.operating_constraints;
  delete copy.time.controller;delete copy.time.actuator_constraints;assertMovingTimeRequest(copy);return copy;
}
function assertSavedRequestPolicy(request,numerics){
  const stateKeys=['initial_state','equilibrium_state','checkpoint'],pending=stateKeys.filter(key=>request[key]!=null).map(key=>request[key]);
  for(const kind of ['modes','time','frequency'])if(plainObject(request[kind]))for(const key of stateKeys)if(request[kind][key]!=null)pending.push(request[kind][key]);
  const visited=new Set();
  while(pending.length){const value=pending.pop();if(!plainObject(value)||visited.has(value))continue;visited.add(value);
    if(plainObject(value.identity))assertNumericalIdentity(numerics,value.identity);
    for(const key of [...stateKeys,'context'])if(value[key]!=null)pending.push(value[key]);
  }
}
export function numericalRequest(request,current){
  if(!Object.hasOwn(request,'source')&&!Object.hasOwn(request,'numerics'))return {...request};
  // An explicit undefined override requests historical semantics while loading
  // an old project into a workbench currently displaying the source policy.
  const numerics=Object.hasOwn(request,'numerics')?request.numerics:current;
  const selected=numericalSelection(numerics),copy={...request};
  if(['extend_frequency','discard_frequency'].includes(request.action)&&plainObject(request.session)){
    const recorded={beam_interpolation:request.session.beam_interpolation??DEFAULT_NUMERICS.beam_interpolation,
      structural_operator:request.session.structural_operator??DEFAULT_NUMERICS.structural_operator};
    if(!sameNumerics(numerics,recorded))throw new Error('Frequency session and request numerical settings do not match.');
  }
  assertSavedRequestPolicy(request,numerics);
  delete copy.numerics;
  if(selected!=='midpoint'){
    const dynamic=['aswing-vacuum','aswing-still-air','aswing-moving-vacuum','aswing-airflow'].includes(selected);
    const frequency=dynamic&&['frequency','extend_frequency','discard_frequency'].includes(request.action);
    const calculation=frequency||(selected==='aswing-airflow'&&request.action==='solve'&&request.mode==='mounted')||(['aswing-moving-vacuum','aswing-airflow'].includes(selected)?((request.action==='modes'&&request.mode==='modes')||['time','launch_time','resume_time'].includes(request.action)):['aswing-vacuum','aswing-still-air'].includes(selected)?request.action==='modes'&&request.mode==='modes':request.action==='solve'&&selectionAllowsMode(selected,request.mode));
    const steadyStack=['aswing-coupled','aswing-airflow'].includes(selected)&&request.action==='operating_points'&&request.mode==='mounted';
    if(!parseActions.has(request.action)&&!calculation&&!steadyStack)throw new Error(`The selected ASWING equations are available only for ${numericalModeLabel(numerics)}.`);
    if(frequency&&request.action==='frequency')assertSourceFrequencyRequest(request,numerics);
    if(selected==='aswing-vacuum'&&!parseActions.has(request.action)&&!frequency)assertVacuumRequest(request);
    if(selected==='aswing-still-air'&&!parseActions.has(request.action)&&!frequency)assertStillAirRequest(request);
    if(selected==='aswing-moving-vacuum'&&!parseActions.has(request.action)&&!frequency){
      if(request.action==='modes')assertMovingVacuumRequest(request);else assertMovingTimeRequest(request);
    }
    if(selected==='aswing-airflow'&&!parseActions.has(request.action)&&!['extend_frequency','discard_frequency','operating_points'].includes(request.action))assertAirflowRequest(request);
    copy.numerics=selectedNumerics(selected);
  }
  return copy;
}

function assertSteadyAirflowTargets(constraints){
  if(!Array.isArray(constraints))throw new Error('Source steady trim requires a list of operating targets.');
  for(const row of constraints){
    if(!plainObject(row)||typeof row.variable!=='string'||typeof row.quantity!=='string')throw new Error('Operating targets require a variable and quantity.');
  }
}
export function assertAirflowInputs(fields,constraints=[],{modalSettings=true,savedLaunch=false}={}){
  if(fields.mode==='mounted'){
    assertSteadyAirflowTargets(constraints);
    for(const group of ['rates','acceleration','angular_acceleration'])for(const axis of ['x','y','z']){
      const value=fields[`${group}-${axis}`];
      if(typeof value!=='string'||!value.trim()||!Number.isFinite(Number(value)))throw new Error('Source steady trim requires finite frame rates and accelerations.');
    }
    return;
  }
  if(!Array.isArray(constraints)||(!savedLaunch&&constraints.length))throw new Error('Remove operating targets before selecting source airflow dynamics; use the dynamic frame targets.');
  if(typeof fields['time-actuators']==='string'&&fields['time-actuators'].trim())throw new Error('Remove actuator targets before selecting source airflow dynamics.');
  if(modalSettings&&(fields['modal-vacuum']!==false||fields['modal-quiescent']!==false))throw new Error('Source airflow dynamics requires vacuum and still air off.');
}
export function assertAirflowRequest(request){
  assertStrutMode(request);
  const action=request.action, saved=['launch_time','resume_time'].includes(action);
  if(action==='solve'){
    if(request.mode!=='mounted'||!plainObject(request.condition))throw new Error('Source steady trim requires mounted mode and a flight condition.');
    assertSteadyAirflowTargets(request.operating_constraints??[]);
    for(const name of ['rates','acceleration','angular_acceleration']){
      const value=request.condition[name]??[0,0,0];
      if(!Array.isArray(value)||value.length!==3||value.some(v=>typeof v!=='number'||!Number.isFinite(v)))throw new Error('Source steady trim requires finite xyz frame rates and accelerations.');
    }
    return;
  }
  if(!['modes','frequency','time','launch_time','resume_time'].includes(action))throw new Error('Unsupported source airflow analysis.');
  if(!saved&&!plainObject(request.condition))throw new Error('Source airflow dynamics requires a flight condition.');
  const options=request[saved?'time':action];
  if(!plainObject(options)||options.quiescent_density!=null||options.vacuum===true)
    throw new Error('Source airflow dynamics requires airflow on, without a separate still-air medium.');
  if(request.controller!=null||request.derivatives!=null||(request.operating_constraints!=null&&request.operating_constraints.length))
    throw new Error('Source airflow dynamics requires feedback in its analysis options and does not support trim targets or steady derivatives.');
  if(options.actuator_constraints!=null&&(!Array.isArray(options.actuator_constraints)||options.actuator_constraints.length))throw new Error('Source airflow dynamics does not support actuator targets.');
  if(['motion','velocity','position','attitude','gravity_magnitude'].some(key=>Object.hasOwn(options,key)))
    throw new Error('Specify airflow motion, pose and gravity in the flight condition.');
  if(!saved)assertMovingFrameTargets(options.frame??(action==='time'?'prescribed':'fixed'),options.load_targets??{});
  if(action==='frequency'&&(!Array.isArray(options.inputs)||!options.inputs.length))throw new Error('Select at least one frequency input.');
  if(['time','launch_time','resume_time'].includes(action))assertMovingTimeRequest(request,{airflow:true});
}
export function airflowDynamicRequest(request){
  assertAirflowRequest(request);
  const copy={...request},key=['launch_time','resume_time'].includes(request.action)?'time':request.action;
  copy[key]={...request[key]};
  if(copy[key].controller==null)delete copy[key].controller;
  for(const name of ['controller','derivatives','operating_constraints'])delete copy[name];
  return copy;
}
