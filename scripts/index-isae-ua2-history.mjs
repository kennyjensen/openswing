// Add only a display index to the previously verified complete archive. Every
// compressed physical record and the root metadata record are copied unchanged.
import assert from 'node:assert/strict';
import {readFile,writeFile,appendFile,open,stat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {gunzipSync} from 'node:zlib';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {encodeHistoryJSON} from '../web/time-history-codec.js';
import {timeHistoryEntry} from '../web/time-history-index.js';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const base=path.join(root,'artifacts/isae/ua2-archive-ui-20261102');
const old=path.join(root,'artifacts/isae/ua2-history-archive-20261102');
const rawBase=path.join(root,'artifacts/isae/ua2-incidence-periodic-browser-20261101/assessment/production');
const sha=bytes=>createHash('sha256').update(bytes).digest('hex'),pins={};
for(const p of ['web/time-history-index.js','web/time-history-codec.js','scripts/index-isae-ua2-history.mjs'])pins[p]=sha(await readFile(path.join(root,p)));
const original=JSON.parse(await readFile(path.join(old,'browser.json'))),size=(await stat(path.join(old,'history.oswh'))).size;
const input=await open(path.join(old,'history.oswh'),'r'),output=await open(path.join(base,'history.oswh'),'wx');
const started=performance.now(),observations=[],entries=[],inputs={};
await writeFile(path.join(base,'index-progress.jsonl'),'',{flag:'wx'});
async function read(offset,length){const bytes=Buffer.alloc(length);let done=0;while(done<length){const value=await input.read(bytes,done,length-done,offset+done);assert.ok(value.bytesRead);done+=value.bytesRead;}return bytes;}
async function write(bytes){let done=0;while(done<bytes.length){const value=await output.write(bytes,done,bytes.length-done);assert.ok(value.bytesWritten);done+=value.bytesWritten;}}
try{
  const footer=await read(size-56,56),offset=Number(footer.readBigUInt64LE(8)),length=Number(footer.readBigUInt64LE(16));
  const originalManifest=await read(offset,length);assert.equal(sha(originalManifest),footer.subarray(24).toString('hex'));
  const manifest=JSON.parse(originalManifest),wholeHash=createHash('sha256'),payloadHash=createHash('sha256');
  for(let start=0;start<size;start+=1024*1024){
    const bytes=await read(start,Math.min(1024*1024,size-start));wholeHash.update(bytes);
    if(start<offset){const copied=bytes.subarray(0,Math.min(bytes.length,offset-start));payloadHash.update(copied);await write(copied);}
  }
  assert.equal(wholeHash.digest('hex'),original.input_archive_sha256);
  for(let part=0;part<330;part++){
    const began=performance.now(),folder=path.join(rawBase,`part${String(part).padStart(3,'0')}`);
    const compressed=await readFile(path.join(folder,'trajectory.json.gz')),receipt=JSON.parse(await readFile(path.join(folder,'receipt.json')));
    assert.equal(sha(compressed),receipt.output_sha256['trajectory.json.gz']);inputs[path.relative(root,folder)+'/trajectory.json.gz']=sha(compressed);
    const result=JSON.parse(gunzipSync(compressed));
    for(const snapshot of result.snapshots.slice(part?1:0))entries.push(timeHistoryEntry(snapshot));
    const record={part,snapshots:entries.length,seconds:(performance.now()-began)/1000};assert.ok(record.seconds<45);observations.push(record);
    await appendFile(path.join(base,'index-progress.jsonl'),JSON.stringify(record)+'\n');
    if((part+1)%64===0||part===329)console.log(JSON.stringify(record));
  }
  assert.equal(entries.length,5281);
  let cacheBytes=0;
  for(const record of manifest.records){
    if(record.kind!=='snapshots')continue;
    record.preview_version=1;record.preview=entries.slice(record.first,record.first+record.count);
    assert.deepEqual(record.preview.map(entry=>entry.time),record.times);cacheBytes+=encodeHistoryJSON(record.preview).length;
  }
  assert.ok(cacheBytes<=4*1024*1024);
  const bytes=encodeHistoryJSON(manifest);await write(bytes);
  const next=Buffer.alloc(56);next.write('OSWEND01');next.writeBigUInt64LE(BigInt(offset),8);next.writeBigUInt64LE(BigInt(bytes.length),16);Buffer.from(sha(bytes),'hex').copy(next,24);
  await write(next);await output.sync();
  for(const [p,h]of Object.entries(pins))assert.equal(sha(await readFile(path.join(root,p))),h);
  const report={passed:true,scope:'Optional display index only. All pre-existing compressed physical records and final-segment metadata are byte-identical.',
    snapshots:5281,physical_chunks:331,original_archive_sha256:original.input_archive_sha256,
    identical_payload_bytes:offset,identical_payload_sha256:payloadHash.digest('hex'),archive_bytes:offset+bytes.length+56,
    index_bytes:bytes.length,preview_bytes:cacheBytes,source_sha256:pins,input_sha256:inputs,
    max_raw_segment_seconds:Math.max(...observations.map(row=>row.seconds)),wall_seconds:(performance.now()-started)/1000,
    numerical_reexecution:false,full_goal_complete:false};
  await writeFile(path.join(base,'index.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({passed:true,snapshots:5281,bytes:report.archive_bytes,index_bytes:report.index_bytes,wall_seconds:report.wall_seconds}));
}finally{await input.close();await output.close();}
