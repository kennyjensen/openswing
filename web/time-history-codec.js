// Lossless JSON numbers (including -0), with explicit size/depth limits.
// No toJSON hooks, accessors, non-finite values or silent coercion are allowed.
import {unpackTimeResult} from './time-result-storage.js';

export const archiveRecordLimit=16*1024*1024;
const plain=x=>x!==null&&typeof x==='object'&&Object.getPrototypeOf(x)===Object.prototype;
const encoder=new TextEncoder();

export function encodeHistoryJSON(value,limit=archiveRecordLimit){
  const pieces=[],active=new WeakSet();let characters=0,visited=0;
  function add(text){
    characters+=text.length;
    if(characters>limit)throw new RangeError('History record exceeds its size limit.');
    pieces.push(text);
  }
  function walk(x,depth){
    if(depth>80||++visited>2000000)throw new RangeError('History record exceeds its structural limit.');
    if(x===null){add('null');return;}
    if(typeof x==='number'&&Number.isFinite(x)){add(Object.is(x,-0)?'-0':String(x));return;}
    if(typeof x==='string'||typeof x==='boolean'){
      if(typeof x==='string'&&x.length>limit)throw new RangeError('History string exceeds its size limit.');
      add(JSON.stringify(x));return;
    }
    if((!Array.isArray(x)&&!plain(x))||active.has(x))throw new Error('History requires finite, acyclic JSON data.');
    const array=Array.isArray(x),keys=Object.keys(x),names=Object.getOwnPropertyNames(x);
    if(Object.getOwnPropertySymbols(x).length||names.length!==keys.length+(array?1:0)
        ||(array&&(Object.getPrototypeOf(x)!==Array.prototype||keys.length!==x.length
          ||keys.some((key,i)=>key!==String(i)))))throw new Error('History contains unsupported properties.');
    active.add(x);add(array?'[':'{');
    keys.forEach((key,i)=>{
      const descriptor=Object.getOwnPropertyDescriptor(x,key);
      if(!Object.hasOwn(descriptor,'value'))throw new Error('History accessors are unsupported.');
      if(i)add(',');
      if(!array){add(JSON.stringify(key));add(':');}
      walk(descriptor.value,depth+1);
    });
    add(array?']':'}');active.delete(x);
  }
  walk(value,0);
  const bytes=encoder.encode(pieces.join(''));
  if(bytes.length>limit)throw new RangeError('History record exceeds its byte limit.');
  return bytes;
}

export function decodeHistoryJSON(bytes){
  const value=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
  // JSON.parse accepts overflowing numeric exponents. Reject these as well as
  // deep or expansive trees before any checkpoint or UI consumer sees them.
  validateTree(value,archiveRecordLimit);
  return value;
}

function validateTree(value,characterLimit){
  let visited=0,characters=0;const active=new WeakSet();
  function walk(x,depth){
    if(depth>80||++visited>2000000)throw new RangeError('History record exceeds its structural limit.');
    if(x===null||typeof x==='boolean')return;
    if(typeof x==='number'){if(!Number.isFinite(x))throw new Error('History contains a non-finite number.');return;}
    if(typeof x==='string')characters+=x.length;
    else{
      if((!Array.isArray(x)&&!plain(x))||active.has(x))throw new Error('History requires finite, acyclic JSON data.');
      const array=Array.isArray(x),keys=Object.keys(x);
      if(Object.getOwnPropertySymbols(x).length||Object.getOwnPropertyNames(x).length!==keys.length+(array?1:0)
          ||(array&&(Object.getPrototypeOf(x)!==Array.prototype||keys.length!==x.length
            ||keys.some((key,i)=>key!==String(i)))))throw new Error('History contains unsupported properties.');
      active.add(x);
      for(const key of keys){
        const descriptor=Object.getOwnPropertyDescriptor(x,key);
        if(!Object.hasOwn(descriptor,'value'))throw new Error('History accessors are unsupported.');
        characters+=key.length;walk(descriptor.value,depth+1);
      }
      active.delete(x);
    }
    if(characters>characterLimit)throw new RangeError('Expanded history record exceeds its size limit.');
  }
  walk(value,0);
}

// Use the existing external-reference wire convention. User objects that look
// like references are always ordinary data. Pool entries are complete values;
// there are no cross-chunk references and no reconstructed numerical states.
export function encodeHistorySnapshots(snapshots){
  // Validate the expanded reader shape before pooling can shorten its depth.
  validateTree({analysis:'time_response',snapshots},64*1024*1024);
  const values=[],references=[],keys=new Map(),encoded=new WeakMap();let keyCharacters=0;
  function pool(parent,key,path){
    const value=parent[key];
    if(!plain(value)&&!Array.isArray(value))return;
    let text=encoded.get(value);
    if(text===undefined){text=new TextDecoder().decode(encodeHistoryJSON(value));encoded.set(value,text);}
    if(text.length<192||text.length>4*1024*1024)return;
    let index=keys.get(text);
    if(index===undefined){
      // Eviction only affects compression, never the stored fields.
      while(keyCharacters+text.length>4*1024*1024){
        const oldest=keys.keys().next().value;keys.delete(oldest);keyCharacters-=oldest.length;
      }
      index=values.length;values.push(value);keys.set(text,index);keyCharacters+=text.length;
    }
    parent[key]=null;references.push([[...path,key],index]);
  }
  const copied=snapshots.map((snapshot,i)=>{
    const next={...snapshot},path=['snapshots',i];
    for(const key of ['section_output_definitions','coefficient_definitions','aerodynamic_lag',
      'mesh_discretization','sensor_metadata','limitations','restart_context'])pool(next,key,path);
    if(plain(snapshot.restart)){
      const restart={...snapshot.restart};next.restart=restart;
      for(const key of ['state','older','options','validation_loads'])pool(restart,key,[...path,'restart']);
      if(plain(restart.accepted_method)){
        const method={...restart.accepted_method};restart.accepted_method=method;
        for(const key of ['previous','previous2','seed','accepted_inputs','layout'])pool(method,key,[...path,'restart','accepted_method']);
        if(plain(method.endpoint)){
          method.endpoint={...method.endpoint};
          for(const key of ['state','options'])pool(method.endpoint,key,[...path,'restart','accepted_method','endpoint']);
        }
      }
    }
    return next;
  });
  return encodeHistoryJSON({format:'openswing-time-result',version:1,
    result:{analysis:'time_response',snapshots:copied},values,references});
}

export function decodeHistorySnapshots(bytes){
  const packet=decodeHistoryJSON(bytes);
  if(packet?.format!=='openswing-time-result')throw new Error('Invalid history chunk.');
  const result=unpackTimeResult(packet);
  // Limit expanded occurrences too, so a tiny malicious reference table cannot
  // cause an unbounded standalone checkpoint copy later.
  validateTree(result,64*1024*1024);
  return result.snapshots;
}
