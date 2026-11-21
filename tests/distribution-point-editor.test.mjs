import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createDistributionEditor,distributionPane} from '../web/distribution-editor.js';

// Exercise the real editor and event handlers without a browser or worker.
// The RPC stub checks automatic editing transport, not spline physics.
function fixture(initial=[[0,1],[3,2],[6,1]],metadata={}){
  class Element {
    constructor(tag){this.tagName=tag.toUpperCase();this.attributes={};this.children=[];this.parentElement=null;this.disabled=false;this.style={setProperty(){}};this.textContent='';this.captured=new Set();}
    setAttribute(k,v){this.attributes[k]=String(v);} getAttribute(k){return this.attributes[k]??null;}
    get id(){return this.attributes.id??'';}
    get value(){return this._value??this.attributes.value??(this.tagName==='SELECT'?this.querySelector('option')?.value??'':'');}
    set value(v){this._value=String(v);}
    get classList(){const e=this;return {contains:s=>(e.attributes.class??'').split(' ').includes(s),toggle(s,on){const set=new Set((e.attributes.class??'').split(' ').filter(Boolean));if(on??!set.has(s))set.add(s);else set.delete(s);e.attributes.class=[...set].join(' ');},add(s){this.toggle(s,true);},remove(s){this.toggle(s,false);}};}
    append(...nodes){for(const node of nodes){node.parentElement=this;this.children.push(node);}}
    replaceChildren(...nodes){this.children=[];if(this.tagName==='SELECT')delete this._value;this.append(...nodes);}
    matches(selector){return selector.split(',').some(s=>{
      if(s[0]==='#')return this.id===s.slice(1);
      if(s[0]==='.')return this.classList.contains(s.slice(1));
      const a=s.match(/^\[([^=\]]+)(?:="([^"]+)")?\]$/);
      if(a)return a[2]===undefined?this.getAttribute(a[1])!==null:this.getAttribute(a[1])===a[2];
      return this.tagName.toLowerCase()===s;
    });}
    closest(s){return this.matches(s)?this:this.parentElement?.closest(s)??null;}
    contains(node){return node===this||this.children.some(c=>c.contains(node));}
    querySelectorAll(s){return this.children.flatMap(c=>[...(c.matches(s)?[c]:[]),...c.querySelectorAll(s)]);}
    querySelector(s){return this.querySelectorAll(s)[0]??null;}
    get tBodies(){return this.querySelectorAll('tbody');} get rows(){return this.children.filter(c=>c.tagName==='TR');}
    focus(){document.activeElement=this;}
    setPointerCapture(id){this.captured.add(id);} hasPointerCapture(id){return this.captured.has(id);}
    releasePointerCapture(id){this.captured.delete(id);this.onlostpointercapture?.({pointerId:id});}
    getScreenCTM(){return {inverse:()=>({})};}
    createSVGPoint(){return {x:0,y:0,matrixTransform(){return {x:(this.x-17)/2,y:(this.y-29)/2};}};}
  }
  const root=new Element('main'),stack=[root];
  // Parse the production panel rather than inventing the removed graft inputs.
  for(const token of distributionPane.matchAll(/<\/?([\w-]+)([^>]*)>/g)){
    if(token[0].startsWith('</')){stack.pop();continue;}
    const e=new Element(token[1]);for(const a of token[2].matchAll(/([\w-]+)(?:="([^"]*)")?/g))e.setAttribute(a[1],a[2]??'');
    stack.at(-1).append(e);if(token[1]!=='input')stack.push(e);
  }
  const document={getElementById:id=>root.querySelector('#'+id),createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag)};
  const previous=globalThis.document;globalThis.document=document;
  const $=id=>document.getElementById(id),clone=v=>JSON.parse(JSON.stringify(v));
  const model={beams:[{index:1}],distributions:[{beam:1,name:'Wing',properties:['chord'],domain:[-6,6],lifting:true}],distribution_defaults:{},...metadata};
  const state={model,source:'original',revision:1,busy:false,dirty:false},sources=new Map([['original',clone(initial)]]),calls=[],commits=[];
  let reject=false,view,delay=null;
  const report=points=>({points:clone(points),domain:[0,6],mirrored:points[0][0]===0,name:'chord',segments:[{t:points.map(p=>p[0]),values:points.map(p=>p[1])}]});
  const rpc=async request=>{
    calls.push(clone(request));
    if(delay?.action===request.action){const pending=delay;delay=null;await pending.promise;}
    if(reject===request.action||(reject===true&&request.action==='edit_distribution'))throw new Error('Invalid property geometry');
    if(request.action==='inspect')return model;
    if(request.action==='distribution')return report(sources.get(request.source));
    assert.equal(request.action,'edit_distribution');
    const points=request.edit.points.map(([t,v])=>[t,v*request.edit.multiplier+request.edit.adder]);
    const source=JSON.stringify(points);sources.set(source,points);
    return {source,distribution:report(points)};
  };
  view=createDistributionEditor({context:()=>state,rpc,panels:()=>4,commit:async(source,next)=>{
    commits.push(source);state.source=source;state.model=next;state.revision++;view.setModel(next,source);
  }});
  const tick=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
  const rows=()=>$('distribution-table').tBodies[0].rows.map(row=>row.querySelectorAll('input').map(e=>Number(e.value)));
  const handle=i=>$('distribution-plot').querySelectorAll('.distribution-point-handle')[i];
  const position=i=>handle(i).parentElement.getAttribute('transform').match(/\(([^)]+)\)/)[1].split(' ').map(Number);
  function event(i,dx=0,dy=0,extra={}){
    const [x,y]=position(i);return {target:handle(i),pointerId:7,button:0,isPrimary:true,pointerType:'touch',clientX:17+2*(x+dx),clientY:29+2*(y+dy),preventDefault(){this.prevented=true;},...extra};
  }
  function drag(i,dx,dy){const svg=$('distribution-plot').querySelector('svg'),down=event(i),move=event(i,dx,dy);svg.onpointerdown(down);svg.onpointermove(move);svg.onpointerup(move);return {down,move};}
  view.setModel(model,'original');
  return {$,state,view,calls,commits,rows,handle,event,drag,tick,setReject:value=>{reject=value;},
    defer(action){let release;const promise=new Promise(resolve=>{release=resolve;});delay={action,promise};return release;},
    restore(){globalThis.document=previous;}};
}

