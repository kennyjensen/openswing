import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createResponsiveWorkbench} from '../web/responsive-workbench.js';

const main=readFileSync(new URL('../web/main.js',import.meta.url),'utf8');

// Lightweight DOM for the layout controller. It moves the same node objects,
// models anchor restoration/focus, and omits deleted main-template elements.
// It does not render CSS or initialize an aircraft/numerical worker.
function fixture(mobile){
  let document;
  class Element {
    constructor(tag='div',attributes={}){this.tagName=tag.toUpperCase();this.attributes={...attributes};this.children=[];this.parentNode=null;this.hidden=false;this.textContent='';this.listeners={};this.style={setProperty(){}};}
    get id(){return this.attributes.id??'';} set id(v){this.attributes.id=v;}
    get className(){return this.attributes.class??'';} set className(v){this.attributes.class=v;}
    get dataset(){return Object.fromEntries(Object.entries(this.attributes).filter(([k])=>k.startsWith('data-')).map(([k,v])=>[k.slice(5),v]));}
    get firstElementChild(){return this.children.find(n=>n.tagName!=='#COMMENT')??null;}
    setAttribute(k,v){this.attributes[k]=String(v);} getAttribute(k){return this.attributes[k]??null;}
    remove(){if(this.parentNode){const a=this.parentNode.children;a.splice(a.indexOf(this),1);this.parentNode=null;}}
    append(node){node.remove();node.parentNode=this;this.children.push(node);}
    prepend(node){node.remove();node.parentNode=this;this.children.unshift(node);}
    before(node){const parent=this.parentNode;node.remove();node.parentNode=parent;parent.children.splice(parent.children.indexOf(this),0,node);}
    replaceWith(node){this.before(node);this.remove();}
    contains(node){return this===node||this.children.some(n=>n.contains(node));}
    matches(selector){
      if(selector.startsWith('#'))return this.id===selector.slice(1);
      if(selector.startsWith('.'))return this.className.split(' ').includes(selector.slice(1));
      const attribute=selector.match(/^\[([^=\]]+)(?:="([^"]*)")?\]$/);
      if(attribute)return attribute[2]===undefined?Object.hasOwn(this.attributes,attribute[1]):this.getAttribute(attribute[1])===attribute[2];
      return this.tagName.toLowerCase()===selector;
    }
    closest(selector){return this.matches(selector)?this:this.parentNode?.closest(selector)??null;}
    querySelectorAll(selector){return this.children.flatMap(node=>[...(node.matches(selector)?[node]:[]),...node.querySelectorAll(selector)]);}
    querySelector(selector){return this.querySelectorAll(selector)[0]??null;}
    addEventListener(type,listener){(this.listeners[type]??=[]).push(listener);}
    focus(){document.activeElement=this;}
    getBoundingClientRect(){return {height:50};}
  }
  const body=new Element('body'),html=new Element('html');html.append(body);
  document={documentElement:html,activeElement:body,createElement:tag=>new Element(tag),createComment:()=>new Element('#comment'),getElementById:id=>html.querySelector('#'+id)};
  const $=id=>document.getElementById(id);
  function add(parent,id,className='',tag='div',attrs={}){const el=new Element(tag,{id,class:className,...attrs});parent.append(el);return el;}
  const desktop=add(body,'desktop-workbench'),compact=add(body,'mobile-workbench');compact.hidden=true;
  const nav=add(body,'workspace-tabs');nav.hidden=true;
  for(const name of ['editor','settings','plots','output']){
    add(compact,'workspace-'+name,'workspace-panel','section');
    add(nav,'workspace-tab-'+name,'','button',{'data-workspace':name,'aria-controls':'workspace-'+name});
  }
  add(compact,'mobile-action-bar');
  for(const id of ['analysis-settings','analysis-actions']){assert.ok(main.includes(`id="${id}"`));add(desktop,id);}
  for(const [,id,open,label] of main.matchAll(/<details id="([^"]+)" class="settings-panel"( open)?>\s*<summary>([^<]+)<\/summary>/g)){
    const panel=add($('analysis-settings'),id,'settings-panel','details');panel.open=!!open;
    const summary=add(panel,'','','summary');summary.textContent=label;
  }
  add($('solution-type-panel'),'mode','','select').value='mounted';
  for(const cls of ['viewport-header','viewport-container','results-panel']){assert.ok(main.includes(`class="${cls}"`));add(desktop,'',cls);}
  add(desktop,'flow-failure');
  for(const id of ['time-transport','mode-transport','frequency-transport','solution-provenance'])add(desktop,id);
  // These elements existed before the UI cleanup. Their absence must remain
  // visible to the controller, rather than being papered over by a fixture.
  if(main.includes('class="scope-note"'))add(desktop,'','scope-note');
  for(const id of ['fw-root-locus-link','daedalus-bode-link'])if(main.includes(`id="${id}"`))add(desktop,id);
  const tabbar=add(desktop,'','tabbar');
  const names=[];
  for(const [,name,label] of main.matchAll(/data-tab="([^"]+)">([^<]+)<\/button>/g)){
    const tab=add(tabbar,'tab-'+name,'','button',{'data-tab':name,'aria-selected':String(name==='loading')});tab.textContent=label;
    add(desktop,'pane-'+name,'tab-pane');names.push(name);
  }
  assert.equal(names.length,6);
  // The editor disclosures travel together, retaining their open state and
  // the live editing controls when the viewport changes.
  for(const [,id,open,label] of main.matchAll(/<details id="([^"]+)" class="editor-panel"( open)?>\s*<summary>([^<]+)<\/summary>/g)){
    const panel=add($('pane-editor'),id,'editor-panel','details');panel.open=!!open;
    const summary=add(panel,'','','summary');summary.textContent=label;
  }
  add($('file-panel'),'model-configuration');
  add($('asw-panel'),'editor','','textarea').value='unsaved ASW edit';
  add($('properties-panel'),'pane-distributions','distribution-pane');
  add($('nodes-panel'),'pane-nodes','distribution-pane');
  const media={matches:mobile,addEventListener(type,callback){this.change=callback;}};
  const previous=Object.fromEntries(['document','matchMedia','ResizeObserver','window'].map(key=>[key,globalThis[key]]));
  Object.assign(globalThis,{document,matchMedia:()=>media,ResizeObserver:class{observe(){}},window:{scrollY:0,scrollTo(){}}});
  return {$,document,desktop,compact,nav,names,resize(value){media.matches=value;media.change();},
    restore(){for(const [key,value] of Object.entries(previous))if(value===undefined)delete globalThis[key];else globalThis[key]=value;}};
}

