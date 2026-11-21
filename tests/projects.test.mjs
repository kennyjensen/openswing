import {test} from 'node:test';
import assert from 'node:assert/strict';
import {emptyProject,changeCase,parseProject,validateProject,validateConfiguration,projectName} from '../web/project-data.js';
const configuration=()=>({source:'Name\nOriginal model\nEnd\n',filename:'original.asw',mesh:{default:4,beams:{'1':{nodes:[0,.2,.5,.8,1]}}},fields:{speed:'12.50',stall:true,'feedback-definition':'{"states":[]}'},controls:{'1':'-.4'},powers:{'2':'5'},circulation:{'1':'3'},derivative_parameters:['alpha','power.2'],constraints:[{variable:'power.2',quantity:'user.trim',target:.01,expression:'sensor("2.displacement_body.y")',unit:'input L',residual_scale:.01}],equilibrium:{state:null,enabled:false,label:''}});
test('portable projects retain literal model text, applied mesh and independent named configurations',()=>{
  const a=configuration(),first=changeCase(emptyProject(),'add',{id:'case-a',name:'  Cruise  ',configuration:a});
  a.mesh.beams['1'].nodes[1]=9;a.fields.speed='99';
  const b=configuration();b.fields.speed='20';b.constraints=[];
  const second=changeCase(first,'add',{id:'case-b',name:'Gust',configuration:b});
  const roundtrip=parseProject(JSON.stringify(second));assert.deepEqual(roundtrip,second);
  assert.equal(first.cases.length,1);assert.equal(first.cases[0].name,'Cruise');assert.equal(first.cases[0].configuration.fields.speed,'12.50');assert.equal(first.cases[0].configuration.mesh.beams['1'].nodes[1],.2);
  assert.equal(roundtrip.cases[0].configuration.source,configuration().source);assert.equal(roundtrip.selected,'case-b');
});
test('portable cases preserve modified-cosine and existing mesh selections',()=>{
  const meshes=[4,...['cosine','modified-cosine','uniform','uniform-breaks'].map(spacing=>({default:4,beams:{'1':{count:8,spacing}}})),configuration().mesh];
  for(const mesh of meshes){
    const inputs={...configuration(),mesh},project=changeCase(emptyProject(),'add',{id:'mesh-case',name:'Mesh case',configuration:inputs});
    const restored=parseProject(JSON.stringify(project)).cases[0].configuration;
    assert.deepEqual(restored.mesh,mesh);
    assert.deepEqual(restored,inputs);
  }
});
test('update, rename, select and deletion produce new projects without mutating prior records',()=>{
  const p=changeCase(changeCase(emptyProject(),'add',{id:'a',name:'A',configuration:configuration()}),'add',{id:'b',name:'B',configuration:configuration()});
  const updated=configuration();updated.fields.speed='22';
  const q=changeCase(changeCase(p,'update',{id:'a',configuration:updated}),'rename',{id:'a',name:'Renamed'});
  assert.equal(p.cases[0].name,'A');assert.equal(p.cases[0].configuration.fields.speed,'12.50');assert.equal(q.cases[0].configuration.fields.speed,'22');
  assert.equal(changeCase(q,'select',{id:'a'}).selected,'a');const removed=changeCase(q,'delete',{id:'b'});assert.equal(removed.selected,'a');assert.equal(q.cases.length,2);
  assert.deepEqual(changeCase(removed,'delete',{id:'a'}).cases,[]);
});
test('loaded equilibrium and all nested setup data are copied without shared ownership',()=>{
  const c=configuration();c.equilibrium={state:{format:'openswing-equilibrium',version:1,positions:[[0,0,0]],launch:{controller:{states:[{name:'lag',rate:'-state("lag")'}]}}},enabled:true,label:'Trim'};
  const saved=validateConfiguration(c);c.equilibrium.state.positions[0][0]=4;c.equilibrium.state.launch.controller.states[0].rate='0';
  assert.equal(saved.equilibrium.state.positions[0][0],0);assert.equal(saved.equilibrium.state.launch.controller.states[0].rate,'-state("lag")');
});
test('ambiguous identities, missing selected cases and unknown or future formats are rejected',()=>{
  const p=changeCase(emptyProject(),'add',{id:'a',name:'A',configuration:configuration()});
  for(const mutate of [v=>v.version=99,v=>v.format='aswing-pnt',v=>v.selected='missing',v=>v.cases.push(structuredClone(v.cases[0])),v=>v.extra=true,v=>v.cases[0].extra=true]){
    const q=structuredClone(p);mutate(q);assert.throws(()=>validateProject(q));
  }
  assert.throws(()=>changeCase(p,'add',{id:'b',name:' A ',configuration:configuration()}),/unique/);
  assert.throws(()=>changeCase(p,'update',{id:'missing',configuration:configuration()}),/Select/);
  assert.throws(()=>projectName('  '));assert.throws(()=>parseProject('{broken'));
});
test('invalid physical input packets fail before JSON can silently replace values',()=>{
  for(const mutate of [c=>c.constraints[0].target=NaN,c=>c.constraints[0].weight=Infinity,c=>c.controls['1']=2,c=>c.fields.stall={},c=>c.derivative_parameters.push('alpha'),c=>c.equilibrium.enabled=true,c=>c.equilibrium.state={positions:[]},c=>c.source='\0',c=>c.mesh=()=>4]){
    const c=configuration();mutate(c);assert.throws(()=>validateConfiguration(c));
  }
});
test('deep or non-JSON equilibrium payloads are rejected while benign names stay plain data',()=>{
  const c=configuration();c.equilibrium.state={format:'openswing-equilibrium',version:1,positions:[]};let point=c.equilibrium.state;
  for(let i=0;i<85;i++){point.next={};point=point.next;}assert.throws(()=>validateConfiguration(c),/deeply nested/);
  const p=changeCase(emptyProject(),'add',{id:'a',name:'<img src=x onerror=alert(1)>',configuration:configuration()});assert.equal(p.cases[0].name,'<img src=x onerror=alert(1)>');
});
