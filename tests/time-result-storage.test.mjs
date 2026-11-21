import {test} from 'node:test';
import assert from 'node:assert/strict';
import {unpackTimeResult} from '../web/time-result-storage.js';
import {checkpointAt} from '../web/time-checkpoint.js';

// Hand-authored wire/legacy pair: no producer or physics helper is shared.
function fixture() {
  const context={method:{order:2,maximum_step:.02},setup:{forcing:'time +F3\n0 0\n.02 .1\n'}};
  const previous={time:0,position:[0,-0,2],commands:{F3:0},extension:{literal:'preserve'}};
  const options={gravity:[0,0,-9.81],negative_zero:-0,unknown:{enabled:false,value:null}};
  const before={time:.02,position:[1,-0,2],commands:{F3:0},phase:'before'};
  const after={time:.02,position:[1,-0,2],commands:{F3:.1},phase:'after'};
  const internal={time:.015,position:[.75,-0,2],commands:{F3:0},internal_only:true};
  const changedContext={method:{order:5,scheme:'historic-radau-scheme'},setup:{forcing:'replacement'},opaque:{keep:7}};
  const layout={columns:['x','y','z'],scales:[1,2,3],marker:{format:'ordinary-user-data',references:[['literal',99]]}};
  const seed={time:.01,position:[.5,-0,2],not_a_public_snapshot:true};
  const accepted={kind:'bdf',scheme:'historic-bdf-scheme',coefficients:[75,-100,25],
    previous,previous2:internal,seed,accepted_inputs:{tolerance:1e-10},layout,
    endpoint:{state:before,options},unknown_old_metadata:{retain:[true,null,'v0']}};
  const snapshots=[
    {time:0,order:0,residual:0,restart:{state:previous,older:null,options,next_step:.02,forcing_side:'left'}},
    {time:.02,order:2,residual:1e-12,input_transition:{side:'before'},
      restart:{state:before,older:previous,options,next_step:.01,forcing_side:'left',accepted_method:accepted}},
    {time:.02,order:0,residual:2e-12,input_transition:{side:'after'},restart_context:changedContext,
      restart:{state:after,older:null,options,next_step:.01,forcing_side:'right',
        accepted_method:{kind:'old-radau',scheme:'opaque-historic-scheme',stages:[seed,internal],metadata:{untouched:true}}}},
  ];
  const expected={analysis:'time_response',restart_context:context,snapshots,
    frame_mode:'free',converged:true,opaque:{keep:false,empty:[],negative_zero:-0}};
  const packet={format:'openswing-time-result',version:1,
    result:{analysis:'time_response',restart_context:null,snapshots:[
      {time:0,order:0,residual:0,restart:{state:null,older:null,options:null,next_step:.02,forcing_side:'left'}},
      {time:.02,order:2,residual:1e-12,input_transition:{side:'before'},
        restart:{state:null,older:null,options:null,next_step:.01,forcing_side:'left',
          accepted_method:{kind:'bdf',scheme:'historic-bdf-scheme',coefficients:[75,-100,25],
            previous:null,previous2:null,seed:null,accepted_inputs:{tolerance:1e-10},layout:null,
            endpoint:{state:null,options:null},unknown_old_metadata:{retain:[true,null,'v0']}}}},
      {time:.02,order:0,residual:2e-12,input_transition:{side:'after'},restart_context:null,
        restart:{state:null,older:null,options:null,next_step:.01,forcing_side:'right',
          accepted_method:{kind:'old-radau',scheme:'opaque-historic-scheme',stages:[seed,internal],metadata:{untouched:true}}}},
    ],frame_mode:'free',converged:true,opaque:{keep:false,empty:[],negative_zero:-0}},
    values:[context,previous,options,before,after,internal,changedContext,layout,seed],
    references:[
      [['restart_context'],0],
      [['snapshots',0,'restart','state'],1],[['snapshots',0,'restart','options'],2],
      [['snapshots',1,'restart','state'],3],[['snapshots',1,'restart','older'],1],
      [['snapshots',1,'restart','options'],2],
      [['snapshots',1,'restart','accepted_method','previous'],1],
      [['snapshots',1,'restart','accepted_method','previous2'],5],
      [['snapshots',1,'restart','accepted_method','seed'],8],
      [['snapshots',1,'restart','accepted_method','layout'],7],
      [['snapshots',1,'restart','accepted_method','endpoint','state'],3],
      [['snapshots',1,'restart','accepted_method','endpoint','options'],2],
      [['snapshots',2,'restart_context'],6],[['snapshots',2,'restart','state'],4],
      [['snapshots',2,'restart','options'],2],
    ]};
  return {packet,expected};
}
function minimal() {
  return {format:'openswing-time-result',version:1,
    result:{analysis:'time_response',snapshots:[{restart:{state:null,options:null}}],restart_context:null},
    values:[{time:0,position:[1,2,3]}],references:[[['snapshots',0,'restart','state'],0]]};
}
function rejected(packet) {
  const before=structuredClone(packet);
  assert.throws(()=>unpackTimeResult(packet),/Invalid compact time result\./);
  assert.deepStrictEqual(packet,before,'failed hydration must not write any target');
}