test('mobile startup works after removing the scope note and validation links',()=>{
  const f=fixture(true);
  try{
    const view=createResponsiveWorkbench();
    assert.equal(view.current(),'plots');assert.equal(f.desktop.hidden,true);assert.equal(f.nav.hidden,false);
    assert.equal(f.document.getElementById('fw-root-locus-link'),null);
    assert.equal(f.$('pane-editor').parentNode,f.$('workspace-editor'));
    assert.equal(f.$('model-configuration').closest('.editor-panel').id,'file-panel');
    assert.deepEqual(f.$('pane-editor').children.map(panel=>panel.firstElementChild.textContent),['File','ASW Editor','Mass Properties','Beam Properties','Beam Nodes']);
    assert.equal(f.$('pane-editor').getAttribute('aria-labelledby'),'workspace-tab-editor');
    assert.equal(f.$('analysis-settings').parentNode,f.$('workspace-settings'));
    assert.equal(f.$('analysis-actions').parentNode,f.$('mobile-action-bar'));
    const aircraft=f.$('workspace-plots').firstElementChild;
    assert.equal(aircraft.matches('.workspace-geometry'),true);
    assert.equal(aircraft.tagName,'DETAILS');assert.equal(aircraft.open,true);
    assert.equal(aircraft.firstElementChild.tagName,'SUMMARY');
    assert.equal(aircraft.firstElementChild.textContent,'Aircraft');
    assert.equal(f.$('time-transport').parentNode,aircraft);
    assert.equal(f.$('workspace-output').firstElementChild.firstElementChild.textContent,'Total Forces');
    assert.equal(f.compact.querySelectorAll('.workspace-card').length,7);
    assert.equal(f.$('heading-loading').textContent,'2D Plot');
    assert.equal(f.$('workspace-section-structure'),null);
    for(const name of f.names){const pane=f.$('pane-'+name);assert.equal(pane.parentNode,name==='editor'?f.$('workspace-editor'):pane.closest('.workspace-card'));assert.equal(pane.hidden,false);}
  }finally{f.restore();}
});

