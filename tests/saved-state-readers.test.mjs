import {test} from 'node:test';
import assert from 'node:assert/strict';
import {validateEquilibriumPacket,validateCheckpointPacket,checkpointRecord} from '../web/saved-state-data.js';
import {createEquilibriumSettings} from '../web/equilibrium-state.js';
import {checkpointAt,createTimeCheckpoints} from '../web/time-checkpoint.js';
import {emptyProject,changeCase,parseProject,validateProject} from '../web/project-data.js';
import {sealSolution,verifySolution,kernelFingerprint,validateSolution} from '../web/solution-data.js';

const clone=structuredClone;
const identity=()=>({constraints:[{kind:'ground',type:0},{kind:'joint',type:3},{kind:'joint',type:0},{kind:'joint',type:3}]});
const rows=(angle=400*Math.PI/180)=>[{joint:1,angle_rad:angle},{joint:3,angle_rad:-4*Math.PI}];
const equilibrium=()=>({format:'openswing-equilibrium',version:2,identity:identity(),positions:[[0,0,0]],hinge_charts:rows(),
  launch:{version:1,controller:null},extra:{original:'keep',values:[1,-2,3]}});
const state=(time,angle)=>({time,network:{version:2,positions:[[0,0,0]],hinge_charts:rows(angle)},feedback:[],opaque:{keep:'state'}});
const options=()=>({hinge_charts:[350*Math.PI/180,-3*Math.PI],gravity:[0,0,-9.81],opaque:'keep reference'});
const checkpoint=()=>({format:'openswing-time-checkpoint',version:2,
  context:{identity:identity(),method:{maximum_step:.01,order:2},setup:{forcing:''}},
  state:state(.5,400*Math.PI/180),older:state(.49,390*Math.PI/180),options:options(),
  accepted_method:{version:1,seed:state(.48,380*Math.PI/180),previous:state(.49,390*Math.PI/180),
    previous2:state(.48,380*Math.PI/180),endpoint:{state:state(.5,400*Math.PI/180),options:options()},opaque:[3,2,1]},
  next_step:.01,forcing_side:'right',extension:{uninterpreted:true}});
const trajectory=()=>{const cp=checkpoint();const {format,version,context,...rest}=cp;
  return {analysis:'time_response',restart_context:context,snapshots:[{time:.5,residual:1e-12,restart:{version,...rest}}]};};
const configuration=seed=>({source:'Name\nReader fixture only\nEnd\n',filename:'fixture.asw',mesh:4,fields:{mode:'structural'},
  controls:{},powers:{},circulation:{},derivative_parameters:[],constraints:[],equilibrium:{state:seed,enabled:seed!==null,label:'Saved'}});

function dom(){
  const elements=new Map();
  globalThis.document={getElementById(id){if(!elements.has(id))elements.set(id,{value:'',checked:false,hidden:false,disabled:false,
    textContent:'',addEventListener(){},click(){}});return elements.get(id);}};
  const get=id=>document.getElementById(id);get('mode').value='structural';return get;
}

test('equilibrium v2/project roundtrip preserves unwrapped values and all unknown nested fields',()=>{
  const seed=equilibrium(),original=clone(seed),clean=validateEquilibriumPacket(seed);
  assert.deepEqual(clean,seed);clean.hinge_charts[0].angle_rad=0;assert.deepEqual(seed,original);
  const p=changeCase(emptyProject(),'add',{id:'a',name:'Large hinge',configuration:configuration(seed)});
  assert.deepEqual(parseProject(JSON.stringify(p)),p);
  assert.equal(p.cases[0].configuration.equilibrium.state.hinge_charts[1].angle_rad,-4*Math.PI);
});

test('legacy v1 packets retain their exact fields and core-owned migration decision',()=>{
  const seed=equilibrium();seed.version=1;delete seed.hinge_charts;
  assert.deepEqual(validateEquilibriumPacket(seed),seed);
  const cp=checkpoint();cp.version=1;delete cp.state.network.version;delete cp.state.network.hinge_charts;
  assert.deepEqual(validateCheckpointPacket(cp),cp);
  const old={context:{method:{order:1}},state:{time:0}};
  assert.equal(checkpointRecord(old,old.context).version,1);
  assert.equal(checkpointRecord({...old,version:1},old.context).version,1);
});

test('strict v2 row IDs, finite angles and constraint order reject before import',()=>{
  for(const edit of [s=>delete s.hinge_charts,s=>s.hinge_charts.pop(),s=>s.hinge_charts.reverse(),
    s=>s.hinge_charts[1].joint=1,s=>s.hinge_charts[0].joint=0,s=>s.hinge_charts[0].joint=true,
    s=>s.hinge_charts[0].joint=Number.MAX_SAFE_INTEGER+1,s=>s.hinge_charts[0].angle_rad=Infinity,
    s=>s.hinge_charts[0].angle_rad=NaN,s=>s.hinge_charts[0].angle_rad='7',
    s=>s.hinge_charts[0].angle_rad=false,s=>s.hinge_charts[0].extra=1,s=>s.version=3,s=>s.version='2']){
    const seed=equilibrium();edit(seed);assert.throws(()=>validateEquilibriumPacket(seed));
    const p=emptyProject();p.cases=[{id:'a',name:'A',configuration:configuration(seed)}];p.selected='a';assert.throws(()=>validateProject(p));
  }
});

