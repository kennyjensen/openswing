import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DEFAULT_NUMERICS,SOURCE_NUMERICS,SECTION_NUMERICS,COUPLED_NUMERICS,VACUUM_NUMERICS,
  numericalSelection,selectedNumerics,numericalMode,selectionAllowsMode,numericalRequest,
  structuralPolicyNote,assertVacuumInputs,assertVacuumRequest,vacuumModalRequest} from '../web/numerical-policy.js';
import {validateConfiguration,parseProject,emptyProject} from '../web/project-data.js';
import {sealSolution,verifySolution,validateSolution,kernelFingerprint} from '../web/solution-data.js';
import {captureSettings,applySettings} from '../web/case-settings.js';

const fields=()=>({mode:'modes','modal-frame':'fixed','modal-ordinary-frame':'fixed','modal-vacuum':true,
  'modal-quiescent':false,'feedback-enabled':false,'gravity-mode':'custom','gravity-magnitude':'0',
  ...Object.fromEntries(['rates','acceleration','angular_acceleration'].flatMap(key=>['x','y','z'].map(axis=>[`${key}-${axis}`,'0'])))});
const configuration=()=>({source:'Name\nVacuum test\nEnd\n',filename:'vacuum.asw',mesh:4,fields:fields(),
  numerics:{...VACUUM_NUMERICS},controls:{},powers:{},circulation:{},derivative_parameters:[],constraints:[],
  equilibrium:{state:null,enabled:false,label:''}});
const request=()=>({action:'modes',mode:'modes',source:configuration().source,condition:null,panels:4,
  numerics:{...VACUUM_NUMERICS},modes:{frame:'fixed',vacuum:true,count:16,shift:[-.01,0],method:'dense',step:1e-5,
    rank_tolerance:1e-9,matrices:true,position:[0,0,0],attitude:[0,0,0],gravity_magnitude:0}});
const condition=()=>({speed:30,alpha:5,beta:1,stall:true,density:1.225,ground_effect:1,
  rates:[0,0,0],acceleration:[0,0,0],angular_acceleration:[0,0,0],position_earth:[1,2,3],attitude:[4,5,6],gravity_magnitude:9.8});
const equilibrium=(numerics=VACUUM_NUMERICS)=>({format:'openswing-equilibrium',version:1,positions:[[0,0,0]],
  identity:{...numerics},circulation:[],launch:{version:1,condition:null,motion:{rates:[0,0,0],acceleration:[0,0,0],angular_acceleration:[0,0,0]},
    frame:{position:[0,0,0],attitude:[0,0,0],velocity:[0,0,0],gravity_magnitude:0},controller:null,loads:[]}});
async function solution(){
  const c=configuration(),p={format:'openswing-kernel-provenance',version:1,modules:{'source_dynamics.py':'a'.repeat(64)},
    runtime:{pyodide:'test',python:'test',numpy:'test',scipy:'test'}};
  p.fingerprint=await kernelFingerprint(p);
  return sealSolution({id:'vacuum',name:'Source vacuum',created_at:'2026-10-26T00:00:00Z',kind:'modes',configuration:c,
    data:{analysis:'eigenmodes',converged:true,vacuum:true,frame_mode:'fixed',controller:null,modes:[],diagnostics:{base_residual:0},
      numerics:{...VACUUM_NUMERICS},structural_operator:VACUUM_NUMERICS.structural_operator,
      base:{structural_operator:VACUUM_NUMERICS.structural_operator,mass_properties:{mass:2,inertia_cg:null,spin:null},
        limitations:['Endpoint-average descriptor inertia.'],equilibrium_state:equilibrium()},
      request:request(),software_provenance:p},auxiliary:{},view:{active_tab:'tab-modes'},provenance:p});
}

