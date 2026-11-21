import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {applySettings} from '../web/case-settings.js';
import {createEquilibriumSettings} from '../web/equilibrium-state.js';
import {frameOptions,frameInputs} from '../web/dynamic-frame.js';
import {frequencyRange} from '../web/frequency-results.js';
import {parseInitialProfiles} from '../web/solver-json.js';
import {fourierWakeOptions} from '../web/fourier-wake.js';
import {steadyFlightConfiguration} from '../web/steady-flight.js';
import {createTimeAccuracy} from '../web/time-accuracy.js';
import {createTimeInitial} from '../web/time-initial.js';
import {parseActuatorTargets} from '../web/time-actuators.js';
import {selectedNumerics,selectionAllowsMode,assertAirflowInputs,airflowDynamicRequest,numericalRequest} from '../web/numerical-policy.js';

const text=path=>readFileSync(new URL(path,import.meta.url),'utf8');
const main=text('../web/main.js'),frequency=text('../web/frequency-results.js');
const configuration=JSON.parse(text('../examples/dae-level-flight-project.json')).cases.find(c=>c.id==='dae-level-bode').configuration;
const between=(source,start,end)=>{
  const a=source.indexOf(start),b=source.indexOf(end,a);
  assert.ok(a>=0&&b>a,`Missing production code: ${start}`);
  return source.slice(a,b);
};
const runSource=between(main,'async function run(', '\nfunction inspectOperatingPoint(');
const optionsSource=between(frequency,'  function options(){','  function initialProfiles(){');
const acceptSource=between(main,'function acceptFlightTrim(', '\nasync function loadCase(');
const switchSource=between(main,'async function changeAnalysisMode(', "\n$('mode').onchange=");
const modalSource=between(text('../web/mode-results.js'),'  return {setResult,geometry,pause,options:', '\n}');
const timeSource=between(text('../web/time-results.js'),'  function options(){', "\n  for(const id of ['time-duration'");

