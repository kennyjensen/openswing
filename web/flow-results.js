import { checkpointAt } from './time-checkpoint.js';
const $=id=>document.getElementById(id);
const fields=[['origin','Plane origin',[0,0,1]],['normal','Plane normal',[0,0,1]],['direction','In-plane u direction',[1,0,0]]];
const components=[['relative','Relative to rigid aircraft frame'],['air','Air relative to still atmosphere'],['gust','Gust'],['induced','All induced flow'],['lifting','Lifting vortices'],['volume','Bodies and point objects'],['jet','Propeller jets'],['kinematic','Rigid-frame kinematics']];
export const flowPane=`<div id="pane-flow" class="tab-pane flow-pane" role="tabpanel" aria-labelledby="tab-flow" hidden>
  <p id="flow-state" class="small muted">Run an aerodynamic analysis to survey its velocity field.</p>
  <details class="advanced" open><summary>Survey plane</summary>
    <label>Coordinate frame<select id="flow-frame"><option value="body">Body axes · x aft, y right, z up</option><option value="earth">Earth axes</option></select></label>
    ${fields.map(([key,label,defaults])=>`<p class="small muted">${label}${key==='origin'?' [input L]':''}</p><div class="fields motion-fields">${['x','y','z'].map((axis,i)=>`<label>${axis}<input id="flow-${key}-${axis}" type="number" step="any" value="${defaults[i]}"></label>`).join('')}</div>`).join('')}
    <p class="small muted">The u direction is projected into the plane and normalized. The v direction is normal × u. Bounds use distances from the origin in input length units.</p>
    <div class="fields">${[['u-min','u minimum',-2],['u-max','u maximum',8],['v-min','v minimum',-6],['v-max','v maximum',6],['nu','u samples',21],['nv','v samples',21]].map(([id,label,value])=>`<label>${label}<input id="flow-${id}" type="number" value="${value}" ${['nu','nv'].includes(id)?'min="2" max="99" step="1"':'step="any"'}></label>`).join('')}</div>
  </details>
  <div class="time-toolbar"><button id="flow-sample" disabled>Sample selected state</button><button id="flow-json" disabled>Field JSON</button><button id="flow-csv" disabled>Field CSV</button><button id="flow-svg" disabled>Plot SVG</button></div>
  <div class="fields"><label>Velocity contribution<select id="flow-component">${components.map(([key,label])=>`<option value="${key}">${label}</option>`).join('')}</select></label><label>Color quantity<select id="flow-color"><option value="speed">Vector magnitude</option><option value="normal">Normal component</option><option value="u">u component</option><option value="v">v component</option></select></label></div>
  <p id="flow-status" class="small muted" role="status">No field sampled.</p><div id="flow-plot"></div><p class="small muted flow-scroll-note">Scroll the plot horizontally to inspect it, or export the full SVG.</p>
  <p class="small muted">Arrows show in-plane velocity; color includes the selected component. Relative flow subtracts rigid flight-frame motion. It does not subtract an off-body elastic velocity. Air velocity is gust plus induced flow relative to the still atmosphere. Masked samples are inside circular body segments or beyond the ground plane.</p>
  <details><summary>Field assumptions</summary><p id="flow-limitations" class="small muted">Frozen straight wakes, current circulation and regularized external fields. A survey inspects a computed state without advancing time. Mode and Bode views survey their steady base.</p></details>
</div>`;
const fmt=x=>Number(x).toPrecision(4);
const esc=x=>String(x).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');

// Use the solved packet, including actual trim/controller settings and time-event side.
export function flowContext(state,index){
  const result=state.result;
  if(!result?.atmosphere||state.modal?.fluid?.kind==='quiescent'||result.fluid?.kind==='quiescent')return null;
  if(state.trajectory){const checkpoint=checkpointAt(state.trajectory,index);return {key:result,label:`Computed time state · t = ${fmt(checkpoint.state.time)} input T`,request:{action:'flow_survey',source:state.source,survey:{checkpoint}}};}
  const base=state.frequency?.base??state.modal?.base??result;
  const label=state.frequency?'Frequency-response steady base':state.modal?'Eigenmode steady base':'Steady state';
  if(base.equilibrium_state)return {key:base,label,request:{action:'flow_survey',source:state.source,survey:{equilibrium_state:base.equilibrium_state}}};
  if(result.request?.action==='solve'&&result.request.mode==='rigid')return {key:result,label:'Rigid steady state',request:{action:'flow_survey',source:result.request.source,panels:result.request.panels,survey:{condition:result.request.condition,circulation:result.strips.filter(s=>s.lifting).map(s=>s.circulation)}}};
  return null;
}

