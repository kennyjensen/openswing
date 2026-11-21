// Version 1 portable, append-only history container. A complete footer commits
// the file; incomplete writes are never readable. Only one chunk is cached.
// A sink implements async write(Uint8Array), close(), abort(); a source implements
// size and slice(start,end).arrayBuffer(), as a browser File/Blob does.
import {archiveRecordLimit,encodeHistoryJSON,decodeHistoryJSON,
  encodeHistorySnapshots,decodeHistorySnapshots} from './time-history-codec.js';
import {timeHistoryEntry,validTimeHistoryEntry} from './time-history-index.js';

const header=new TextEncoder().encode('OSWHST01'),endMagic=new TextEncoder().encode('OSWEND01');
const footerSize=56,manifestLimit=16*1024*1024,maxRecords=65536,maxSnapshots=2000000;
const format='openswing-time-history',hex=b=>Array.from(b,x=>x.toString(16).padStart(2,'0')).join('');
const hash=async bytes=>new Uint8Array(await crypto.subtle.digest('SHA-256',bytes));
const invalid=()=>{throw new Error('Invalid or incomplete time-history archive.');};
const integer=(x,min,max)=>Number.isSafeInteger(x)&&x>=min&&x<=max;
const plain=x=>x!==null&&typeof x==='object'&&Object.getPrototypeOf(x)===Object.prototype;
const same=(a,b)=>a.length===b.length&&a.every((x,i)=>x===b[i]);