test('desktop/mobile resizing retains each pane once and restores desktop anchors',()=>{
  const f=fixture(false);
  try{
    const view=createResponsiveWorkbench();
    assert.equal(view.current(),null);
    const originals=new Map(f.names.map(name=>[name,f.$('pane-'+name)]));
    const editor=f.$('editor');
    f.$('asw-panel').open=false;f.$('nodes-panel').open=true;
    for(let cycle=0;cycle<3;cycle++){
      f.resize(true);assert.equal(view.current(),'plots');
      for(const name of ['aircraft','loading','results','report']){
        const card=f.$('workspace-section-'+name);
        assert.equal(card.open,cycle===0);card.open=false;
      }
      f.resize(false);assert.equal(view.current(),null);assert.equal(f.desktop.hidden,false);
      assert.equal(f.$('analysis-actions').parentNode,f.desktop);
      assert.equal(f.compact.querySelectorAll('.workspace-card').length,0);
      assert.equal(f.$('asw-panel').open,false);assert.equal(f.$('nodes-panel').open,true);
      assert.equal(f.$('editor'),editor);assert.equal(editor.value,'unsaved ASW edit');
      assert.equal(f.$('model-configuration').parentNode,f.$('file-panel'));
      for(const [name,pane] of originals){assert.equal(f.$('pane-'+name),pane);assert.equal(pane.parentNode,f.desktop);assert.equal(pane.hidden,name!=='loading');}
    }
  }finally{f.restore();}
});

test('mobile main tabs and detail tabs still select the right workspace',()=>{
  const f=fixture(true);let pauses=0;
  try{
    const view=createResponsiveWorkbench({onLeavePlots:()=>pauses++});
    f.$('workspace-tab-settings').onclick();assert.equal(view.current(),'settings');assert.equal(pauses,1);
    f.$('workspace-section-frequency').open=false;
    f.$('tab-frequency').onclick();assert.equal(view.current(),'plots');
    assert.equal(f.$('workspace-section-frequency').open,true);
    f.$('workspace-tab-editor').onclick();assert.equal(view.current(),'editor');
    f.$('tab-report').onclick();assert.equal(view.current(),'output');
    assert.equal(f.$('workspace-output').hidden,false);assert.equal(f.$('workspace-plots').hidden,true);
    f.$('workspace-section-report').open=false;
    f.$('workspace-tab-plots').onclick();f.$('workspace-tab-output').onclick();
    assert.equal(f.$('workspace-section-report').open,false);
    f.$('heading-report').focus();f.resize(false);
    assert.equal(f.document.activeElement,f.$('tab-report'));
    assert.equal(f.$('pane-report').hidden,false);
  }finally{f.restore();}
});

test('Settings disclosures keep their state and inputs when resizing; collapsed Solution Type receives visible focus',()=>{
  const f=fixture(true);
  try{
    createResponsiveWorkbench();
    const panels=f.$('analysis-settings').children;
    assert.deepEqual(panels.map(p=>p.firstElementChild.textContent),['Solution Type','Flight Conditions','Advanced']);
    assert.deepEqual(panels.map(p=>p.open),[true,true,false]);
    f.$('solution-type-panel').open=false;f.$('advanced-panel').open=true;
    f.$('mode').value='frequency';
    f.$('workspace-tab-settings').onclick();f.$('workspace-tab-settings').focus();
    f.resize(false);
    assert.equal(f.document.activeElement,f.$('solution-type-panel').firstElementChild);
    f.resize(true);
    assert.equal(f.$('analysis-settings').children,panels);
    assert.deepEqual(panels.map(p=>p.open),[false,true,true]);
    assert.equal(f.$('mode').value,'frequency');
    f.$('solution-type-panel').open=true;
    f.$('workspace-tab-settings').focus();f.resize(false);
    assert.equal(f.document.activeElement,f.$('mode'));
  }finally{f.restore();}
});

test('plots without data cannot open and regain their previous disclosure state when data returns',()=>{
  const f=fixture(true);
  try{
    const view=createResponsiveWorkbench(),empty={loading:false,modes:false,time:false,frequency:false};
    view.setAvailable(empty);
    for(const name of Object.keys(empty)){
      const card=f.$('workspace-section-'+name),summary=card.firstElementChild;
      assert.equal(f.$('tab-'+name).disabled,true);assert.equal(card.open,false);
      assert.equal(summary.getAttribute('aria-disabled'),'true');assert.equal(summary.tabIndex,-1);
      let prevented=false;summary.onclick({preventDefault(){prevented=true;}});assert.equal(prevented,true);
    }
    view.setAvailable({loading:true,frequency:true});
    assert.equal(f.$('tab-frequency').disabled,false);assert.equal(f.$('workspace-section-frequency').open,true);
    f.$('workspace-section-frequency').open=false;view.setAvailable({frequency:false});
    f.resize(false);f.resize(true);view.setAvailable({frequency:true});
    assert.equal(f.$('workspace-section-frequency').open,false);
    f.$('tab-frequency').onclick();assert.equal(f.$('workspace-section-frequency').open,true);
    view.setAvailable({frequency:false});assert.equal(f.$('tab-loading').getAttribute('aria-selected'),'true');
  }finally{f.restore();}
});
