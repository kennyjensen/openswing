// Count the real retained history without allocating the whole trajectory.
// One verified 17-state segment is decoded at a time; no solver runs.
import assert from 'node:assert/strict';
import {readFile,writeFile,appendFile} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {PROJECT_LIMIT} from '../web/project-data.js';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const source=path.join(root,'artifacts/isae/ua2-incidence-periodic-browser-20261101/assessment');
const base=path.join(root,'artifacts/isae/ua2-history-storage-20261102');
const hash=b=>createHash('sha256').update(b).digest('hex');
const read=async p=>JSON.parse(await readFile(p));
const plan=await read(path.join(source,'plan.json'));
const audit=await read(path.join(source,'audit.json'));
assert.equal(audit.passed,true);assert.equal(audit.audited_unique_snapshots,5281);
assert.equal(plan.jobs.length,330);
const started=performance.now(),bytes=x=>Buffer.byteLength(JSON.stringify(x));
const fields={},metadata=new Map(),inputs={},observations=[];
let total=2,values=1,snapshots=0,firstFileLimit=null,firstValueLimit=null,previous=null;
// The repeated metadata is compared by exact JSON text, not a hash or numeric
// tolerance. This is a diagnostic opportunity count, not a storage change.
let metadataOccurrences=0,metadataBytes=0;
function countValues(value){let count=0;const pending=[value];while(pending.length){const v=pending.pop();count++;if(v!==null&&typeof v==='object')for(const child of Object.values(v))pending.push(child);}return count;}
function candidate(value){
  if(value===undefined)return;
  const text=JSON.stringify(value);metadataOccurrences++;metadataBytes+=Buffer.byteLength(text);
  if(!metadata.has(text))metadata.set(text,Buffer.byteLength(text));
}
await writeFile(path.join(base,'sizing-progress.jsonl'),'',{flag:'wx'});
for(const job of plan.jobs){
  const began=performance.now(),part=`part${String(job.part).padStart(3,'0')}`;
  const folder=path.join(source,'production',part),receipt=await read(path.join(folder,'receipt.json'));
  assert.equal(receipt.outcome,'success');
  const p=path.join(folder,'trajectory.json.gz'),compressed=await readFile(p),sha=hash(compressed);
  assert.equal(sha,receipt.output_sha256['trajectory.json.gz']);inputs[path.relative(root,p)]=sha;
  const raw=JSON.parse(gunzipSync(compressed));
  assert.equal(raw.snapshots.length,17);assert.equal(raw.accepted_steps,16);assert.equal(raw.rejected_steps,0);
  const join=s=>({time:s.time,force:s.force,frame:s.frame,circulation_rate:s.circulation_rate,circulation:s.strips.map(row=>row.circulation)});
  if(previous)assert.deepEqual(join(raw.snapshots[0]),previous,'physical join '+part);
  previous=join(raw.snapshots.at(-1));
  for(const s of raw.snapshots.slice(job.part?1:0)){
    assert.equal(s.time,plan.times[snapshots]);
    // main.js continueTime retains the context on every previous segment's
    // snapshot. The final 16 states have no added prefix context yet.
    const retained=job.part<329?{...s,restart_context:s.restart_context??raw.restart_context}:s;
    const size=bytes(retained),count=countValues(retained);
    if(snapshots)total++;total+=size;values+=count;snapshots++;
    for(const [key,value]of Object.entries(retained))fields[key]=(fields[key]??0)+bytes(value);
    candidate(retained.restart_context);
    candidate(retained.restart?.accepted_method?.accepted_inputs);
    if(firstFileLimit===null&&total>PROJECT_LIMIT)firstFileLimit={snapshots,minimum_JSON_bytes:total,part:job.part};
    if(firstValueLimit===null&&values>2000000)firstValueLimit={snapshots,minimum_JSON_values:values,part:job.part};
  }
  const observation={part:job.part,snapshots,minimum_snapshots_JSON_bytes:total,minimum_JSON_values:values,seconds:(performance.now()-began)/1000,heap_bytes:process.memoryUsage().heapUsed,RSS_bytes:process.memoryUsage().rss};
  assert.ok(observation.seconds<45,'One read/measurement segment exceeded the 45-second bound');
  observations.push(observation);await appendFile(path.join(base,'sizing-progress.jsonl'),JSON.stringify(observation)+'\n');
  if((job.part+1)%16===0||job.part===329)console.log(JSON.stringify(observation));
}
assert.equal(snapshots,5281);
const pins={};
for(const p of ['web/main.js','web/project-data.js','web/solution-data.js','web/time-result-storage.js','openswing/time_result_storage.py','scripts/measure-isae-ua2-history-storage.mjs'])pins[p]=hash(await readFile(path.join(root,p)));
const report={passed:true,scope:'Complete retained-history sizing, not a successful full-history UI load/save. Snapshot JSON alone is a strict lower bound for the full result/project.',snapshots,accepted_steps:5280,serial_segments:330,minimum_snapshots_JSON_bytes:total,minimum_JSON_values:values,project_limit_bytes:PROJECT_LIMIT,first_exceeds_file_limit:firstFileLimit,first_exceeds_value_limit:firstValueLimit,snapshot_field_value_bytes:fields,exact_metadata:{scope:'restart_context and accepted_inputs only; includes all original keys and values and preserves JSON key order',occurrences:metadataOccurrences,inline_bytes:metadataBytes,distinct_exact_values:metadata.size,distinct_value_bytes:[...metadata.values()].reduce((a,b)=>a+b,0),note:'This is not the size of a valid new archive: references, indices, checksums and other fields still require storage.'},max_segment_seconds:Math.max(...observations.map(o=>o.seconds)),sampled_max_heap_bytes:Math.max(...observations.map(o=>o.heap_bytes)),process_peak_RSS_kib:process.resourceUsage().maxRSS,wall_seconds:(performance.now()-started)/1000,source_sha256:pins,input_sha256:inputs,production_changed:false,numerical_reexecution:false,full_history_UI_validation:false,native_ASWING_comparison:false,full_goal_complete:false};
await writeFile(path.join(base,'sizing.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({passed:true,snapshots,minimum_snapshots_JSON_bytes:total,firstFileLimit,firstValueLimit,distinct_metadata_values:metadata.size,wall_seconds:report.wall_seconds}));