export function createFlowResults(getState,getIndex,rpc,download,showError){
  let data=null,identity=null,generation=0,busy=false,contextLabel='';
  function current(){return flowContext(getState(),getIndex());}
  function clear(){generation++;data=null;$('flow-plot').replaceChildren();$('flow-status').textContent='No field sampled for this state and plane.';for(const id of ['json','csv','svg'])$(`flow-${id}`).disabled=true;}
  function refresh(){const context=current();if(identity!==context?.key){identity=context?.key;clear();}
    $('flow-state').textContent=context?`${context.label}. Sampling uses its solved geometry, circulation and actuators.`:'Run an aerodynamic analysis to survey its velocity field. Structural-only states have no aerodynamic field.';
    $('flow-sample').disabled=busy||getState().busy||!context;$('flow-sample').textContent=busy?'Sampling…':'Sample selected state';}
  function draw(){
    if(!data)return;
    const component=$('flow-component').value,quantity=$('flow-color').value,values=data.plane_velocity[component],p=data.plane,[nu,nv]=p.counts;
    const scalar=v=>quantity==='speed'?Math.hypot(...v):v[{u:0,v:1,normal:2}[quantity]];
    const valid=values.filter((_,i)=>data.valid[i]),scalars=valid.map(scalar);
    let lo=quantity==='speed'?0:-Math.max(0,...scalars.map(Math.abs)),hi=Math.max(0,...scalars.map(Math.abs));
    if(hi===0){hi=1;lo=quantity==='speed'?0:-1;}
    const umax=p.u.at(-1),vmax=p.v.at(-1),du=umax-p.u[0],dv=vmax-p.v[0],scale=Math.min(620/du,370/dv),w=du*scale,h=dv*scale,x0=72+(620-w)/2,y0=60+(370-h)/2;
    const X=u=>x0+(u-p.u[0])*scale,Y=v=>y0+h-(v-p.v[0])*scale;
    const maxVector=Math.max(0,...valid.map(v=>Math.hypot(v[0],v[1]))),stride=Math.max(1,Math.ceil(Math.max(nu,nv)/25)),arrowScale=maxVector?Math.min(w/(nu-1),h/(nv-1))*stride*.78/maxVector:0;
    const color=value=>{const t=Math.max(0,Math.min(1,(value-lo)/(hi-lo)));return quantity==='speed'?`hsl(${210-165*t} 55% ${24+38*t}%)`:`hsl(${t<.5?210:25} 58% ${28+40*(1-Math.abs(2*t-1))}%)`;};
    let svg=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 530" role="img" aria-label="Velocity field on the selected plane"><title>${esc(contextLabel)} · ${esc(component)} · ${esc(quantity)}</title><rect width="800" height="530" fill="#111e22"/><defs><pattern id="flow-mask" width="6" height="6" patternUnits="userSpaceOnUse"><path d="M0 6L6 0" stroke="#5b6870"/></pattern><marker id="flow-arrow" markerWidth="4" markerHeight="4" refX="3" refY="2" orient="auto"><path d="M0 0L4 2L0 4Z" fill="#f1fff7"/></marker></defs><g fill="#c8dbd3" font-family="monospace" font-size="11"><text x="72" y="22">${esc(component)} · ${esc(quantity)} [input L/T] · ${esc(data.coordinates)} plane</text><text x="72" y="40">${esc(contextLabel)}</text>`;
    for(let j=0;j<nv;j++)for(let i=0;i<nu;i++){
      const k=j*nu+i,a=i?(p.u[i-1]+p.u[i])/2:p.u[0],b=i<nu-1?(p.u[i]+p.u[i+1])/2:umax,c=j?(p.v[j-1]+p.v[j])/2:p.v[0],d=j<nv-1?(p.v[j]+p.v[j+1])/2:vmax;
      svg+=`<rect x="${X(a)}" y="${Y(d)}" width="${(b-a)*scale+.05}" height="${(d-c)*scale+.05}" fill="${data.valid[k]?color(scalar(values[k])):'url(#flow-mask)'}"><title>u=${fmt(p.u[i])}, v=${fmt(p.v[j])}; ${data.valid[k]?`${quantity}=${fmt(scalar(values[k]))}`:'masked'}</title></rect>`;
    }
    for(let j=0;j<nv;j+=stride)for(let i=0;i<nu;i+=stride){const k=j*nu+i,v=values[k];if(data.valid[k]&&Math.hypot(v[0],v[1])>1e-14){const dx=v[0]*arrowScale,dy=-v[1]*arrowScale,x=X(p.u[i]),y=Y(p.v[j]);svg+=`<path d="M${x-dx/2} ${y-dy/2}l${dx} ${dy}" stroke="#f1fff7" stroke-width="1" marker-end="url(#flow-arrow)"/>`;}}
    for(let i=0;i<=4;i++){const u=p.u[0]+du*i/4,v=p.v[0]+dv*i/4;svg+=`<text x="${X(u)}" y="${y0+h+18}" text-anchor="middle">${fmt(u)}</text><text x="${x0-8}" y="${Y(v)+4}" text-anchor="end">${fmt(v)}</text>`;}
    svg+=`<rect x="${x0}" y="${y0}" width="${w}" height="${h}" fill="none" stroke="#75978c"/><text x="${x0+w/2}" y="${y0+h+37}" text-anchor="middle">u [input L]</text><text x="16" y="${y0+h/2}" transform="rotate(-90 16 ${y0+h/2})" text-anchor="middle">v [input L]</text>`;
    for(let i=0;i<100;i++)svg+=`<rect x="722" y="${430-i*3.7}" width="14" height="3.8" fill="${color(lo+(hi-lo)*i/99)}"/>`;
    svg+=`<text x="743" y="68">${fmt(hi)}</text><text x="743" y="432">${fmt(lo)}</text><text x="72" y="492">Arrows: maximum in-plane speed ${fmt(maxVector)} L/T; shared linear scale.</text><text x="72" y="513">${data.valid.filter(Boolean).length}/${values.length} fluid samples · hatched = masked</text></g></svg>`;
    $('flow-plot').innerHTML=svg;
  }
  $('flow-sample').onclick=async()=>{
    if(busy||getState().busy)return;
    const context=current();if(!context)return;
    const number=id=>{const input=$(`flow-${id}`);if(!input.value||!input.checkValidity())throw new Error('Enter finite plane vectors, increasing bounds and 2–99 samples per axis.');return Number(input.value);};
    try{
      const plane=Object.fromEntries(fields.map(([key])=>[key,['x','y','z'].map(a=>number(`${key}-${a}`))]));
      Object.assign(plane,{u:[number('u-min'),number('u-max')],v:[number('v-min'),number('v-max')],counts:[number('nu'),number('nv')]});
      const request=structuredClone(context.request);Object.assign(request.survey,{plane,coordinates:$('flow-frame').value});
      clear();const token=generation;busy=true;refresh();$('flow-status').textContent='Sampling the saved field…';
      const output=await rpc(request);
      if(token!==generation||current()?.key!==context.key)return;
      contextLabel=context.label;data={...output,request,context:contextLabel};
      $('flow-status').textContent=`${contextLabel} · ${plane.counts.join(' × ')} samples · t = ${fmt(data.time)} input T. Component and color controls reuse these samples.`;
      $('flow-limitations').textContent=data.limitations.join(' ');for(const id of ['json','csv','svg'])$(`flow-${id}`).disabled=false;draw();
    }catch(error){$('flow-status').textContent='Field sampling failed.';showError(error);}finally{busy=false;refresh();}
  };
  for(const input of document.querySelectorAll('#pane-flow details.advanced input,#flow-frame'))input.addEventListener('change',clear);
  $('flow-component').onchange=draw;$('flow-color').onchange=draw;
  $('flow-json').onclick=()=>{if(data)download('openswing-flow.json',JSON.stringify(data,null,2),'application/json');};
  $('flow-svg').onclick=()=>{if(data)download('openswing-flow.svg',$('flow-plot').innerHTML,'image/svg+xml');};
  $('flow-csv').onclick=()=>{if(!data)return;const keys=Object.keys(data.velocity),p=data.plane;
    const columns=['time_T','u_L','v_L','valid','inside_body','fluid_side',...['x','y','z'].map(a=>`${data.coordinates}_${a}_L`),...keys.flatMap(k=>['x','y','z'].map(a=>`${k}_${data.coordinates}_${a}_L_per_T`)),...keys.flatMap(k=>['u','v','normal'].map(a=>`${k}_${a}_L_per_T`))];
    const rows=data.position.map((r,i)=>[data.time,p.u[i%p.counts[0]],p.v[Math.floor(i/p.counts[0])],Number(data.valid[i]),Number(data.inside_body[i]),Number(data.fluid_side[i]),...r,...keys.flatMap(k=>data.velocity[k][i]),...keys.flatMap(k=>data.plane_velocity[k][i])].join(','));
    download('openswing-flow.csv',[columns.join(','),...rows].join('\n')+'\n','text/csv');};
  return {refresh,capture:()=>data?structuredClone(data):null,restore(saved){
    if(!saved)return;data=structuredClone(saved);identity=current()?.key;contextLabel=data.context;
    $('flow-status').textContent=`Saved field · ${data.plane.counts.join(' × ')} samples · t = ${fmt(data.time)} input T.`;
    $('flow-limitations').textContent=data.limitations.join(' ');for(const id of ['json','csv','svg'])$(`flow-${id}`).disabled=false;draw();
  }};
}
