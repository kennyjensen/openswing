import test from 'node:test';
import assert from 'node:assert/strict';
import {steadyRequest,validateSteadyCheckpoint,validateSteadyProgress,progressRecord,nextSteadyRequest} from '../web/steady-progress-data.js';
import {SECTION_NUMERICS} from '../web/numerical-policy.js';
import {validateEquilibriumPacket,validateCheckpointPacket} from '../web/saved-state-data.js';

const fixture=()=>{
  const request={action:'solve',mode:'structural',source:'Name\nSynthetic test\nEnd\n',panels:4,condition:null,gravity:[0,1,0],numerics:{...SECTION_NUMERICS}};
  const configuration={source:request.source,filename:'synthetic.asw',mesh:4,fields:{mode:'structural'},controls:{},powers:{},circulation:{},derivative_parameters:[],constraints:[],equilibrium:{state:null,enabled:false,label:''},numerics:{...SECTION_NUMERICS}};
  // Syntax fixture only; a real core checksum/residual is exercised in Chromium.
  const checkpoint={format:'openswing-static-continuation',version:1,context:{coordinates:{size:2},identity:{...SECTION_NUMERICS}},coordinates:[.0001,-.01],hinge_charts:[],load_fraction:.25,next_increment:.25,accepted_load_steps:1,rejected_load_attempts:0,physical_residual:1e-14,sha256:'a'.repeat(64)};
  const result={continuation_status:'pending',converged:false,checkpoint};
  return {request,configuration,checkpoint,result};
};

test('portable progress retains all inputs and owns each saved value',()=>{
  const {configuration,request,result}=fixture(),before=structuredClone({configuration,request,result});
  const saved=progressRecord(configuration,nextSteadyRequest({...request,derivatives:undefined}),result);
  assert.deepEqual(saved,validateSteadyProgress(JSON.parse(JSON.stringify(saved))));
  const next=nextSteadyRequest({...request,derivatives:undefined},saved);
  assert.equal(next.continuation.max_load_steps,1);
  assert.deepEqual(next.continuation.checkpoint,result.checkpoint);
  next.continuation.checkpoint.coordinates[0]=10;saved.configuration.fields.mode='mounted';
  assert.deepEqual({configuration,request,result},before);
  assert.notEqual(next.continuation.checkpoint.coordinates[0],saved.checkpoint.coordinates[0]);
});

test('resume matches every solve setting, independently of key order',()=>{
  const {configuration,request,result}=fixture(),saved=progressRecord(configuration,request,result);
  assert.doesNotThrow(()=>nextSteadyRequest(Object.fromEntries(Object.entries(request).reverse()),saved));
  for(const change of [r=>r.gravity[1]=2,r=>r.source+='!',r=>r.panels=8,r=>r.condition={speed:5},r=>delete r.numerics]){
    const r=structuredClone(request);change(r);assert.throws(()=>nextSteadyRequest(r,saved),/inputs changed/);
  }
});

test('unfinished progress cannot masquerade as time or equilibrium state',()=>{
  const {configuration,request,result,checkpoint}=fixture(),saved=progressRecord(configuration,request,result);
  for(const value of [saved,checkpoint]){
    assert.throws(()=>validateEquilibriumPacket(value),/equilibrium/);
    assert.throws(()=>validateCheckpointPacket(value),/time checkpoint/);
  }
  for(const change of [{converged:true},{continuation_status:'complete'},{equilibrium_state:{}}])
    assert.throws(()=>progressRecord(configuration,request,{...result,...change}),/unfinished accepted/);
  assert.throws(()=>validateSteadyProgress({...saved,format:'openswing-time-checkpoint'}),/equilibrium-progress/);
});

test('incompatible case, mesh, mode and numerical identity fail import',()=>{
  const {configuration,request,result}=fixture(),saved=progressRecord(configuration,request,result);
  for(const change of [s=>s.configuration.source+='!',s=>s.configuration.mesh=8,s=>s.configuration.fields.mode='mounted',s=>delete s.request.numerics,s=>s.checkpoint.context.identity.structural_operator='midpoint-v1',s=>s.version=2,s=>s.extra=true]){
    const s=structuredClone(saved);change(s);assert.throws(()=>validateSteadyProgress(s));
  }
});

test('nonfinite, mistyped and malformed partial states fail syntax checks',()=>{
  for(const change of [p=>p.load_fraction=1,p=>p.load_fraction='0.25',p=>p.next_increment=true,p=>p.next_increment=0,p=>p.coordinates.pop(),p=>p.coordinates[0]=Infinity,p=>p.hinge_charts=[false],p=>p.physical_residual=-1,p=>p.accepted_load_steps=true,p=>p.sha256='wrong']){
    const p=fixture().checkpoint;change(p);assert.throws(()=>validateSteadyCheckpoint(p));
  }
});

test('only supported cold steady requests enter the bounded route',()=>{
  for(const extra of [{controller:{}},{derivatives:{}},{initial_state:{}},{continuation:{}},{mode:'time'},{operating_constraints:[null]},{operating_constraints:[{}]},{operating_constraints:[{variable:'alpha',quantity:'force.z'}]},{gravity:[0,Infinity,0]}])
    assert.throws(()=>steadyRequest({...fixture().request,...extra}));
  const constraints=[{variable:'acceleration.z',quantity:'force.z',target:0}];
  assert.doesNotThrow(()=>steadyRequest({...fixture().request,operating_constraints:constraints}));
  assert.throws(()=>steadyRequest({...fixture().request,operating_constraints:[...constraints,...constraints]}),/trim targets/);
});