// This checks the JS request boundary without a browser, worker or numerical solve.
// The DOM stub dispatches setting events and exposes active flight/Bode fields;
// it does not model rendering, responsive layout or all main.js event handlers.
async function requestFor(edit=()=>{},trimTo=null,coldTrim=false){
  const previous=globalThis.document,fields=new Map(),extra=new Map(),noop=()=>{};
  const input=(id,value)=>({id,tagName:'INPUT',type:typeof value==='boolean'?'checkbox':'text',
    value:typeof value==='boolean'?'':value,checked:value===true,disabled:false,hidden:false,dataset:{},
    listeners:{},addEventListener(kind,fn){(this.listeners[kind]??=[]).push(fn);},
    dispatchEvent(event){for(const fn of this.listeners[event.type]??[])fn(event);this['on'+event.type]?.(event);},
    closest(){return null;},getAttribute(name){return name==='data-control'?this.dataset.control:
      name==='data-power'?this.dataset.power:name==='data-circulation-beam'?this.dataset.circulationBeam:null;},
    click(){},focus(){},checkValidity(){return this.value!==''&&Number.isFinite(Number(this.value));},reportValidity(){return this.checkValidity();}});
  for(const [key,value] of Object.entries(configuration.fields))fields.set(key,input(key,value));
  for(const key of ['moving-velocity-x','moving-velocity-y','moving-velocity-z'])fields.set(key,input(key,'0'));
  fields.set('fourier-wake-diagnostic',input('fourier-wake-diagnostic',false));
  const dynamic={};
  for(const [name,attribute] of [['controls','control'],['powers','power'],['circulation','circulationBeam']])
    dynamic[name]=Object.keys(configuration[name]).map(key=>Object.assign(input('', '0'),{dataset:{[attribute]:key}}));
  dynamic.derivatives=configuration.derivative_parameters.map(key=>input('',key));
  const $=id=>fields.get(id)??extra.get(id)??(extra.set(id,input(id,'')),extra.get(id));
  for(const [id,name] of [['controls','controls'],['powers','powers'],['circulation-modes','circulation']])$(id).querySelectorAll=()=>dynamic[name];
  const active=['speed','alpha','beta','frequency-start','frequency-end','frequency-count','frequency-step'];
  const document={getElementById:$,querySelectorAll(selector){
    if(selector.startsWith('#model-configuration input'))return [...fields.values()];
    if(selector==='[data-control]')return dynamic.controls;
    if(selector==='[data-power]')return dynamic.powers;
    if(selector==='[data-circulation-beam]')return dynamic.circulation;
    if(selector==='#derivative-parameters input')return dynamic.derivatives;
    if(selector.startsWith('#analysis-settings .fields input'))return [...active.map($),...dynamic.controls,...dynamic.powers];
    throw new Error('Unexpected selector: '+selector);
  },querySelector(selector){
    const match=selector.match(/^\[data-(control|power)="(\d+)"\]$/);
    if(match)return dynamic[match[1]==='control'?'controls':'powers'].find(e=>e.dataset[match[1]]===match[2]);
    throw new Error('Unexpected selector: '+selector);
  }};
  globalThis.document=document;
  try{
    const equilibriumView=createEquilibriumSettings(noop,noop,error=>{throw error;});
    let constraints=[];
    applySettings(configuration,{clearConstraints:()=>{constraints=[];},addConstraint:c=>constraints.push(c),
      refreshDerivatives:noop,restoreEquilibrium:value=>equilibriumView.restore(value)});
    assert.equal($('equilibrium-enable').disabled,false);
    assert.equal($('equilibrium-enable').checked,true);
    for(const name of ['controls','powers'])for(const e of dynamic[name])assert.equal(e.value,configuration[name][e.dataset.control??e.dataset.power]);
    const model={name:'Daedalus',controls:[2,3],engine_controls:[{index:1}],beams:[],reference:[[1,1,1]]};
    const state={model,source:configuration.source,revision:0,busy:false,dirty:false};
    const options=new Function('$','getModel','frequencyRange','frameOptions','frameInputs','initialProfiles',
      optionsSource+'return options;')($,()=>model,frequencyRange,frameOptions,frameInputs,()=>parseInitialProfiles($('frequency-initial').value));
    const requests=[],errors=[];
    const view={pause:noop,setResult:noop,setBase:noop,setTrajectory:noop};
    const timeOptions=new Function('$','document','getState','parseActuatorTargets','accuracy','initial',timeSource+'return options;')
      ($,document,()=>state,parseActuatorTargets,createTimeAccuracy('time'),createTimeInitial(noop,noop,noop));
    const modalOptions=new Function('$','frameOptions','setResult','geometry','pause',modalSource)
      ($,frameOptions,noop,noop,noop).options;
    const dependencies={state,$,document,equilibriumView,
      quiescentSelected:()=>false,sourceVacuumSelected:()=>false,sourceStillAirSelected:()=>false,
      sourceMovingVacuumSelected:()=>false,sourceAirflowSelected:()=>$('structural-equations').value==='aswing-airflow',
      vacuumWorkbenchFields:()=>Object.fromEntries([...fields].map(([key,e])=>[key,e.type==='checkbox'?e.checked:e.value])),
      readConstraints:()=>constraints,assertAirflowInputs,airflowDynamicRequest,numericalRequest,fourierWakeOptions,
      currentNumerics:()=>selectedNumerics($('structural-equations').value),
      motionGroups:[['rates'],['acceleration'],['angular_acceleration']],flowFailureView:{clear:noop,set:noop},
      workbenchView:{show:noop},timeView:{...view,options:timeOptions},modeView:{...view,options:modalOptions},romView:view,stabilityView:view,
      frequencyView:{...view,options},nodeView:{settings:()=>configuration.mesh},
      feedbackView:{options:()=>{assert.equal($('feedback-enabled').checked,false);return null;},inputs:()=>[]},
      gustView:{condition:()=>{assert.equal($('gust-kind').value,'none');return {gust:null,time:0};}},
      toggleBusy:value=>{state.busy=value;},status:noop,resetResult:noop,
      showError:error=>errors.push(error.message),rpc:async request=>{requests.push(request);return {converged:true,restart_context:{setup:{condition:configuration.equilibrium.state.launch.condition}}};},
      presentResult:noop,presentFrequency:noop,presentModes:noop,shareTimeHistoryMetadata:value=>value};
    if(trimTo){
      // Replay the completed physical trim through the actual UI adoption and
      // mode-switch code. The next request is captured before any solver runs.
      const starting=structuredClone(configuration);
      starting.fields.alpha='1';starting.fields.beta='0';
      starting.controls={'2':'0','3':'0'};starting.powers={'1':'0'};
      const trim=steadyFlightConfiguration(starting,model,{kind:'level',pitch:'2',yaw:'3',roll:'',power:'1'});
      applySettings(trim,{clearConstraints:()=>{constraints=[];},addConstraint:c=>constraints.push(c),refreshDerivatives:noop,restoreEquilibrium:value=>equilibriumView.restore(value)});
      assert.equal(constraints.length,7);assert.equal(equilibriumView.initial(),null);
      $('constraint-rows').replaceChildren=()=>{constraints=[];};
      const accept=new Function('$','document','equilibriumView','allocationView','customView','status','projectView',acceptSource+'return acceptFlightTrim;')
        ($,document,equilibriumView,{refresh:noop},{refresh:noop},noop,null);
      const seed=configuration.equilibrium.state;
      accept({equilibrium_state:seed,operating_values:seed.operating_values});
      assert.equal(constraints.length,0);
      assert.equal(Number($('alpha').value),seed.launch.condition.alpha);
      $('mode').value=trimTo;equilibriumView.refresh();
      const switchDependencies={...dependencies,selectionAllowsMode,configureSourceFrequencyInputs:noop,refreshAnalysisVisibility:noop};
      await new Function(...Object.keys(switchDependencies),switchSource+'return changeAnalysisMode;')(...Object.values(switchDependencies))();
      assert.equal($('structural-equations').value,'aswing-airflow');
      assert.deepEqual(equilibriumView.initial(),seed);
    }
    if(coldTrim){
      // Take literal flight defaults from the current main template, not the
      // checked project's solved condition. Dynamic pose/motion fields start
      // at zero, except the upward ground normal, as in the template loops.
      const starting=structuredClone(configuration);
      for(const [key,value] of Object.entries(starting.fields)){
        const input=main.match(new RegExp(`<input\\b[^>]*\\bid="${key}"[^>]*>`))?.[0];
        if(input){
          if(typeof value==='boolean')starting.fields[key]=/\bchecked\b/.test(input);
          else {const literal=input.match(/\bvalue="([^"]*)"/)?.[1];if(literal!==undefined&&!literal.includes('${'))starting.fields[key]=literal;}
        }
        const select=main.match(new RegExp(`<select\\b[^>]*\\bid="${key}"[^>]*>([\\s\\S]*?)<\\/select>`))?.[1];
        if(select){const options=[...select.matchAll(/<option\b([^>]*)value="([^"]+)"([^>]*)>/g)];
          const chosen=options.find(o=>/\bselected\b/.test(o[1]+o[3]))??options[0];
          if(chosen)starting.fields[key]=chosen[2];}
      }
      for(const prefix of ['rates','acceleration','angular_acceleration','position-earth'])
        for(const axis of ['x','y','z'])starting.fields[`${prefix}-${axis}`]='0';
      for(const axis of ['bank','elevation','heading'])starting.fields[`attitude-${axis}`]='0';
      for(const axis of ['x','y','z'])starting.fields[`ground-normal-${axis}`]=axis==='z'?'1':'0';
      for(const group of ['controls','powers','circulation'])for(const key of Object.keys(starting[group]))starting[group][key]='0';
      starting.fields['gust-kind']='none';
      const trim=steadyFlightConfiguration(starting,model,{kind:'level',pitch:'2',yaw:'3',roll:'',power:'1'});
      applySettings(trim,{clearConstraints:()=>{constraints=[];},addConstraint:c=>constraints.push(c),refreshDerivatives:noop,restoreEquilibrium:value=>equilibriumView.restore(value)});
      assert.equal(equilibriumView.initial(),null);
    }
    edit($);
    await new Function(...Object.keys(dependencies),runSource+'return run;')(...Object.values(dependencies))();
    assert.equal(state.busy,false);
    return {requests,errors};
  }finally{globalThis.document=previous;}
}

