// Keep at most one read in flight and the newest requested selection. The
// selected index changes only when its complete physical state is available.
export function createHistorySelection(commit){
  let generation=0,pending=null,running=false,latest=Promise.resolve(false);
  function cancel(){generation++;if(pending)pending.resolve(false);pending=null;}
  async function drain(){
    if(running)return;running=true;
    try{
      while(pending){
        const job=pending;pending=null;
        try{
          const snapshot=await job.source.read(job.index);
          if(job.generation===generation){job.source.pin(job.index,snapshot);commit(snapshot,job.index,job.fit);job.resolve(true);}
          else job.resolve(false);
        }catch(error){if(job.generation===generation)job.reject(error);else job.resolve(false);}
      }
    }finally{running=false;}
  }
  function select(source,index,fit=false){
    cancel();const token=generation;
    latest=new Promise((resolve,reject)=>{
      try{
        const snapshot=source.peek(index);
        if(snapshot){commit(snapshot,index,fit);resolve(true);return;}
        pending={source,index,fit,generation:token,resolve,reject};void drain();
      }catch(error){reject(error);}
    });
    return latest;
  }
  return {select,cancel,ready:()=>latest};
}
