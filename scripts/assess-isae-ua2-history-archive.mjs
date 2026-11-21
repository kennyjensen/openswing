// Assess the completed exact comparison whose final packaged-file path check
// failed. Preserve that exit 1; do not rerun or relabel its producer as success.
import assert from 'node:assert/strict';
import {readFile,writeFile,open,stat,readdir} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {openTimeHistoryArchive} from '../web/time-history-archive.js';
import {encodeHistoryJSON} from '../web/time-history-codec.js';
import {checkpointAt} from '../web/time-checkpoint.js';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const base=path.join(root,'artifacts/isae/ua2-history-archive-20261102');
const source=path.join(root,'artifacts/isae/ua2-incidence-periodic-browser-20261101/assessment');
const hash=b=>createHash('sha256').update(b).digest('hex'),json=async p=>JSON.parse(await readFile(p));
const started=performance.now(),execution=await json(path.join(base,'producer-execution.json'));
assert.equal(execution.exit_code,1);assert.equal(execution.terminal_chunk_id,'0142dc');
assert.equal(execution.snapshots_compared_exactly,5281);assert.equal(execution.checkpoints_compared_exactly,660);
const original=await readFile(path.join(base,'producer-original.mjs'),'utf8');
assert.equal(hash(original),execution.producer_sha256);
const current=await readFile(path.join(root,'scripts/verify-isae-ua2-history-archive.mjs'),'utf8');
assert.equal(original.replace('path.join(root,prefix,p)',"path.join(root,prefix,p.slice('openswing/'.length))"),current,
  'Only the final packaged-module path may differ from the completed producer');
const log=await readFile(path.join(base,'progress.jsonl'));assert.equal(hash(log),execution.progress_sha256);
const progress=log.toString().trim().split('\n').map(line=>JSON.parse(line));assert.equal(progress.length,660);
for(const [i,row]of progress.entries()){
  assert.equal(row.phase,i<330?'write':'verify');assert.equal(row.part,i%330);
  assert.equal(row.snapshots,17+(i%330)*16);assert.ok(row.seconds>0&&row.seconds<45);
  if(i>=330)assert.equal(row.checkpoints,2*(i%330+1));
}
const pins={},scientific={},inputs={};
for(const p of ['web/time-history-archive.js','web/time-history-codec.js','web/time-result-storage.js',
  'web/saved-state-data.js','web/time-checkpoint.js','scripts/verify-isae-ua2-history-archive.mjs','scripts/assess-isae-ua2-history-archive.mjs'])
  pins[p]=hash(await readFile(path.join(root,p)));
async function checkPython(folder='openswing'){
  for(const entry of await readdir(path.join(root,folder),{withFileTypes:true})){
    const p=folder+'/'+entry.name;
    if(entry.isDirectory()&&entry.name!=='__pycache__')await checkPython(p);
    else if(entry.isFile()&&p.endsWith('.py')){
      const sha=hash(await readFile(path.join(root,p)));scientific[p]=sha;
      for(const prefix of ['public/kernel','dist/kernel'])assert.equal(hash(await readFile(path.join(root,prefix,p.slice('openswing/'.length)))),sha);
    }
  }
}
await checkPython();assert.equal(Object.keys(scientific).length,136);
const plan=await json(path.join(source,'plan.json')),filePath=path.join(base,'history.oswh'),size=(await stat(filePath)).size;
const file=await open(filePath,'r');const samples=[];let metadata;
try{
  const reader=await openTimeHistoryArchive({size,slice(start,end){return {async arrayBuffer(){
    const bytes=Buffer.alloc(end-start);let done=0;
    while(done<bytes.length){const result=await file.read(bytes,done,bytes.length-done,start+done);assert.ok(result.bytesRead>0);done+=result.bytesRead;}
    return bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.length);
  }};}});
  assert.equal(reader.snapshotCount,5281);assert.deepEqual(reader.times(),plan.times);metadata=reader.metadata();
  const selected=[0,1,16,17,159,160,2000,3344,3345,3359,5279,5280];
  for(let part=0;part<330;part++){
    const folder=path.join(source,'production',`part${String(part).padStart(3,'0')}`),receipt=await json(path.join(folder,'receipt.json'));
    const compressed=await readFile(path.join(folder,'trajectory.json.gz'));assert.equal(receipt.outcome,'success');
    const sha=hash(compressed);assert.equal(sha,receipt.output_sha256['trajectory.json.gz']);inputs[path.relative(root,folder)+'/trajectory.json.gz']=sha;
    const indices=selected.filter(index=>(index===0?0:Math.floor((index-1)/16))===part);
    if(!indices.length&&part!==329)continue;
    const raw=JSON.parse(gunzipSync(compressed));
    if(part===329){const {snapshots:ignored,...expected}=raw;assert.deepEqual(metadata,expected);}
    for(const index of indices){
      const local=index===0?0:(index-1)%16+1,s=raw.snapshots[local];
      const expected=part<329?{...s,restart_context:s.restart_context??raw.restart_context}:s;
      const actual=await reader.readSnapshot(index);assert.deepEqual(actual,expected);
      const checkpoint=checkpointAt({...raw,snapshots:[expected]},0);
      assert.deepEqual(checkpointAt({...metadata,snapshots:[actual]},0),checkpoint);
      samples.push({index,time:expected.time,snapshot_sha256:hash(encodeHistoryJSON(expected)),checkpoint_sha256:hash(encodeHistoryJSON(checkpoint))});
    }
  }
  assert.equal(samples.length,12);
  for(const [p,sha]of Object.entries(pins))assert.equal(hash(await readFile(path.join(root,p))),sha);
  const sizing=await json(path.join(root,'artifacts/isae/ua2-history-storage-20261102/sizing.json'));
  const report={passed:true,scope:'Completed exact joined-state comparison assessed after correcting only a final packaged-module path. Root metadata is the unmodified last segment, not an integrated joined-app/project envelope.',
    original_producer:execution,assessment_rechecked_samples:12,assessment_seconds:(performance.now()-started)/1000,
    snapshots:5281,segments:330,exact_checkpoints:660,archive:{format:'openswing-time-history',version:1,snapshots:5281,chunks:reader.chunkCount,bytes:size},
    ordinary_snapshot_JSON_bytes:sizing.minimum_snapshots_JSON_bytes,size_ratio:size/sizing.minimum_snapshots_JSON_bytes,
    sampled_max_heap_bytes:Math.max(...progress.map(x=>x.heap_bytes)),process_peak_RSS_kib:null,
    memory_note:'192 MiB V8 heap cap. Samples are not peak heap or total process RSS; the failed final producer summary did not retain RSS.',
    max_segment_seconds:Math.max(...progress.map(x=>x.seconds)),recorded_batch_seconds:progress.reduce((total,x)=>total+x.seconds,0),
    source_sha256:pins,scientific_modules_unchanged:136,scientific_sha256:scientific,input_sha256:inputs,
    browser_samples:samples,metadata_sha256:hash(encodeHistoryJSON(metadata)),numerical_reexecution:false,
    production_solver_changed:false,full_history_UI_validation:false,native_ASWING_comparison:false,full_goal_complete:false};
  await writeFile(path.join(base,'archive.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({passed:true,snapshots:5281,checkpoints:660,bytes:size,modules:136,assessment_seconds:report.assessment_seconds}));
}finally{await file.close();}