test('restored Daedalus case sends the checked trim and complete 41-point Bode setup',async()=>{
  const {requests,errors}=await requestFor();
  assert.deepEqual(errors,[]);assert.equal(requests.length,1);
  const request=requests[0],seed=configuration.equilibrium.state;
  assert.equal(request.action,'frequency');assert.equal(request.mode,'frequency');
  assert.equal(request.source,configuration.source);assert.deepEqual(request.panels,configuration.mesh);
  assert.deepEqual(request.numerics,configuration.numerics);
  assert.deepEqual(request.frequency.initial_state,seed);
  assert.equal(request.frequency.frame,'free');assert.equal(request.frequency_spacing,'log');
  assert.equal(request.retain_frequency,true);assert.equal(request.frequency.matrices,false);
  assert.deepEqual(request.frequency.inputs,['control.2','control.3','power.1']);
  assert.equal(request.frequency.frequencies.length,41);
  assert.ok(Math.abs(request.frequency.frequencies[0]/(2*Math.PI)-.1)<1e-14);
  assert.ok(Math.abs(request.frequency.frequencies[20]/(2*Math.PI)-1)<1e-14);
  assert.ok(Math.abs(request.frequency.frequencies[40]/(2*Math.PI)-10)<1e-14);
  assert.equal(request.operating_constraints,undefined);assert.equal(request.frequency.controller,undefined);
  // Explicit zero per-beam modes and an empty map both select interval circulation.
  for(const key of Object.keys(seed.launch.condition)){
    if(key==='circulation_modes'){
      assert.ok(Object.values(request.condition[key]).every(v=>v===0));
      assert.ok(Object.values(seed.launch.condition[key]).every(v=>v===0));
    }else assert.deepEqual(request.condition[key],seed.launch.condition[key],key);
  }
});

