export function captureSize(width,height,maxSize=1600){
  if(!(width>1&&height>1&&maxSize>1))throw new Error('The aircraft view is not ready to download.');
  const scale=Math.min(1,maxSize/Math.max(width,height));
  return {width:Math.max(1,Math.round(width*scale)),height:Math.max(1,Math.round(height*scale))};
}

// Copy immediately after drawing WebGL: its drawing buffer is not preserved
// between browser frames. Reuse one small canvas throughout a GIF recording.
export function copyViewerFrame(source,target,{maxSize=1600,resize=true}={}){
  const size=captureSize(source.width,source.height,maxSize);
  if(resize){target.width=size.width;target.height=size.height;}
  const ctx=target.getContext('2d',{alpha:false,willReadFrequently:true});
  if(!ctx)throw new Error('Image export is unavailable in this browser.');
  ctx.fillStyle='#131d20';ctx.fillRect(0,0,target.width,target.height);
  const scale=Math.min(target.width/source.width,target.height/source.height);
  const width=source.width*scale,height=source.height*scale;
  ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
  ctx.drawImage(source,(target.width-width)/2,(target.height-height)/2,width,height);
  return target;
}