test('ordinary and legacy results pass through unchanged',()=>{
  for(const value of [null,undefined,false,0,'text',[],{},
    {analysis:'time_response',snapshots:[]}, {format:'another-format',version:1}])
    assert.strictEqual(unpackTimeResult(value),value);
});

test('hydration restores the complete legacy tree and JSON export',()=>{
  const {packet,expected}=fixture();const result=unpackTimeResult(packet);
  assert.strictEqual(result,packet.result);
  assert.deepStrictEqual(result,expected);
  assert.equal(JSON.stringify(result),JSON.stringify(expected));
  assert.equal(Object.hasOwn(result,'values'),false);
  assert.equal(Object.hasOwn(result,'references'),false);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(result)),JSON.parse(JSON.stringify(expected)));
});

test('pool identity survives structuredClone and signed zero is retained before JSON normalization',()=>{
  const {packet}=fixture();const result=unpackTimeResult(packet),copy=structuredClone(result);
  for(const r of [result,copy]){
    const a=r.snapshots[0].restart,b=r.snapshots[1].restart,c=r.snapshots[2].restart;
    assert.strictEqual(a.state,b.older);assert.strictEqual(a.state,b.accepted_method.previous);
    assert.strictEqual(a.options,b.options);assert.strictEqual(b.options,c.options);
    assert.strictEqual(b.state,b.accepted_method.endpoint.state);
    assert.strictEqual(b.options,b.accepted_method.endpoint.options);
    assert.ok(Object.is(b.state.position[1],-0));assert.ok(Object.is(b.options.negative_zero,-0));
    assert.ok(Object.is(r.opaque.negative_zero,-0));
  }
  assert.notStrictEqual(copy.snapshots[0].restart.state,result.snapshots[0].restart.state);
  // JSON.stringify already normalizes -0 in the legacy path; no new loss is claimed or hidden.
  assert.equal(JSON.stringify(copy),JSON.stringify(result));
});

test('equal-time states, adaptive internal predecessors and old schemes remain distinct and complete',()=>{
  const {packet,expected}=fixture();const result=unpackTimeResult(packet);
  const before=result.snapshots[1],after=result.snapshots[2],method=before.restart.accepted_method;
  assert.equal(before.time,after.time);assert.notStrictEqual(before.restart.state,after.restart.state);
  assert.equal(before.restart.state.commands.F3,0);assert.equal(after.restart.state.commands.F3,.1);
  assert.deepStrictEqual(before.input_transition,{side:'before'});assert.deepStrictEqual(after.input_transition,{side:'after'});
  assert.equal(method.previous2.time,.015);assert.equal(method.seed.time,.01);
  assert.ok(!result.snapshots.some(s=>s.time===method.previous2.time));
  assert.deepStrictEqual(method,expected.snapshots[1].restart.accepted_method);
  assert.deepStrictEqual(after.restart.accepted_method,expected.snapshots[2].restart.accepted_method);
  assert.notStrictEqual(result.restart_context,after.restart_context);
  assert.deepStrictEqual(method.layout.marker,{format:'ordinary-user-data',references:[['literal',99]]});
});

