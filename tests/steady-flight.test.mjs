import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {steadyFlightConfiguration,createSteadyFlight,solvedFlightCondition} from '../web/steady-flight.js';
import {portableResult} from '../web/solution-data.js';

const project=JSON.parse(readFileSync(new URL('../examples/dae-level-flight-project.json',import.meta.url),'utf8'));
const configuration=project.cases.find(c=>c.id==='dae-level-trim').configuration;
const model={controls:[2,3],engine_controls:[{index:1}]};
const choices={kind:'level',pitch:'2',yaw:'3',roll:'',power:'1'};

test('ordinary Daedalus trim reproduces seven balance targets without loading a reference state',()=>{
  const before=JSON.stringify(configuration),result=steadyFlightConfiguration(configuration,model,choices);
  assert.deepEqual(result.constraints,configuration.constraints);
  assert.equal(result.source,configuration.source);
  assert.deepEqual(result.mesh,configuration.mesh);
  assert.deepEqual(result.numerics,configuration.numerics);
  assert.equal(result.fields.speed,configuration.fields.speed);
  assert.deepEqual(result.controls,configuration.controls);
  assert.deepEqual(result.equilibrium,{state:null,enabled:false,label:''});
  for(const group of ['rates','acceleration','angular_acceleration'])for(const axis of ['x','y','z'])assert.equal(result.fields[`${group}-${axis}`],'0');
  for(const key of ['time-frame','frequency-frame','modal-frame','modal-ordinary-frame'])assert.equal(result.fields[key],'free');
  assert.equal(result.fields['feedback-enabled'],false);
  assert.equal(JSON.stringify(configuration),before);
});

test('glide solves its flight angle with thrust off; independent roll control keeps prescribed zero sideslip',()=>{
  const result=steadyFlightConfiguration(configuration,{controls:[1,2,3],engine_controls:[{index:1}]},{...choices,kind:'glide',roll:'1'});
  assert.equal(result.constraints.length,6);
  assert.deepEqual(result.constraints.find(c=>c.quantity==='force.x'),{variable:'attitude.elevation',quantity:'force.x',target:0});
  assert.equal(result.constraints.find(c=>c.quantity==='moment.x').variable,'control.1');
  assert.equal(result.fields.beta,'0');
  assert.equal(result.powers['1'],'0');
  assert.ok(!result.constraints.some(c=>c.quantity==='flight_path'));
  const unpowered={...configuration,powers:{}};
  assert.equal(steadyFlightConfiguration(unpowered,{...model,engine_controls:[]},{...choices,kind:'glide',power:''}).constraints.length,6);
});

test('bad assignments and speed fail before inputs change or a solve starts',()=>{
  for(const update of [{yaw:'2'},{roll:'2'},{power:''},{kind:'unknown'}])assert.throws(()=>steadyFlightConfiguration(configuration,model,{...choices,...update}));
  for(const speed of ['', '0','-1','Infinity','no'])assert.throws(()=>steadyFlightConfiguration({...configuration,fields:{...configuration.fields,speed}},model,choices),/airspeed/);
});

function fixture(run){
  const elements=new Map();
  const el=()=>({value:'',hidden:false,disabled:false,textContent:'',children:[],append(x){this.children.push(x);},replaceChildren(){this.children=[];}});
  const document={getElementById(id){if(!elements.has(id))elements.set(id,el());return elements.get(id);},createElement:el};
  const $=id=>document.getElementById(id);
  $('steady-flight-settings').querySelectorAll=()=>['kind','pitch','yaw','roll','power'].map(key=>$('flight-trim-'+key)).concat($('trim-steady-flight'));
  const previous=globalThis.document;globalThis.document=document;
  const calls=[],state={model,source:configuration.source,busy:false,dirty:false};
  const view=createSteadyFlight({getState:()=>state,capture:()=>configuration,
    load:async c=>{calls.push(['load',c]);},run:async()=>{calls.push(['run']);return run();},
    accept:r=>calls.push(['accept',r]),showError:e=>calls.push(['error',e.message])});
  view.setModel(model,configuration.source);
  return {$,calls,state,view,restore(){globalThis.document=previous;}};
}

