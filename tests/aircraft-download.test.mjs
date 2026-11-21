import {test} from 'node:test';
import assert from 'node:assert/strict';
import {aircraftPDF} from '../web/aircraft-pdf.js';
import {createAircraftGif} from '../web/aircraft-gif.js';
import {captureSize,copyViewerFrame} from '../web/viewer-capture.js';
import {createAircraftDownload,recordingDuration} from '../web/aircraft-download.js';

const binary=bytes=>Array.from(bytes,c=>String.fromCharCode(c)).join('');
const jpeg=new Uint8Array([255,216,255,224,0,4,128,255,255,217]);
test('PDF embeds exact JPEG bytes with valid binary offsets and matching page proportions',()=>{
  const bytes=aircraftPDF(jpeg,640,320),text=binary(bytes);
  assert.ok(text.startsWith('%PDF-1.4'));
  assert.ok(text.includes('/MediaBox [0 0 480 240]'));
  const imageStart=text.indexOf('stream\n')+7;
  assert.deepEqual(bytes.slice(imageStart,imageStart+jpeg.length),jpeg);
  const xref=Number(text.match(/startxref\n(\d+)/)[1]);
  assert.equal(text.slice(xref,xref+4),'xref');
  const entries=text.slice(xref).split('\n').slice(3,8);
  entries.forEach((entry,i)=>assert.ok(text.slice(Number(entry.slice(0,10))).startsWith(`${i+1} 0 obj\n`)));
  assert.throws(()=>aircraftPDF(new Uint8Array(4),10,10),/JPEG/);
});

test('capture preserves aspect ratio and letterboxes resizing during an animation',()=>{
  assert.deepEqual(captureSize(1920,1080,640),{width:640,height:360});
  assert.deepEqual(captureSize(200,400,640),{width:200,height:400});
  assert.throws(()=>captureSize(0,0),/not ready/);
  const draws=[],context={fillRect(){},drawImage(...args){draws.push(args);}};
  const canvas={getContext:()=>context};
  const source={width:1280,height:640};copyViewerFrame(source,canvas,{maxSize:640});
  assert.deepEqual([canvas.width,canvas.height],[640,320]);
  source.width=640;source.height=1280;copyViewerFrame(source,canvas,{resize:false});
  assert.deepEqual(draws[1].slice(1),[240,0,160,320]);
});

test('GIF encoder accepts successive frames, bounds storage and rejects malformed data',()=>{
  const rgba=new Uint8Array([255,0,0,255,0,255,0,255]);
  const encoder=createAircraftGif(2,1);encoder.frame(rgba,0);encoder.frame(rgba.slice().reverse(),40);
  const bytes=encoder.finish(100);
  assert.equal(binary(bytes.slice(0,6)),'GIF89a');assert.equal(bytes.at(-1),59);
  assert.ok(binary(bytes).includes('NETSCAPE2.0'));
  assert.throws(()=>encoder.frame(rgba,100),/complete/);
  assert.throws(()=>createAircraftGif(641,1),/size/);
  const invalid=createAircraftGif(2,1);assert.throws(()=>invalid.frame(new Uint8Array(4),0),/frame/);
  const limited=createAircraftGif(2,1,{maxBytes:1});limited.frame(rgba,0);assert.throws(()=>limited.finish(100),/size limit/);
  assert.equal(recordingDuration({durationMs:100000}),10000);
  assert.equal(recordingDuration({durationMs:100,periodic:true}),1000);
  assert.equal(recordingDuration({durationMs:1250,periodic:true}),1250);
});

function fixture({playing=false,holdImage=false,holdFrame=false,failWorker=false}={}){
  const previous=Object.fromEntries(['document','Worker'].map(key=>[key,globalThis[key]]));
  const downloads=[],errors=[],workers=[];let context={},captureCount=0,release;
  const button={innerHTML:'download icon',setAttribute(){},removeAttribute(){}};
  const canvas={width:0,height:0,getContext:()=>({getImageData:()=>({data:new Uint8ClampedArray([255,0,0,255,0,255,0,255])})}),toBlob(callback){
    release=()=>callback({arrayBuffer:async()=>jpeg.buffer});if(!holdImage)release();
  }};
  class Worker {
    constructor(){workers.push(this);this.inflight=0;}
    postMessage(message){
      assert.equal(this.inflight++,0);
      if(holdFrame&&message.action==='frame')return;
      Promise.resolve().then(()=>{
        this.inflight--;if(this.terminated)return;
        this.onmessage({data:{id:message.id,...(failWorker?{error:'Encoding failed'}:message.action==='finish'?{bytes:new Uint8Array([71,73,70])}:{})}});
      });
    }
    terminate(){this.terminated=true;}
  }
  Object.assign(globalThis,{Worker,document:{hidden:false,createElement:()=>canvas}});
  const view=createAircraftDownload({button,viewer:{capture(target){captureCount++;target.width=2;target.height=1;}},
    available:()=>true,getContext:()=>context,getPlayback:()=>({playing,durationMs:100}),filename:()=> 'dae.asw',
    download:(...args)=>downloads.push(args),showError:error=>errors.push(error)});
  return {view,button,canvas,downloads,errors,workers,captures:()=>captureCount,release:()=>release(),changeContext:()=>context={},
    restore(){for(const [key,value] of Object.entries(previous))if(value===undefined)delete globalThis[key];else globalThis[key]=value;}};
}

test('a paused view downloads PDF without starting a GIF worker',async()=>{
  const f=fixture();try{
    await f.button.onclick();assert.equal(f.downloads.length,1);assert.equal(f.downloads[0][0],'dae-aircraft.pdf');
    assert.equal(f.downloads[0][2],'application/pdf');assert.equal(f.workers.length,0);assert.equal(f.errors.length,0);
    assert.equal(f.canvas.width,0);assert.equal(f.button.innerHTML,'download icon');
  }finally{f.restore();}
});
test('cancelling an image or replacing the model prevents a stale download',async()=>{
  for(const cancel of [true,false]){
    const f=fixture({holdImage:true});try{
      const pending=f.button.onclick();if(cancel)await f.button.onclick();else f.changeContext();f.release();await pending;
      assert.equal(f.downloads.length,0);assert.equal(f.errors.length,0);assert.equal(f.canvas.width,0);
    }finally{f.restore();}
  }
});
test('playing view uses serial worker frames and cleans up after export or error',async()=>{
  for(const failWorker of [false,true]){
    const f=fixture({playing:true,failWorker});try{
      await f.button.onclick();assert.equal(f.workers.length,1);assert.equal(f.workers[0].terminated,true);
      assert.equal(f.canvas.width,0);
      if(failWorker){assert.equal(f.errors.length,1);assert.equal(f.downloads.length,0);}
      else {assert.ok(f.captures()>=2);assert.equal(f.errors.length,0);assert.equal(f.downloads[0][0],'dae-aircraft.gif');assert.equal(f.downloads[0][2],'image/gif');}
    }finally{f.restore();}
  }
});
test('cancelling a GIF terminates its worker while a frame is pending',async()=>{
  const f=fixture({playing:true,holdFrame:true});try{
    const pending=f.button.onclick();
    for(let i=0;i<10&&!f.captures();i++)await Promise.resolve();
    assert.equal(f.captures(),1);await f.button.onclick();await pending;
    assert.equal(f.workers[0].terminated,true);assert.equal(f.downloads.length,0);assert.equal(f.errors.length,0);
    assert.equal(f.canvas.width,0);
  }finally{f.restore();}
});