test('fixed vacuum is a distinct explicit modal policy; old defaults remain absent',()=>{
  assert.equal(numericalSelection(VACUUM_NUMERICS),'aswing-vacuum');
  assert.deepEqual(selectedNumerics('aswing-vacuum'),VACUUM_NUMERICS);
  assert.equal(numericalMode(VACUUM_NUMERICS),'modes');
  for(const mode of ['rigid','mounted','structural','time','modes','frequency'])assert.equal(selectionAllowsMode('aswing-vacuum',mode),['modes','frequency'].includes(mode));
  assert.match(structuralPolicyNote('aswing-vacuum'),/endpoint-averaged inertia/);
  assert.match(structuralPolicyNote('aswing-vacuum'),/material damping; physical nonnegative masses and damping times/);
  assert.match(structuralPolicyNote('aswing-vacuum'),/archived ASWING agreement are unverified/);
  for(const malformed of [{...VACUUM_NUMERICS,beam_interpolation:'natural-v1'},{...VACUUM_NUMERICS,extra:1}])assert.throws(()=>numericalSelection(malformed));
  for(const action of ['inspect','distribution','edit_distribution','canonical_asw']){
    const r={action,source:'literal'};
    assert.deepEqual(numericalRequest(r,VACUUM_NUMERICS),{...r,numerics:VACUUM_NUMERICS});
    assert.deepEqual(numericalRequest({...r,numerics:undefined},VACUUM_NUMERICS),r);
    assert.deepEqual(numericalRequest({...r,numerics:DEFAULT_NUMERICS},VACUUM_NUMERICS),r);
  }
  assert.deepEqual(numericalRequest(request(),VACUUM_NUMERICS),request());
});

test('vacuum policy cannot launch nonlinear time, aerodynamic or auxiliary calculations',()=>{
  for(const action of ['solve','time','launch_time','resume_time','flow_survey','stability','rom'])
    assert.throws(()=>numericalRequest({action,mode:action==='solve'?'structural':action,source:'literal'},VACUUM_NUMERICS),/vacuum eigenmodes/);
  for(const mutate of [r=>r.mode='time',r=>r.condition={speed:0},r=>r.condition=[],r=>r.modes.frame='free',
    r=>r.modes.vacuum=false,r=>r.modes.quiescent_density=1.2,r=>r.modes.controller={},r=>r.modes.load_targets={x:0},
    r=>r.modes.load_targets=[],r=>r.modes.motion={},r=>r.operating_constraints=[{target:0}]]){
    const r=request();mutate(r);assert.throws(()=>numericalRequest(r,VACUUM_NUMERICS));
  }
});

test('selection refuses every nonzero or malformed motion component before hiding inputs',()=>{
  assert.doesNotThrow(()=>assertVacuumInputs(fields(),[]));
  for(const key of ['rates','acceleration','angular_acceleration'])for(const axis of ['x','y','z'])for(const value of ['1','-0.01','','Infinity','NaN']){
    const f=fields();f[`${key}-${axis}`]=value;
    assert.throws(()=>assertVacuumInputs(f,[],{modalSettings:false}),/zero body rates and accelerations/);
  }
  const f=fields();f['rates-x']='-0';assert.doesNotThrow(()=>assertVacuumInputs(f,[]));
  for(const mutate of [f=>f['feedback-enabled']=true,f=>f['modal-vacuum']=false,f=>f['modal-quiescent']=true,
    f=>f['modal-frame']='free',f=>f['modal-ordinary-frame']='free',f=>f.mode='mounted']){
    const f=fields();mutate(f);assert.throws(()=>assertVacuumInputs(f,[]));
  }
  assert.throws(()=>assertVacuumInputs(fields(),[{variable:'speed'}]),/operating targets/);
  const prior=fields();prior['modal-vacuum']=false;prior['modal-frame']=prior['modal-ordinary-frame']='free';
  assert.doesNotThrow(()=>assertVacuumInputs(prior,[],{modalSettings:false}));
});

test('vacuum request mapping retains Earth pose and gravity and emits no FlightCondition',()=>{
  const raw={...request(),condition:condition(),derivatives:undefined,controller:null,strut_mode:'bilateral',operating_constraints:[]};
  raw.modes.controller=null;const before=structuredClone(raw);
  const r=vacuumModalRequest(raw,raw.condition);
  assert.equal(r.condition,null);assert.deepEqual(r.modes.position,[1,2,3]);assert.deepEqual(r.modes.attitude,[4,5,6]);
  assert.equal(r.modes.gravity_magnitude,9.8);
  for(const key of ['derivatives','controller','operating_constraints','gravity'])assert(!Object.hasOwn(r,key));
  assert(!Object.hasOwn(r.modes,'controller'));assert.deepEqual(raw,before);
  for(const g of [null,0,9.80665]){const c=condition();c.gravity_magnitude=g;assert.equal(vacuumModalRequest(raw,c).modes.gravity_magnitude,g);}
  for(const key of ['rates','acceleration','angular_acceleration']){
    const c=condition();c[key][1]=.01;assert.throws(()=>vacuumModalRequest(raw,c),/zero body rates/);
  }
  for(const mutate of [c=>c.position_earth[0]=Infinity,c=>c.attitude[2]=NaN,c=>c.gravity_magnitude=-1]){
    const c=condition();mutate(c);assert.throws(()=>vacuumModalRequest(raw,c));
  }
  assert.throws(()=>vacuumModalRequest({...raw,strut_mode:'unknown'},condition()));
  assert.throws(()=>vacuumModalRequest({...raw,derivatives:{}},condition()));
  assert.throws(()=>vacuumModalRequest({...raw,controller:{}},condition()));
  assertVacuumRequest(r);
});