for(const mode of ['frequency','modes','time'])test(`completed trim reaches ${mode} with solved controls, free frame and released targets`,async()=>{
  const {requests,errors}=await requestFor(()=>{},mode),seed=configuration.equilibrium.state;
  assert.deepEqual(errors,[]);assert.equal(requests.length,1);
  const request=requests[0];
  assert.equal(request.action,mode==='time'?'launch_time':mode);
  assert.equal(request.source,configuration.source);assert.deepEqual(request.numerics,configuration.numerics);
  assert.equal(request.operating_constraints,undefined);
  if(mode==='time'){
    assert.equal(request.time.frame,'free');assert.deepEqual(request.equilibrium_state,seed);
    assert.equal(request.condition,undefined);
  }else{
    assert.equal(request[mode].frame,'free');assert.deepEqual(request[mode].initial_state,seed);
    for(const key of ['speed','alpha','beta','attitude','controls','powers','rates','acceleration','angular_acceleration'])
      assert.deepEqual(request.condition[key],seed.launch.condition[key],key);
    assert.deepEqual(request.panels,configuration.mesh);
  }
});

test('an empty restored airspeed is reported before any solver request',async()=>{
  const {requests,errors}=await requestFor($=>{$('speed').value='';});
  assert.equal(requests.length,0);
  assert.deepEqual(errors,['Check speed: A value is required.']);
});

test('invalid settings open every enclosing disclosure before focusing and reporting validity',async()=>{
  const events=[];
  const outer={setAttribute(name,value){assert.equal(name,'open');assert.equal(value,'');events.push('outer open');},parentElement:{closest:()=>null}};
  const inner={setAttribute(name,value){assert.equal(name,'open');assert.equal(value,'');events.push('inner open');},parentElement:{closest:()=>outer}};
  const {requests,errors}=await requestFor($=>{
    const field=$('frequency-count');field.value='';
    field.closest=selector=>selector==='details'?inner:null;
    field.focus=()=>events.push('focus');
    field.reportValidity=()=>events.push('validity');
  });
  assert.equal(requests.length,0);
  assert.deepEqual(errors,['Check frequency-count: A value is required.']);
  assert.deepEqual(events,['inner open','outer open','focus','validity']);
});

test('disabling the loaded trim explicitly removes the initial state from the Bode request',async()=>{
  const {requests,errors}=await requestFor($=>{$('equilibrium-enable').checked=false;});
  assert.deepEqual(errors,[]);assert.equal(requests.length,1);
  assert.equal(requests[0].frequency.initial_state,undefined);
});

test('default Daedalus steady-flight action requests a cold trim from the actual flight defaults',async()=>{
  const {requests,errors}=await requestFor(()=>{},null,true);
  assert.deepEqual(errors,[]);assert.equal(requests.length,1);
  const request=requests[0];
  assert.equal(request.action,'solve');assert.equal(request.mode,'mounted');
  assert.equal(request.initial_state,undefined);
  assert.equal(request.controller,null);assert.equal(request.derivatives,undefined);
  assert.equal(request.condition.speed,21.981627296587927);
  assert.equal(request.condition.alpha,3);assert.equal(request.condition.beta,0);
  assert.deepEqual(request.condition.attitude,[0,3,0]);
  assert.deepEqual(request.condition.controls,{'2':0,'3':0});
  assert.deepEqual(request.condition.powers,{'1':0});
  assert.equal(request.condition.mach,null);assert.equal(request.condition.density,null);
  assert.equal(request.condition.gravity_magnitude,null);
  assert.equal(request.condition.freeze_influences,true);
  assert.equal(request.operating_constraints.length,7);
  assert.deepEqual(request.panels,JSON.parse(text('../web/daedalus-mesh.json')));
  assert.equal(request.source,text('../public/examples/dae.asw'));
});
