// Display-only counterpart of beam_spline.py. The worker still validates and
// serializes every completed edit; this keeps the curve attached while dragging.
export function distributionSegments(points,report,policy='natural-v1') {
  if(points.some(row=>row.some(v=>String(v).trim()===''||!Number.isFinite(Number(v)))))return [];
  const rows=points.map(row=>row.map(Number));
  if(rows.length===1&&report.rigid_zero&&rows[0][1]===0)return [{t:report.domain,values:[0,0],extrapolated:false}];
  if(rows.length<2)return [];
  if(rows[0][0]>rows.at(-1)[0])rows.reverse();
  if(rows.some((r,i)=>i&&r[0]<rows[i-1][0]))return [];
  const groups=[[]];
  rows.forEach((row,i)=>{if(i&&row[0]===rows[i-1][0])groups.push([]);groups.at(-1).push(row);});
  if(groups.some(g=>g.length<2))return [];
  const splines=groups.map(g=>{
    const n=g.length,h=g.slice(1).map((r,i)=>r[0]-g[i][0]),d=h.map((v,i)=>(g[i+1][1]-g[i][1])/v);
    const a=Array(n).fill(0),b=Array(n).fill(0),c=Array(n).fill(0),r=Array(n).fill(0);
    const natural=policy==='natural-v1';
    b[0]=b[n-1]=natural?2:1;c[0]=a[n-1]=1;r[0]=(natural?3:2)*d[0];r[n-1]=(natural?3:2)*d.at(-1);
    for(let i=1;i<n-1;i++){a[i]=h[i];b[i]=2*(h[i-1]+h[i]);c[i]=h[i-1];r[i]=3*(h[i]*d[i-1]+h[i-1]*d[i]);}
    let m;
    if(n===2)m=[d[0],d[0]];
    else{
      for(let i=1;i<n;i++){const f=a[i]/b[i-1];b[i]-=f*c[i-1];r[i]-=f*r[i-1];}
      m=Array(n);m[n-1]=r[n-1]/b[n-1];
      for(let i=n-2;i>=0;i--)m[i]=(r[i]-c[i]*m[i+1])/b[i];
    }
    return {left:g[0][0],value(x){
      let i=0;while(i<n-2&&x>g[i+1][0])i++;
      const u=(x-g[i][0])/h[i],u2=u*u,u3=u2*u;
      return (2*u3-3*u2+1)*g[i][1]+(u3-2*u2+u)*h[i]*m[i]+(-2*u3+3*u2)*g[i+1][1]+(u3-u2)*h[i]*m[i+1];
    }};
  });
  const mirror=report.mirrored&&rows[0][0]===0,[lo,hi]=report.domain;
  const knots=rows.map(r=>r[0]),breaks=groups.slice(1).map(g=>g[0][0]);
  const boundaries=[...new Set([lo,hi,...breaks,...(mirror?[0,...breaks.map(t=>-t)]:[])])].filter(t=>t>=lo&&t<=hi).sort((a,b)=>a-b);
  return boundaries.slice(1).map((right,j)=>{
    const left=boundaries[j],sampleKnots=mirror?[...knots,...knots.map(t=>-t)]:knots;
    const t=[...new Set([...Array.from({length:81},(_,i)=>left+(right-left)*i/80),...sampleKnots.filter(x=>x>=left&&x<=right)])].sort((a,b)=>a-b);
    const middle=mirror?Math.abs((left+right)/2):(left+right)/2;
    let i=0;while(i<splines.length-1&&middle>=splines[i+1].left)i++;
    const query=t.map(x=>mirror?Math.abs(x):x),values=query.map(x=>splines[i].value(x));
    return {t,values,extrapolated:query.some(x=>x<knots[0]||x>knots.at(-1))};
  }).filter(s=>s.values.every(Number.isFinite));
}