test('trim action loads current-aircraft targets, runs once, then adopts only a completed equilibrium',async()=>{
  const solved={equilibrium_state:{positions:[1]},operating_values:{alpha:3.1}};
  const f=fixture(()=>solved);
  try{
    assert.equal(f.$('flight-trim-pitch').value,'2');assert.equal(f.$('flight-trim-yaw').value,'3');assert.equal(f.$('flight-trim-roll').value,'');
    await f.$('trim-steady-flight').onclick();
    assert.deepEqual(f.calls.map(c=>c[0]),['load','run','accept']);
    assert.deepEqual(f.calls[0][1].constraints,configuration.constraints);
    assert.equal(f.calls[2][1],solved);
    assert.match(f.$('flight-trim-status').textContent,/Trim complete/);
    f.state.dirty=true;await f.$('trim-steady-flight').onclick();assert.equal(f.calls.length,3);
  }finally{f.restore();}
});

test('failed or cancelled trim never reports success or adopts a state',async()=>{
  const f=fixture(()=>undefined);
  try{
    await f.$('trim-steady-flight').onclick();
    assert.deepEqual(f.calls.map(c=>c[0]),['load','run']);
    assert.match(f.$('flight-trim-status').textContent,/did not finish/);
    assert.equal(f.$('trim-steady-flight').disabled,false);
  }finally{f.restore();}
});

test('split horizontal foils use sideslip for yaw and retain independent pitch and roll',async()=>{
  const f=fixture(()=>undefined);
  try{
    const foilModel={controls:[1,2,3],engine_controls:[{index:1}],reference:[[1,1,1],[0,0,0]],
      distributions:[1,2,3].map(beam=>({beam,lifting:true,properties:[`dCLdF${beam}`]})),
      beams:[[-1,1],[-2,-.1],[.1,2]].map(([start,end],i)=>({index:i+1,axis:[[[0,start,0],[0,end,0]]]}))};
    f.state.model=foilModel;f.view.setModel(foilModel,'split foils');
    assert.equal(f.$('flight-trim-pitch').value,'1');
    assert.equal(f.$('flight-trim-roll').value,'2');
    assert.equal(f.$('flight-trim-yaw').value,'');
    await f.$('trim-steady-flight').onclick();
    const targets=f.calls[0][1].constraints;
    for(const [variable,quantity] of [['control.2','moment.x'],['control.1','moment.y'],['beta','moment.z']])
      assert.ok(targets.some(target=>target.variable===variable&&target.quantity===quantity));
    assert.throws(()=>steadyFlightConfiguration(configuration,foilModel,{...choices,pitch:'1',yaw:'',roll:''}),/either roll or yaw/);
  }finally{f.restore();}
});

test('fresh aircraft imports clear previous equilibrium and targets; mesh edits preserve them',()=>{
  const main=readFileSync(new URL('../web/main.js',import.meta.url),'utf8');
  const start=main.indexOf('  if(freshMesh){',main.indexOf('async function inspect('));
  const end=main.indexOf('  const sameSource=',start);
  assert.ok(start>=0&&end>start);
  const setup=new Function('freshMesh','source','nodeView','equilibriumView','daedalusDefaultMesh','$','allocationView','customView','exampleKey','sailplaneMesh',main.slice(start,end));
  for(const [mesh,exampleKey] of [[null,''],[{default:48},''],[{default:32},'usa']]){
    const calls=[];
    let targets=[{variable:'control.3',quantity:'user.trim1',expression:'sensor("8.displacement_body.y")',target:0}];
    const $=id=>{assert.equal(id,'constraint-rows');return {replaceChildren:()=>{targets=[];calls.push('clear targets');}};};
    const allocation={refresh:preserve=>{assert.equal(preserve,false);assert.deepEqual(targets,[]);calls.push('clear allocation');}};
    const custom={refresh:()=>{assert.deepEqual(targets,[]);calls.push('clear custom targets');}};
    const nodes={clear:()=>calls.push('clear mesh'),restore:value=>{assert.equal(value,mesh);calls.push('restore mesh');}};
    const equilibrium={restore:value=>{assert.deepEqual(value,{state:null,enabled:false,label:''});calls.push('clear equilibrium');}};
    setup(true,'aircraft',nodes,equilibrium,()=>exampleKey==='usa'?null:mesh,$,allocation,custom,exampleKey,mesh);
    const cleared=['clear mesh','clear equilibrium','clear targets','clear allocation','clear custom targets'];
    assert.deepEqual(calls,mesh?[...cleared,'restore mesh']:cleared);
    calls.length=0;
    targets=[{variable:'alpha',quantity:'force.z',target:0}];
    setup(false,'aircraft',nodes,equilibrium,()=>mesh,$,allocation,custom);
    assert.deepEqual(calls,[]);
    assert.deepEqual(targets,[{variable:'alpha',quantity:'force.z',target:0}]);
  }
});

