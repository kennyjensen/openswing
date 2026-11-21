import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {frequencySettings,frequencyTransport,frequencyPane,createFrequencyResults} from '../web/frequency-results.js';

const fixture=JSON.parse(await readFile(new URL('./data/daedalus-frame-response.json',import.meta.url),'utf8'));
const yawGeometryFixture=JSON.parse(await readFile(new URL('./data/daedalus-yaw-geometry.json',import.meta.url),'utf8'));

// A small event/selection DOM, not a layout engine. Browser rendering has a
// separate Playwright regression; this check never starts a numerical worker.
class Element {
  constructor(tag='div'){this.tagName=tag;this.children=[];this.listeners={};this.dataset={};this.style={};this._value=null;this.textContent='';}
  get options(){return this.children.filter(c=>c.tagName==='option');}
  get value(){return this._value??(this.tagName==='select'?(this.options.find(o=>o.selected)??this.options[0])?.value??'':'');}
  set value(v){this._value=String(v);}
  set selectedIndex(i){this._value=this.options[i]?.value??'';}
  append(...nodes){for(const node of nodes){node.parent=this;this.children.push(node);}}
  replaceChildren(...nodes){this.children=[];this._value=null;this.textContent='';this.append(...nodes);}
  setAttribute(k,v){this[k]=v;}
  closest(tag){return this.tagName===tag?this:this.parent?.closest(tag);}
  querySelectorAll(selector){
    const matches=node=>selector.split(',').some(s=>s.trim()===node.tagName||s.trim()==='input:not([type=file])'&&node.tagName==='input'&&node.type!=='file');
    return this.children.flatMap(node=>[...(matches(node)?[node]:[]),...node.querySelectorAll(selector)]);
  }
  addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);}
  dispatchEvent(event){for(const fn of this.listeners[event.type]??[])fn(event);this['on'+event.type]?.(event);if(event.bubbles)this.parent?.bubble(event);}
  bubble(event){for(const fn of this.listeners[event.type]??[])fn(event);this.parent?.bubble(event);}
  focus(){}
  scrollIntoView(){}
  checkValidity(){return Number.isFinite(Number(this.value))&&(this.min==null||Number(this.value)>=Number(this.min));}
}
function documentFor(markup){
  const root=new Element(),stack=[root],ids=new Map();
  for(const token of markup.match(/<[^>]*>|[^<]+/g)??[]){
    if(token.startsWith('</')){stack.pop();continue;}
    if(!token.startsWith('<')){stack.at(-1).textContent+=token;continue;}
    const tag=/^<(\w+)/.exec(token)?.[1];if(!tag)continue;
    const node=new Element(tag);
    for(const [,key,value] of token.matchAll(/([\w-]+)="([^"]*)"/g))node[key]=value;
    node.hidden=/\shidden\b/.test(token);node.selected=/\sselected\b/.test(token);
    if(node.id)ids.set(node.id,node);
    stack.at(-1).append(node);if(!['input','br','hr'].includes(tag))stack.push(node);
  }
  return {getElementById:id=>ids.get(id)??null,createElement:tag=>new Element(tag)};
}

test('all output groups retain saved fixed/free results; only numerical settings invalidate',()=>{
  const previous=globalThis.document;
  globalThis.document=documentFor(frequencySettings+frequencyTransport+frequencyPane);
  try {
    const get=id=>document.getElementById('frequency-'+id);
    const choose=(id,value)=>{get(id).value=value;for(const type of ['input','change'])get(id).dispatchEvent({type,bubbles:true});};
    let edits=0,extensions=0;const downloads=[];let view;
    view=createFrequencyResults(()=>{},()=>{edits++;view.setResult(null);},(name,text)=>downloads.push({name,text}),()=>fixture.model_metadata,()=>extensions++);
    const before=JSON.stringify(fixture.results);
    for(const frame of ['fixed','free']){
      view.setResult(fixture.results[frame]);const summary=get('summary').textContent;
      for(const group of ['global','nodes','sections','strips','frame','operating','sensors','feedback']){
        choose('group',group);
        assert.equal(edits,0);assert.equal(extensions,0);assert.equal(get('summary').textContent,summary);
      }
      choose('group','frame');
      if(frame==='fixed'){
        assert.equal(get('quantity').disabled,true);
        assert.match(get('quantity').options[0].textContent,/motion held fixed/);
        assert.equal(get('frame-notice').hidden,false);
        assert.match(get('frame-explanation').textContent,/no Flight frame outputs/);
      }else{
        assert.equal(get('quantity').disabled,false);
        assert.equal(get('quantity').options.length,12);
        const yaw=get('quantity').options.find(o=>o.textContent.startsWith('Yaw angular velocity Ω_z'));
        choose('quantity',yaw.value);get('csv').onclick();
        assert.match(downloads.at(-1).text,/rates_body/);
        assert.equal(get('frame-notice').hidden,true);
      }
    }
    assert.equal(JSON.stringify(fixture.results),before);
    assert.equal(edits,0);assert.equal(extensions,0);
    choose('count','41');assert.equal(edits,1);
    assert.equal(get('summary').textContent,'Select frequency response, then run an analysis.');
  }finally{globalThis.document=previous;}
});