test('property dropdown lists every defined property and selection loads it immediately',async()=>{
  const distributions=[
    {beam:1,name:'Wing',properties:['x','y','z','chord','alpha','EA','EIcc','dCLdF2'],domain:[-6,6],lifting:true},
    {beam:2,name:'Boom',properties:['x','y','mg'],domain:[0,6],lifting:false},
  ];
  const f=fixture(undefined,{distributions,distribution_defaults:{alpha:0,EA:0,mg:0}});try{
    await f.tick();const select=f.$('distribution-name');
    assert.equal(select.tagName,'SELECT');assert.equal(f.$('distribution-names'),null);
    assert.equal(select.value,'chord');assert.equal(f.$('distribution-custom-field').hidden,true);
    assert.equal(select.children[0].label,'Defined in file');
    assert.deepEqual(select.children[0].children.map(e=>e.value),distributions[0].properties);
    select.value='EA';await select.onchange();
    assert.equal(f.calls.at(-1).action,'distribution');assert.equal(f.calls.at(-1).name,'EA');
    assert.equal(f.$('distribution-edit').disabled,false);
    f.$('distribution-beam').value='2';f.$('distribution-beam').onchange();await f.tick();
    assert.deepEqual(select.children[0].children.map(e=>e.value),distributions[1].properties);
    assert.equal(select.value,'x');assert.equal(f.calls.at(-1).beam,2);assert.equal(f.calls.at(-1).name,'x');
    assert.equal(f.commits.length,0);
  }finally{f.restore();}
});

test('other properties and custom indexed derivatives remain available without filtering the file list',async()=>{
  const f=fixture(undefined,{distribution_defaults:{EA:0}});try{
    await f.tick();const select=f.$('distribution-name');
    assert.equal(select.children[1].label,'Other properties');
    assert.ok(select.children[1].children.some(e=>e.value==='EA'));
    select.value='EA';await select.onchange();assert.deepEqual(f.rows(),[[0,0],[6,0]]);
    select.value='';select.onchange();assert.equal(f.$('distribution-custom-field').hidden,false);
    assert.equal(document.activeElement,f.$('distribution-custom-name'));
    f.$('distribution-custom-name').value='dCLdF12';f.$('distribution-custom-name').oninput();
    await f.$('distribution-custom-name').onchange();assert.deepEqual(f.rows(),[[0,0],[6,0]]);
    assert.equal(f.$('distribution-status').classList.contains('distribution-error'),false);
    select.value='chord';await select.onchange();assert.equal(f.$('distribution-custom-field').hidden,true);
    assert.deepEqual(select.children[0].children.map(e=>e.value),['chord']);assert.equal(f.calls.at(-1).name,'chord');
  }finally{f.restore();}
});