test('main workbench opens Drela Daedalus, keeps tabs, and removes validation shortcuts',()=>{
  const main=readFileSync(new URL('../web/main.js',import.meta.url),'utf8');
  const selector=main.match(/<select id="example">([\s\S]*?)<\/select>/)[1];
  assert.deepEqual([...selector.matchAll(/<option value="([^" ]+)"/g)].map(m=>m[1]),['dae','usa','fw']);
  assert.match(selector,/<option value="dae" selected>/);
  assert.ok(main.includes("[['editor','Editor'],['settings','Settings'],['plots','Plots'],['output','Output']]"));
  assert.ok(!/\/validation\/|\/isae-progress\/|dae-level-apply|sa12-baseline-apply|st5-baseline-apply/.test(main));
});

test('accepting trim preserves fractional controls, releases targets and retains the converged base',()=>{
  const main=readFileSync(new URL('../web/main.js',import.meta.url),'utf8');
  const source=main.slice(main.indexOf('function acceptFlightTrim('),main.indexOf('\nasync function loadCase('));
  const elements=new Map(),$=id=>{if(!elements.has(id))elements.set(id,{value:'',replaceChildren(){this.cleared=true;}});return elements.get(id);};
  const document={querySelector:selector=>$(selector)};let saved;
  const noop=()=>{};
  const accept=new Function('$','document','equilibriumView','allocationView','customView','status','projectView','setFieldValue',source+'return acceptFlightTrim;')
    ($,document,{restore:value=>{saved=value;}},{refresh:noop},{refresh:noop},noop,null,(field,value)=>{field.value=String(value);});
  const result={equilibrium_state:configuration.equilibrium.state,operating_values:{alpha:3.087143345018976,'attitude.elevation':3.0871450932,'control.2':-8.825752955534778,'power.1':6.01740609,'position_earth.z':-100,'rates.z':Math.PI/180,'angular_acceleration.x':Math.PI/90}};
  accept(result);
  assert.equal($('alpha').value,String(result.operating_values.alpha));
  assert.equal($('attitude-elevation').value,'3.0871450932');
  assert.equal($('[data-control="2"]').value,'-8.825752955534778');
  assert.equal($('[data-power="1"]').value,'6.01740609');
  assert.equal($('position-earth-z').value,'-100');
  assert.equal($('rates-z').value,'1');
  assert.equal($('angular_acceleration-x').value,'2');
  assert.equal($('constraint-rows').cleared,true);
  assert.equal(saved.state,result.equilibrium_state);assert.equal(saved.enabled,true);
});

test('solved condition agrees with the saved Daedalus equilibrium without changing its starting request',()=>{
  const seed=configuration.equilibrium.state,expected=seed.launch.condition;
  const initial=structuredClone(expected);
  initial.alpha=1;initial.beta=0;initial.attitude=[0,1,0];
  initial.controls={'2':0,'3':0};initial.powers={'1':0};
  const before=JSON.stringify(initial);
  const actual=solvedFlightCondition(initial,{operating_values:seed.operating_values});
  assert.deepEqual(actual,expected);
  assert.equal(JSON.stringify(initial),before);
  actual.controls['2']=999;actual.attitude[0]=999;
  assert.equal(JSON.stringify(initial),before);
  assert.equal(solvedFlightCondition(null,{}),null);
  assert.equal(solvedFlightCondition(undefined,{}),undefined);
});

test('solved conditions preserve units and options and include final feedback actuator values',()=>{
  const condition={speed:20,alpha:1,beta:0,rates:[0,0,0],attitude:[0,1,0],ground_normal:[0,0,1],stall:true,stall_factor:40};
  const actual=solvedFlightCondition(condition,{operating_values:{speed:21,'rates.z':0.1,'angular_acceleration.x':0.2,'position_earth.z':-100,'attitude.elevation':3,'control.2':-8,'power.1':6,'ground_normal.y':0.5,'unknown.x':9},feedback:{actuators:{F2:-7,E1:7}}});
  assert.deepEqual(actual,{speed:21,alpha:1,beta:0,rates:[0,0,0.1],angular_acceleration:[0.2,0,0],position_earth:[0,0,-100],attitude:[0,3,0],ground_normal:[0,0.5,1],controls:{'2':-7},powers:{'1':7},stall:true,stall_factor:40});
  assert.deepEqual(condition.rates,[0,0,0]);
  assert.deepEqual(condition.ground_normal,[0,0,1]);
});

test('steady, Bode and mode result captures save solved conditions and retain the original request',()=>{
  const main=readFileSync(new URL('../web/main.js',import.meta.url),'utf8');
  const prefix=(start,end)=>main.slice(main.indexOf(start),main.indexOf(end,main.indexOf(start)));
  const initial={speed:20,alpha:1,beta:0,controls:{'2':0},powers:{'1':0}};
  const solved={...initial,alpha:3,controls:{'2':-8},powers:{'1':6}};
  const request={mode:'mounted',condition:initial};
  const base={operating_values:{alpha:3,'control.2':-8,'power.1':6},request,software_provenance:{version:1}};
  const state={model:{name:'Aircraft'}},noop=()=>{};
  const present=new Function('state','equilibriumView','checkpointView','solvedFlightCondition','renderFlightOutput',
    prefix('function presentResult(', '    const map=')+'return state.result;} return presentResult;')
    (state,{setComputed:noop},{refresh:noop},solvedFlightCondition,noop);
  const capture=new Function('state','captureCase','hasComputedSolution','resultViewFields','document','workbenchView','archivedTimeHistory','portableResult','modeView','savedModalSupplements','frequencyView','structuredClone',
    prefix('function captureComputedSolution(', '\nasync function restoreComputedSolution(')+'return captureComputedSolution;')
    (state,()=>configuration,()=>true,()=>[],{querySelector:()=>null},{current:()=>null},()=>false,portableResult,{selectedIndex:()=>0},new WeakMap(),{captureComparison:()=>null},structuredClone);
  for(const mode of ['mounted','rigid']){
    present(base,mode,initial);
    const saved=JSON.parse(JSON.stringify(capture()));
    assert.deepEqual(saved.data.condition,solved);
    assert.deepEqual(saved.data.request.condition,initial);
  }
  for(const kind of ['frequency','modes']){
    const start=kind==='frequency'?'function presentFrequency(':'function presentModes(';
    const end=kind==='frequency'?'  state.frequency=result;':'  equilibriumView.setComputed(quiescent?null:';
    const presenter=new Function('solvedFlightCondition','isQuiescentResult','presentResult',
      prefix(start,end)+'return result;} return '+(kind==='frequency'?'presentFrequency':'presentModes')+';')
      (solvedFlightCondition,()=>false,present);
    const result=presenter({base,condition:initial,request:{...request,mode:kind},software_provenance:base.software_provenance});
    state[kind==='frequency'?'frequency':'modal']=result;
    const saved=JSON.parse(JSON.stringify(capture()));
    assert.deepEqual(saved.data.condition,solved);
    assert.deepEqual(saved.data.request.condition,initial);
    state.frequency=null;state.modal=null;
  }
  present({...base,atmosphere:{},time:1},'time',initial);
  assert.deepEqual(state.result.condition,initial,'Time snapshots keep their existing trajectory condition semantics.');
  assert.deepEqual(request.condition,initial);
});