test('plot, geometry and playback retain the same selected frequency and input',()=>{
  const previous=globalThis.document,oldRAF=globalThis.requestAnimationFrame,oldCancel=globalThis.cancelAnimationFrame,oldPerformance=Object.getOwnPropertyDescriptor(globalThis,'performance');
  globalThis.document=documentFor(frequencySettings+frequencyTransport+frequencyPane);
  Object.defineProperty(globalThis,'performance',{configurable:true,value:{now:()=>1000}});
  const frames=new Map();let nextFrame=0;
  globalThis.requestAnimationFrame=callback=>{frames.set(++nextFrame,callback);return nextFrame;};
  globalThis.cancelAnimationFrame=id=>frames.delete(id);
  let view;
  try{
    const get=id=>document.getElementById('frequency-'+id);
    const choose=(id,value)=>{get(id).value=value;for(const type of ['input','change'])get(id).dispatchEvent({type,bubbles:true});};
    const data=structuredClone(fixture.results.free),model={...fixture.model_metadata,units:{T:[1,'s']}};
    data.base.geometry=[{index:1,axis:[[[0,0,0],[1,0,0]]],quads:[]}];data.base.attachments=[];
    data.inputs=[{...data.inputs[0],name:'control.3'},{...data.inputs[0],name:'control.2'}];
    data.samples=data.samples.map((s,j)=>({...s,omega:2*Math.PI*[.2,1,2][j],frequency:[.2,1,2][j],responses:[0,1].map(i=>{
      const r=structuredClone(s.responses[0]),marker=10*j+i+1;
      r.output.geometry=[{index:1,axis:{real:[[[0,0,0],[marker,0,0]]],imag:[[[0,0,0],[0,0,0]]]},quads:{real:[],imag:[]}}];
      r.output.attachments=[];
      r.output.frame.rates_body={real:[0,0,marker],imag:[0,0,0]};
      return r;
    }),gust_profiles:[{},{}],diagnostics:{...s.diagnostics,backward_errors:[0,0]}}));
    const before=JSON.stringify(data);let edits=0;const downloads=[];
    view=createFrequencyResults(()=>{},()=>edits++,(name,text)=>downloads.push(text),()=>model);
    view.setResult(data);choose('group','frame');
    const yaw=get('quantity').options.find(o=>o.textContent.startsWith('Yaw angular velocity Ω_z'));
    choose('quantity',yaw.value);choose('sample',1);choose('input',1);
    get('phase').value=0;get('amplitude').value=1;
    assert.equal(view.geometry().beams[0].axis[0][1][0],13);
    assert.equal(view.spanState().output,data.samples[1].responses[1].output);
    assert.equal(view.spanState().phase,0);assert.equal(view.spanState().scale,1);
    assert.match(get('detail').textContent,/Magnitude 687\.549 \[deg\/T/);
    assert.match(get('sample').options[1].textContent,/^1 Hz · 6\.28319 rad\/s/);
    choose('amplitude',2);choose('angle-units','radians');
    assert.match(get('detail').textContent,/Magnitude 12\.0000 \[rad\/T/);
    assert.equal(view.spanState().scale,2);
    choose('amplitude',1);choose('angle-units','degrees');
    get('csv').onclick();assert.match(downloads.at(-1),/control\.2/);
    choose('units','radians');assert.match(get('sample').options[1].textContent,/^6\.28319 rad\/s · 1 Hz/);
    choose('playback','inspection');get('play').onclick();assert.equal(frames.size,1);
    const callback=[...frames.values()][0];frames.clear();callback(2000);
    assert.equal(Number(get('phase').value),90);
    assert.equal(view.spanState().phase,Math.PI/2);
    view.pause();assert.equal(frames.size,0);
    choose('playback','model');get('phase').value=0;get('play').onclick();
    const modelCallback=[...frames.values()][0];frames.clear();modelCallback(1125);
    assert.equal(Number(get('phase').value),45);
    view.pause();choose('sample',2);choose('input',0);get('phase').value=0;
    assert.equal(view.geometry().beams[0].axis[0][1][0],22);
    assert.match(get('detail').textContent,/Magnitude 1203\.21 \[deg\/T/);
    assert.equal(edits,0);assert.equal(JSON.stringify(data),before);
  }finally{
    view?.pause();globalThis.document=previous;globalThis.requestAnimationFrame=oldRAF;globalThis.cancelAnimationFrame=oldCancel;
    if(oldPerformance)Object.defineProperty(globalThis,'performance',oldPerformance);else delete globalThis.performance;
  }
});

test('Daedalus plotted omega_z equals the independently differentiated Earth-view cabin chord',()=>{
  const previous=globalThis.document;
  globalThis.document=documentFor(frequencySettings+frequencyTransport+frequencyPane);
  try{
    const get=id=>document.getElementById('frequency-'+id);
    const choose=(id,value)=>{get(id).value=value;for(const type of ['input','change'])get(id).dispatchEvent({type,bubbles:true});};
    const data=yawGeometryFixture.result,before=JSON.stringify(data),R=data.base.modal_base.body_to_earth;
    const downloads=[];let edits=0;
    const view=createFrequencyResults(()=>{},()=>edits++,(name,text)=>downloads.push(text),()=>({units:{T:[1,'s']}}));
    view.setResult(data);choose('group','frame');choose('view','earth');
    const yaw=get('quantity').options.find(o=>o.textContent.startsWith('Yaw angular velocity Ω_z'));
    choose('quantity',yaw.value);
    const magnitude=index=>Number([...get('gain-plot').innerHTML.matchAll(/<title>f=[^,]+, ([^<]+)<\/title>/g)][index][1]);
    const chord=phase=>{
      get('phase').value=phase*180/Math.PI;
      const q=view.geometry().beams[0].quads[0];
      return q[3].map((v,i)=>v-q[0][i]);
    };
    // The first fairing chord is fixed to the aircraft frame and points along
    // body +x. Its y velocity in the base body axes is length * omega_z.
    // Differentiate rendered points, without reading frame rate or attitude
    // perturbations; translation cancels in the chord endpoint difference.
    const root=data.base.geometry[0].quads[0],length=root[3][0]-root[0][0];
    assert.equal(root[3][1]-root[0][1],0);assert.equal(root[3][2]-root[0][2],0);
    const rate=(omega,phase)=>{
      const dt=1e-4,plus=chord(phase+omega*dt),minus=chord(phase-omega*dt);
      return R.reduce((sum,row,k)=>sum+row[1]*(plus[k]-minus[k])/(2*dt),0)/length;
    };
    for(const [j,sample] of data.samples.entries()){
      choose('sample',j);choose('amplitude',1);choose('angle-units','degrees');
      const re=rate(sample.omega,0),im=-rate(sample.omega,Math.PI/2);
      const geometryMagnitude=Math.hypot(re,im)*180/Math.PI,shown=magnitude(j);
      const stored=sample.responses[0].output.frame.rates_body;
      assert.ok(Math.abs(re-stored.real[2])<2e-10);
      assert.ok(Math.abs(im-stored.imag[2])<2e-10);
      // The SVG title deliberately rounds to six significant digits.
      assert.ok(Math.abs(shown/geometryMagnitude-1)<2e-6);
      assert.match(get('detail').textContent,new RegExp(`Magnitude ${shown.toPrecision(6)} \\[deg/T`));
      get('csv').onclick();assert.match(downloads.at(-1),/"rates_body","2"/);
      const row=downloads.at(-1).trim().split('\n')[j+1].split(',').map(v=>v.slice(1,-1));
      assert.ok(Math.abs(Number(row[12])*180/Math.PI/geometryMagnitude-1)<2e-6);
      choose('amplitude',3);
      assert.equal(magnitude(j),shown);
      assert.ok(Math.abs(Math.hypot(rate(sample.omega,0),rate(sample.omega,Math.PI/2))*180/Math.PI/geometryMagnitude-3)<1e-8);
      choose('angle-units','radians');
      assert.ok(Math.abs(magnitude(j)/(geometryMagnitude*Math.PI/180)-1)<2e-6);
      assert.match(get('detail').textContent,/\[rad\/T/);
      choose('angle-units','degrees');choose('gain','db');
      assert.ok(Math.abs(magnitude(j)-20*Math.log10(geometryMagnitude))<1e-4);
      choose('gain','absolute');
    }
    assert.equal(edits,0);assert.equal(JSON.stringify(data),before);
    const changed=structuredClone(data);
    changed.samples[0].responses[0].output.frame.rates_body.real[2]*=2;
    view.setResult(changed);choose('group','frame');choose('quantity',yaw.value);
    assert.equal(view.spanState().output,changed.samples[0].responses[0].output);
  }finally{globalThis.document=previous;}
});
