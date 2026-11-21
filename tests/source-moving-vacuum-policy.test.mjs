import {test} from 'node:test';
import assert from 'node:assert/strict';
import {MOVING_VACUUM_NUMERICS as POLICY,DEFAULT_NUMERICS,VACUUM_NUMERICS,STILL_AIR_NUMERICS,
  numericalSelection,selectedNumerics,numericalMode,selectionAllowsMode,numericalRequest,
  movingVacuumNumerics,structuralPolicyNote,assertMovingVacuumInputs,assertMovingVacuumRequest,
  movingVacuumFrame,movingVacuumModalRequest} from '../web/numerical-policy.js';
import {validateConfiguration,parseProject,emptyProject} from '../web/project-data.js';
import {sealSolution,verifySolution,validateSolution,kernelFingerprint} from '../web/solution-data.js';
import {captureSettings,applySettings,validateSettings} from '../web/case-settings.js';

const fields=(frame='prescribed')=>({mode:'modes','modal-frame':frame,'modal-ordinary-frame':frame,
  'modal-vacuum':true,'modal-quiescent':false,'modal-quiescent-density':'1.2','feedback-enabled':false,
  'gravity-mode':'custom','gravity-magnitude':'9.81',
  ...Object.fromEntries(['moving-velocity','rates','acceleration','angular_acceleration','position-earth'].flatMap(kind=>['x','y','z'].map((axis,i)=>[`${kind}-${axis}`,String(i+1)]))),
  'attitude-bank':'10','attitude-elevation':'20','attitude-heading':'30',
  ...Object.fromEntries(['F','M'].flatMap(kind=>['x','y','z'].flatMap(axis=>[[`modal-load-${kind}${axis}`,kind==='F'&&axis==='x'?'load':'prescribed'],[`modal-target-${kind}${axis}`,'0']])))});
const configuration=(frame='prescribed')=>({source:'Name\nMoving vacuum boundary fixture\nEnd\n',filename:'moving.asw',mesh:4,
  fields:fields(frame),numerics:{...POLICY},controls:{},powers:{},circulation:{},derivative_parameters:[],constraints:[],
  equilibrium:{state:null,enabled:false,label:''}});
const request=(frame='prescribed')=>({action:'modes',mode:'modes',source:configuration().source,condition:null,panels:4,
  numerics:{...POLICY},modes:{frame,vacuum:true,count:8,shift:[-.1,1],method:'full_shift_invert',step:1e-5,
    rank_tolerance:1e-9,matrices:true,...movingVacuumFrame(fields(frame)),...(frame==='mixed'?{load_targets:{'force.x':0}}:{})}});
const equilibrium=(policy=POLICY)=>({format:'openswing-equilibrium',version:1,positions:[[0,0,0]],
  identity:{...policy},circulation:[],launch:{version:1,condition:null,motion:request().modes.motion,
    frame:{...movingVacuumFrame(fields())},controller:null,loads:[]}});
async function solution(frame='prescribed'){
  const p={format:'openswing-kernel-provenance',version:1,modules:{'source_dynamics.py':'a'.repeat(64)},
    runtime:{pyodide:'test',python:'test',numpy:'test',scipy:'test'}};p.fingerprint=await kernelFingerprint(p);
  return sealSolution({id:'moving',name:'Moving vacuum',created_at:'2026-10-26T00:00:00Z',kind:'modes',configuration:configuration(frame),
    data:{analysis:'eigenmodes',converged:true,vacuum:true,frame_mode:frame,condition:null,controller:null,modes:[],
      diagnostics:{base_residual:0},numerics:{...POLICY},structural_operator:POLICY.structural_operator,
      base:{structural_operator:POLICY.structural_operator,mass_properties:{mass:2,inertia_cg:null,spin:null},
        limitations:['Frozen local linearization.'],equilibrium_state:equilibrium()},request:request(frame),software_provenance:p},
    auxiliary:{},view:{active_tab:'tab-modes'},provenance:p});
}