async function collect(stream,limit){
  const reader=stream.getReader(),pieces=[];let length=0;
  try{
    while(true){
      const {done,value}=await reader.read();if(done)break;
      length+=value.length;
      if(length>limit)throw new RangeError('History stream exceeds its declared size.');
      pieces.push(value);
    }
  }catch(error){await reader.cancel(error).catch(()=>{});throw error;}
  finally{reader.releaseLock();}
  const result=new Uint8Array(length);let offset=0;
  for(const piece of pieces){result.set(piece,offset);offset+=piece.length;}
  return result;
}
const compress=bytes=>collect(new Blob([bytes]).stream().pipeThrough(new CompressionStream('gzip')),archiveRecordLimit+65536);
const decompress=(bytes,limit)=>collect(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip')),limit);

export async function createTimeHistoryWriter(sink,{chunkSize=16}={}){
  if(!integer(chunkSize,1,128))throw new RangeError('History chunk size must be 1–128.');
  if(!sink||['write','close','abort'].some(key=>typeof sink[key]!=='function'))throw new Error('A writable history sink is required.');
  if(typeof CompressionStream!=='function'||!globalThis.crypto?.subtle)throw new Error('History compression and checksums are unavailable in this browser.');
  let offset=0,count=0,lastTime=-Infinity,status='open',busy=false,previewBytes=0,previews=true;
  const records=[];
  async function write(bytes){await sink.write(bytes);offset+=bytes.length;}
  async function fail(error){status='failed';await sink.abort(error).catch(()=>{});throw error;}
  async function action(callback){
    if(status!=='open'||busy)throw new Error('History writes must be serial and the writer must be open.');
    busy=true;
    try{return await callback();}catch(error){return await fail(error);}finally{busy=false;}
  }
  try{await write(header);}catch(error){return await fail(error);}
  async function record(kind,bytes,details={}){
    if(records.length>=maxRecords-1)throw new RangeError('History has too many chunks.');
    const compressed=await compress(bytes);
    const entry={kind,offset,bytes:compressed.length,plain_bytes:bytes.length,sha256:hex(await hash(bytes)),...details};
    await write(compressed);records.push(entry);
  }
  async function batch(snapshots){
    let bytes;
    try{bytes=encodeHistorySnapshots(snapshots);}
    catch(error){
      // A large batch can be split without dropping states. A single oversized
      // snapshot fails explicitly; the writer never silently thins a history.
      if(!(error instanceof RangeError)||snapshots.length===1)throw error;
      const middle=Math.floor(snapshots.length/2);
      await batch(snapshots.slice(0,middle));await batch(snapshots.slice(middle));return;
    }
    const times=snapshots.map(snapshot=>snapshot.time);
    const details={first:count,count:snapshots.length,times};
    if(previews){
      const preview=snapshots.map(timeHistoryEntry);
      try{previewBytes+=encodeHistoryJSON(preview,4*1024*1024).length;}
      catch(error){if(!(error instanceof RangeError))throw error;previewBytes=Infinity;}
      // The optional display cache must never prevent an otherwise valid file
      // from fitting. Older files and oversized indexes scan physical chunks.
      if(previewBytes<=4*1024*1024){details.preview_version=1;details.preview=preview;}
      else {previews=false;for(const old of records){delete old.preview;delete old.preview_version;}}
    }
    await record('snapshots',bytes,details);
    count+=snapshots.length;
  }
  return {
    async append(snapshots){return action(async()=>{
      if(!Array.isArray(snapshots)||count+snapshots.length>maxSnapshots)throw new RangeError('Invalid history snapshot count.');
      for(const snapshot of snapshots){
        const time=plain(snapshot)?Object.getOwnPropertyDescriptor(snapshot,'time')?.value:undefined;
        if(!Number.isFinite(time)||time<lastTime)throw new Error('History snapshot times must be finite and nondecreasing.');
        lastTime=time;
      }
      for(let i=0;i<snapshots.length;i+=chunkSize)await batch(snapshots.slice(i,i+chunkSize));
    });},
    async finish(metadata){return action(async()=>{
      const encoded=encodeHistoryJSON(metadata);
      if(!count||!plain(metadata)||metadata.analysis!=='time_response'||Object.hasOwn(metadata,'snapshots'))
        throw new Error('Finish history with time-response metadata and no inline snapshots.');
      await record('metadata',encoded);
      const manifest={format,version:1,snapshots:count,records};
      const bytes=encodeHistoryJSON(manifest,manifestLimit),manifestOffset=offset;
      await write(bytes);
      const footer=new Uint8Array(footerSize),view=new DataView(footer.buffer);
      footer.set(endMagic);view.setBigUint64(8,BigInt(manifestOffset),true);view.setBigUint64(16,BigInt(bytes.length),true);
      footer.set(await hash(bytes),24);await write(footer);await sink.close();status='closed';
      return {format,version:1,snapshots:count,chunks:records.length-1,bytes:offset};
    });},
    async abort(){
      if(busy)throw new Error('Wait for the current history write before aborting.');
      if(status==='open'){status='aborted';await sink.abort();}
    },
    get snapshotCount(){return count;},
  };
}

export async function openTimeHistoryArchive(source){
  if(!source||!integer(source.size,header.length+footerSize,Number.MAX_SAFE_INTEGER)||typeof source.slice!=='function')invalid();
  if(typeof DecompressionStream!=='function'||!globalThis.crypto?.subtle)throw new Error('History decompression and checksums are unavailable in this browser.');
  const statistics={bytesRead:0,recordsRead:0,maxReadBytes:0,cacheHits:0};
  async function read(start,length){
    const bytes=new Uint8Array(await source.slice(start,start+length).arrayBuffer());
    if(bytes.length!==length)invalid();
    statistics.bytesRead+=length;statistics.maxReadBytes=Math.max(statistics.maxReadBytes,length);return bytes;
  }
  if(!same(await read(0,header.length),header))invalid();
  const footer=await read(source.size-footerSize,footerSize);
  if(!same(footer.subarray(0,8),endMagic))invalid();
  const view=new DataView(footer.buffer,footer.byteOffset,footer.byteLength);
  const manifestOffset=Number(view.getBigUint64(8,true)),manifestBytes=Number(view.getBigUint64(16,true));
  if(!integer(manifestOffset,header.length,source.size-footerSize)||!integer(manifestBytes,1,manifestLimit)
      ||manifestOffset+manifestBytes!==source.size-footerSize)invalid();
  const bytes=await read(manifestOffset,manifestBytes);
  if(!same(await hash(bytes),footer.subarray(24)))throw new Error('History index checksum mismatch.');
  const manifest=decodeHistoryJSON(bytes);
  if(!plain(manifest)||manifest.format!==format||manifest.version!==1||!integer(manifest.snapshots,1,maxSnapshots)
      ||!Array.isArray(manifest.records)||!integer(manifest.records.length,2,maxRecords))invalid();
  let offset=header.length,count=0,lastTime=-Infinity;
  for(const [i,record]of manifest.records.entries()){
    if(!plain(record)||record.offset!==offset||!integer(record.bytes,1,archiveRecordLimit+65536)
        ||!integer(record.plain_bytes,1,archiveRecordLimit)||typeof record.sha256!=='string'
        ||!/^[0-9a-f]{64}$/.test(record.sha256))invalid();
    offset+=record.bytes;if(offset>manifestOffset)invalid();
    if(i===manifest.records.length-1){if(record.kind!=='metadata')invalid();}
    else{
      if(record.kind!=='snapshots'||record.first!==count||!integer(record.count,1,128)
          ||!Array.isArray(record.times)||record.times.length!==record.count)invalid();
      for(const time of record.times){if(!Number.isFinite(time)||time<lastTime)invalid();lastTime=time;}
      if(record.preview_version===1&&(!Array.isArray(record.preview)||record.preview.length!==record.count
          ||record.preview.some((entry,j)=>!validTimeHistoryEntry(entry,record.times[j]))))invalid();
      count+=record.count;
    }
  }
  if(offset!==manifestOffset||count!==manifest.snapshots)invalid();
  async function load(record){
    const bytes=await decompress(await read(record.offset,record.bytes),record.plain_bytes);
    if(bytes.length!==record.plain_bytes||hex(await hash(bytes))!==record.sha256)throw new Error('History record checksum mismatch.');
    statistics.recordsRead++;return bytes;
  }
  const metadata=decodeHistoryJSON(await load(manifest.records.at(-1)));
  if(!plain(metadata)||metadata.analysis!=='time_response'||Object.hasOwn(metadata,'snapshots'))invalid();
  const chunks=manifest.records.slice(0,-1);let cachedIndex=-1,cached=null,tail=Promise.resolve();
  function serial(fn){const next=tail.then(fn);tail=next.catch(()=>{});return next;}
  function chunkAt(index){
    if(!integer(index,0,count-1))throw new RangeError('History snapshot index is out of range.');
    let lo=0,hi=chunks.length;
    while(lo+1<hi){const mid=(lo+hi)>>>1;if(chunks[mid].first<=index)lo=mid;else hi=mid;}
    return lo;
  }
  async function snapshot(index){
    const which=chunkAt(index),record=chunks[which];
    if(cachedIndex!==which){
      cached=null;cachedIndex=-1;
      const snapshots=decodeHistorySnapshots(await load(record));
      if(snapshots.length!==record.count||snapshots.some((s,i)=>!plain(s)||!Object.is(s.time,record.times[i])))invalid();
      if(record.preview_version===1&&snapshots.some((snapshot,i)=>{
        const expected=timeHistoryEntry(snapshot),entry=record.preview[i];
        return Object.keys(expected).some(key=>key==='values'
          ?expected.values.some((value,j)=>!Object.is(value,entry.values[j])):!Object.is(expected[key],entry[key]));
      }))throw new Error('History display index does not match its physical states.');
      cached=snapshots;cachedIndex=which;
    }else statistics.cacheHits++;
    // A caller can edit a selected snapshot without corrupting future reads.
    return structuredClone(cached[index-record.first]);
  }
  return {
    snapshotCount:count,chunkCount:chunks.length,
    metadata(){return structuredClone(metadata);},
    times(){return chunks.flatMap(record=>record.times);},
    index(){return chunks.every(record=>record.preview_version===1)?structuredClone(chunks.flatMap(record=>record.preview)):null;},
    readSnapshot(index){return serial(()=>snapshot(index));},
    async *snapshots(){for(let i=0;i<count;i++)yield await serial(()=>snapshot(i));},
    async verify(){for await(const ignored of this.snapshots()){}return {snapshots:count,chunks:chunks.length};},
    get statistics(){return {...statistics};},
  };
}
