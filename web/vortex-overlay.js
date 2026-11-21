export const vortexColors={bound:'#67e8f9',wake:'#a5b4fc',imageBound:'#fbbf24',imageWake:'#fb7185'};

// Wake legs are semi-infinite in the solver; truncate only the drawing.
export function vortexOverlay(data,length,frame=null,ground=null) {
  const transform=p=>frame?frame.body_to_earth.map((row,i)=>frame.position_earth[i]+row.reduce((s,r,j)=>s+r*p[j],0)):p.slice();
  function lines(segments,direction,image=false) {
    const bound=segments.map(s=>s.map(transform));
    const wake=segments.flatMap(segment=>segment.map(p=>[transform(p),transform(p.map((v,i)=>v+length*direction[i]))]));
    return [{kind:image?'vortex-image-bound':'vortex-bound',overlay:true,color:image?vortexColors.imageBound:vortexColors.bound,segments:bound},
      {kind:image?'vortex-image-wake':'vortex-wake',overlay:true,color:image?vortexColors.imageWake:vortexColors.wake,segments:wake}];
  }
  const result=lines(data.bound_segments,data.wake_direction);
  if(ground?.flag) {
    // The report's plane is in body axes, including for Earth-view snapshots.
    // Reflect the complete path before applying the display-frame transform.
    const n=ground.normal_body,dot=p=>p.reduce((sum,v,i)=>sum+v*n[i],0);
    const reflectPoint=p=>p.map((v,i)=>v-2*(dot(p)+ground.offset)*n[i]);
    const direction=data.wake_direction.map((v,i)=>v-2*dot(data.wake_direction)*n[i]);
    result.push(...lines(data.bound_segments.map(s=>s.map(reflectPoint)),direction,true));
  }
  return result;
}
