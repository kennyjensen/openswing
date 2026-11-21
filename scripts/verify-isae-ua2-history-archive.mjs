// Complete retained UA-2 states, one serial segment at a time. No solver runs.
import assert from 'node:assert/strict';
import {readFile,writeFile,appendFile,mkdir,open,link,unlink,stat,readdir} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createTimeHistoryWriter,openTimeHistoryArchive} from '../web/time-history-archive.js';
import {encodeHistoryJSON} from '../web/time-history-codec.js';
import {checkpointAt} from '../web/time-checkpoint.js';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const base=path.join(root,'artifacts/isae/ua2-history-archive-20261102');
const source=path.join(root,'artifacts/isae/ua2-incidence-periodic-browser-20261101/assessment');
const hash=b=>createHash('sha256').update(b).digest('hex');
const json=async p=>JSON.parse(await readFile(p));
const started=performance.now(),pins={},inputs={},observations=[],samples=[];
for(const p of ['web/time-history-archive.js','web/time-history-codec.js','web/time-result-storage.js',
  'web/saved-state-data.js','web/time-checkpoint.js','scripts/verify-isae-ua2-history-archive.mjs'])pins[p]=hash(await readFile(path.join(root,p)));
const scientific={};
async function pinPython(folder='openswing'){
  for(const entry of await readdir(path.join(root,folder),{withFileTypes:true})){
    const p=folder+'/'+entry.name;
    if(entry.isDirectory()&&entry.name!=='__pycache__')await pinPython(p);
    else if(entry.isFile()&&p.endsWith('.py'))scientific[p]=hash(await readFile(path.join(root,p)));
  }
}
await pinPython();assert.equal(Object.keys(scientific).length,136);
const plan=await json(path.join(source,'plan.json')),audit=await json(path.join(source,'audit.json'));
assert.equal(audit.passed,true);assert.equal(audit.audited_unique_snapshots,5281);assert.equal(plan.jobs.length,330);
await mkdir(base,{recursive:true});await writeFile(path.join(base,'progress.jsonl'),'',{flag:'wx'});
await writeFile(path.join(base,'isae-status-before.md'),await readFile(path.join(root,'docs/validation/ISAE_STATUS.md')),{flag:'wx'});
let maxHeap=0,maxRSS=0,lastMetadata=null,index=0,checkpoints=0;
async function segment(part){
  const folder=path.join(source,'production',`part${String(part).padStart(3,'0')}`);
  const compressed=await readFile(path.join(folder,'trajectory.json.gz')),receipt=await json(path.join(folder,'receipt.json'));
  assert.equal(receipt.outcome,'success');assert.equal(hash(compressed),receipt.output_sha256['trajectory.json.gz']);
  inputs[path.relative(root,folder)+'/trajectory.json.gz']=hash(compressed);
  const raw=JSON.parse(gunzipSync(compressed));assert.equal(raw.snapshots.length,17);
  const snapshots=raw.snapshots.slice(part?1:0).map(s=>part<329?{...s,restart_context:s.restart_context??raw.restart_context}:s);
  return {raw,snapshots};
}
async function progress(phase,part,began,extra={}){
  const memory=process.memoryUsage();maxHeap=Math.max(maxHeap,memory.heapUsed);maxRSS=Math.max(maxRSS,memory.rss);
  const record={phase,part,snapshots:index,seconds:(performance.now()-began)/1000,heap_bytes:memory.heapUsed,...extra};
  assert.ok(record.seconds<45,'One storage segment exceeded the 45-second bound');observations.push(record);
  await appendFile(path.join(base,'progress.jsonl'),JSON.stringify(record)+'\n');
  if((part+1)%16===0||part===329)console.log(JSON.stringify(record));
}
const temporary=path.join(base,'history.oswh.partial'),destination=path.join(base,'history.oswh');
const handle=await open(temporary,'wx');let sinkClosed=false;
const writer=await createTimeHistoryWriter({
  async write(bytes){let done=0;while(done<bytes.length){const result=await handle.write(bytes,done,bytes.length-done);assert.ok(result.bytesWritten>0);done+=result.bytesWritten;}},
  async close(){await handle.sync();await handle.close();sinkClosed=true;await link(temporary,destination);await unlink(temporary);},
  async abort(){if(!sinkClosed){await handle.close();sinkClosed=true;}},
});
let written;
try{
  for(let part=0;part<330;part++){
    const began=performance.now(),{raw,snapshots}=await segment(part);
    for(const snapshot of snapshots)assert.equal(snapshot.time,plan.times[index++]);
    await writer.append(snapshots);
    if(part===329){const {snapshots:ignored,...metadata}=raw;lastMetadata=metadata;}
    await progress('write',part,began);
  }
  assert.equal(index,5281);written=await writer.finish(lastMetadata);
}finally{if(!sinkClosed)await writer.abort();}

