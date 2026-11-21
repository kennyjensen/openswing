// Check every retained result with the UI metadata-sharing implementation.
// Process one segment at a time; never retain the entire physical trajectory.
import assert from 'node:assert/strict';
import {readFile,writeFile,appendFile} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {shareTimeHistoryMetadata} from '../web/time-history-metadata.js';
import {checkpointAt} from '../web/time-checkpoint.js';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const base=path.join(root,'artifacts/isae/ua2-history-storage-20261102');
const source=path.join(root,'artifacts/isae/ua2-incidence-periodic-browser-20261101/assessment/production');
const sha=b=>createHash('sha256').update(b).digest('hex');
const started=performance.now(),reports=[],pins={};
for(const p of ['web/time-history-metadata.js','web/main.js','scripts/verify-isae-ua2-history-metadata.mjs'])pins[p]=sha(await readFile(path.join(root,p)));
await writeFile(path.join(base,'sharing-progress.jsonl'),'',{flag:'wx'});
let parent=null,reused=0,snapshots=0,maxHeap=0;
for(let part=0;part<330;part++){
  const began=performance.now(),folder=path.join(source,`part${String(part).padStart(3,'0')}`);
  const compressed=await readFile(path.join(folder,'trajectory.json.gz'));
  const receipt=JSON.parse(await readFile(path.join(folder,'receipt.json')));
  assert.equal(sha(compressed),receipt.output_sha256['trajectory.json.gz']);
  const raw=JSON.parse(gunzipSync(compressed)),before=JSON.stringify(raw);
  const shared=shareTimeHistoryMetadata(raw,parent);
  assert.equal(JSON.stringify(shared),before,'Every exported field, value and property order: part '+part);
  assert.equal(JSON.stringify(raw),before,'Input was mutated: part '+part);
  // Check the actual standalone reader at both ends of every segment.
  for(const index of [0,16])assert.deepEqual(checkpointAt(shared,index),checkpointAt(raw,index));
  if(parent&&shared.restart_context===parent.restart_context)reused++;
  snapshots+=part?16:17;
  // Only keep metadata plus the last state for the next sharing operation.
  parent={restart_context:shared.restart_context,snapshots:[shared.snapshots.at(-1)]};
  const seconds=(performance.now()-began)/1000;assert.ok(seconds<45);
  maxHeap=Math.max(maxHeap,process.memoryUsage().heapUsed);
  const report={part,snapshots,seconds,original_file_sha256:sha(compressed),serialized_result_sha256:sha(before),exact_result_equal:true,standalone_checkpoints_equal:2};reports.push(report);
  await appendFile(path.join(base,'sharing-progress.jsonl'),JSON.stringify(report)+'\n');
  if((part+1)%32===0||part===329)console.log(JSON.stringify({part,snapshots,seconds,reused_contexts:reused}));
}
for(const [p,h]of Object.entries(pins))assert.equal(sha(await readFile(path.join(root,p))),h,'Source changed during verification');
assert.equal(snapshots,5281);assert.ok(reused>0);
const report={passed:true,scope:'Every retained segment and endpoint checkpoint compared exactly; this is not a full-history UI memory or durable-save test.',segments:330,unique_snapshots:snapshots,serialized_snapshots_including_joins:330*17,standalone_checkpoints_compared:660,consecutive_root_context_identity_reuses:reused,sampled_max_heap_bytes:maxHeap,process_peak_RSS_kib:process.resourceUsage().maxRSS,max_segment_seconds:Math.max(...reports.map(r=>r.seconds)),wall_seconds:(performance.now()-started)/1000,source_sha256:pins,segments_evidence:reports,numerical_reexecution:false,production_solver_changed:false,full_history_UI_validation:false,full_goal_complete:false};
await writeFile(path.join(base,'sharing.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({passed:true,segments:330,unique_snapshots:snapshots,standalone_checkpoints_compared:660,reused_contexts:reused,wall_seconds:report.wall_seconds}));