test('moving vacuum is explicit and does not change historical or fixed policies',()=>{
  assert.equal(numericalSelection(POLICY),'aswing-moving-vacuum');assert(movingVacuumNumerics(POLICY));
  assert.deepEqual(selectedNumerics('aswing-moving-vacuum'),POLICY);assert.equal(numericalMode(POLICY),'modes');
  assert.equal(selectedNumerics('midpoint'),undefined);
  assert.equal(numericalSelection(VACUUM_NUMERICS),'aswing-vacuum');assert.equal(numericalSelection(STILL_AIR_NUMERICS),'aswing-still-air');
  for(const mode of ['rigid','mounted','structural','time','modes','frequency'])assert.equal(selectionAllowsMode('aswing-moving-vacuum',mode),['modes','time','frequency'].includes(mode));
  assert.match(structuralPolicyNote('aswing-moving-vacuum'),/frozen local model/);
  assert.match(structuralPolicyNote('aswing-moving-vacuum'),/Archived ASWING agreement is unverified/);
  for(const malformed of [{...POLICY,beam_interpolation:'natural-v1'},{...POLICY,extra:1}])assert.throws(()=>numericalSelection(malformed));
  for(const action of ['inspect','distribution','edit_distribution','canonical_asw']){
    const r={action,source:'literal'};assert.deepEqual(numericalRequest(r,POLICY),{...r,numerics:POLICY});
    assert.deepEqual(numericalRequest({...r,numerics:undefined},POLICY),r);
    assert.deepEqual(numericalRequest({...r,numerics:DEFAULT_NUMERICS},POLICY),r);
  }
});

test('all four frames permit finite motion while mixed targets stay canonical',()=>{
  for(const frame of ['fixed','prescribed','free','mixed']){
    assertMovingVacuumInputs(fields(frame),[]);assertMovingVacuumRequest(request(frame));
    assert.deepEqual(numericalRequest(request(frame),POLICY),request(frame));
  }
  const free=request('free');free.modes.load_targets={'force.y':-2,'moment.z':3};assertMovingVacuumRequest(free);
  for(const frame of ['fixed','prescribed']){const r=request(frame);r.modes.load_targets={'force.x':0};assert.throws(()=>assertMovingVacuumRequest(r));}
  const mixed=request('mixed');delete mixed.modes.load_targets;assert.throws(()=>assertMovingVacuumRequest(mixed));
  for(const target of [{lift:1},{'force.x':true},{'moment.z':Infinity},[]]){
    const r=request('mixed');r.modes.load_targets=target;assert.throws(()=>assertMovingVacuumRequest(r));
  }
});

test('body velocity is direct and angular UI units convert once without flight-speed data',()=>{
  const f=fields();f['moving-velocity-x']='-20';f['rates-z']='180';f['angular_acceleration-y']='90';f['acceleration-x']='7';
  f.speed='999';f.alpha='89';f.beta='40';const physical=movingVacuumFrame(f);
  assert.deepEqual(physical.velocity,[-20,2,3]);assert.equal(physical.motion.rates[2],Math.PI);
  assert.equal(physical.motion.angular_acceleration[1],Math.PI/2);assert.equal(physical.motion.acceleration[0],7);
  assert.deepEqual(physical.position,[1,2,3]);assert.deepEqual(physical.attitude,[10,20,30]);assert.equal(physical.gravity_magnitude,9.81);
  const raw={...request(),condition:{speed:999,alpha:89,beta:40},derivatives:undefined,controller:null,
    strut_mode:'bilateral',operating_constraints:[]};raw.modes.controller=null;
  const before=structuredClone(raw),mapped=movingVacuumModalRequest(raw,physical);
  assert.equal(mapped.condition,null);for(const [key,value] of Object.entries(physical))assert.deepEqual(mapped.modes[key],value);
  for(const key of ['derivatives','controller','operating_constraints'])assert(!Object.hasOwn(mapped,key));
  assert(!Object.hasOwn(mapped.modes,'controller'));assert.deepEqual(raw,before);
  f['gravity-mode']='file';assert.equal(movingVacuumFrame(f).gravity_magnitude,null);
  assert.throws(()=>movingVacuumModalRequest(raw,{...physical,speed:1}));
});

