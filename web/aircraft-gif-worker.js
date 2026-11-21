import {createAircraftGif} from './aircraft-gif.js';
let encoder=null;
self.onmessage=({data})=>{
  const {id,action}=data;
  try{
    if(action==='start'){
      encoder=null;self.postMessage({id});
    }else if(action==='frame'){
      encoder??=createAircraftGif(data.width,data.height);
      encoder.frame(new Uint8Array(data.rgba),data.time);
      self.postMessage({id});
    }else if(action==='finish'){
      if(!encoder)throw new Error('No animation frames to download.');
      const bytes=encoder.finish(data.time);encoder=null;
      self.postMessage({id,bytes},[bytes.buffer]);
    }else throw new Error('Unknown image export request.');
  }catch(error){encoder=null;self.postMessage({id,error:error.message});}
};
