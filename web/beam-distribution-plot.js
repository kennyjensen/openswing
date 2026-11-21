const escape=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');

export function beamPlotControls({prefix,quantityOptions,extraControls=''}){
  return `<div class="beam-distribution-toolbar">
    <label>Beam<select id="${prefix}-beam" aria-label="Beam"></select></label>
    <label>Property<select id="${prefix}-quantity" aria-label="Property">${quantityOptions}</select></label>
    ${extraControls}
  </div>
  <div class="beam-distribution-heading"><strong id="${prefix}-title"></strong><span id="${prefix}-unit"></span></div>`;
}

// All span properties use the same axes and sample styling. Section averages retain
// their element extents; impulses and missing values keep their own meaning.
export function beamValueAt(samples,t,kind='curve'){
  const finite=p=>Number.isFinite(p?.t)&&Number.isFinite(p.value);
  if(kind==='impulses'){
    const valid=samples.filter(finite);
    return valid.length?valid.reduce((a,b)=>Math.abs(a.t-t)<=Math.abs(b.t-t)?a:b):null;
  }
  if(kind==='sections'){
    const section=samples.find(p=>t>=Math.min(p.t0,p.t1)&&t<=Math.max(p.t0,p.t1));
    return finite(section)?{t,value:section.value}:null;
  }
  const exact=samples.find(p=>p.t===t);
  if(exact)return finite(exact)?{t,value:exact.value}:null;
  for(let i=1;i<samples.length;i++){
    const a=samples[i-1],b=samples[i];
    if(t>Math.min(a.t,b.t)&&t<Math.max(a.t,b.t))return finite(a)&&finite(b)?{t,value:a.value+(b.value-a.value)*(t-a.t)/(b.t-a.t)}:null;
  }
  return null;
}

const cursors=new WeakMap();
export function renderBeamDistribution(target,samples,{kind='curve',label='Beam property distribution',domain=null,unit='',range=null,hoverKey=null,emptyMessage='No values available for this property.'}={}){
  target.className='plot-chart';
  target.onpointermove=target.onpointerdown=target.onpointerleave=target.onpointercancel=null;
  const valid=samples.filter(p=>Number.isFinite(p.t)&&Number.isFinite(p.value));
  if(!valid.length){cursors.delete(target);target.textContent=emptyMessage;return;}
  const coordinates=domain??samples.flatMap(p=>kind==='sections'?[p.t0,p.t1]:[p.t]);
  const xs=coordinates.filter(Number.isFinite),xmin=Math.min(...xs),xmax=Math.max(...xs);
  const fixed=range?.length===2&&range.every(Number.isFinite)&&range[0]<=range[1];
  let ymin=Math.min(0,...(fixed?range:valid.map(p=>p.value))),ymax=Math.max(0,...(fixed?range:valid.map(p=>p.value)));
  const pad=(ymax-ymin||1)*.12;ymin-=pad;ymax+=pad;
  const width=Math.max(320,target.clientWidth||770),left=72,right=width-20;
  const X=x=>left+(x-xmin)/(xmax-xmin||1)*(right-left),Y=y=>180-(y-ymin)/(ymax-ymin)*160;
  const fmt=x=>x===0?'0':Number(x.toPrecision(3)).toString();
  let svg=`<svg viewBox="0 0 ${width} 215" role="img" aria-label="${escape(label)}" data-y-min="${ymin}" data-y-max="${ymax}">`;
  for(let i=0;i<5;i++){
    const y=ymin+(ymax-ymin)*i/4,x=xmin+(xmax-xmin)*i/4;
    svg+=`<path d="M${left} ${Y(y)}H${right}" class="plot-grid"/><text x="62" y="${Y(y)+4}" text-anchor="end">${fmt(Math.abs(y)<(ymax-ymin)*1e-10?0:y)}</text><text x="${X(x)}" y="205" text-anchor="middle">${fmt(x)}</text>`;
  }
  svg+=`<path d="M${left} ${Y(0)}H${right}" class="plot-zero"/>`;
  if(kind==='curve'){
    let path='',drawing=false;
    for(const p of samples){
      if(!Number.isFinite(p.t)||!Number.isFinite(p.value)){drawing=false;continue;}
      path+=`${drawing?'L':'M'}${X(p.t)} ${Y(p.value)} `;drawing=true;
    }
    svg+=`<path d="${path}" class="plot-line"/>`;
  }
  for(const p of valid){
    if(kind==='sections'&&Number.isFinite(p.t0)&&Number.isFinite(p.t1))svg+=`<path d="M${X(p.t0)} ${Y(p.value)}H${X(p.t1)}" class="section-segment"/>`;
    if(kind==='impulses')svg+=`<path d="M${X(p.t)} ${Y(0)}V${Y(p.value)}" class="plot-line"/>`;
    svg+=`<circle cx="${X(p.t)}" cy="${Y(p.value)}" r="3" class="${p.stalled?'distribution-stalled':'section-point'}"><title>t=${p.t.toPrecision(6)}; value=${p.value.toPrecision(7)}</title></circle>`;
  }
  target.innerHTML=svg+'<g class="beam-hover" visibility="hidden" pointer-events="none"><path/><circle r="4"/><rect height="24" rx="3"/><text/></g></svg>';
  const chart=target.querySelector?.('svg'),hover=chart?.querySelector('.beam-hover');
  if(!hover)return;
  const line=hover.querySelector('path'),dot=hover.querySelector('circle'),box=hover.querySelector('rect'),text=hover.querySelector('text');
  const key=hoverKey??`${kind}:${label}:${unit}:${xmin}:${xmax}`;
  const hide=()=>{cursors.delete(target);hover.setAttribute('visibility','hidden');};
  const persistent=event=>event?.pointerType==='touch'||event?.pointerType==='pen';
  const show=t=>{
    const sample=beamValueAt(samples,t,kind),x=X(t);
    const number=value=>Number(value.toPrecision(6)).toString();
    text.textContent=`t = ${number(sample?.t??t)} · ${sample?number(sample.value)+(unit?' '+unit:''):'—'}`;
    line.setAttribute('d',`M${x} 20V180`);
    dot.setAttribute('visibility',sample?'visible':'hidden');
    if(sample){dot.setAttribute('cx',X(sample.t));dot.setAttribute('cy',Y(sample.value));}
    const boxWidth=text.getComputedTextLength()+16,boxX=Math.max(4,Math.min(x+10,width-4-boxWidth));
    box.setAttribute('width',boxWidth);box.setAttribute('x',boxX);box.setAttribute('y',24);
    text.setAttribute('x',boxX+8);text.setAttribute('y',40);
    hover.setAttribute('visibility','visible');
  };
  const previous=cursors.get(target);
  if(previous?.key===key&&previous.t>=xmin&&previous.t<=xmax)show(previous.t);
  else cursors.delete(target);
  const move=event=>{
    const matrix=chart.getScreenCTM();if(!matrix)return;
    const pointer=chart.createSVGPoint();pointer.x=event.clientX;pointer.y=event.clientY;
    const point=pointer.matrixTransform(matrix.inverse());
    if(point.x<left||point.x>right||point.y<20||point.y>180){if(!persistent(event))hide();return;}
    const t=xmin+(point.x-left)/(right-left)*(xmax-xmin);
    cursors.set(target,{key,t});show(t);
  };
  target.onpointermove=target.onpointerdown=move;
  target.onpointerleave=target.onpointercancel=event=>{if(!persistent(event))hide();};
}