test('unsafe or malformed requests cannot escape via explicit new policy',()=>{
  for(const action of ['solve','time','frequency','launch_time','resume_time','flow_survey','stability','rom'])
    assert.throws(()=>numericalRequest({action,mode:action,source:'literal'},POLICY));
  for(const mutate of [r=>r.condition={},r=>r.modes.vacuum=false,r=>r.modes.quiescent_density=1.2,
    r=>r.modes.controller={},r=>r.modes.motion={speed:1},r=>r.modes.motion.rates=[0,true,0],
    r=>r.modes.velocity=[1,2],r=>r.modes.attitude=[0,NaN,0],r=>r.modes.gravity_magnitude=-1,
    r=>r.operating_constraints=[{quantity:'lift'}],r=>r.gravity=[0,0,-1],r=>r.controller=null,
    r=>r.modes.structural_operator=VACUUM_NUMERICS.structural_operator]){
    const r=request();mutate(r);assert.throws(()=>numericalRequest(r,POLICY));
  }
  for(const mutate of [r=>r.controller={},r=>r.derivatives={},r=>r.strut_mode='unknown',r=>r.modes.controller={}]){
    const r=request();mutate(r);assert.throws(()=>movingVacuumModalRequest(r,movingVacuumFrame(fields())));
  }
});

test('input guards keep nonzero motion visible but reject invalid values and feedback',()=>{
  for(const kind of ['moving-velocity','rates','acceleration','angular_acceleration'])for(const axis of ['x','y','z'])for(const value of ['','NaN','Infinity']){
    const f=fields();f[`${kind}-${axis}`]=value;assert.throws(()=>assertMovingVacuumInputs(f,[],{modalSettings:false}));
  }
  for(const mutate of [f=>f['feedback-enabled']=true,f=>f['modal-vacuum']=false,f=>f['modal-quiescent']=true,
    f=>f['modal-ordinary-frame']='fixed',f=>f['gravity-magnitude']='-1',f=>f['position-earth-y']='',f=>f.mode='time']){
    const f=fields();mutate(f);assert.throws(()=>assertMovingVacuumInputs(f,[]));
  }
  assert.throws(()=>assertMovingVacuumInputs(fields(),[{variable:'speed'}]));
  const f=fields();f['modal-vacuum']=false;assert.doesNotThrow(()=>assertMovingVacuumInputs(f,[],{modalSettings:false}));
});

test('new saved configuration retains dynamic identity and rejects policy mismatch',()=>{
  const c=configuration();c.equilibrium={state:equilibrium(),enabled:true,label:'Moving base'};
  assert.deepEqual(validateConfiguration(c),c);
  for(const policy of [DEFAULT_NUMERICS,VACUUM_NUMERICS,STILL_AIR_NUMERICS]){
    const bad=structuredClone(c);bad.equilibrium.state=equilibrium(policy);assert.throws(()=>validateConfiguration(bad),/numerical settings/);
  }
});

test('saved modal projects preserve bytes across all four frames with no extra solve',async()=>{
  for(const frame of ['fixed','prescribed','free','mixed']){
    const saved=await solution(frame),text=JSON.stringify(saved),p={...emptyProject(),solutions:[saved],selected_solution:saved.id};
    const restored=parseProject(JSON.stringify(p)).solutions[0];await verifySolution(restored);assert.equal(JSON.stringify(restored),text);
  }
});

