import {vortexColors} from './vortex-overlay.js';

export const failureColors={point:'#fb7185',receiver:'#fbbf24',...vortexColors};
const vector=p=>Array.isArray(p)&&p.length===3&&p.every(Number.isFinite);
const number=x=>Number.isFinite(x)?x.toPrecision(5):'—';
const rejectedSections=details=>(details.rejected_sections??[]).filter(s=>vector(s.position)&&s.normal_mach>=1);

// Source positions are already in physical body coordinates, including when
// the influences were frozen. Never apply a deformation or a PG map here.
export function failureOverlay(details,length=1) {
  if(details?.kind!=='section_normal_mach'||!vector(details.maximum?.position))return [];
  const span=Number.isFinite(length)&&length>0?length:1;
  const objects=[];
  const add=(kind,color,segments)=>{if(segments.length)objects.push({kind,color,segments,overlay:true});};
  const cross=(p,r)=>[0,1,2].map(i=>[-1,1].map(sign=>p.map((v,j)=>v+(j===i?sign*r:0))));
  const point=details.maximum.position,b=details.vortex_breakdown;
  const sections=rejectedSections(details);
  const same=(a,b)=>a.every((v,i)=>v===b[i]);
  const receivers=[];
  for(const s of sections) {
    if(vector(s.influence_position)&&!same(s.influence_position,s.position))receivers.push(s.influence_position);
  }
  if(b?.available&&b.axes==='body') {
    add('failure-bound',failureColors.bound,(b.bound_sources??[]).filter(s=>vector(s.start)&&vector(s.end)).map(s=>[s.start.slice(),s.end.slice()]));
    if(vector(b.direction)&&Math.hypot(...b.direction)>0) {
      const direction=b.direction.map(v=>v/Math.hypot(...b.direction));
      add('failure-wake',failureColors.wake,(b.wake_sources??[]).filter(s=>vector(s.origin)).map(s=>[s.origin.slice(),s.origin.map((v,i)=>v+span*direction[i])]));
    }
    if(vector(b.influence_receiver)&&b.influence_receiver.some((v,i)=>v!==point[i])) {
      if(!receivers.some(p=>same(p,b.influence_receiver)))receivers.push(b.influence_receiver);
    }
  }
  add('failure-receiver',failureColors.receiver,receivers.flatMap(p=>cross(p,span*.008)));
  add('failure-point',failureColors.point,[...cross(point,span*.012),
    ...sections.filter(s=>!same(s.position,point)).flatMap(s=>cross(s.position,span*.007))]);
  return objects;
}

