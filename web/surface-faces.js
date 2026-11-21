// ASW chord is measured in the beam-normal airfoil plane, not along body x.
// Keep those section coordinates intact. At an automatically mirrored root,
// trim only the displayed skin to the bisector of the adjoining beam axes.
// Recompute the plane from current coordinates so body/Earth views and mode
// playback agree. Do not clip or retopologize the solver's saved geometry.
const sub=(a,b)=>a.map((v,i)=>v-b[i]);
const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
const unit=a=>{const n=Math.hypot(...a);return n>0?a.map(v=>v/n):null;};

export function surfaceFaces(beam,{streamwise=false}={}) {
  if(streamwise && beam.lifting && beam.streamwise_quads)return beam.streamwise_quads;
  const {quads,axis,mirror_join:join}=beam;
  if(!beam.lifting || !Number.isInteger(join) || join<1 || join>=axis.length || quads.length!==axis.length)return quads;
  const left=axis[join-1],right=axis[join];
  const a=unit(sub(left[1],left[0])),b=unit(sub(right[1],right[0]));
  if(!a || !b)return quads;
  const normal=unit(a.map((v,i)=>v+b[i]));
  if(!normal)return quads;
  const origin=left[1],scale=Math.max(Math.hypot(...sub(left[1],left[0])),Math.hypot(...sub(right[1],right[0])),
    ...[quads[join-1],quads[join]].map(q=>Math.hypot(...sub(q[3],q[0]))));
  const tolerance=1e-10*scale;
  // Separate root nodes must remain separate (e.g. an opened joint).
  if(Math.hypot(...sub(origin,right[0]))>tolerance)return quads;
  const faces=quads.slice();
  for(const side of [-1,1]) {
    for(let i=side<0?join-1:join;i>=0&&i<quads.length;i+=side) {
      const q=quads[i],d=q.map(p=>side*dot(sub(p,origin),normal));
      // Only trim the connected root region, not a distant folded wingtip.
      if(d.every(v=>v>=-tolerance))break;
      const clipped=[];
      for(let k=0;k<q.length;k++) {
        const next=(k+1)%q.length,p=q[k],r=q[next],inside=d[k]>=0;
        if(inside)clipped.push(p);
        if(inside!==(d[next]>=0)) {
          const fraction=d[k]/(d[k]-d[next]);
          clipped.push(p.map((v,j)=>v+fraction*(r[j]-v)));
        }
      }
      const unique=clipped.filter((p,k)=>Math.hypot(...sub(p,clipped[(k+clipped.length-1)%clipped.length]))>tolerance);
      faces[i]=unique.length>=3?unique:[];
    }
  }
  return faces.filter(q=>q.length>=3);
}
