// Physical image-plane grid, in the same body coordinates as the aircraft.
export function groundGrid(plane,center,extent) {
  if(!plane?.flag)return null;
  const n=plane.normal_body;
  const dot=(a,b)=>a.reduce((sum,x,i)=>sum+x*b[i],0);
  const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
  const u=cross(n,Math.abs(n[1])<.8?[0,1,0]:[1,0,0]);const length=Math.hypot(...u);u.forEach((x,i)=>u[i]=x/length);
  const v=cross(n,u),origin=center.map((x,i)=>x-(dot(center,n)+plane.offset)*n[i]);
  const point=(x,y)=>origin.map((a,i)=>a+extent*(x*u[i]+y*v[i]));
  const segments=[];
  for(let i=-10;i<=10;i++)segments.push([point(-1,i/10),point(1,i/10)],[point(i/10,-1),point(i/10,1)]);
  return {segments,color:plane.flag===1?'#756044':'#396c83'};
}