const file=await open(destination,'r'),size=(await stat(destination)).size;
const reader=await openTimeHistoryArchive({size,slice(start,end){return {async arrayBuffer(){
  const bytes=Buffer.alloc(end-start);let done=0;
  while(done<bytes.length){const result=await file.read(bytes,done,bytes.length-done,start+done);assert.ok(result.bytesRead>0);done+=result.bytesRead;}
  return bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.length);
}};}});
try{
  assert.deepEqual(reader.metadata(),lastMetadata);assert.deepEqual(reader.times(),plan.times);index=0;
  for(let part=0;part<330;part++){
    const began=performance.now(),{raw,snapshots}=await segment(part);
    for(let i=0;i<snapshots.length;i++){
      const expected=snapshots[i],actual=await reader.readSnapshot(index);
      assert.deepEqual(actual,expected,'Every field at snapshot '+index);
      assert.equal(JSON.stringify(actual),JSON.stringify(expected),'Property order at snapshot '+index);
      if(i===0||i===snapshots.length-1){
        assert.deepEqual(checkpointAt({...lastMetadata,snapshots:[actual]},0),checkpointAt({...raw,snapshots:[expected]},0));checkpoints++;
      }
      if([0,1,16,17,159,160,2000,3344,3345,3359,5279,5280].includes(index))samples.push({index,time:expected.time,
        snapshot_sha256:hash(encodeHistoryJSON(expected)),checkpoint_sha256:hash(encodeHistoryJSON(checkpointAt({...raw,snapshots:[expected]},0)))});
      index++;
    }
    await progress('verify',part,began,{checkpoints});
  }
  assert.equal(index,5281);assert.equal(checkpoints,660);
}finally{await file.close();}
for(const [p,sha]of Object.entries(pins))assert.equal(hash(await readFile(path.join(root,p))),sha,'Source changed during archive verification');
for(const [p,sha]of Object.entries(scientific)){
  assert.equal(hash(await readFile(path.join(root,p))),sha);
  for(const prefix of ['public/kernel/','dist/kernel/'])assert.equal(hash(await readFile(path.join(root,prefix,p.slice('openswing/'.length)))),sha);
}
const original=await json(path.join(root,'artifacts/isae/ua2-history-storage-20261102/sizing.json'));
const report={passed:true,scope:'Complete joined physical snapshot array plus unmodified final-segment metadata. The app joined-result envelope and project persistence are not integrated.',
  snapshots:index,segments:330,exact_checkpoints:checkpoints,archive:written,ordinary_snapshot_JSON_bytes:original.minimum_snapshots_JSON_bytes,
  size_ratio:written.bytes/original.minimum_snapshots_JSON_bytes,reader_statistics:reader.statistics,
  sampled_max_heap_bytes:maxHeap,sampled_max_RSS_bytes:maxRSS,process_peak_RSS_kib:process.resourceUsage().maxRSS,
  max_segment_seconds:Math.max(...observations.map(r=>r.seconds)),wall_seconds:(performance.now()-started)/1000,
  source_sha256:pins,scientific_modules_unchanged:Object.keys(scientific).length,scientific_sha256:scientific,input_sha256:inputs,
  browser_samples:samples,metadata_sha256:hash(encodeHistoryJSON(lastMetadata)),numerical_reexecution:false,
  production_solver_changed:false,full_history_UI_validation:false,native_ASWING_comparison:false,full_goal_complete:false};
await writeFile(path.join(base,'archive.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({passed:true,snapshots:index,checkpoints,archive_bytes:written.bytes,max_segment_seconds:report.max_segment_seconds,wall_seconds:report.wall_seconds}));
