import {validateConfiguration} from './project-data.js';
import {numericalSelection,sameNumerics} from './numerical-policy.js';
const $=id=>document.getElementById(id);
// The documented uncapped axial law is the app's brace model.
export const defaultStrutMode='bilateral';
// Transverse added mass of a circular cylinder: rho*pi*R^2 per unit length.
export const defaultBodyAddedMassFactor=1;
const excluded=new Set(['example','panels','equilibrium-enable']);
// Saved cases retain angular frequencies in rad/input T; the UI shows cycles.
const savedFrequencyText=new WeakMap();
const savedNumberText=new WeakMap();
export function fieldValue(element){
  if(element.type==='checkbox')return element.checked;
  const number=savedNumberText.get(element);
  if(number?.display===element.value)return number.raw;
  if(element.dataset?.frequencyUnit!=='cycles')return element.value;
  const saved=savedFrequencyText.get(element);
  if(saved?.display===element.value)return saved.angular;
  return element.value.trim()===''?'':String(2*Math.PI*Number(element.value));
}
function formatNumberField(element){
  if(element.dataset?.displayDecimals===undefined)return;
  const raw=fieldValue(element),number=Number(raw);
  if(raw.trim()===''||!Number.isFinite(number)||!element.checkValidity())return;
  const display=number.toFixed(Number(element.dataset.displayDecimals));
  // Keep very small valid inputs from displaying as an invalid zero speed.
  if(element.min!==''&&Number(display)<Number(element.min))return;
  element.value=display;savedNumberText.set(element,{display:element.value,raw});
}
export function bindNumberFormatting(element){
  element.addEventListener('input',()=>savedNumberText.delete(element));
  element.addEventListener('blur',()=>formatNumberField(element));
  formatNumberField(element);
}
export function setFieldValue(element,value){
  if(element.type==='checkbox'){element.checked=value;return;}
  savedNumberText.delete(element);
  if(element.dataset?.frequencyUnit==='cycles'){
    element.value=value.trim()===''?'':String(Number(value)/(2*Math.PI));
    savedFrequencyText.set(element,{display:element.value,angular:value});
  }else {element.value=value;formatNumberField(element);}
}
// Stable configuration containers own inputs in both responsive layouts. Result selectors,
// generated plots, file-input paths and worker session handles are not inputs.
export function settingFields(){
  const fields=new Map();
  for(const element of document.querySelectorAll('#model-configuration input,#model-configuration select,#model-configuration textarea,#analysis-settings input,#analysis-settings select,#analysis-settings textarea')){
    if(element.type==='file'||element.closest('#project-settings,#steady-flight-settings')||excluded.has(element.id))continue;
    const key=element.id|| (element.dataset.timeLoad?'time-load:'+element.dataset.timeLoad:element.dataset.timeTarget?'time-target:'+element.dataset.timeTarget:null);
    if(key)fields.set(key,element);
  }
  return fields;
}
const values=attribute=>Object.fromEntries([...document.querySelectorAll(`[data-${attribute}]`)].map(e=>[e.getAttribute('data-'+attribute),e.value]));
export function captureSettings({source,filename,mesh,constraints,equilibrium,numerics}){
  return validateConfiguration({source,filename,mesh,constraints,equilibrium,
    ...(numerics===undefined?{}:{numerics}),
    fields:Object.fromEntries([...settingFields()].map(([key,e])=>[key,fieldValue(e)])),
    controls:values('control'),powers:values('power'),circulation:values('circulation-beam'),
    derivative_parameters:[...document.querySelectorAll('#derivative-parameters input:checked')].map(e=>e.value)});
}
export function validateSettings(configuration,model=null){
  const value=validateConfiguration(configuration),fields=settingFields();
  if(Object.hasOwn(value.fields,'strut-mode')){
    if(value.fields['strut-mode']!==defaultStrutMode)throw new Error('This saved case uses a nondefault brace model; its settings cannot be restored in this app.');
    delete value.fields['strut-mode'];
  }
  if(Object.hasOwn(value.fields,'body-added-mass')){
    if(Number(value.fields['body-added-mass'])!==defaultBodyAddedMassFactor)throw new Error('This saved case uses a nondefault fuselage apparent mass; its settings cannot be restored in this app.');
    delete value.fields['body-added-mass'];
  }
  // Normalize only the editable workspace copy, never an archived solution.
  if(numericalSelection(value.numerics)==='midpoint')delete value.numerics;
  // Still-air is opt-in: existing cases keep their original modal medium.
  if(!Object.hasOwn(value.fields,'modal-quiescent'))value.fields['modal-quiescent']=false;
  if(!Object.hasOwn(value.fields,'modal-quiescent-density'))value.fields['modal-quiescent-density']=value.fields.density??'1.225';
  // Old cases have no separate prior-frame value. Preserve their saved frame;
  // a first-version still-air case can only recover its printed fixed frame.
  if(!Object.hasOwn(value.fields,'modal-ordinary-frame'))value.fields['modal-ordinary-frame']=value.fields['modal-frame'];
  // Migrate only the editable workspace; archived configuration bytes stay intact.
  for(const axis of ['x','y','z'])if(!Object.hasOwn(value.fields,`moving-velocity-${axis}`))value.fields[`moving-velocity-${axis}`]='0';
  if(!['fixed','prescribed','free','mixed'].includes(value.fields['modal-ordinary-frame']))throw new Error('Unsupported saved ordinary modal frame.');
  if(!value.fields['modal-quiescent']&&value.fields['modal-ordinary-frame']!==value.fields['modal-frame'])throw new Error('Saved ordinary modal frames do not match.');
  if(value.fields['modal-quiescent']&&(value.fields['modal-vacuum']||value.fields['modal-frame']!=='fixed'))throw new Error('Still-air cases require a fixed modal frame and vacuum off.');
  // Older cases used enabled lag and the fixed quarter-chord wake core.
  if(!Object.hasOwn(value.fields,'aero-lag'))value.fields['aero-lag']=true;
  if(!Object.hasOwn(value.fields,'wake-core-ratio'))value.fields['wake-core-ratio']='0.25';
  // Older saved cases used current influences; the new-analysis default is frozen.
  if(!Object.hasOwn(value.fields,'freeze-influences'))value.fields['freeze-influences']=false;
  if(!Object.hasOwn(value.fields,'fourier-wake-diagnostic'))value.fields['fourier-wake-diagnostic']=false;
  if(!Object.hasOwn(value.fields,'stall-factor'))value.fields['stall-factor']='40';
  if(!Object.hasOwn(value.fields,'stall-width'))value.fields['stall-width']='0.05';
  // The polar panel is no longer part of the workbench.
  delete value.fields['operating-points-values'];
  delete value.fields['operating-points-initialization'];
  if(!Object.hasOwn(value.fields,'time-actuators'))value.fields['time-actuators']='';
  for(const [key,defaultValue] of Object.entries({'static-gravity-mode':'file','static-gravity-x':'0','static-gravity-y':'0','static-gravity-z':'-9.81'}))
    if(!Object.hasOwn(value.fields,key))value.fields[key]=defaultValue;
  for(const [key,defaultValue] of Object.entries({'time-accuracy-enabled':false,'time-accuracy-rtol':'0.001','time-accuracy-atol':'0.000001','time-accuracy-minimum':''}))
    if(!Object.hasOwn(value.fields,key))value.fields[key]=defaultValue;
  if(Object.keys(value.fields).length!==fields.size||[...fields.keys()].some(key=>!Object.hasOwn(value.fields,key)))throw new Error('Project workbench settings do not match this app version.');
  for(const [key,v] of Object.entries(value.fields)){
    const e=fields.get(key);if(!e)throw new Error('Unknown workbench setting: '+key);
    if(e.type==='checkbox'?typeof v!=='boolean':typeof v!=='string')throw new Error('Invalid setting: '+key);
    if(e.tagName==='SELECT'&&!key.startsWith('trim-')&&![...e.options].some(o=>o.value===v))throw new Error('Unsupported choice for '+key);
  }
  if(model){
    if(!sameNumerics(value.numerics,model.numerics))throw new Error('Saved numerical settings do not match the inspected model.');
    for(const [name,ids] of [['controls',model.controls],['powers',model.engine_controls.map(e=>e.index)],['circulation',model.beams.filter(b=>b.lifting).map(b=>b.index)]]){
      if(Object.keys(value[name]).length!==ids.length||ids.some(id=>!Object.hasOwn(value[name],id)))throw new Error('Saved '+name+' do not match the ASW model.');
    }
    for(const key of ['roll','pitch','yaw','engine']){
      const available=key==='engine'?model.engine_controls.map(e=>String(e.index)):model.controls.map(String),selected=value.fields['trim-'+key];
      if(available.length?!available.includes(selected):selected!=='')throw new Error('Saved trim preset does not match the ASW model.');
    }
  }
  return value;
}
export function applySettings(value,{refreshDerivatives,addConstraint,clearConstraints,restoreEquilibrium}){
  clearConstraints();
  const fields=settingFields();
  function assign(){for(const [key,v] of Object.entries(value.fields)){const e=fields.get(key);setFieldValue(e,v);}}
  assign();
  // Dispatch only ordinary setting events. Mesh/example imports are handled by
  // the owning views, and project loading never sends a solve request.
  for(const e of fields.values()){e.dispatchEvent(new Event('input'));e.dispatchEvent(new Event('change'));}
  // Unit selectors can convert display values; restore the exact saved text
  // after their bookkeeping, then rebuild dependent constraint/control lists.
  assign();
  for(const [name,attribute] of [['controls','control'],['powers','power'],['circulation','circulation-beam']]){
    for(const e of document.querySelectorAll(`[data-${attribute}]`))e.value=value[name][e.getAttribute('data-'+attribute)];
  }
  for(const constraint of value.constraints)addConstraint(constraint);
  refreshDerivatives();
  const derivatives=[...document.querySelectorAll('#derivative-parameters input')];
  if(value.derivative_parameters.some(key=>!derivatives.some(e=>e.value===key)))throw new Error('Saved derivative inputs do not match the controller and model.');
  for(const e of derivatives)e.checked=value.derivative_parameters.includes(e.value);
  restoreEquilibrium(value.equilibrium);
  $('mode').dispatchEvent(new Event('change'));
}
