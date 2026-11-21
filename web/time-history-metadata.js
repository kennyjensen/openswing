// Computed histories are read-only. Reuse exactly equal checkpoint metadata
// across continuation responses, just as the worker shares it within a response.
// Saved checkpoints still make their independent copies in saved-state-data.js.
const pools=new WeakMap();
const maximumKeyCharacters=4*1024*1024;
const plain=x=>x!==null&&typeof x==='object'&&!Array.isArray(x)
  && Object.getPrototypeOf(x)===Object.prototype;

function createPool(){return {entries:new Map(),characters:0};}

export function shareTimeHistoryMetadata(result,parent=null){
  if(result?.analysis!=='time_response'||!plain(result.restart_context)||!Array.isArray(result.snapshots))return result;
  const pool=pools.get(parent?.restart_context)??createPool();
  // Keep encoding caches local to this response. A retained history must not
  // also retain one large serialized key for every original metadata object.
  const encoded=new WeakMap(),active=new WeakSet();
  function key(value,depth=0){
    if(depth>80)return null;
    if(value===null)return 'null';
    if(typeof value==='number')return Number.isFinite(value)?Object.is(value,-0)?'-0':String(value):null;
    if(typeof value==='string'||typeof value==='boolean')return JSON.stringify(value);
    if(!Array.isArray(value)&&!plain(value))return null;
    if(encoded.has(value))return encoded.get(value);
    if(active.has(value)||Object.getOwnPropertySymbols(value).length)return null;
    const names=Object.keys(value),descriptors=Object.getOwnPropertyDescriptors(value);
    if(names.some(name=>!Object.hasOwn(descriptors[name],'value')))return null;
    if(Array.isArray(value)?Object.getPrototypeOf(value)!==Array.prototype
      ||Object.getOwnPropertyNames(value).length!==names.length+1
      ||names.length!==value.length||names.some((name,i)=>name!==String(i))
      :Object.getOwnPropertyNames(value).length!==names.length)return null;
    active.add(value);const pieces=[];
    for(const name of names){
      const part=key(value[name],depth+1);
      if(part===null){active.delete(value);return null;}
      pieces.push(Array.isArray(value)?part:JSON.stringify(name)+':'+part);
    }
    active.delete(value);
    const text=Array.isArray(value)?'['+pieces.join(',')+']':'{'+pieces.join(',')+'}';
    encoded.set(value,text);return text;
  }
  function intern(value,setup=false){
    if(!plain(value))return value;
    const text=key(value);
    if(text===null||text.length<192||text.length>maximumKeyCharacters)return value;
    if(pool.entries.has(text))return pool.entries.get(text);
    const shared=setup&&plain(value.setup)?{...value,setup:intern(value.setup)}:value;
    while(pool.characters+text.length>maximumKeyCharacters){
      const oldest=pool.entries.keys().next().value;
      pool.entries.delete(oldest);pool.characters-=oldest.length;
    }
    pool.entries.set(text,shared);pool.characters+=text.length;
    return shared;
  }
  // An archive or older result may not have an associated pool. Seed only the
  // most recent context, without walking the complete retained history.
  if(parent&&!pools.has(parent.restart_context)){
    intern(parent.restart_context,true);
    intern(parent.snapshots?.at(-1)?.restart?.accepted_method?.accepted_inputs,true);
  }
  const context=intern(result.restart_context,true);
  const snapshots=result.snapshots.map(snapshot=>{
    let next=snapshot;
    if(plain(snapshot.restart_context)){
      const shared=intern(snapshot.restart_context,true);
      if(shared!==snapshot.restart_context)next={...next,restart_context:shared};
    }
    const accepted=snapshot.restart?.accepted_method;
    if(plain(accepted?.accepted_inputs)){
      const shared=intern(accepted.accepted_inputs,true);
      if(shared!==accepted.accepted_inputs)next={...next,restart:{...snapshot.restart,accepted_method:{...accepted,accepted_inputs:shared}}};
    }
    return next;
  });
  pools.set(context,pool);
  return {...result,restart_context:context,snapshots};
}