export function createFlowFailure(element,onChange,download) {
  let evidence=null,objects=[],visible=true;
  function node(tag,text,parent=element){const n=document.createElement(tag);n.textContent=text;parent.append(n);return n;}
  function clear(){evidence=null;objects=[];element.hidden=true;element.replaceChildren();onChange();}
  function set(details,{span=1,request=null,provenance=null,message=null}={}) {
    clear();
    objects=failureOverlay(details,span);
    if(!objects.length)return;
    evidence={format:'openswing-rejected-airflow',version:1,error:message,request,details,software_provenance:provenance};
    visible=true;element.hidden=false;
    const m=details.maximum,b=details.vortex_breakdown;
    const sections=rejectedSections(details);
    node('strong',`Rejected airflow · M⊥ = ${number(m.normal_mach)}`);
    node('p',`${sections.length?`${sections.length} rejected section${sections.length===1?'':'s'}. Worst: `:''}Beam ${m.beam}, t = ${number(m.t)} · circulation residual ${number(details.circulation_residual)}. No accepted solution.`);
    const legend=node('p','');legend.className='flow-failure-legend';
    const key=(text,color)=>{node('span',text,legend).style.color=color;};
    key(sections.length>1?'Red crosses: rejected force points; largest is worst':'Red cross: force point',failureColors.point);
    if(b?.available&&b.axes==='body') {
      key('Cyan: bound',failureColors.bound);key('Violet: wake',failureColors.wake);
      if(objects.some(o=>o.kind==='failure-receiver'))key('Amber cross: influence receiver',failureColors.receiver);
      node('p',`Body coordinates · ${b.influence_geometry==='frozen jig'?'frozen jig':'current'} influence geometry. Sources shown belong to the worst section: up to three strongest nonzero contributions of each kind; wake rays shown for one reference span. Large terms can cancel. The aircraft surface shows the jig shape.`);
    } else node('p',b?.reason??'Vortex source breakdown unavailable.');
    const actions=node('div','');actions.className='flow-failure-actions';
    const toggle=node('button','Hide markers',actions);toggle.type='button';toggle.id='flow-failure-toggle';toggle.setAttribute('aria-pressed','true');
    toggle.onclick=()=>{visible=!visible;toggle.textContent=visible?'Hide markers':'Show markers';toggle.setAttribute('aria-pressed',String(visible));onChange();};
    const save=node('button','Download diagnostic JSON',actions);save.type='button';save.id='flow-failure-download';
    save.onclick=()=>download('rejected-airflow.json',JSON.stringify(evidence,null,2),'application/json');
    const forces=details.surface_force_diagnostic;
    if(forces){
      const disclosure=node('details','');disclosure.id='flow-failure-forces';disclosure.open=true;
      node('summary','Partial surface-force diagnostics',disclosure);
      if(!forces.available)node('p',forces.reason??'Finite surface forces unavailable.',disclosure);
      else {
        node('p','Rejected-state calculations, not validated aircraft coefficients. Pitching moment is unavailable because its local Mach correction is undefined.',disclosure);
        const scroll=node('div','',disclosure);scroll.className='flow-failure-table';
        const table=node('table','',scroll),head=node('tr','',node('thead','',table));
        for(const title of ['Surface contribution','Lift (input F)','Drag (input F)','CL','CD'])node('th',title,head);
        const body=node('tbody','',table);
        const row=(label,value)=>{if(!value)return;const r=node('tr','',body);for(const text of [label,number(value.lift),number(value.drag),number(value.CL),number(value.CD)])node('td',text,r);};
        row('Surface sum',forces.terms?.sum);
        row('Circulatory · near field',forces.terms?.circulatory);
        row('Circulation rate',forces.terms?.circulation_rate);
        row('Profile drag',forces.terms?.profile);
        row(`Mach-invalid strips (${forces.rejected_strips}) · included above`,forces.rejected_strip_sum);
        for(const beam of forces.beams??[])row(`Beam ${beam.beam} · all contributions`,beam);
        node('p','Includes lifting-surface circulation, circulation-rate and profile forces. Excludes apparent mass, bodies, point-object drag and engines. CD here is a near-field force projection, not Trefftz CDi. Beam and invalid-strip subtotals are already included in the surface sum.',disclosure);
        node('p',forces.normalization?.coefficients_available
          ?'Coefficients use flight dynamic pressure and the model’s reference area. Exported JSON contains body-force vectors and wind axes.'
          :'Coefficient normalization is unavailable; dimensional forces remain shown.',disclosure);
      }
    }
    if(sections.length) {
      const disclosure=node('details','');disclosure.id='flow-failure-sections';
      node('summary',`All rejected sections (${sections.length})`,disclosure);
      const scroll=node('div','',disclosure);scroll.className='flow-failure-table';
      const table=node('table','',scroll),head=node('tr','',node('thead','',table));
      for(const title of ['Beam','t','M⊥','Force point x, y, z (input L)'])node('th',title,head);
      const body=node('tbody','',table);
      for(const s of sections) {
        const row=node('tr','',body);
        for(const value of [String(s.beam),number(s.t),number(s.normal_mach),s.position.map(number).join(', ')])node('td',value,row);
      }
      node('p','Sorted by local Mach. These are rejected-state locations, not an accepted aerodynamic solution.',disclosure);
    }
    if(b?.available&&b.axes==='body') {
      const disclosure=node('details','');disclosure.id='flow-failure-sources';node('summary','Worst-section source contributions and distances',disclosure);
      const scroll=node('div','',disclosure);scroll.className='flow-failure-table';
      const table=node('table','',scroll),head=node('tr','',node('thead','',table));
      for(const title of ['Source','Speed (input L/T)','Distance (input L)'])node('th',title,head);
      const body=node('tbody','',table);
      const row=(label,speed,distance)=>{const r=node('tr','',body);for(const text of [label,number(speed),number(distance)])node('td',text,r);};
      for(const s of b.bound_sources??[])row(`Bound · beam ${s.beam}, t ${number(s.strip_t)}`,s.speed,s.physical_bound_distance);
      for(const s of b.wake_sources??[])row(`Wake group ${s.group_index} · ${s.source_count} endpoints`,s.speed,s.physical_ray_distance);
      node('p','Speeds are vector magnitudes, not signed contributions. Distances are from the influence receiver to physical sources. Ground images are not drawn; their velocity contributions remain included.',disclosure);
    }
    onChange();
  }
  return {set,clear,overlays:()=>visible?objects:[]};
}