test('pencil enables live curve dragging and release applies once without preview buttons',async()=>{
  const f=fixture();try{
    await f.tick();
    for(const id of ['distribution-graft','distribution-draw','distribution-preview','distribution-apply','distribution-load','distribution-remove','distribution-add'])assert.equal(f.$(id),null);
    const actions=f.$('distribution-table').tBodies[0].rows[0].querySelectorAll('button');
    assert.equal(actions.length,2);assert.equal(actions[0].textContent,'+');
    assert.equal(actions[1].getAttribute('aria-label'),'Delete station 1');assert.ok(actions[1].querySelector('svg'));
    assert.equal(f.$('distribution-edit').getAttribute('aria-label'),'Edit points');
    assert.ok(f.$('distribution-edit').querySelector('svg'));
    const before=f.rows();f.drag(1,49,-18);assert.deepEqual(f.rows(),before);
    f.$('distribution-edit').onclick();
    assert.equal(f.$('distribution-plot').classList.contains('distribution-editing'),true);
    const svg=f.$('distribution-plot').querySelector('svg'),curve=()=>svg.querySelector('.distribution-curve').getAttribute('d'),old=curve();
    const down=f.event(1),move=f.event(1,49,-18);
    svg.onpointerdown(down);svg.onpointermove(move);
    assert.equal(down.prevented,true);assert.equal(move.prevented,true);
    assert.ok(Math.abs(f.rows()[1][0]-3.6)<1e-10);assert.ok(Math.abs(f.rows()[1][1]-2.08)<1e-10);
    assert.ok(curve()!==old);
    const position=f.handle(1).parentElement.getAttribute('transform').slice(10,-1);
    assert.ok(curve().includes('L'+position)); // Curve actually passes through moved knot.
    assert.equal(f.state.source,'original');assert.equal(f.calls.filter(c=>c.action==='edit_distribution').length,0);
    svg.onpointerup(move);const expected=f.rows();await f.tick();
    assert.deepEqual(JSON.parse(f.state.source),expected);assert.equal(f.commits.length,1);
    assert.equal(f.calls.filter(c=>c.action==='edit_distribution').length,1);
    assert.equal(f.$('distribution-edit').getAttribute('aria-pressed'),'true');assert.equal(f.view.hasDraft(),false);
    f.$('distribution-edit').onclick();
    assert.equal(f.$('distribution-plot').classList.contains('distribution-editing'),false);
    f.drag(1,-20,20);assert.deepEqual(f.rows(),expected);
    const css=readFileSync(new URL('../web/style.css',import.meta.url),'utf8');
    assert.match(css,/\.distribution-plot\.distribution-editing, svg\.distribution-editing\s*\{[^}]*touch-action:\s*none/);
  }finally{f.restore();}
});

test('trash sends the chosen row index even for identical doubled stations and Undo restores it',async()=>{
  for(const index of [1,2]){
    const original=[[0,1],[1,1],[1,1],[2,1]],f=fixture(original);try{
      await f.tick();
      const row=f.$('distribution-table').tBodies[0].rows[index];
      await row.querySelectorAll('button')[1].onclick();
      const request=f.calls.filter(c=>c.action==='edit_distribution').at(-1);
      assert.equal(request.edit.delete_station,index);
      assert.deepEqual(request.edit.points,[[0,1],[1,1],[2,1]]);
      assert.deepEqual(f.rows(),request.edit.points);assert.equal(f.commits.length,1);
      await f.$('distribution-undo').onclick();await f.tick();
      assert.equal(f.state.source,'original');assert.deepEqual(f.rows(),original);
    }finally{f.restore();}
  }
});

