import {test} from 'node:test';
import assert from 'node:assert/strict';
import {MOVING_VACUUM_NUMERICS as POLICY,VACUUM_NUMERICS,STILL_AIR_NUMERICS,DEFAULT_NUMERICS,
  selectedNumerics,numericalRequest,selectionAllowsMode,assertMovingVacuumInputs,movingVacuumFrame,
  movingVacuumTimeRequest,assertMovingTimeRequest} from '../web/numerical-policy.js';
import {validateConfiguration,parseProject,emptyProject} from '../web/project-data.js';
import {sealSolution,verifySolution,validateSolution,kernelFingerprint} from '../web/solution-data.js';
import {captureSettings,applySettings} from '../web/case-settings.js';

const fields=(frame='prescribed')=>({mode:'time','time-frame':frame,'time-actuators':'','feedback-enabled':false,
  'gravity-mode':'custom','gravity-magnitude':'0','modal-frame':'free','modal-ordinary-frame':'free',
  'modal-vacuum':true,'modal-quiescent':false,'time-duration':'0.1','time-step':'0.01','time-order':'2',
  'time-forcing':'','time-initial-enable':false,
  ...Object.fromEntries(['moving-velocity','rates','acceleration','angular_acceleration','position-earth'].flatMap(kind=>['x','y','z'].map((axis,i)=>[`${kind}-${axis}`,String(i)]))),
  'attitude-bank':'10','attitude-elevation':'20','attitude-heading':'30',
  ...Object.fromEntries(['F','M'].flatMap(kind=>['x','y','z'].flatMap(axis=>[[`time-load:${kind}${axis}`,kind==='F'&&axis==='x'?'load':'prescribed'],[`time-target:${kind}${axis}`,'0']])))});
const config=(frame='prescribed')=>({source:'Name\nSource moving time fixture\nEnd\n',filename:'source-time.asw',mesh:4,
  fields:fields(frame),numerics:{...POLICY},controls:{},powers:{},circulation:{},derivative_parameters:[],constraints:[],equilibrium:{state:null,enabled:false,label:''}});
const setup=(frame='prescribed')=>({condition:null,controller:null,frame,actuator_constraints:[],forcing:'',...movingVacuumFrame(fields(frame))});
const seed=()=>({format:'openswing-equilibrium',version:1,positions:[[0,0,0]],circulation:[],identity:{...POLICY},launch:setup()});
const context=(frame='prescribed')=>({identity:{...POLICY},setup:setup(frame),method:{order:2,maximum_step:.01}});
const checkpoint=(frame='prescribed')=>({format:'openswing-time-checkpoint',version:1,state:{time:.1},context:context(frame)});
function request(action='time',frame='prescribed'){
  const r={action,source:config().source,numerics:{...POLICY},time:{duration:.1,dt:.01,order:2,forcing:'',accuracy:{rtol:.001,atol:1e-6}}};
  if(action!=='resume_time'){r.time.frame=frame;if(frame==='mixed')r.time.load_targets={'force.x':0};}
  if(action==='time')Object.assign(r,{mode:'time',condition:null,panels:4,time:{...r.time,...movingVacuumFrame(fields(frame))}});
  else if(action==='launch_time')r.equilibrium_state=seed();else r.checkpoint=checkpoint(frame);
  return r;
}
async function solution(action='time',frame='prescribed'){
  const p={format:'openswing-kernel-provenance',version:1,modules:{'source_dynamics.py':'a'.repeat(64)},runtime:{pyodide:'test',python:'test',numpy:'test',scipy:'test'}};
  p.fingerprint=await kernelFingerprint(p);
  const snapshot=time=>({time,residual:0,structural_operator:POLICY.structural_operator,
    mass_properties:{mass:2},limitations:['Source moving time fixture'],restart:{version:1,state:{time},
      accepted_method:{accepted_inputs:{identity:{...POLICY}}}}});
  return sealSolution({id:'time',name:'Source time',created_at:'2026-10-26T00:00:00Z',kind:'time',configuration:config(frame),
    data:{analysis:'time_response',converged:true,condition:null,controller:null,frame_mode:frame,structural_operator:POLICY.structural_operator,
      numerics:{...POLICY},snapshots:[snapshot(0),snapshot(.1)],restart_context:context(frame),request:request(action,frame),software_provenance:p},
    auxiliary:{},view:{active_tab:'tab-time'},provenance:p});
}

