import test from 'node:test';
import assert from 'node:assert/strict';
import {AIRFLOW_NUMERICS,selectedNumerics,numericalSelection,selectionAllowsMode,
  numericalRequest,airflowDynamicRequest,assertAirflowInputs} from '../web/numerical-policy.js';
import {validateConfiguration} from '../web/project-data.js';
import {sealSolution,verifySolution,validateSolution,kernelFingerprint} from '../web/solution-data.js';

const fields={mode:'frequency','structural-equations':'aswing-airflow',
  'feedback-enabled':false,'modal-vacuum':false,'modal-quiescent':false,'time-actuators':''};
const request=action=>({action,mode:action,source:'Model',panels:4,
  condition:{speed:23,alpha:0,controls:{1:.1},gravity_magnitude:0},
  operating_constraints:[],strut_mode:'bilateral',derivatives:undefined,
  [action]:{controller:null,frame:action==='time'?'prescribed':'fixed',
    ...(action==='frequency'?{inputs:['control.1'],frequencies:[1,10]}:
      action==='time'?{duration:.1,dt:.01,order:2,forcing:'',actuator_constraints:[]}:{} )}});
const controller={outputs:[{actuator:'F1',terms:[{input:'Cr[1]',gain:-.1},
  {input:'Cr[1]',gain:-.15,mode:'integral'}]}]};

test('source airflow preserves feedback and rejects controller replacement on saved histories',()=>{
  for(const action of ['modes','frequency','time']){
    const raw=request(action);raw[action].controller=structuredClone(controller);
    const before=structuredClone(raw),value=numericalRequest(airflowDynamicRequest(raw),AIRFLOW_NUMERICS);
    assert.deepEqual(value[action].controller,controller);assert.deepEqual(raw,before);
  }
  for(const action of ['launch_time','resume_time']){
    const setup={condition:{speed:23},controller:structuredClone(controller)};
    const packet=action==='launch_time'?{format:'openswing-equilibrium',version:1,positions:[[0,0,0]],identity:{...AIRFLOW_NUMERICS},launch:setup}
      :{format:'openswing-time-checkpoint',version:1,state:{time:0},context:{method:{},identity:{...AIRFLOW_NUMERICS},setup}};
    const raw={action,mode:'time',source:'Model',numerics:{...AIRFLOW_NUMERICS},
      [action==='launch_time'?'equilibrium_state':'checkpoint']:packet,time:{duration:.1,dt:.01}};
    assert.deepEqual(airflowDynamicRequest(raw),raw);
    raw.time.controller=structuredClone(controller);
    assert.throws(()=>airflowDynamicRequest(raw),/saved physical setup/);
  }
});

test('airflow selection supports all dynamic analyses and preserves flight/control data',()=>{
  assert.deepEqual(selectedNumerics('aswing-airflow'),AIRFLOW_NUMERICS);
  assert.equal(numericalSelection(AIRFLOW_NUMERICS),'aswing-airflow');
  for(const action of ['modes','frequency','time']){
    assert(selectionAllowsMode('aswing-airflow',action));
    const raw=request(action),before=structuredClone(raw);
    const value=numericalRequest(airflowDynamicRequest(raw),AIRFLOW_NUMERICS);
    assert.deepEqual(raw,before);assert.deepEqual(value.condition,raw.condition);
    assert.deepEqual(value.numerics,AIRFLOW_NUMERICS);
    for(const key of ['controller','derivatives','operating_constraints'])assert(!Object.hasOwn(value,key));
    assert(!Object.hasOwn(value[action],'controller'));
  }
  for(const mode of ['rigid','structural'])assert(!selectionAllowsMode('aswing-airflow',mode));
});