test('checkpoint v2 preserves current/older/method ownership and distinct reference options',()=>{
  const cp=checkpoint(),before=clone(cp),copy=validateCheckpointPacket(cp);
  assert.deepEqual(copy,cp);assert.notEqual(copy.options.hinge_charts[0],copy.state.network.hinge_charts[0].angle_rad);
  copy.accepted_method.seed.network.hinge_charts[0].angle_rad=0;assert.deepEqual(cp,before);
  const tr=trajectory();assert.deepEqual(checkpointAt(tr,0),cp);
  for(const version of [0,3,'2',true,1.5]){const changed=clone(tr);changed.snapshots[0].restart.version=version;assert.throws(()=>checkpointAt(changed,0));}
});

test('malformed nested checkpoint branches and option reference arrays reject',()=>{
  for(const edit of [c=>delete c.state.network.hinge_charts,c=>c.state.network.version=1,c=>c.older.network.hinge_charts[0].joint=3,
    c=>delete c.accepted_method.seed.network.hinge_charts,c=>c.accepted_method.previous.network.hinge_charts[0].angle_rad=Infinity,
    c=>c.accepted_method.previous2.network.hinge_charts.reverse(),c=>c.accepted_method.endpoint.state.network.version=1,
    c=>c.accepted_method.endpoint.options.hinge_charts[0]='6',c=>c.options.hinge_charts.pop(),c=>c.options.hinge_charts[0]=false]){
    const cp=checkpoint();edit(cp);assert.throws(()=>validateCheckpointPacket(cp));
  }
});

test('actual equilibrium controller imports, reuses and exports version2 unchanged',async()=>{
  const $=dom(),downloads=[],errors=[];const api=createEquilibriumSettings((name,text)=>downloads.push(JSON.parse(text)),()=>{},e=>errors.push(e));
  const seed=equilibrium();await $('equilibrium-file').onchange({target:{files:[{name:'saved.json',text:async()=>JSON.stringify(seed)}]}});
  assert.deepEqual(api.initial(),seed);assert.deepEqual(api.capture().state,seed);assert.equal(errors.length,0);
  api.setComputed(seed);$('equilibrium-save').onclick();assert.deepEqual(downloads[0],seed);
  $('equilibrium-use').onclick();assert.deepEqual(api.initial(),seed);
  const old={format:'openswing-equilibrium',version:1,positions:[]};api.restore({state:old,label:'old',enabled:true});assert.deepEqual(api.initial(),old);
  const bad=equilibrium();bad.hinge_charts[0].joint=7;
  await $('equilibrium-file').onchange({target:{files:[{name:'bad.json',text:async()=>JSON.stringify(bad)}]}});
  assert.equal(errors.length,1);assert.deepEqual(api.initial(),old);
});

test('actual checkpoint controller imports, exports and sends exact version2 to continuation',async()=>{
  const $=dom(),downloads=[],errors=[],runs=[],tr=trajectory();
  $('time-continue-duration').value='.1';$('time-continue-step').value='.01';$('time-continue-order').value='2';
  createTimeCheckpoints(()=>({trajectory:tr,model:{},dirty:false}),()=>0,async(...args)=>runs.push(args),
    (name,text)=>downloads.push(JSON.parse(text)),e=>errors.push(e));
  $('time-checkpoint-save').onclick();assert.deepEqual(downloads[0],checkpoint());
  await $('time-checkpoint-file').onchange({target:{files:[{name:'hinge.json',text:async()=>JSON.stringify(checkpoint())}]}});
  await $('time-continue').onclick();assert.deepEqual(runs[0][0],checkpoint());assert.equal(runs[0][2],null);
  $('time-checkpoint-use').onclick();await $('time-continue').onclick();assert.equal(runs[1][2],tr);assert.equal(runs[1][3],0);
  const bad=checkpoint();bad.older.network.hinge_charts[0].joint=3;
  await $('time-checkpoint-file').onchange({target:{files:[{name:'bad.json',text:async()=>JSON.stringify(bad)}]}});
  assert.equal(errors.length,1);await $('time-continue').onclick();assert.deepEqual(runs.at(-1)[0],checkpoint());
});

async function solution(kind){
  const c=configuration(equilibrium()),p={format:'openswing-kernel-provenance',version:1,modules:{'aero.py':'b'.repeat(64)},
    runtime:{pyodide:'test',python:'test',numpy:'test',scipy:'test'}};p.fingerprint=await kernelFingerprint(p);
  const data=kind==='time'?trajectory():{analysis:'structural_static',residual:1e-12,strips:[],equilibrium_state:equilibrium()};
  Object.assign(data,{converged:true,request:{source:c.source},software_provenance:p});
  const base=kind==='time'?data.snapshots[0]:data;Object.assign(base,{mass_properties:{physical:true},limitations:[]});
  return sealSolution({id:'solution',name:'Hinge',created_at:'2026-10-15T00:00:00Z',kind,configuration:c,data,
    auxiliary:{},view:{},provenance:p});
}

test('computed solution/project archives preserve v2 and reject corrupt nested charts',async()=>{
  for(const kind of ['structural','time']){
    const s=await solution(kind);await verifySolution(s);
    const p={...emptyProject(),solutions:[s],selected_solution:s.id};assert.deepEqual(parseProject(JSON.stringify(p)),p);
    const bad=clone(s);
    if(kind==='time')bad.data.snapshots[0].restart.accepted_method.seed.network.hinge_charts[0].joint=7;
    else bad.data.equilibrium_state.hinge_charts[0].joint=7;
    assert.throws(()=>validateSolution(bad));
  }
});