test('saved results reject policy, medium, frame and physical request/configuration mismatch',async()=>{
  const saved=await solution('mixed');
  for(const mutate of [s=>delete s.configuration.numerics,s=>delete s.data.numerics,s=>delete s.data.request.numerics,
    s=>s.data.structural_operator=VACUUM_NUMERICS.structural_operator,s=>s.data.base.structural_operator=VACUUM_NUMERICS.structural_operator,
    s=>s.data.base.equilibrium_state.identity=VACUUM_NUMERICS,s=>s.data.vacuum=false,s=>s.data.fluid={},s=>s.data.controller={},
    s=>s.data.frame_mode='fixed',s=>s.data.condition={speed:1},s=>s.data.request.modes.velocity[0]=99,
    s=>s.data.request.modes.motion.rates[0]=99,s=>s.data.request.modes.attitude[0]=99,
    s=>s.data.request.modes.load_targets['force.x']=1,s=>s.data.request.modes.position[0]=99,
    s=>s.data.request.modes.gravity_magnitude=0,s=>s.auxiliary.rom={},s=>s.auxiliary.stability={},s=>s.auxiliary.flow={}]){
    const bad=structuredClone(saved);mutate(bad);assert.throws(()=>validateSolution(bad));
  }
});

test('restoring new settings selects policy before events and keeps motion exactly',()=>{
  const previous=globalThis.document,events=[],c=configuration('mixed');
  const nodes=new Map(Object.entries(c.fields).map(([id,value])=>[id,{id,value:typeof value==='string'?value:'',
    checked:typeof value==='boolean'?value:false,type:typeof value==='boolean'?'checkbox':'text',tagName:'INPUT',dataset:{},closest:()=>null,
    dispatchEvent(){events.push(nodes.get('structural-equations').value);}}]));
  nodes.set('structural-equations',{id:'structural-equations',value:'midpoint',tagName:'SELECT',type:'select-one',dataset:{},closest:()=>null});
  globalThis.document={getElementById:id=>nodes.get(id)??null,querySelectorAll:query=>query.includes('#model-configuration')?[...nodes.values()]:[]};
  try{assert.deepEqual(captureSettings(c),c);applySettings(c,{refreshDerivatives(){},addConstraint(){},clearConstraints(){},restoreEquilibrium(){}});
    assert.equal(nodes.get('structural-equations').value,'aswing-moving-vacuum');assert(events.every(selection=>selection==='aswing-moving-vacuum'));
    assert.equal(nodes.get('modal-frame').value,'mixed');assert.deepEqual(captureSettings(c),c);
  }finally{globalThis.document=previous;}
});

test('old settings acquire only missing zero velocity defaults in editable copy',()=>{
  const previous=globalThis.document,c=configuration('fixed');delete c.numerics;
  Object.assign(c.fields,{'aero-lag':true,'wake-core-ratio':'0.25','freeze-influences':false,'stall-factor':'40','stall-width':'0.05',
    'fourier-wake-diagnostic':false,
    'operating-points-values':'-2, 0, 2, 4, 6, 8','operating-points-initialization':'cold',
    'time-actuators':'','static-gravity-mode':'file','static-gravity-x':'0','static-gravity-y':'0','static-gravity-z':'-9.81',
    'time-accuracy-enabled':false,'time-accuracy-rtol':'0.001','time-accuracy-atol':'0.000001','time-accuracy-minimum':''});
  const domFields=structuredClone(c.fields);for(const axis of ['x','y','z'])delete c.fields[`moving-velocity-${axis}`];
  delete c.fields['fourier-wake-diagnostic'];
  const before=JSON.stringify(c),nodes=new Map(Object.entries(domFields).map(([id,value])=>[id,{id,type:typeof value==='boolean'?'checkbox':'text',
    tagName:'INPUT',dataset:{},closest:()=>null}]));
  globalThis.document={querySelectorAll:()=>[...nodes.values()]};
  try{const migrated=validateSettings(c);assert.equal(JSON.stringify(c),before);assert(!Object.hasOwn(migrated,'numerics'));
    assert.equal(migrated.fields['fourier-wake-diagnostic'],false);
    for(const axis of ['x','y','z'])assert.equal(migrated.fields[`moving-velocity-${axis}`],'0');
    for(const [key,value] of Object.entries(c.fields))assert.equal(migrated.fields[key],value);
  }finally{globalThis.document=previous;}
});