test('all five configurations keep distinct equilibrium identities',()=>{
  const policies=[DEFAULT_NUMERICS,SOURCE_NUMERICS,SECTION_NUMERICS,COUPLED_NUMERICS,VACUUM_NUMERICS];
  for(const saved of policies){
    const c=configuration();c.equilibrium={state:equilibrium(saved),enabled:true,label:'Loaded modal base'};
    if(saved===VACUUM_NUMERICS)assert.deepEqual(validateConfiguration(c),c);
    else assert.throws(()=>validateConfiguration(c),/numerical settings/);
  }
  for(const selected of policies.slice(0,-1)){
    const c=configuration();c.numerics=selected;c.fields.mode=numericalMode(selected)??'mounted';
    c.equilibrium={state:equilibrium(),enabled:true,label:'Source vacuum'};
    assert.throws(()=>validateConfiguration(c),/numerical settings/);
  }
  const c=configuration();c.equilibrium={state:equilibrium(),enabled:true,label:'Modal'};
  for(const mutate of [c=>c.fields['modal-frame']='mixed',c=>c.fields['rates-z']='2',c=>c.fields['feedback-enabled']=true,
    c=>c.fields['modal-vacuum']=false,c=>delete c.numerics]){
    const bad=structuredClone(c);mutate(bad);assert.throws(()=>validateConfiguration(bad));
  }
});

test('modal archive preserves source policy, launch metadata and sealed bytes without computing',async()=>{
  const saved=await solution(),text=JSON.stringify(saved);
  const p={...emptyProject(),solutions:[saved],selected_solution:saved.id};
  const restored=parseProject(JSON.stringify(p)).solutions[0];
  await verifySolution(restored);assert.equal(JSON.stringify(restored),text);
  assert.deepEqual(restored.data.base.equilibrium_state.launch,equilibrium().launch);
  for(const mutate of [s=>s.kind='structural',s=>delete s.configuration.numerics,s=>delete s.data.numerics,
    s=>delete s.data.request.numerics,s=>s.data.request.modes.frame='free',s=>s.data.request.modes.vacuum=false,
    s=>s.data.request.condition={speed:0},s=>s.data.structural_operator=SECTION_NUMERICS.structural_operator,
    s=>s.data.base.structural_operator=SECTION_NUMERICS.structural_operator,
    s=>s.data.base.equilibrium_state.identity=SECTION_NUMERICS,s=>delete s.data.base.equilibrium_state,
    s=>s.data.vacuum=false,s=>s.data.frame_mode='free',s=>s.data.fluid={},s=>s.data.controller={}]){
    const bad=structuredClone(saved);mutate(bad);assert.throws(()=>validateSolution(bad));
  }
});

test('restoring settings selects the vacuum policy before input events, preserving stored fields',()=>{
  const previous=globalThis.document,events=[];
  const c=configuration(),nodes=new Map(Object.entries(c.fields).map(([id,value])=>[id,{id,value:typeof value==='string'?value:'',
    checked:typeof value==='boolean'?value:false,type:typeof value==='boolean'?'checkbox':'text',tagName:'INPUT',dataset:{},closest:()=>null,
    dispatchEvent(){events.push(nodes.get('structural-equations').value);}}]));
  nodes.set('structural-equations',{id:'structural-equations',value:'midpoint',tagName:'SELECT',type:'select-one',dataset:{},closest:()=>null});
  globalThis.document={getElementById:id=>nodes.get(id)??null,querySelectorAll:query=>query.includes('#model-configuration')?[...nodes.values()]:[]};
  try{
    assert.deepEqual(captureSettings(c),c);
    applySettings(c,{refreshDerivatives(){},addConstraint(){},clearConstraints(){},restoreEquilibrium(){}});
    assert.equal(nodes.get('structural-equations').value,'aswing-vacuum');
    assert(events.length>0&&events.every(selection=>selection==='aswing-vacuum'));
    assert.equal(nodes.get('modal-frame').value,'fixed');assert.equal(nodes.get('modal-vacuum').checked,true);
    assert.deepEqual(captureSettings(c),c);
  }finally{globalThis.document=previous;}
});
