import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {DEFAULT_NUMERICS,SOURCE_NUMERICS,SECTION_NUMERICS,COUPLED_NUMERICS,VACUUM_NUMERICS,STILL_AIR_NUMERICS,
  numericalSelection,selectedNumerics,numericalMode,selectionAllowsMode,numericalRequest,structuralPolicyNote,
  assertStillAirInputs,assertStillAirRequest,stillAirModalRequest} from '../web/numerical-policy.js';
import {validateConfiguration,parseProject,emptyProject} from '../web/project-data.js';
import {sealSolution,verifySolution,validateSolution,kernelFingerprint} from '../web/solution-data.js';
import {captureSettings,applySettings} from '../web/case-settings.js';
import {quiescentCondition,isQuiescentResult,hasQuiescentEquilibrium} from '../web/quiescent-settings.js';

const density=1.2256;
const fields=()=>({mode:'modes','modal-frame':'fixed','modal-ordinary-frame':'fixed','modal-vacuum':false,
  'modal-quiescent':true,'modal-quiescent-density':String(density),'feedback-enabled':false,
  'gravity-mode':'custom','gravity-magnitude':'0',
  ...Object.fromEntries(['rates','acceleration','angular_acceleration'].flatMap(key=>['x','y','z'].map(axis=>[`${key}-${axis}`,'0'])))});
const configuration=()=>({source:'Name\nStill-air test\nEnd\n',filename:'still-air.asw',mesh:4,fields:fields(),
  numerics:{...STILL_AIR_NUMERICS},controls:{},powers:{},circulation:{},derivative_parameters:[],constraints:[],
  equilibrium:{state:null,enabled:false,label:''}});
const request=()=>({action:'modes',mode:'modes',source:configuration().source,condition:null,panels:4,
  numerics:{...STILL_AIR_NUMERICS},modes:{frame:'fixed',vacuum:false,quiescent_density:density,count:16,
    shift:[-.01,0],method:'dense',step:1e-5,rank_tolerance:1e-9,matrices:true,
    position:[0,0,0],attitude:[0,0,0],gravity_magnitude:0}});
const condition=()=>quiescentCondition({density,position_earth:[1,2,3],attitude:[4,5,6],gravity_magnitude:9.8});
const equilibrium=(numerics=STILL_AIR_NUMERICS,rho=density)=>({format:'openswing-equilibrium',version:1,positions:[[0,0,0]],
  identity:{...numerics,quiescent_density:rho},circulation:[],launch:{version:1,condition:null,
    motion:{rates:[0,0,0],acceleration:[0,0,0],angular_acceleration:[0,0,0]},
    frame:{position:[0,0,0],attitude:[0,0,0],velocity:[0,0,0],gravity_magnitude:0},
    controller:null,loads:[],quiescent_density:rho}});
async function solution(){
  const c=configuration(),p={format:'openswing-kernel-provenance',version:1,modules:{'source_quiescent.py':'a'.repeat(64)},
    runtime:{pyodide:'test',python:'test',numpy:'test',scipy:'test'}};
  p.fingerprint=await kernelFingerprint(p);
  return sealSolution({id:'still-air',name:'Source still air',created_at:'2026-10-26T00:00:00Z',kind:'modes',configuration:c,
    data:{analysis:'eigenmodes',converged:true,vacuum:false,frame_mode:'fixed',controller:null,condition:null,
      modes:[],diagnostics:{base_residual:0},fluid:{kind:'quiescent',density},
      numerics:{...STILL_AIR_NUMERICS},structural_operator:STILL_AIR_NUMERICS.structural_operator,
      base:{structural_operator:STILL_AIR_NUMERICS.structural_operator,fluid:{kind:'quiescent',density},
        mass_properties:{mass:2,inertia_cg:null,spin:null},limitations:['Linear normal and pitch apparent inertia.'],
        equilibrium_state:equilibrium()},request:request(),software_provenance:p},auxiliary:{},
    view:{active_tab:'tab-modes'},provenance:p});
}

test('body coefficient survives sealing and loaded cases and rejects mismatched solution parts',async()=>{
  const value=await solution();value.configuration.fields['body-added-mass']='2';
  value.data.request.modes.quiescent_body_added_mass_factor=2;
  const seed=value.data.base.equilibrium_state;
  seed.identity.quiescent_body_added_mass_factor=seed.launch.quiescent_body_added_mass_factor=2;
  value.data.fluid.body_added_mass_factor=value.data.base.fluid.body_added_mass_factor=2;
  value.configuration.equilibrium.state=structuredClone(seed);
  const sealed=await sealSolution(value);await verifySolution(sealed);
  validateConfiguration(sealed.configuration);
  for(const mutate of [
    s=>s.configuration.fields['body-added-mass']='1',
    s=>s.data.request.modes.quiescent_body_added_mass_factor=1,
    s=>s.data.fluid.body_added_mass_factor=1,
    s=>s.data.base.fluid.body_added_mass_factor=1,
    s=>s.data.base.equilibrium_state.identity.quiescent_body_added_mass_factor=1,
    s=>s.data.base.equilibrium_state.launch.quiescent_body_added_mass_factor=1]){
    const bad=structuredClone(sealed);mutate(bad);assert.throws(()=>validateSolution(bad),/coefficient/);
  }
});