test('every Daedalus wing plus button adds a distinct station and saves the result',async()=>{
  const original=[[0,3.75],[14,3.75],[14,3.75],[42,2.5],[42,2.5],[55.42,1.25],[55.42,1.25],[56,.625]];
  const added=[7,28,28,48.71,48.71,55.71,55.71,57];
  for(let index=0;index<original.length;index++){
    const f=fixture(original);try{
      await f.tick();
      await f.$('distribution-table').tBodies[0].rows[index].querySelectorAll('button')[0].onclick();
      const request=f.calls.filter(c=>c.action==='edit_distribution').at(-1),points=request.edit.points;
      assert.equal(points.length,original.length+1);
      const inserted=points.findIndex(row=>row[0]===added[index]);assert.ok(inserted>=0);
      assert.deepEqual(points.filter((_,i)=>i!==inserted),original);
      assert.deepEqual(JSON.parse(f.state.source),points);
      assert.equal(f.$('distribution-status').textContent,'ASW updated.');
      assert.equal(f.view.hasDraft(),false);
    }finally{f.restore();}
  }
});

test('failed row changes restore the saved grid and subsequent add/delete still save',async()=>{
  for(const phase of ['edit_distribution','inspect'])for(const button of [0,1]){
    const f=fixture();try{
      await f.tick();const original=f.rows();f.setReject(phase);
      await f.$('distribution-table').tBodies[0].rows[1].querySelectorAll('button')[button].onclick();
      assert.equal(f.state.source,'original');assert.deepEqual(f.rows(),original);
      assert.equal(f.view.hasDraft(),false);assert.equal(f.commits.length,0);
      assert.match(f.$('distribution-status').textContent,/Edit not applied/);
      f.setReject(false);
      await f.$('distribution-table').tBodies[0].rows[0].querySelectorAll('button')[0].onclick();
      assert.equal(f.rows().length,original.length+1);
      assert.deepEqual(JSON.parse(f.state.source),f.rows());
      await f.$('distribution-table').tBodies[0].rows[1].querySelectorAll('button')[1].onclick();
      assert.deepEqual(f.rows(),original);assert.deepEqual(JSON.parse(f.state.source),original);
      assert.equal(f.commits.length,2);assert.equal(f.view.hasDraft(),false);
    }finally{f.restore();}
  }
});

test('scale is consumed once, further drags apply automatically and Undo restores each edit',async()=>{
  const f=fixture();try{
    await f.tick();f.$('distribution-scale').value='2';f.$('distribution-scale').oninput();
    assert.equal(f.state.source,'original');
    await f.$('distribution-scale').onchange();
    assert.deepEqual(f.rows(),[[0,2],[3,4],[6,2]]);assert.equal(f.$('distribution-scale').value,'1');
    f.$('distribution-edit').onclick();f.drag(1,0,18);const expected=f.rows();await f.tick();
    const request=f.calls.filter(c=>c.action==='edit_distribution').at(-1);
    assert.deepEqual(request.edit.points,expected);assert.equal(request.edit.multiplier,1);assert.equal(request.edit.graft,undefined);
    assert.deepEqual(JSON.parse(f.state.source),expected);
    await f.$('distribution-undo').onclick();await f.tick();assert.deepEqual(f.rows(),[[0,2],[3,4],[6,2]]);
    await f.$('distribution-undo').onclick();await f.tick();
    assert.equal(f.state.source,'original');assert.deepEqual(f.rows(),[[0,1],[3,2],[6,1]]);
    assert.equal(f.$('distribution-undo').disabled,true);
  }finally{f.restore();}
});

test('cancelled touch, Escape, lost capture and taps do not save or leave a draft',async()=>{
  const f=fixture();try{
    await f.tick();f.$('distribution-edit').onclick();
    const svg=f.$('distribution-plot').querySelector('svg'),before=f.rows(),curve=()=>svg.querySelector('.distribution-curve').getAttribute('d'),old=curve();
    svg.onpointerdown(f.event(1));svg.onpointermove(f.event(1,20,20,{pointerId:8}));assert.deepEqual(f.rows(),before);
    svg.onpointermove(f.event(1,20,20));assert.ok(f.rows()[1][0]>3);svg.onpointercancel({pointerId:7});
    assert.deepEqual(f.rows(),before);assert.equal(curve(),old);assert.equal(f.view.hasDraft(),false);
    assert.equal(svg.hasPointerCapture(7),false);
    svg.onpointerdown(f.event(1));svg.onpointermove(f.event(1,-20,20));svg.onkeydown({key:'Escape',preventDefault(){}});
    assert.deepEqual(f.rows(),before);assert.equal(svg.classList.contains('distribution-dragging'),false);
    svg.onpointerdown(f.event(1));svg.onpointermove(f.event(1,20,20));svg.onlostpointercapture({pointerId:7});
    assert.deepEqual(f.rows(),before);assert.equal(f.view.hasDraft(),false);
    f.drag(1,0,0);await f.tick();assert.equal(f.commits.length,0);assert.equal(f.view.hasDraft(),false);
  }finally{f.restore();}
});