test('source airflow steady trim retains targets and releases them only for a saved time launch',()=>{
  const targets=[{variable:'alpha',quantity:'CL',target:.4}];
  const steadyFields={...fields,mode:'mounted',...Object.fromEntries(
    ['rates','acceleration','angular_acceleration'].flatMap(k=>['x','y','z'].map(a=>[`${k}-${a}`,'0'])))};
  assert(selectionAllowsMode('aswing-airflow','mounted'));
  assertAirflowInputs(steadyFields,targets);
  const raw={action:'solve',mode:'mounted',source:'Model',condition:{speed:23},operating_constraints:targets};
  const before=structuredClone(raw);
  assert.deepEqual(numericalRequest(raw,AIRFLOW_NUMERICS),{...raw,numerics:AIRFLOW_NUMERICS});
  assert.deepEqual(raw,before);
  const stack={...raw,action:'operating_points',operating_points:{points:[{}]}};
  assert.deepEqual(numericalRequest(stack,AIRFLOW_NUMERICS),{...stack,numerics:AIRFLOW_NUMERICS});
  for(const variable of ['rates.x','acceleration.y','angular_acceleration.z']){
    const moving={...raw,condition:{...raw.condition,rates:[.1,0,.7],acceleration:[1,2,3],angular_acceleration:[.2,.3,.4]},
      operating_constraints:[{variable,quantity:'force.z',target:0}]};
    assert.deepEqual(numericalRequest(moving,AIRFLOW_NUMERICS),{...moving,numerics:AIRFLOW_NUMERICS});
  }
  assertAirflowInputs({...steadyFields,'rates-x':'1'},targets);
  for(const bad of ['', 'Infinity', 'invalid'])assert.throws(()=>assertAirflowInputs({...steadyFields,'rates-x':bad},targets),/finite/);
  for(const group of ['rates','acceleration','angular_acceleration'])for(const bad of [[1,2],[true,0,0],[Infinity,0,0],['1',0,0]])
    assert.throws(()=>numericalRequest({...raw,condition:{...raw.condition,[group]:bad}},AIRFLOW_NUMERICS),/finite/);
  assertAirflowInputs({...steadyFields,'feedback-enabled':true},targets);
  const controlled={...raw,controller,operating_constraints:[{variable:'command.F1',quantity:'CL',target:.4}]};
  assert.deepEqual(numericalRequest(controlled,AIRFLOW_NUMERICS),{...controlled,numerics:AIRFLOW_NUMERICS});
  const differentiated={...controlled,derivatives:{response:'free_flight',parameters:['command.F1']}};
  assert.deepEqual(numericalRequest(differentiated,AIRFLOW_NUMERICS),{...differentiated,numerics:AIRFLOW_NUMERICS});
  const custom=[{variable:'power.1',quantity:'user.tip',expression:'sensor("2.strain.s")',
    residual_scale:.01,unit:'dimensionless',target:.005},
    {variable:'power.2',quantity:'minimum_control',weight:4,preferred:.2,target:0}];
  assertAirflowInputs(steadyFields,custom);
  const allocated={...raw,operating_constraints:custom};
  assert.deepEqual(numericalRequest(allocated,AIRFLOW_NUMERICS),{...allocated,numerics:AIRFLOW_NUMERICS});
  const config={source:'Model',filename:'model.asw',mesh:4,fields:steadyFields,
    controls:{},powers:{},circulation:{},derivative_parameters:[],constraints:targets,
    equilibrium:{state:null,enabled:false,label:''},numerics:{...AIRFLOW_NUMERICS}};
  assert.deepEqual(validateConfiguration(config),config);
  assert.deepEqual(validateConfiguration({...config,constraints:custom}),{...config,constraints:custom});
  const time={...config,fields:{...steadyFields,mode:'time'},equilibrium:{enabled:true,label:'Trim',
    state:{format:'openswing-equilibrium',version:1,positions:[[0,0,0]],identity:{...AIRFLOW_NUMERICS},launch:{condition:{speed:23}}}}};
  assert.deepEqual(validateConfiguration(time),time);
  assert.throws(()=>validateConfiguration({...time,equilibrium:{state:null,enabled:false,label:''}}),/operating targets/);
  assert.deepEqual(targets,before.operating_constraints);
});

test('unsupported physics and duplicate motion inputs are rejected without being discarded',()=>{
  for(const action of ['modes','frequency','time'])for(const change of [
    {vacuum:true},{quiescent_density:1.2},{motion:{rates:[0,0,0]}},
    {velocity:[0,0,0]},{actuator_constraints:[{}]},{actuator_constraints:{}},
    {frame:'mixed',load_targets:{lift:0}},
  ]){
    const raw=request(action);Object.assign(raw[action],change);
    assert.throws(()=>airflowDynamicRequest(raw));
  }
  for(const change of [{duration:0},{dt:Infinity},{order:3},{frame:'fixed'},{disturbance:{frame:{velocity:[0,1,0]}}}]){
    const raw=request('time');Object.assign(raw.time,change);assert.throws(()=>airflowDynamicRequest(raw));
  }
});

test('saved case keeps airflow identity and validates its medium',()=>{
  const configuration={source:'Model',filename:'flow.asw',mesh:4,fields:{...fields},
    controls:{},powers:{},circulation:{},derivative_parameters:[],constraints:[],
    equilibrium:{state:null,enabled:false,label:''},numerics:{...AIRFLOW_NUMERICS}};
  assert.deepEqual(validateConfiguration(configuration),configuration);
  for(const key of ['modal-vacuum','modal-quiescent']){
    const bad=structuredClone(configuration);bad.fields[key]=true;assert.throws(()=>validateConfiguration(bad));
  }
  assertAirflowInputs(fields,[]);
  assertAirflowInputs({...fields,'feedback-enabled':true},[]);
  assert.throws(()=>assertAirflowInputs({...fields,'time-actuators':'F1 My 0'},[]));
  assert.throws(()=>assertAirflowInputs(fields,[{}]));
});

