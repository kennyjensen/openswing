// Standalone browser storage/codec check, not an integrated workbench UI test.
import assert from 'node:assert/strict';
import {readFile,writeFile,appendFile,stat} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {createServer} from 'node:http';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from '@playwright/test';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const base=path.join(root,'artifacts/isae/ua2-history-archive-20261102');
const archiveFile=path.join(base,'history.oswh'),reference=JSON.parse(await readFile(path.join(base,'archive.json')));
assert.equal(reference.passed,true);
const sha=b=>createHash('sha256').update(b).digest('hex'),pins={};
const modules=['time-history-archive.js','time-history-codec.js','time-result-storage.js','saved-state-data.js'];
for(const name of modules){const p='web/'+name;pins[p]=sha(await readFile(path.join(root,p)));assert.equal(pins[p],reference.source_sha256[p]);}
pins['scripts/test-isae-ua2-history-archive-browser.mjs']=sha(await readFile(fileURLToPath(import.meta.url)));
const size=(await stat(archiveFile)).size;assert.equal(size,reference.archive.bytes);
const fileDigest=createHash('sha256'),blocks=[];let fileOffset=0;
for await(const bytes of createReadStream(archiveFile,{highWaterMark:1024*1024})){
  fileDigest.update(bytes);blocks.push({offset:fileOffset,bytes:bytes.length,sha256:sha(bytes)});fileOffset+=bytes.length;
}
assert.equal(fileOffset,size);const inputArchiveSHA=fileDigest.digest('hex');
const started=performance.now(),errors=[],progress=[],directory='openswing-archive-check-'+crypto.randomUUID();
await writeFile(path.join(base,'browser-progress.jsonl'),'',{flag:'wx'});
const server=createServer(async(req,res)=>{
  try{
    if(req.url==='/'){res.setHeader('Content-Type','text/html');res.end('<!doctype html><title>OpenSwing history storage check</title><p>Serial retained-history storage validation.</p>');return;}
    if(req.url==='/history.oswh'){res.setHeader('Content-Length',size);res.setHeader('Content-Type','application/octet-stream');createReadStream(archiveFile).pipe(res);return;}
    const name=req.url?.startsWith('/web/')?req.url.slice(5):'';
    if(modules.includes(name)){res.setHeader('Content-Type','text/javascript');res.end(await readFile(path.join(root,'web',name)));return;}
    res.writeHead(404);res.end();
  }catch(error){res.writeHead(500);res.end(String(error));}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
let browser,page,timer,report;
try{
  browser=await chromium.launch({executablePath:path.join(root,'artifacts/isae/browser-libs-20261101/chromium/chrome-linux/chrome'),headless:true,timeout:45000,
    env:{...process.env,LP_NUM_THREADS:'1',LD_LIBRARY_PATH:[path.join(root,'artifacts/isae/browser-libs-20261101/lib'),process.env.LD_LIBRARY_PATH].filter(Boolean).join(':')},
    args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--enable-precise-memory-info','--js-flags=--max-old-space-size=192']});
  timer=setTimeout(()=>browser?.close().catch(()=>{}),600000);
  page=await browser.newPage();page.on('pageerror',error=>errors.push(error.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/`,{timeout:45000});
  const stored=await page.evaluate(async directory=>{
    const began=performance.now();
    const parent=await navigator.storage.getDirectory(),folder=await parent.getDirectoryHandle(directory,{create:true});
    const handle=await folder.getFileHandle('history.oswh',{create:true});
    const response=await fetch('/history.oswh');if(!response.ok)throw Error('Archive download failed');
    await response.body.pipeTo(await handle.createWritable());
    const file=await handle.getFile();return {bytes:file.size,copy_seconds:(performance.now()-began)/1000};
  },directory);
  assert.equal(stored.bytes,size);assert.ok(stored.copy_seconds<45);
  // Drop the download page and reopen the actual disk File in a new document.
  await page.reload({timeout:45000});
  const opened=await page.evaluate(async directory=>{
    const began=performance.now();
    const {openTimeHistoryArchive,createTimeHistoryWriter}=await import('/web/time-history-archive.js');
    const {encodeHistoryJSON}=await import('/web/time-history-codec.js');
    const {checkpointRecord}=await import('/web/saved-state-data.js');
    const parent=await navigator.storage.getDirectory(),folder=await parent.getDirectoryHandle(directory);
    const handle=await folder.getFileHandle('history.oswh'),file=await handle.getFile();
    const archive=await openTimeHistoryArchive(file);
    const hash=async value=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',encodeHistoryJSON(value))),x=>x.toString(16).padStart(2,'0')).join('');
    window.archiveCheck={archive,file,folder,hash,checkpointRecord,createTimeHistoryWriter,openTimeHistoryArchive};
    return {snapshots:archive.snapshotCount,chunks:archive.chunkCount,metadata_sha256:await hash(archive.metadata()),
      open_seconds:(performance.now()-began)/1000,statistics:archive.statistics,user_agent:navigator.userAgent};
  },directory);
  assert.equal(opened.snapshots,5281);assert.equal(opened.chunks,reference.archive.chunks);
  assert.equal(opened.metadata_sha256,reference.metadata_sha256);assert.equal(opened.statistics.recordsRead,1);
  assert.ok(opened.statistics.bytesRead<size/10,'Opening reads the index and metadata, not the physical history');
  // Independently verify every copied byte after reload, in bounded slices.
  // This binds the browser file to the exact artifact audited against the raws.
  for(let i=0;i<blocks.length;i+=16){
    const actual=await page.evaluate(async blocks=>{
      const output=[];for(const block of blocks){
        const bytes=await window.archiveCheck.file.slice(block.offset,block.offset+block.bytes).arrayBuffer();
        output.push(Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join(''));
      }return output;
    },blocks.slice(i,i+16));
    assert.deepEqual(actual,blocks.slice(i,i+16).map(block=>block.sha256));
  }
  // Each evaluation reads at most 16 physical states, with one decoded chunk
  // cached. The reader verifies every touched compressed record's checksum.
  const samples=new Map(reference.browser_samples.map(sample=>[sample.index,sample]));let maxHeap=0;
  for(let start=0;start<5281;start+=16){
    const result=await page.evaluate(async({start,indices})=>{
      const began=performance.now(),{archive,hash,checkpointRecord}=window.archiveCheck,selected=[];
      const context=archive.metadata().restart_context;
      for(let index=start;index<Math.min(start+16,archive.snapshotCount);index++){
        const snapshot=await archive.readSnapshot(index);
        if(indices.includes(index))selected.push({index,time:snapshot.time,snapshot_sha256:await hash(snapshot),
          checkpoint_sha256:await hash(checkpointRecord(snapshot.restart,snapshot.restart_context??context))});
      }
      return {start,end:Math.min(start+16,archive.snapshotCount),seconds:(performance.now()-began)/1000,
        selected,heap_bytes:performance.memory?.usedJSHeapSize??null,statistics:archive.statistics};
    },{start,indices:[...samples.keys()]});
    assert.ok(result.seconds<45);for(const sample of result.selected)assert.deepEqual(sample,samples.get(sample.index));
    maxHeap=Math.max(maxHeap,result.heap_bytes??0);progress.push(result);
    await appendFile(path.join(base,'browser-progress.jsonl'),JSON.stringify(result)+'\n');
    if(start%256===0||result.end===5281)console.log(JSON.stringify({end:result.end,seconds:result.seconds,heap_bytes:result.heap_bytes}));
  }
  const writerCheck=await page.evaluate(async()=>{
    const {archive,folder,createTimeHistoryWriter,openTimeHistoryArchive,hash}=window.archiveCheck;
    const snapshots=[];for(let i=0;i<3;i++)snapshots.push(await archive.readSnapshot(i));
    const handle=await folder.getFileHandle('written-in-browser.oswh',{create:true});
    const writer=await createTimeHistoryWriter(await handle.createWritable(),{chunkSize:2});
    await writer.append(snapshots);const written=await writer.finish(archive.metadata());
    const reopened=await openTimeHistoryArchive(await handle.getFile());
    for(let i=0;i<3;i++)if(await hash(await reopened.readSnapshot(i))!==await hash(snapshots[i]))throw Error('Browser writer changed snapshot '+i);
    return {...written,metadata_equal:await hash(reopened.metadata())===await hash(archive.metadata()),exact_states:3};
  });
  assert.equal(writerCheck.metadata_equal,true);assert.equal(writerCheck.exact_states,3);assert.deepEqual(errors,[]);
  for(const [p,hash]of Object.entries(pins))assert.equal(sha(await readFile(path.join(root,p))),hash);
  report={passed:true,scope:'Standalone Chromium codec and origin-private file persistence. Every physical chunk is read after page reload; 12 full-state/checkpoint hashes match the serial original-data audit. Not the workbench, project undo, or WASM solver.',
    archive_bytes:size,input_archive_sha256:inputArchiveSHA,persisted_bytes_verified:size,persisted_blocks_verified:blocks.length,
    original_data_audit_sha256:sha(await readFile(path.join(base,'archive.json'))),
    snapshots:5281,chunks:opened.chunks,full_state_and_checkpoint_hash_samples:samples.size,
    stored,opened,browser_writer:writerCheck,sampled_max_JS_heap_bytes:maxHeap,
    max_batch_seconds:Math.max(...progress.map(x=>x.seconds)),browser_version:browser.version(),page_errors:errors,
    source_sha256:pins,wall_seconds:(performance.now()-started)/1000,
    full_history_UI_validation:false,numerical_reexecution:false,native_ASWING_comparison:false,full_goal_complete:false};
}finally{
  if(page&&!page.isClosed())await page.evaluate(async directory=>{await(await navigator.storage.getDirectory()).removeEntry(directory,{recursive:true});},directory).catch(()=>{});
  if(timer)clearTimeout(timer);if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));
}
await writeFile(path.join(base,'browser.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({passed:true,snapshots:report.snapshots,archive_bytes:size,max_batch_seconds:report.max_batch_seconds,wall_seconds:report.wall_seconds}));