test('dragging preserves mirrored centers, station order and doubled-station jump positions',async()=>{
  const f=fixture([[0,1],[2,1],[2,2],[6,2]]);try{
    await f.tick();f.$('distribution-edit').onclick();f.drag(0,80,-10);await f.tick();assert.equal(f.rows()[0][0],0);
    f.drag(1,80,-10);await f.tick();
    assert.equal(f.rows()[1][0],2);assert.equal(f.rows()[2][0],2);assert.ok(f.rows()[1][1]>1);
    f.drag(3,-1000,0);await f.tick();assert.ok(f.rows()[3][0]>2);assert.ok(f.rows()[3][0]<6);
  }finally{f.restore();}
});

test('keyboard edits apply on release, retain focus, and busy or dirty models block gestures',async()=>{
  const f=fixture();try{
    await f.tick();f.$('distribution-edit').onclick();let svg=f.$('distribution-plot').querySelector('svg');
    f.handle(1).focus();assert.equal(f.handle(1).getAttribute('tabindex'),'0');
    svg.onkeydown({target:f.handle(1),key:'ArrowDown',shiftKey:true,preventDefault(){}});
    assert.ok(f.rows()[1][1]<2);assert.equal(f.commits.length,0);
    svg.onkeyup({key:'ArrowDown'});await f.tick();assert.equal(f.commits.length,1);
    assert.equal(document.activeElement,f.handle(1));
    const before=f.rows();f.state.busy=true;f.view.refresh();
    assert.equal(f.$('distribution-plot').classList.contains('distribution-editing'),false);
    f.drag(1,20,20);assert.deepEqual(f.rows(),before);assert.equal(f.handle(1).getAttribute('tabindex'),'-1');
    f.state.busy=false;f.state.dirty=true;f.view.refresh();assert.equal(f.$('distribution-edit').disabled,true);
  }finally{f.restore();}
});

test('table edits move the curve immediately; rejected edits preserve source and can be corrected',async()=>{
  const f=fixture();try{
    await f.tick();let input=f.$('distribution-table').tBodies[0].rows[1].querySelectorAll('input')[1];
    const old=f.$('distribution-plot').querySelector('.distribution-curve').getAttribute('d');
    input.value='1.5';input.oninput();
    assert.ok(f.$('distribution-plot').querySelector('.distribution-curve').getAttribute('d')!==old);
    assert.match(f.handle(1).getAttribute('aria-label'),/value 1.5/);
    f.setReject(true);await input.onchange();
    assert.equal(f.state.source,'original');assert.equal(f.$('distribution-undo').disabled,true);
    assert.match(f.$('distribution-status').textContent,/Edit not applied: Invalid property geometry/);
    f.setReject(false);input.value='1.4';input.oninput();await input.onchange();
    assert.equal(f.rows()[1][1],1.4);assert.equal(f.commits.length,1);assert.equal(f.view.hasDraft(),false);
    input=f.$('distribution-table').tBodies[0].rows[1].querySelectorAll('input')[1];
    input.value='';input.oninput();await input.onchange();
    assert.equal(f.commits.length,1);assert.match(f.$('distribution-status').textContent,/finite numbers/);
  }finally{f.restore();}
});

test('pending checks cannot overwrite new settings or a raw ASW draft',async()=>{
  for(const phase of ['edit_distribution','inspect']){
    const f=fixture();try{
      await f.tick();f.$('distribution-edit').onclick();const release=f.defer(phase);
      f.drag(1,0,15);await f.tick();
      assert.equal(f.$('distribution-edit').disabled,true);
      if(phase==='inspect')f.state.dirty=true;else f.state.revision++;
      release();await f.tick();
      assert.equal(f.state.source,'original');assert.equal(f.commits.length,0);
      assert.equal(f.view.hasDraft(),true);
    }finally{f.restore();}
  }
});
