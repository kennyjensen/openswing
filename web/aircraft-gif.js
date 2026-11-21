import {GIFEncoder,quantize,applyPalette} from './vendor/gifenc/gifenc.esm.js';

// Retain only one indexed frame and the encoded stream. One global palette
// keeps the aircraft colors stable instead of requantizing every frame.
export function createAircraftGif(width,height,{maxBytes=16*1024*1024}={}){
  if(!Number.isInteger(width)||!Number.isInteger(height)||width<1||height<1||width>640||height>640)throw new Error('Invalid GIF frame size.');
  const gif=GIFEncoder();let palette=null,pending=null,lastTime=0,writtenTime=0,frames=0,finished=false;
  function write(time){
    if(!pending)return;
    const elapsed=time-lastTime;
    if(!Number.isFinite(elapsed)||elapsed<0)throw new Error('Invalid GIF frame timing.');
    // GIF delays are hundredths of a second. Carry rounding between frames.
    const delay=Math.max(20,Math.round((time-writtenTime)/10)*10);
    gif.writeFrame(pending,width,height,{...(frames===0?{palette}:{}),delay,repeat:0,dispose:1});
    writtenTime+=delay;frames++;
    if(gif.bytesView().length>maxBytes)throw new Error('GIF reached the size limit. Try a shorter recording.');
  }
  return {
    frame(rgba,time){
      if(finished)throw new Error('GIF recording is already complete.');
      if(rgba.length!==width*height*4||!Number.isFinite(time)||time<lastTime)throw new Error('Invalid GIF frame.');
      if(!palette){palette=quantize(rgba,256);writtenTime=time;}
      write(time);pending=applyPalette(rgba,palette);lastTime=time;
    },
    finish(time){
      if(finished||!pending)throw new Error('No animation frames to download.');
      write(time);finished=true;pending=null;gif.finish();
      return gif.bytes();
    },
  };
}
