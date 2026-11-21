import {createTimeHistoryWriter} from './time-history-archive.js';
import {timeHistory} from './time-history-source.js';

// Export one batch at a time. The browser's File is passed directly to download;
// neither the original trajectory nor its compressed file becomes one string.
export async function exportTimeHistory(trajectory,{workbench=null,download,onProgress=()=>{},
  picker=globalThis.showSaveFilePicker?.bind(globalThis),storage=globalThis.navigator?.storage}={}){
  const source=timeHistory(trajectory),{snapshots:ignored,...metadata}=trajectory;
  if(metadata.request)metadata.request=JSON.parse(JSON.stringify(metadata.request));
  if(workbench)metadata.openswing_workbench=workbench;
  let handle,temporary=null,writer;
  if(picker)handle=await picker({suggestedName:'openswing-time.oswh',types:[{description:'OpenSwing complete time history',accept:{'application/octet-stream':['.oswh']}}]});
  else{
    if(!storage?.getDirectory)throw new Error('This browser cannot write a complete history archive. Export results remains available for smaller histories.');
    const directory=await(await storage.getDirectory()).getDirectoryHandle('openswing-temporary-exports',{create:true});
    // These are disposable download files, never project history records. Keep
    // recent files alive for downloads; clean only this export namespace.
    const now=Date.now();
    for await(const [name]of directory.entries()){
      const time=Number(name.split('-')[0]);
      if(Number.isFinite(time)&&time>0&&time<now-86400000)await directory.removeEntry(name).catch(()=>{});
    }
    const name=`${now}-${crypto.randomUUID()}.oswh`;
    handle=await directory.getFileHandle(name,{create:true});temporary={directory,name};
  }
  try{
    writer=await createTimeHistoryWriter(await handle.createWritable());let batch=[],done=0;
    for await(const snapshot of source.scan()){
      batch.push(snapshot);
      if(batch.length===16){await writer.append(batch);done+=batch.length;batch=[];onProgress(done,source.count);}
    }
    if(batch.length){await writer.append(batch);done+=batch.length;onProgress(done,source.count);}
    const summary=await writer.finish(metadata);
    if(temporary){
      if(typeof download!=='function')throw new Error('A history download handler is required.');
      download('openswing-time.oswh',await handle.getFile(),'application/octet-stream');
    }
    return summary;
  }catch(error){
    await writer?.abort().catch(()=>{});
    if(temporary)await temporary.directory.removeEntry(temporary.name).catch(()=>{});
    throw error;
  }
}