test('moving selection keeps one policy across modes/time/frequency while fixed policies exclude nonlinear time',()=>{
  for(const mode of ['modes','time','frequency'])assert(selectionAllowsMode('aswing-moving-vacuum',mode));
  for(const selection of ['aswing-vacuum','aswing-still-air'])assert(!selectionAllowsMode(selection,'time'));
  for(const mode of ['mounted','structural'])assert(!selectionAllowsMode('aswing-moving-vacuum',mode));
  assert.equal(selectedNumerics('midpoint'),undefined);
  for(const old of [VACUUM_NUMERICS,STILL_AIR_NUMERICS])for(const action of ['time','launch_time','resume_time']){
    const r=request(action);r.numerics=old;assert.throws(()=>numericalRequest(r,old));
  }
});

test('cold, launch and resume support standard methods and retain their input',()=>{
  for(const action of ['time','launch_time','resume_time'])for(const order of [1,2,5]){
    const r=request(action);r.time.order=order;const before=structuredClone(r);
    assertMovingTimeRequest(r);assert.deepEqual(numericalRequest(r,POLICY),r);assert.deepEqual(r,before);
  }
  for(const frame of ['prescribed','free','mixed']){
    assertMovingVacuumInputs(fields(frame),[]);validateConfiguration(config(frame));assertMovingTimeRequest(request('time',frame));
  }
});

test('cold mapping separates motion from flight flow and only removes empty unsupported placeholders',()=>{
  const raw={...request(),condition:{speed:300,alpha:80},derivatives:undefined,controller:null,strut_mode:'bilateral',operating_constraints:[]};
  raw.time.actuator_constraints=[];raw.time.controller=null;
  const f=movingVacuumFrame(fields()),mapped=movingVacuumTimeRequest(raw,f);
  assert.equal(mapped.condition,null);for(const [key,v] of Object.entries(f))assert.deepEqual(mapped.time[key],v);
  for(const key of ['derivatives','controller','operating_constraints'])assert(!Object.hasOwn(mapped,key));
  assert(!Object.hasOwn(mapped.time,'actuator_constraints'));assert(!Object.hasOwn(mapped.time,'controller'));
  for(const mutate of [r=>r.time.actuator_constraints=[{}],r=>r.time.controller={},r=>r.controller={},r=>r.operating_constraints=[{}]]){
    const bad=structuredClone(raw);mutate(bad);assert.throws(()=>movingVacuumTimeRequest(bad,f));
  }
});

test('saved launch accepts physical disturbance and never copies current motion controls',()=>{
  const r=request('launch_time');r.time.actuator_constraints=[];r.time.disturbance={frame:{velocity:[0,.1,0]}};
  r.time.initial_difference_step=.01;r.time.initial_rank_tolerance=1e-7;
  const changed=movingVacuumFrame(fields());changed.velocity=[90,80,70];
  const mapped=movingVacuumTimeRequest(r,changed);
  assert.deepEqual(mapped.equilibrium_state,r.equilibrium_state);assert.deepEqual(mapped.time.disturbance,r.time.disturbance);
  for(const key of ['velocity','motion','position','attitude','gravity_magnitude'])assert(!Object.hasOwn(mapped.time,key));
  assertMovingTimeRequest(mapped);
  const cold=request();cold.time.disturbance=r.time.disturbance;assert.throws(()=>assertMovingTimeRequest(cold));
});

test('saved setup cannot be overridden and checkpoint identity rejects policy downgrade',()=>{
  for(const action of ['launch_time','resume_time'])for(const key of ['velocity','motion','position','attitude','gravity_magnitude','condition']){
    const r=request(action);r.time[key]=[0,0,0];assert.throws(()=>assertMovingTimeRequest(r));
  }
  for(const action of ['launch_time','resume_time']){
    const r=request(action),container=action==='launch_time'?r.equilibrium_state:r.checkpoint.context;
    for(const policy of [DEFAULT_NUMERICS,VACUUM_NUMERICS,STILL_AIR_NUMERICS]){
      container.identity=policy;assert.throws(()=>assertMovingTimeRequest(r));
    }
    container.identity={...POLICY};
    const natural={...r};delete natural.numerics;assert.throws(()=>numericalRequest(natural,undefined),/numerical settings/);
    const recorded=action==='launch_time'?container.launch:container.setup;
    recorded.condition={speed:0};assert.throws(()=>assertMovingTimeRequest(r));recorded.condition=null;
    recorded.controller={};assert.throws(()=>assertMovingTimeRequest(r));
  }
});