test('selected checkpoint owns each formerly aliased branch independently',()=>{
  const {packet}=fixture();const result=unpackTimeResult(packet),before=structuredClone(result);
  const selected=checkpointAt(result,1);
  assert.equal(selected.format,'openswing-time-checkpoint');assert.equal(selected.version,1);
  assert.notStrictEqual(selected.state,selected.accepted_method.endpoint.state);
  assert.notStrictEqual(selected.options,selected.accepted_method.endpoint.options);
  assert.notStrictEqual(selected.older,selected.accepted_method.previous);
  assert.ok(Object.is(selected.state.position[1],-0));
  selected.state.position[0]=999;selected.options.gravity[0]=777;selected.older.position[0]=555;
  assert.equal(selected.accepted_method.endpoint.state.position[0],1);
  assert.equal(selected.accepted_method.endpoint.options.gravity[0],0);
  assert.equal(selected.accepted_method.previous.position[0],0);
  assert.deepStrictEqual(result,before);
  const after=checkpointAt(result,2);
  assert.deepStrictEqual(after.context,result.snapshots[2].restart_context);
  assert.equal(after.forcing_side,'right');assert.equal(selected.forcing_side,'left');
});

test('raw pooled arrays and literal reference-like user data are not recursively interpreted',()=>{
  const packet=minimal();packet.values=[[-0,{format:'openswing-time-result',version:99,values:['literal'],references:[['not','an instruction']]}]];
  const result=unpackTimeResult(packet);
  assert.strictEqual(result.snapshots[0].restart.state,packet.values[0]);
  assert.ok(Object.is(result.snapshots[0].restart.state[0],-0));
  assert.equal(result.snapshots[0].restart.state[1].version,99);
});

test('malformed wrapper headers and reference records reject without partial hydration',()=>{
  const changes=[p=>p.version=0,p=>p.version=2,p=>p.version='1',p=>p.version=true,p=>delete p.version,
    p=>p.result=null,p=>p.result=[],p=>p.result.analysis='frequency_response',p=>delete p.result.snapshots,
    p=>p.result.snapshots={},p=>p.values=null,p=>p.values={},p=>p.references=null,p=>p.references={},
    p=>p.references=[null],p=>p.references=[{}],p=>p.references=[[]],p=>p.references=[[['restart_context']]],
    p=>p.references=[[['restart_context'],0,'extra']]];
  for(const edit of changes){const p=minimal();edit(p);rejected(p);}
});

test('invalid pool indices and noncontainer pool values reject',()=>{
  for(const index of [-1,1,.5,'0',true,null,NaN,Infinity,Number.MAX_SAFE_INTEGER+1]){
    const p=minimal();p.references[0][1]=index;rejected(p);
  }
  for(const value of [null,undefined,false,4,'literal']){
    const p=minimal();p.values[0]=value;rejected(p);
  }
});

test('invalid target paths, nonholes, duplicates and overlap reject atomically',()=>{
  const paths=[null,'snapshots',[],Array(7).fill('x'),['missing'],[0],['snapshots','0','restart','state'],
    ['snapshots',-1],['snapshots',.5],['snapshots',true],['snapshots',1],['snapshots','length'],
    ['snapshots',0,'missing'],['snapshots',0,'restart','state','time'],['toString']];
  for(const path of paths){const p=minimal();p.references.push([path,0]);rejected(p);}
  const nonhole=minimal();nonhole.result.restart_context={};nonhole.references.push([['restart_context'],0]);rejected(nonhole);
  const duplicate=minimal();duplicate.references.push(structuredClone(duplicate.references[0]));rejected(duplicate);
  for(const reverse of [false,true]){
    const overlap=minimal();const refs=[[['restart_context'],0],[['restart_context','method'],0]];
    overlap.references.push(...(reverse?refs.reverse():refs));rejected(overlap);
  }
});

test('prototype mutation paths reject even when malicious keys are own JSON properties',()=>{
  for(const key of ['__proto__','constructor','prototype']){
    const packet=minimal();Object.defineProperty(packet.result,key,{value:null,enumerable:true,writable:true,configurable:true});
    packet.references.push([[key],0]);rejected(packet);
    const nested=minimal();nested.result.extension=JSON.parse(`{"${key}":null}`);
    nested.references.push([['extension',key],0]);rejected(nested);
  }
  assert.equal(Object.hasOwn(Object.prototype,'time'),false);
  assert.equal(Object.hasOwn(Object.prototype,'position'),false);
});
