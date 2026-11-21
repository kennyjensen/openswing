import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createNodeEditor,nodePane} from '../web/node-editor.js';

// Small DOM/RPC fixture: exercise the real auto-apply handlers without a solver.
function fixture(){
  class Element{
    constructor(tag){this.tagName=tag;this.children=[];this.attrs={};this.textContent='';}
    setAttribute(k,v){this.attrs[k]=String(v);if(k==='hidden')this.hidden=true;}
    get value(){return this._value??this.attrs.value??(this.tagName==='select'?this.children[0]?.value??'':'');}
    set value(v){this._value=String(v);}
    append(...nodes){this.children.push(...nodes);}
    replaceChildren(...nodes){this.children=[];if(this.tagName==='select')delete this._value;this.append(...nodes);}
    querySelectorAll(s){return this.children.flatMap(c=>[...(s.split(',').some(t=>t[0]==='#'?c.attrs.id===t.slice(1):c.tagName===t)?[c]:[]),...c.querySelectorAll(s)]);}
    querySelector(s){return this.querySelectorAll(s)[0]??null;}
    get tBodies(){return this.querySelectorAll('tbody');}
    get classList(){return {toggle(){}};}
  }
  const root=new Element('main'),stack=[root];
  for(const token of nodePane.matchAll(/<\/?([\w-]+)([^>]*)>/g)){
    if(token[0].startsWith('</')){stack.pop();continue;}
    const e=new Element(token[1]);for(const a of token[2].matchAll(/([\w-]+)(?:="([^"]*)")?/g))e.setAttribute(a[1],a[2]??'');
    stack.at(-1).append(e);if(token[1]!=='input')stack.push(e);
  }
  const previous=globalThis.document;
  globalThis.document={getElementById:id=>root.querySelector('#'+id),querySelector:()=>null,createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag)};
  const $=id=>document.getElementById(id),state={source:'ASW source',revision:1,busy:false,dirty:false};
  const defaultNodes=[-6,-3,0,3,6],calls=[],commits=[],errors=[];let reject=false,delay=null,view;
  const model=settings=>({beams:[{index:1,name:'Wing'},{index:2,name:'Tail'}],mesh_discretization:{settings,beams:[1,2].map(beam=>{
    const spec=settings.beams?.[beam],n=spec?.count??4,values=spec?.nodes??(spec?Array.from({length:n+1},(_,i)=>-6+12*i/n):defaultNodes);
    return {beam,name:beam===1?'Wing':'Tail',nodes:values.map((t,i)=>({t,fraction:(t+6)/12,theta:Math.acos(t/6),required:i===0||i===values.length-1?['endpoint']:[]}))};
  })}});
  const rpc=async request=>{calls.push(structuredClone(request));if(delay){const pending=delay;delay=null;await pending.promise;}if(reject)throw Error('Node stations must be strictly increasing');return model(request.panels);};
  view=createNodeEditor({context:()=>state,rpc,showError:e=>errors.push(e.message),commit:async(source,next)=>{commits.push(next);state.source=source;state.revision++;view.setModel(next);}});
  assert.equal(view.settings(),48);
  view.restore(4);
  view.setModel(model(4));
  const change=async(id,value)=>{const e=$(id);e.value=value;e.oninput?.();await e.onchange();};
  return {$,state,view,calls,commits,errors,change,rows:()=>$('node-table').tBodies[0].children.map(r=>Number(r.children[0].textContent)),setReject:v=>{reject=v;},
    defer(){let release;const promise=new Promise(resolve=>{release=resolve;});delay={promise};return release;},restore(){globalThis.document=previous;}};
}