test('source still air is a separate opt-in modal policy and parsing retains its exact pair',()=>{
  assert.equal(numericalSelection(STILL_AIR_NUMERICS),'aswing-still-air');
  assert.deepEqual(selectedNumerics('aswing-still-air'),STILL_AIR_NUMERICS);
  assert.equal(numericalMode(STILL_AIR_NUMERICS),'modes');
  for(const mode of ['rigid','mounted','structural','time','modes','frequency'])
    assert.equal(selectionAllowsMode('aswing-still-air',mode),['modes','frequency'].includes(mode));
  assert.match(structuralPolicyNote('aswing-still-air'),/Set a positive fluid density; Earth pose and gravity remain active/);
  assert.match(structuralPolicyNote('aswing-still-air'),/Archived ASWING agreement is unverified/);
  for(const malformed of [{beam_interpolation:'drela-segspl-v1'},{...STILL_AIR_NUMERICS,beam_interpolation:'natural-v1'},
    {...STILL_AIR_NUMERICS,extra:1},{...STILL_AIR_NUMERICS,structural_operator:'unknown'}])
    assert.throws(()=>numericalSelection(malformed));
  for(const action of ['inspect','distribution','edit_distribution','canonical_asw']){
    const r={action,source:'literal'};
    assert.deepEqual(numericalRequest(r,STILL_AIR_NUMERICS),{...r,numerics:STILL_AIR_NUMERICS});
    assert.deepEqual(numericalRequest({...r,numerics:undefined},STILL_AIR_NUMERICS),r);
    assert.deepEqual(numericalRequest({...r,numerics:DEFAULT_NUMERICS},STILL_AIR_NUMERICS),r);
  }
  assert.deepEqual(numericalRequest(request(),STILL_AIR_NUMERICS),request());
});

test('the still-air policy refuses flow, nonlinear time, controllers and unknown modal options',()=>{
  for(const action of ['solve','time','launch_time','resume_time','flow_survey','stability','rom'])
    assert.throws(()=>numericalRequest({action,mode:action==='solve'?'structural':action,source:'literal'},STILL_AIR_NUMERICS),/still-air eigenmodes/);
  for(const mutate of [r=>r.mode='time',r=>r.condition={},r=>delete r.condition,r=>r.condition={speed:0},
    r=>r.modes.frame='free',r=>r.modes.vacuum=true,r=>r.modes.controller={},r=>r.modes.load_targets={},
    r=>r.modes.motion={},r=>r.modes.condition=null,r=>r.modes.damping=.1,r=>r.rates=[0,0,0],
    r=>r.controller={},r=>r.derivatives={},r=>r.gravity=[0,0,0],r=>r.strut_mode='unknown',
    r=>r.operating_constraints=[{target:0}],r=>r.operating_constraints={},r=>r.initial_state=equilibrium()]){
    const r=request();mutate(r);assert.throws(()=>numericalRequest(r,STILL_AIR_NUMERICS));
  }
  for(const rho of [undefined,null,0,-1,NaN,Infinity,'1.2',true]){
    const r=request();r.modes.quiescent_density=rho;assert.throws(()=>assertStillAirRequest(r));
  }
});

test('selection validates all live motion fields, density and unsupported settings before hiding them',()=>{
  assert.doesNotThrow(()=>assertStillAirInputs(fields(),[]));
  for(const kind of ['rates','acceleration','angular_acceleration'])for(const axis of ['x','y','z'])
    for(const value of ['1','-0.01','',' ','Infinity','NaN',0]){
      const f=fields();f[`${kind}-${axis}`]=value;
      assert.throws(()=>assertStillAirInputs(f,[],{modalSettings:false}),/zero body rates and accelerations/);
    }
  const zero=fields();zero['rates-x']='-0';assert.doesNotThrow(()=>assertStillAirInputs(zero,[]));
  for(const value of ['', ' ','0','-1','NaN','Infinity',1.2]){
    const f=fields();f['modal-quiescent-density']=value;assert.throws(()=>assertStillAirInputs(f,[]),/positive finite/);
  }
  for(const mutate of [f=>f['feedback-enabled']=true,f=>f['modal-vacuum']=true,f=>f['modal-quiescent']=false,
    f=>f['modal-frame']='free',f=>f['modal-ordinary-frame']='free',f=>f.mode='mounted']){
    const f=fields();mutate(f);assert.throws(()=>assertStillAirInputs(f,[]));
  }
  assert.throws(()=>assertStillAirInputs(fields(),[{variable:'speed'}]),/operating targets/);
  const prior=fields();prior['modal-vacuum']=true;prior['modal-quiescent']=false;
  prior['modal-frame']=prior['modal-ordinary-frame']='free';
  assert.doesNotThrow(()=>assertStillAirInputs(prior,[],{modalSettings:false}));
});

