import test from 'node:test';
import assert from 'node:assert/strict';
import {massPane,createMassEditor} from '../web/mass-editor.js';
import {weightRecords} from '../web/mass-data.js';

function documentFor(html){
  const nodes=new Map();
  class Element{
    constructor(tag='div'){this.tagName=tag;this.children=[];this.dataset={};this._value=null;this.disabled=false;this.hidden=false;this.textContent='';this.classList={toggle(){}};}
    get value(){return this._value??(this.tagName==='select'?this.children[0]?.value??'':'');}
    set value(v){this._value=String(v);}
    append(...nodes){this.children.push(...nodes);}
    replaceChildren(...nodes){this.children=[];this._value=null;this.append(...nodes);}
    querySelectorAll(selector){const parts=selector.split(',');return this.children.flatMap(node=>[...(parts.some(s=>s===node.tagName||s==='[data-weight-column]'&&node.dataset.weightColumn!==undefined||s==='[data-mass-length-unit]'&&node.lengthUnit)?[node]:[]),...node.querySelectorAll(selector)]);}
    checkValidity(){return this.value.trim()!==''&&Number.isFinite(Number(this.value));}
    focus(){document.activeElement=this;}
  }
  const root=new Element(),stack=[root];
  for(const match of html.matchAll(/<(\/?)([\w-]+)([^>]*)>/g)){
    const [,end,tag,attributes]=match;if(end){stack.pop();continue;}
    const node=new Element(tag),id=attributes.match(/\bid="([^"]+)"/),column=attributes.match(/data-weight-column="([^"]+)"/);
    if(id){node.id=id[1];nodes.set(node.id,node);}if(column)node.dataset.weightColumn=column[1];
    node.lengthUnit=attributes.includes('data-mass-length-unit');stack.at(-1).append(node);
    if(!['input','br'].includes(tag)&&!attributes.endsWith('/'))stack.push(node);
  }
  return {getElementById:id=>nodes.get(id),createElement:tag=>new Element(tag)};
}

const source='Weight\n! pilot\n1 0 0 0 0 100\nEnd\n';
const model={constants:[10],si:{M:1,L:1},beams:[{index:1,name:'Wing',axis:[[[0,0,0],[0,2,0]]]}],distributions:[{beam:1,domain:[0,2]}],mass_properties:{mass:10,cg:[0,0,0]}};

test('mass fields commit inspected ASW edits automatically; add, delete and undo round-trip',async()=>{
  const previous=globalThis.document;globalThis.document=documentFor(massPane);
  try{
    const state={source,model,dirty:false,busy:false,revision:0},requests=[],commits=[];let view;
    view=createMassEditor({context:()=>state,panels:()=>4,rpc:async request=>{requests.push(request);return model;},commit:async(text,prepared)=>{commits.push(text);Object.assign(state,{source:text,model:prepared});state.revision++;view.setModel(prepared,text);}});
    const get=id=>document.getElementById('mass-'+id);view.setModel(model,source);
    assert.equal(get('value').value,'10');assert.equal(get('total').textContent,'10 kg');
    get('value').value='12';get('value').oninput();await get('value').onchange();
    assert.equal(requests[0].action,'inspect');assert.equal(requests[0].panels,4);assert.equal(commits[0],requests[0].source);
    assert.equal(weightRecords(state.source).records[0].values[5],120);assert.match(state.source,/! pilot/);
    assert.equal(view.hasDraft(),false);assert.equal(get('value').value,'12');
    await get('undo').onclick();assert.equal(state.source,source);
    await get('add').onclick();assert.equal(weightRecords(state.source).records.length,2);assert.equal(get('item').value,'1');assert.equal(get('value').value,'0');
    await get('delete').onclick();assert.equal(weightRecords(state.source).records.length,1);
    await get('undo').onclick();assert.equal(weightRecords(state.source).records.length,2);
    state.dirty=true;view.refresh();assert.equal(get('add').disabled,true);assert.equal(get('value').disabled,true);
  }finally{globalThis.document=previous;}
});

test('invalid or failed mass edits leave the applied model and source unchanged',async()=>{
  const previous=globalThis.document;globalThis.document=documentFor(massPane);
  try{
    const state={source,model,dirty:false,busy:false,revision:0};let calls=0;
    const view=createMassEditor({context:()=>state,panels:()=>4,rpc:async()=>{calls++;throw Error('Invalid inertia');},commit:()=>assert.fail('No commit on failure')});
    view.setModel(model,source);const get=id=>document.getElementById('mass-'+id);
    get('value').value='';get('value').oninput();await get('value').onchange();assert.equal(calls,0);assert.equal(view.hasDraft(),true);
    get('value').value='20';await get('value').onchange();await view.ready();
    assert.equal(calls,1);assert.equal(state.source,source);assert.match(get('status').textContent,/Invalid inertia/);assert.equal(get('value').disabled,false);
  }finally{globalThis.document=previous;}
});

test('an inspection finishing after another model edit cannot overwrite it',async()=>{
  const previous=globalThis.document;globalThis.document=documentFor(massPane);
  try{
    const state={source,model,dirty:false,busy:false,revision:0};let complete,commits=0;
    const view=createMassEditor({context:()=>state,panels:()=>4,rpc:()=>new Promise(resolve=>complete=resolve),commit:()=>commits++});
    view.setModel(model,source);const input=document.getElementById('mass-value');input.value='15';input.oninput();const saved=input.onchange();
    assert.equal(input.disabled,true);
    state.source=source+'! another edit\n';state.revision++;view.setModel(model,state.source);complete(model);await saved;
    assert.equal(commits,0);assert.equal(input.disabled,false);assert.equal(view.hasDraft(),false);
  }finally{globalThis.document=previous;}
});
