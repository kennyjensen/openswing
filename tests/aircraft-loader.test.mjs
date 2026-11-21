import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createAircraftLoader} from '../web/aircraft-loader.js';

const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
const aircraft=(name,example=name)=>({source:`Name\n${name}\nEnd\n`,filename:`${name}.asw`,example});
const fixture=()=>{
  const inspections=[],errors=[];
  return {inspections,errors,load:createAircraftLoader({inspect:async(...args)=>inspections.push(args),showError:error=>errors.push(error.message)})};
};

test('a slow older example cannot replace the most recent aircraft selection',async()=>{
  const f=fixture(),first=deferred(),second=deferred();
  const old=f.load(()=>first.promise),current=f.load(()=>second.promise);
  second.resolve(aircraft('fw'));await current;
  first.resolve(aircraft('dae'));await old;
  assert.deepEqual(f.inspections,[[aircraft('fw').source,'fw.asw','fw',null,false,true]]);
  assert.deepEqual(f.errors,[]);
});

test('file reads and dropped models share selection order with example downloads',async()=>{
  const f=fixture(),example=deferred(),file=deferred(),drop=deferred();
  const jobs=[f.load(()=>example.promise),f.load(()=>file.promise),f.load(()=>drop.promise)];
  file.resolve(aircraft('picked',undefined));await jobs[1];
  example.resolve(aircraft('dae'));await jobs[0];
  assert.deepEqual(f.inspections,[]);
  drop.resolve({source:'dropped ASW',filename:'my aircraft.asw'});await jobs[2];
  assert.deepEqual(f.inspections,[['dropped ASW','my aircraft.asw','',null,false,true]]);
  assert.deepEqual(f.errors,[]);
});

test('failure of a superseded read does not replace the latest load status',async()=>{
  const f=fixture(),first=deferred();
  const old=f.load(()=>first.promise);
  await f.load(()=>aircraft('usa'));
  first.reject(new Error('Old download failed'));await old;
  assert.equal(f.inspections.length,1);
  assert.equal(f.inspections[0][1],'usa.asw');
  assert.deepEqual(f.errors,[]);
});

test('latest read failure is reported and never falls back to an obsolete pending selection',async()=>{
  const f=fixture(),first=deferred();
  const old=f.load(()=>first.promise);
  await f.load(()=>{throw new Error('Selected file unreadable');});
  first.resolve(aircraft('dae'));await old;
  assert.deepEqual(f.inspections,[]);
  assert.deepEqual(f.errors,['Selected file unreadable']);
  await f.load(()=>aircraft('fw'));
  assert.equal(f.inspections[0][1],'fw.asw');
});

test('inspection rejection is handled and later aircraft loads can recover',async()=>{
  const errors=[],inspections=[];
  const load=createAircraftLoader({inspect:async(source,filename)=>{
    inspections.push(filename);if(filename==='bad.asw')throw new Error('Invalid ASW');
  },showError:error=>errors.push(error.message)});
  await load(()=>aircraft('bad'));await load(()=>aircraft('dae'));
  assert.deepEqual(inspections,['bad.asw','dae.asw']);
  assert.deepEqual(errors,['Invalid ASW']);
});

test('actual example, file-picker and drop handlers use the same latest selection',async()=>{
  const main=readFileSync(new URL('../web/main.js',import.meta.url),'utf8');
  const start=main.indexOf("$('open').onclick="),end=main.indexOf("$('solve').onclick=",start);
  assert.ok(start>=0&&end>start);
  const dropHandler=main.match(/^document\.addEventListener\('drop',.*$/m)?.[0];
  assert.ok(dropHandler);
  const elements=new Map(),$=id=>{if(!elements.has(id))elements.set(id,{value:'',click(){}});return elements.get(id);};
  const events={},inspections=[],errors=[],urls=[],download=deferred(),picked=deferred();
  new Function('$','document','createAircraftLoader','inspect','showError','fetch',main.slice(start,end)+'\n'+dropHandler)
    ($,{addEventListener:(name,callback)=>{events[name]=callback;}},createAircraftLoader,
      async(...args)=>inspections.push(args),error=>errors.push(error.message),url=>{urls.push(url);return download.promise;});
  $('example').value='dae';const example=$('example').onchange();
  const target={value:'picked.asw',files:[{name:'picked.asw',text:()=>picked.promise}]};
  const file=$('file').onchange({target});
  assert.equal(target.value,'','The picker clears immediately, before asynchronous reads.');
  let prevented=false;
  await events.drop({preventDefault(){prevented=true;},dataTransfer:{files:[{name:'dropped.asw',text:async()=>'dropped source'}]}});
  assert.equal(prevented,true);
  download.resolve({ok:true,text:async()=>'Daedalus source'});await example;
  picked.reject(new Error('Superseded file read failed'));await file;
  assert.deepEqual(urls,['/examples/dae.asw']);
  assert.deepEqual(inspections,[['dropped source','dropped.asw','',null,false,true]]);
  assert.deepEqual(errors,[]);
  await $('file').onchange({target:{value:'bad.asw',files:[{name:'bad.asw',text:async()=>{throw new Error('File unreadable');}}]}});
  assert.deepEqual(errors,['File unreadable']);
});