test('wire mapping retains pose, gravity and density without copying ordinary flight data',()=>{
  const raw={...request(),condition:condition(),derivatives:undefined,controller:null,strut_mode:'bilateral',operating_constraints:[]};
  const before=structuredClone(raw),r=stillAirModalRequest(raw,raw.condition);
  assert.equal(r.condition,null);assert.deepEqual(r.modes.position,[1,2,3]);assert.deepEqual(r.modes.attitude,[4,5,6]);
  assert.equal(r.modes.gravity_magnitude,9.8);assert.equal(r.modes.quiescent_density,density);
  for(const key of ['derivatives','controller','operating_constraints','gravity'])assert(!Object.hasOwn(r,key));
  assert.deepEqual(raw,before);assertStillAirRequest(r);
  for(const g of [null,0,9.80665]){const c=condition();c.gravity_magnitude=g;assert.equal(stillAirModalRequest(raw,c).modes.gravity_magnitude,g);}
  for(const extra of ['alpha','beta','rates','acceleration','ground_effect','controls','powers','wake_core_ratio','stall']){
    const c=condition();c[extra]=0;assert.throws(()=>stillAirModalRequest(raw,c),/zero-flow/);
  }
  for(const mutate of [c=>c.speed=1,c=>c.density=1,c=>c.position_earth[0]=Infinity,
    c=>c.attitude[2]=NaN,c=>c.gravity_magnitude=-1,c=>c.gravity_magnitude='0']){
    const c=condition();mutate(c);assert.throws(()=>stillAirModalRequest(raw,c));
  }
  for(const override of [{controller:{}},{derivatives:{}},{strut_mode:'unknown'},{operating_constraints:[{}]}])
    assert.throws(()=>stillAirModalRequest({...raw,...override},condition()));
});

test('native matching-policy and matching-density warm starts remain valid but confer no time permission',()=>{
  const r=request();r.modes.initial_state=equilibrium();
  assert.deepEqual(numericalRequest(r,STILL_AIR_NUMERICS),r);
  const noLaunch=structuredClone(r);delete noLaunch.modes.initial_state.launch;
  assert.doesNotThrow(()=>assertStillAirRequest(noLaunch));
  for(const mutate of [s=>s.identity.quiescent_density=1,s=>s.launch.quiescent_density=1,
    s=>delete s.identity.quiescent_density,s=>s.identity=VACUUM_NUMERICS,s=>delete s.identity]){
    const bad=structuredClone(r);mutate(bad.modes.initial_state);assert.throws(()=>assertStillAirRequest(bad));
  }
  const c=configuration();c.equilibrium={state:equilibrium(),enabled:true,label:'API-compatible modal base'};
  assert.deepEqual(validateConfiguration(c),c);
  assert(hasQuiescentEquilibrium(c.equilibrium.state));
  assert.throws(()=>numericalRequest({action:'launch_time',source:c.source,equilibrium_state:c.equilibrium.state},c.numerics));
});

test('all six policies and fluid densities have distinct saved state identities',()=>{
  for(const policy of [DEFAULT_NUMERICS,SOURCE_NUMERICS,SECTION_NUMERICS,COUPLED_NUMERICS,VACUUM_NUMERICS,STILL_AIR_NUMERICS]){
    const c=configuration();c.equilibrium={state:equilibrium(policy),enabled:true,label:'Loaded modal base'};
    if(policy===STILL_AIR_NUMERICS)assert.deepEqual(validateConfiguration(c),c);
    else assert.throws(()=>validateConfiguration(c),/numerical settings/);
  }
  for(const mutate of [c=>c.fields['modal-quiescent-density']='1',c=>c.fields['modal-quiescent']=false,
    c=>c.fields['modal-vacuum']=true,c=>c.fields['rates-z']='2',c=>c.fields['feedback-enabled']=true,
    c=>c.fields['modal-ordinary-frame']='free',c=>delete c.numerics]){
    const c=configuration();c.equilibrium={state:equilibrium(),enabled:true,label:'Base'};mutate(c);
    assert.throws(()=>validateConfiguration(c));
  }
});

