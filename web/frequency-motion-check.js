// Independent output check for a stationary reference frame. Remove elastic
// body-view displacement from Earth-view displacement, then recover the rigid
// infinitesimal rotation of the frame. No saved attitude/rate perturbations
// enter the reconstruction. Rates are compared only after differentiating it.
export function frameMotionRateCheck(result,point,input=0){
  const base=result?.base,frame=base?.modal_base,output=point?.responses?.[input]?.output;
  if(result?.inputs?.[input]?.kind==='initial'||frame?.kinematically_steady!==true)return null;
  const R=frame.body_to_earth,omega=point?.omega;
  if(!Array.isArray(R)||R.length!==3||!R.every(r=>Array.isArray(r)&&r.length===3&&r.every(Number.isFinite))||!Number.isFinite(omega))return null;
  const stationary=frame.attitude_rates_rad;
  if(!Array.isArray(stationary)||stationary.length!==3||stationary.some(v=>!Number.isFinite(v)||Math.abs(v)>1e-12))return null;
  const rows=[],body=new Map((output?.geometry??[]).map(b=>[b.index,b])),earth=new Map((output?.earth_geometry??[]).map(b=>[b.index,b]));
  const vector=v=>Array.isArray(v)&&v.length===3&&v.every(Number.isFinite);
  function collect(p,br,bi,er,ei){
    if(vector(p)){
      if(![br,bi,er,ei].every(vector))return false;
      // R maps body to Earth, so apply R transpose to the Earth perturbation.
      const transform=(e,b)=>b.map((v,j)=>R.reduce((s,row,k)=>s+row[j]*e[k],0)-v);
      rows.push([p,transform(er,br),transform(ei,bi)]);return true;
    }
    if(!Array.isArray(p)||![br,bi,er,ei].every(v=>Array.isArray(v)&&v.length===p.length))return false;
    return p.every((v,k)=>collect(v,br[k],bi[k],er[k],ei[k]));
  }
  for(const beam of base.geometry??[]){
    const b=body.get(beam.index),e=earth.get(beam.index);
    for(const key of ['axis','quads']){
      if(!beam[key]?.length)continue;
      if(!collect(beam[key],b?.[key]?.real,b?.[key]?.imag,e?.[key]?.real,e?.[key]?.imag))return null;
    }
  }
  if(rows.length<3)return null;
  // Center points and displacements to remove arbitrary frame translation.
  const mean=[0,1,2].map(k=>[0,1,2].map(j=>rows.reduce((s,r)=>s+r[k][j],0)/rows.length));
  const H=Array.from({length:3},()=>[0,0,0]),rhs=[[0,0,0],[0,0,0]];
  const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
  for(const row of rows){
    const p=row[0].map((v,j)=>v-mean[0][j]),p2=p.reduce((s,v)=>s+v*v,0);
    for(let j=0;j<3;j++)for(let k=0;k<3;k++)H[j][k]+=(j===k?p2:0)-p[j]*p[k];
    for(let part=0;part<2;part++){
      const c=cross(p,row[part+1].map((v,j)=>v-mean[part+1][j]));
      c.forEach((v,j)=>rhs[part][j]+=v);
    }
  }
  const size=Math.max(...H.flat().map(Math.abs));if(!(size>0))return null;
  const a=H.map((r,j)=>[...r.map(v=>v/size),rhs[0][j]/size,rhs[1][j]/size]);
  for(let j=0;j<3;j++){
    let pivot=j;for(let k=j+1;k<3;k++)if(Math.abs(a[k][j])>Math.abs(a[pivot][j]))pivot=k;
    if(Math.abs(a[pivot][j])<1e-10)return null; // No unique 3D orientation.
    [a[j],a[pivot]]=[a[pivot],a[j]];
    const d=a[j][j];a[j]=a[j].map(v=>v/d);
    for(let k=0;k<3;k++)if(k!==j){const f=a[k][j];a[k]=a[k].map((v,i)=>v-f*a[j][i]);}
  }
  const rotation=[a.map(r=>r[3]),a.map(r=>r[4])];
  let defect2=0,signal2=0;
  for(const row of rows){
    const p=row[0].map((v,j)=>v-mean[0][j]);
    for(let part=0;part<2;part++){
      const fitted=cross(rotation[part],p);
      row[part+1].forEach((v,j)=>{const delta=v-mean[part+1][j];defect2+=(delta-fitted[j])**2;signal2+=delta**2;});
    }
  }
  const rmsDefect=Math.sqrt(defect2/(6*rows.length)),relativeDefect=Math.sqrt(defect2/Math.max(signal2,1e-30));
  // Inconsistent geometry must not be presented as agreement with a rate.
  if(relativeDefect>1e-4&&rmsDefect>1e-9*Math.sqrt(size/rows.length))return null;
  const rates={real:rotation[1].map(v=>-omega*v),imag:rotation[0].map(v=>omega*v)};
  return {rates,points:rows.length,relativeDefect,rmsDefect};
}

export function yawMotionCheckText(result,point,input,plotted,unit,scale=1){
  const check=frameMotionRateCheck(result,point,input);
  if(!check||![plotted?.real,plotted?.imag].every(Number.isFinite))return '';
  const fromMotion=Math.hypot(check.rates.real[2],check.rates.imag[2]),fromPlot=Math.hypot(plotted.real,plotted.imag);
  const mismatch=Math.hypot(check.rates.real[2]-plotted.real,check.rates.imag[2]-plotted.imag);
  const number=v=>Number(v.toPrecision(6)).toString();
  const agreement=mismatch<=1e-6*Math.max(fromMotion,fromPlot)+1e-10;
  return `Yaw-rate check, per unit input: plot ${number(fromPlot*scale)}, reconstructed from Earth-view motion ${number(fromMotion*scale)} [${unit}]. ${agreement?'Consistent complex rates.':'The complex rates differ; save this computed solution for diagnosis.'} Elastic motion is removed from this aircraft-frame comparison.`;
}
