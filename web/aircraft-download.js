import {aircraftPDF} from './aircraft-pdf.js';

const aborted=()=>new DOMException('Download cancelled.','AbortError');
export function recordingDuration(playback){
  let duration=Number.isFinite(playback.durationMs)&&playback.durationMs>0?playback.durationMs:4000;
  if(playback.periodic&&duration<1000)duration*=Math.ceil(1000/duration);
  return Math.max(100,Math.min(10000,duration));
}
function wait(milliseconds,signal){
  return new Promise((resolve,reject)=>{
    if(signal.aborted){reject(aborted());return;}
    const cancel=()=>{clearTimeout(timer);reject(aborted());};
    const timer=setTimeout(()=>{signal.removeEventListener('abort',cancel);resolve();},milliseconds);
    signal.addEventListener('abort',cancel,{once:true});
  });
}
function gifWorker(signal){
  const worker=new Worker(new URL('./aircraft-gif-worker.js',import.meta.url),{type:'module'});
  let serial=0,pending=null;
  const fail=error=>{if(pending){clearTimeout(pending.timer);pending.reject(error);pending=null;}};
  const cancel=()=>{fail(aborted());worker.terminate();};
  signal.addEventListener('abort',cancel,{once:true});
  worker.onmessage=({data})=>{
    if(data.id!==pending?.id)return;
    const task=pending;pending=null;clearTimeout(task.timer);
    if(data.error)task.reject(new Error(data.error));else task.resolve(data.bytes);
  };
  worker.onerror=event=>fail(new Error(event.message||'GIF encoding failed.'));
  return {
    send(message,transfer=[]){
      if(signal.aborted)return Promise.reject(aborted());
      return new Promise((resolve,reject)=>{
        const id=++serial;
        pending={id,resolve,reject,timer:setTimeout(()=>fail(new Error('GIF encoding timed out.')),15000)};
        try{worker.postMessage({id,...message},transfer);}catch(error){fail(error);}
      });
    },
    dispose(){signal.removeEventListener('abort',cancel);fail(aborted());worker.terminate();},
  };
}

export function createAircraftDownload({button,viewer,getPlayback,getContext,available,filename,download,showError}){
  const markup=button.innerHTML;
  let operation=null;
  function refresh(){
    button.disabled=!operation&&!available();
    if(operation)return;
    button.innerHTML=markup;
    button.title='Download view: PDF when paused, animated GIF during playback (up to 10 seconds)';
    button.setAttribute('aria-label',button.title);button.removeAttribute('aria-busy');
  }
  function progress(percent){
    button.textContent=`${percent}% ×`;
    button.title='Cancel aircraft download';
    button.setAttribute('aria-label',`Cancel aircraft download (${percent}%)`);button.setAttribute('aria-busy','true');
  }
  button.onclick=async()=>{
    if(operation){operation.abort();return;}
    if(!available())return;
    const controller=new AbortController(),signal=controller.signal;
    operation=controller;progress(0);
    const canvas=document.createElement('canvas'),context=getContext(),playback=getPlayback();
    let encoder=null;
    const check=()=>{if(signal.aborted||getContext()!==context||!available())throw aborted();};
    const name=filename().replace(/\.asw$/i,'').replace(/[\\/:*?"<>|]/g,'-')||'openswing';
    try{
      if(!playback.playing){
        viewer.capture(canvas,{maxSize:1600});
        const jpeg=await new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(new Error('The aircraft image could not be captured.')),'image/jpeg',.95));
        const bytes=new Uint8Array(await jpeg.arrayBuffer());check();
        download(`${name}-aircraft.pdf`,aircraftPDF(bytes,canvas.width,canvas.height),'application/pdf');
      }else{
        encoder=gifWorker(signal);
        await encoder.send({action:'start'});check();
        const duration=recordingDuration(playback),start=performance.now();let frames=0,last=0;
        while(true){
          check();
          if(document.hidden)throw new Error('Keep the aircraft view visible while recording a GIF.');
          const elapsed=performance.now()-start;
          if(frames&&elapsed>=duration)break;
          viewer.capture(canvas,{maxSize:640,resize:frames===0});
          const pixels=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
          last=elapsed;
          await encoder.send({action:'frame',width:canvas.width,height:canvas.height,rgba:pixels.buffer,time:elapsed},[pixels.buffer]);
          frames++;progress(Math.min(99,Math.round(100*(performance.now()-start)/duration)));
          if(!getPlayback().playing)break;
          const interval=Math.max(1000/25,duration/250);
          await wait(Math.max(0,Math.min(start+duration, start+elapsed+interval)-performance.now()),signal);
        }
        check();
        if(frames<2)throw new Error('The animation stopped before a GIF could be recorded. Press Play and try again.');
        const bytes=await encoder.send({action:'finish',time:Math.max(last+20,Math.min(performance.now()-start,duration))});check();
        download(`${name}-aircraft.gif`,bytes,'image/gif');
      }
    }catch(error){if(error.name!=='AbortError')showError(error);}
    finally{encoder?.dispose();canvas.width=canvas.height=0;operation=null;refresh();}
  };
  refresh();return {refresh,cancel:()=>operation?.abort()};
}