test('saved still-air modal projects retain sealed bytes, density and launch metadata',async()=>{
  const saved=await solution(),text=JSON.stringify(saved),p={...emptyProject(),solutions:[saved],selected_solution:saved.id};
  const restored=parseProject(JSON.stringify(p)).solutions[0];
  await verifySolution(restored);assert.equal(JSON.stringify(restored),text);
  assert.deepEqual(restored.data.base.equilibrium_state.launch,equilibrium().launch);assert(isQuiescentResult(restored.data));
  for(const mutate of [s=>s.kind='structural',s=>delete s.configuration.numerics,s=>delete s.data.numerics,
    s=>delete s.data.request.numerics,s=>s.data.request.modes.frame='free',s=>s.data.request.modes.vacuum=true,
    s=>s.data.request.condition={speed:0},s=>s.data.condition={speed:0},s=>s.data.request.modes.quiescent_density=1,
    s=>s.data.fluid.density=1,s=>s.data.base.fluid.density=1,s=>delete s.data.fluid,s=>delete s.data.base.fluid,
    s=>s.data.fluid.kind='moving',s=>s.data.base.fluid.kind='moving',s=>s.data.structural_operator=VACUUM_NUMERICS.structural_operator,
    s=>s.data.base.structural_operator=VACUUM_NUMERICS.structural_operator,
    s=>s.data.base.equilibrium_state.identity=VACUUM_NUMERICS,s=>delete s.data.base.equilibrium_state,
    s=>s.data.base.equilibrium_state.launch.quiescent_density=1,s=>s.data.vacuum=true,
    s=>s.data.frame_mode='free',s=>s.data.controller={},s=>s.auxiliary.rom={},s=>s.auxiliary.flow={},s=>s.auxiliary.stability={}]){
    const bad=structuredClone(saved);mutate(bad);assert.throws(()=>validateSolution(bad));
  }
});

test('existing published vacuum projects retain their exact solution bytes and checksums',async()=>{
  for(const path of ['../examples/source-vacuum-check-project.json','../examples/source-vacuum-damped-check-project.json']){
    const original=JSON.parse(await readFile(new URL(path,import.meta.url),'utf8'));
    const restored=parseProject(JSON.stringify(original));
    for(let i=0;i<original.solutions.length;i++){
      await verifySolution(restored.solutions[i]);
      assert.equal(JSON.stringify(restored.solutions[i]),JSON.stringify(original.solutions[i]));
    }
  }
});

test('ordinary still-air saved results keep absent numerical policy and their existing wire shape',async()=>{
  const saved=await solution();
  delete saved.configuration.numerics;delete saved.data.numerics;delete saved.data.structural_operator;
  delete saved.data.base.structural_operator;delete saved.data.request.numerics;
  saved.data.base.equilibrium_state.identity={quiescent_density:density};
  saved.data.request.condition=condition();saved.data.condition=condition();
  for(const key of ['position','attitude','gravity_magnitude'])delete saved.data.request.modes[key];
  const sealed=await sealSolution(saved),text=JSON.stringify(sealed);
  const restored=parseProject(JSON.stringify({...emptyProject(),solutions:[sealed],selected_solution:sealed.id})).solutions[0];
  await verifySolution(restored);assert.equal(JSON.stringify(restored),text);
  assert(!Object.hasOwn(restored.data.request,'numerics'));
  assert.deepEqual(numericalRequest(restored.data.request),restored.data.request);
});

test('settings restoration selects still air before field events and preserves exact stored values',()=>{
  const previous=globalThis.document,events=[],c=configuration();
  const nodes=new Map(Object.entries(c.fields).map(([id,value])=>[id,{id,value:typeof value==='string'?value:'',
    checked:typeof value==='boolean'?value:false,type:typeof value==='boolean'?'checkbox':'text',tagName:'INPUT',dataset:{},closest:()=>null,
    dispatchEvent(){events.push(nodes.get('structural-equations').value);}}]));
  nodes.set('structural-equations',{id:'structural-equations',value:'midpoint',tagName:'SELECT',type:'select-one',dataset:{},closest:()=>null});
  globalThis.document={getElementById:id=>nodes.get(id)??null,querySelectorAll:q=>q.includes('#model-configuration')?[...nodes.values()]:[]};
  try{
    assert.deepEqual(captureSettings(c),c);
    applySettings(c,{refreshDerivatives(){},addConstraint(){},clearConstraints(){},restoreEquilibrium(){}});
    assert.equal(nodes.get('structural-equations').value,'aswing-still-air');
    assert(events.length>0&&events.every(selection=>selection==='aswing-still-air'));
    assert.equal(nodes.get('modal-frame').value,'fixed');assert.equal(nodes.get('modal-vacuum').checked,false);
    assert.equal(nodes.get('modal-quiescent').checked,true);assert.equal(nodes.get('modal-quiescent-density').value,String(density));
    assert.deepEqual(captureSettings(c),c);
  }finally{globalThis.document=previous;}
});