test('computed airflow modes and spectra can be sealed and reopened with their equations',async()=>{
  const p={format:'openswing-kernel-provenance',version:1,modules:{'source_airflow.py':'b'.repeat(64)},
    runtime:{pyodide:'test',python:'test',numpy:'test',scipy:'test'}};
  p.fingerprint=await kernelFingerprint(p);
  for(const mode of ['modes','frequency'])for(const closedLoop of [false,true]){
    const config={source:'Model',filename:'flow.asw',mesh:4,fields:{...fields,mode,
      'frequency-frame':'fixed','modal-frame':'fixed','feedback-enabled':closedLoop},controls:{},powers:{},circulation:{},
      derivative_parameters:[],constraints:[],equilibrium:{state:null,enabled:false,label:''},numerics:{...AIRFLOW_NUMERICS}};
    const raw=request(mode);if(closedLoop)raw[mode].controller=structuredClone(controller);
    const r=numericalRequest(airflowDynamicRequest(raw),AIRFLOW_NUMERICS);
    const base={structural_operator:AIRFLOW_NUMERICS.structural_operator,mass_properties:{mass:1},limitations:[],
      equilibrium_state:{format:'openswing-equilibrium',version:1,positions:[[0,0,0]],identity:{...AIRFLOW_NUMERICS},launch:{condition:{speed:23}}}};
    const s=await sealSolution({id:'flow-'+mode,name:mode,created_at:'2026-10-30T00:00:00Z',kind:mode,
      configuration:config,data:{analysis:mode==='modes'?'eigenmodes':'frequency_response',converged:true,
      vacuum:false,frame_mode:'fixed',structural_operator:AIRFLOW_NUMERICS.structural_operator,
      controller:closedLoop?{definition:structuredClone(controller)}:null,
      numerics:{...AIRFLOW_NUMERICS},base,request:r,diagnostics:{},modes:[],samples:[{omega:1}],inputs:['control.1'],software_provenance:p},
      auxiliary:{},view:{},provenance:p});
    assert.deepEqual(await verifySolution(s),s);
    const bad=structuredClone(s);bad.data.vacuum=true;assert.throws(()=>validateSolution(bad));
    const changed=structuredClone(s);changed.data.base.structural_operator='midpoint-v1';assert.throws(()=>validateSolution(changed));
    const mismatch=structuredClone(s);mismatch.data.controller=closedLoop?null:{definition:controller};
    assert.throws(()=>validateSolution(mismatch),/controller does not match/);
  }
});

test('source steady controller projects retain the request and launch controller',async()=>{
  const provenance={format:'openswing-kernel-provenance',version:1,modules:{'source_airflow.py':'b'.repeat(64)},
    runtime:{pyodide:'test',python:'test',numpy:'test',scipy:'test'}};
  provenance.fingerprint=await kernelFingerprint(provenance);
  const config={source:'Model',filename:'flow.asw',mesh:4,fields:{...fields,mode:'mounted','feedback-enabled':true,
    ...Object.fromEntries(['rates','acceleration','angular_acceleration'].flatMap(k=>['x','y','z'].map(a=>[`${k}-${a}`,'0'])))},
    controls:{},powers:{},circulation:{},derivative_parameters:[],constraints:[],
    equilibrium:{state:null,enabled:false,label:''},numerics:{...AIRFLOW_NUMERICS}};
  const calculation={action:'solve',mode:'mounted',source:'Model',condition:{speed:23},controller,numerics:AIRFLOW_NUMERICS};
  const solution=await sealSolution({id:'steady-controller',name:'Steady controller',created_at:'2026-11-05T00:00:00Z',kind:'mounted',
    configuration:config,data:{analysis:'mounted_static',converged:true,request:calculation,numerics:AIRFLOW_NUMERICS,
      structural_operator:AIRFLOW_NUMERICS.structural_operator,controller:{definition:controller},strips:[],residual:0,
      mass_properties:{mass:1},limitations:[],software_provenance:provenance,
      equilibrium_state:{format:'openswing-equilibrium',version:1,positions:[[0,0,0]],identity:AIRFLOW_NUMERICS,
        launch:{condition:{speed:23},controller}}},auxiliary:{},view:{},provenance});
  assert.deepEqual(await verifySolution(solution),solution);
  for(const field of ['result','request','launch']){
    const bad=structuredClone(solution);
    if(field==='result')bad.data.controller=null;
    else if(field==='request')bad.data.request.controller=null;
    else bad.data.equilibrium_state.launch.controller=null;
    assert.throws(()=>validateSolution(bad),/controller/);
  }
});