test('malformed settings cannot enable airflow, inverse targets or unsafe time methods',()=>{
  for(const change of [{frame:'fixed'},{frame:'mixed'},{vacuum:true},{quiescent_density:1.2},{controller:{}},
    {actuator_constraints:[{}]},{velocity:[1,2]},{motion:{rates:[0,true,0]}},{gravity_magnitude:-1},
    {duration:0},{dt:Infinity},{order:3},{order:true},{forcing:{}}]){
    const r=request();Object.assign(r.time,change);assert.throws(()=>assertMovingTimeRequest(r));
  }
  const f=fields();f['time-actuators']='F1 My 0';assert.throws(()=>assertMovingVacuumInputs(f,[]));
  const bad=fields('mixed');bad['time-load:Fx']='prescribed';assert.throws(()=>assertMovingVacuumInputs(bad,[]));
});

test('null forcing retains the saved table only for continuation',()=>{
  for(const action of ['time','launch_time','resume_time']){
    const r=request(action);r.time.forcing=null;
    if(action==='resume_time')assertMovingTimeRequest(r);else assert.throws(()=>assertMovingTimeRequest(r),/Forcing/);
  }
});

test('all saved time routes and canonical frame choices seal and roundtrip byte-exactly',async()=>{
  for(const action of ['time','launch_time','resume_time'])for(const frame of ['prescribed','free','mixed']){
    const saved=await solution(action,frame),text=JSON.stringify(saved);
    const restored=parseProject(JSON.stringify({...emptyProject(),solutions:[saved],selected_solution:saved.id})).solutions[0];
    await verifySolution(restored);assert.equal(JSON.stringify(restored),text);
  }
});

test('saved trajectories reject mismatched policy, setup, cold controls and per-snapshot evidence',async()=>{
  const saved=await solution('time','mixed');
  for(const mutate of [s=>delete s.data.numerics,s=>s.data.request.numerics=VACUUM_NUMERICS,
    s=>s.data.structural_operator=VACUUM_NUMERICS.structural_operator,s=>s.data.snapshots[1].structural_operator='midpoint-v1',
    s=>s.data.snapshots[1].restart.accepted_method.accepted_inputs.identity=DEFAULT_NUMERICS,s=>s.data.restart_context.identity=VACUUM_NUMERICS,
    s=>s.data.restart_context.setup.condition={speed:0},s=>s.data.restart_context.setup.controller={},
    s=>s.data.restart_context.setup.actuator_constraints=[{}],s=>s.data.frame_mode='free',
    s=>s.data.request.time.velocity[0]=99,s=>s.data.request.time.motion.rates[0]=99,
    s=>s.data.request.time.load_targets['force.x']=1,s=>s.auxiliary.rom={},s=>s.auxiliary.stability={}]){
    const bad=structuredClone(saved);mutate(bad);assert.throws(()=>validateSolution(bad));
  }
});

test('same moving policy survives mode/time settings restore without migration or lost seed',()=>{
  const previous=globalThis.document,c=config('mixed');c.equilibrium={state:seed(),enabled:true,label:'Saved moving base'};
  const nodes=new Map(Object.entries(c.fields).map(([key,value])=>{
    const split=key.split(':'),id=split.length===1?key:'',dataset=split[0]==='time-load'?{timeLoad:split[1]}:split[0]==='time-target'?{timeTarget:split[1]}:{};
    return [key,{id,dataset,value:typeof value==='string'?value:'',checked:typeof value==='boolean'?value:false,
      type:typeof value==='boolean'?'checkbox':'text',tagName:'INPUT',closest:()=>null,dispatchEvent(){}}];
  }));
  nodes.set('structural-equations',{id:'structural-equations',value:'aswing-moving-vacuum',type:'select-one',tagName:'SELECT',dataset:{},closest:()=>null});
  globalThis.document={getElementById:id=>nodes.get(id)??null,querySelectorAll:q=>q.includes('#model-configuration')?[...nodes.values()]:[]};
  try{applySettings(c,{refreshDerivatives(){},addConstraint(){},clearConstraints(){},restoreEquilibrium(){}});
    assert.equal(nodes.get('mode').value,'time');assert.equal(nodes.get('structural-equations').value,'aswing-moving-vacuum');
    assert.deepEqual(captureSettings(c),c);
  }finally{globalThis.document=previous;}
});