test('node settings apply on completed edits and redraw without changing ASW source',async()=>{
  const f=fixture();try{
    await f.change('node-spacing','uniform');
    assert.deepEqual(f.view.settings(),{default:4,beams:{'1':{count:4,spacing:'uniform'}}});
    f.$('node-count').value='6';f.$('node-count').oninput();
    assert.equal(f.calls.length,1);assert.equal(f.view.hasDraft(),true);
    await f.$('node-count').onchange();assert.equal(f.rows().length,7);
    await f.change('node-min-spacing','.2');
    assert.deepEqual(f.view.settings(),{default:4,beams:{'1':{count:6,spacing:'uniform',min_spacing:.2}}});
    assert.equal(f.state.source,'ASW source');assert.equal(f.view.hasDraft(),false);
    assert.equal(f.$('node-status').hidden,true);assert.equal(f.$('node-count').disabled,false);
    for(const call of f.calls)assert.equal(call.action,'inspect');
  }finally{f.restore();}
});

test('explicit stations start from displayed nodes and apply when the field is completed',async()=>{
  const f=fixture();try{
    const original=f.rows();await f.change('node-spacing','custom');
    assert.deepEqual(f.view.settings().beams['1'].nodes,original);
    assert.equal(f.$('node-custom').hidden,false);assert.equal(f.$('node-count-label').hidden,true);
    await f.change('node-stations','-6, -4, 0, 2, 6');
    assert.deepEqual(f.rows(),[-6,-4,0,2,6]);assert.equal(f.view.hasDraft(),false);
  }finally{f.restore();}
});

test('default resets only the selected beam and restoring saved meshes still works',async()=>{
  const f=fixture();try{
    await f.change('node-spacing','uniform');await f.change('node-count','8');
    await f.change('node-beam','2');await f.change('node-spacing','modified-cosine');
    await f.change('node-beam','1');await f.change('node-spacing','default');
    assert.deepEqual(f.view.settings(),{default:4,beams:{'2':{count:4,spacing:'modified-cosine'}}});
    await f.change('node-beam','2');assert.equal(f.$('node-spacing').value,'modified-cosine');
    await f.change('node-spacing','default');assert.equal(f.view.settings(),4);
    f.view.restore({default:12,beams:{'2':{count:8,spacing:'uniform'}}});
    assert.deepEqual(f.view.settings(),{default:12,beams:{'2':{count:8,spacing:'uniform'}}});
    f.view.clear();assert.equal(f.view.settings(),12);
  }finally{f.restore();}
});

test('invalid automatic updates preserve the applied mesh and can be corrected',async()=>{
  const f=fixture();try{
    await f.change('node-spacing','custom');const rows=f.rows(),applied=f.view.settings();
    f.setReject(true);await f.change('node-stations','-6, 0, 0, 6');
    assert.deepEqual(f.rows(),rows);assert.deepEqual(f.view.settings(),applied);
    assert.equal(f.view.hasDraft(),true);assert.equal(f.$('node-spacing').disabled,false);
    assert.match(f.$('node-status').textContent,/Mesh not applied.*strictly increasing/);
    assert.equal(f.$('node-status').hidden,false);assert.equal(f.errors.length,1);
    f.setReject(false);await f.change('node-stations','-6, -2, 0, 6');
    assert.deepEqual(f.rows(),[-6,-2,0,6]);assert.equal(f.$('node-status').hidden,true);
    await f.change('node-spacing','uniform');const count=f.calls.length;
    await f.change('node-min-spacing','-1');assert.equal(f.calls.length,count);
    assert.match(f.$('node-status').textContent,/nonnegative/);
    await f.change('node-min-spacing','0');assert.equal(f.view.hasDraft(),false);
  }finally{f.restore();}
});

test('pending node edits disable controls and stale replies do not overwrite source or mesh',async()=>{
  for(const changeSource of [true,false]){
    const f=fixture();try{
      const release=f.defer(),pending=f.change('node-spacing','uniform');
      assert.equal(f.$('node-count').disabled,true);assert.equal(f.$('node-status').textContent,'Updating…');
      if(changeSource)f.state.source='Edited ASW';else f.state.revision++;
      release();await pending;
      assert.equal(f.commits.length,0);assert.equal(f.view.settings(),4);
      assert.equal(f.$('node-count').disabled,false);assert.match(f.$('node-status').textContent,/not applied/);
    }finally{f.restore();}
  }
});
