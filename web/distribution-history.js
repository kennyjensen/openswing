// Sampled distributions only: no interpolation in time or between material grids.
import {timeHistory} from './time-history-source.js';
export const atPath=(row,path)=>path.split('.').reduce((v,k)=>v?.[k],row);
const finite=x=>typeof x==='number'&&Number.isFinite(x);
export const csvLine=row=>row.map(x=>'"'+String(typeof x==='number'&&!finite(x)?'':x??'').replaceAll('"','""')+'"').join(',');
const provenance=(s,index)=>({index,time:s.time,step:s.step,side:s.forcing_side??''});

export function distributionHistory(snapshots,field,beam,value) {
  if(!Array.isArray(snapshots)||!snapshots.length)throw new Error('No computed time snapshots.');
  const accumulator=distributionAccumulator(field,beam,value);
  snapshots.forEach((snapshot,index)=>accumulator.add(snapshot,index));
  return accumulator.result();
}

export function distributionAccumulator(field,beam,value){
  let template,stations=null,peak=null,missing=0;const series=[];
  function add(snapshot,index){
    if(!finite(snapshot.time))throw new Error(`Snapshot ${index} has no finite time.`);
    const rows=(snapshot[field]??[]).filter(r=>r.beam===beam);
    const grid=rows.map(r=>{
      if(!finite(r.t)||(field==='elements'&&(!finite(r.t0)||!finite(r.t1))))throw new Error(`Snapshot ${index} has an invalid material station.`);
      return [r.t,...(field==='elements'?[r.t0,r.t1]:[])];
    });
    const signature=JSON.stringify(grid);
    if(template===undefined)template=signature;
    else if(signature!==template)throw new Error(`Snapshot ${index} has a different material station grid. History plots require identical ordered stations; no interpolation was applied.`);
    const s={...provenance(snapshot,index),samples:rows.map((row,station)=>{
      const raw=value(row,snapshot);
      return {station,t:row.t,t0:row.t0,t1:row.t1,value:finite(raw)?raw:null};
    })};
    series.push(s);stations??=s.samples.map(point=>({...point,count:0,min:null,max:null}));
    for(const p of s.samples){
    if(p.value===null){missing++;continue;}
    const station=stations[p.station],sample={...p,index:s.index,time:s.time,step:s.step,side:s.side};
    station.count++;
    // Strict comparisons preserve the first stored sample when values tie.
    if(!station.min||sample.value<station.min.value)station.min=sample;
    if(!station.max||sample.value>station.max.value)station.max=sample;
    if(!peak||Math.abs(sample.value)>Math.abs(peak.value))peak=sample;
    }
  }
  return {add,result(){if(!series.length)throw new Error('No computed time snapshots.');return {series,stations,peak,missing,total:series.length};}};
}

export function envelopeCSV(history,beam,quantity,unit) {
  const header=['beam','station_index (0-based)','t','t0','t1','quantity','unit','available_snapshots','total_snapshots'];
  for(const kind of ['min','max'])header.push(`${kind}_value`,`${kind}_snapshot_index (0-based)`,`${kind}_time [input T]`,`${kind}_step [input T]`,`${kind}_forcing_side`);
  return [csvLine(header),...history.stations.map(s=>csvLine([beam,s.station,s.t,s.t0,s.t1,quantity,unit,s.count,history.total,...['min','max'].flatMap(k=>[s[k]?.value,s[k]?.index,s[k]?.time,s[k]?.step,s[k]?.side])]))].join('\n')+'\n';
}

export const sectionColumns=[['beam','beam'],['t','t'],['t0','t0'],['t1','t1'],['material_length [L]','length'],
  ...['c','s','n'].flatMap((a,i)=>[[`F${a} [F]`,`force_local.${i}`],[`M${a}_reference [F L]`,`moment_local.${i}`],[`M${a}_axes [F L]`,`moment_axes.${i}`],[`strain_${a}`,`strain.${i}`],[`curvature_change_${a} [rad/L]`,`curvature_change.${i}`]]),
  ['axial_strain_tension','axial_strain_tension'],['Cshell [L]','shell.c'],['Nshell [L]','shell.n'],['Atshell [L^3]','shell.area_thickness'],['shell_strain_available','shell.strain_available'],['shell_axial_strain','shell.axial_strain'],['shell_strain_bound','shell.axial_strain_bound'],['torsional_shear_stress [F/L^2]','shell.shear_stress'],['absolute_torsional_shear_stress [F/L^2]','shell.shear_stress_abs'],['shear_status','shell.shear_status']];
export const stripColumns=[['beam','beam'],['lifting','lifting'],['t','t'],['current_length [L]','length'],
  ...['x','y','z'].map((a,i)=>[`${a} [L]`,`position.${i}`]),['circulation [L^2/T]','circulation'],['cl_circulatory','cl'],['wake_core_radius [L]','wake_core_radius'],['circulation_rate [L^2/T^2]','circulation_rate'],
  ...[['force','F','F'],['moment','M','F L'],['apparent_force','F_apparent','F'],['apparent_moment','M_apparent','F L'],['circulation_rate_force','F_circulation_rate','F']].flatMap(([field,label,unit])=>['x','y','z'].map((a,i)=>[`${label}_${a} [${unit}]`,`${field}.${i}`])),['stalled','stalled'],
  ...['x','y','z'].flatMap((a,i)=>[[`force_point_${a} [L]`,`velocity_position.${i}`],[`V_relative_${a} [L/T]`,`relative_velocity.${i}`]]),
  ['V_normal [L/T]','normal_speed'],['Mach_normal','normal_mach'],
  ['cm_quarter_chord','cm'],['f_aero [F/L]','f_aero'],['f_reac [F/L]','f_reac'],['da_eff [rad]','da_eff']];
export const shoulderColumns=[['beam','beam'],['t','t'],...['x','y','z'].map((a,i)=>[`${a} [L]`,`position.${i}`]),['radius_left [L]','radius_left'],['radius_right [L]','radius_right'],['area_jump [L^2]','area_jump'],...['x','y','z'].map((a,i)=>[`V${a} [L/T]`,`incident_velocity.${i}`]),...['x','y','z'].map((a,i)=>[`F${a} [F]`,`force.${i}`])];

export function historyCSV(snapshots,field,columns) {
  const lines=[csvLine(['snapshot_index (0-based)','time [input T]','step [input T]','forcing_side','beam_station_index (0-based)',...columns.map(c=>c[0])])];
  snapshots.forEach((s,index)=>{for(const line of snapshotCSV(s,index,field,columns))lines.push(line);});
  return lines.join('\n')+'\n';
}
function *snapshotCSV(s,index,field,columns){
    const ordinals=new Map();
    for(const row of s[field]??[]){
      const station=ordinals.get(row.beam)??0;ordinals.set(row.beam,station+1);
      yield csvLine([index,s.time,s.step,s.forcing_side,station,...columns.map(c=>atPath(row,c[1]))]);
    }
}

export const historyControls=prefix=>`<div class="distribution-history-toolbar">
  <label>Time distribution view<select id="${prefix}-scope"><option value="current">Current snapshot</option><option value="overlay">All snapshots</option><option value="envelope">Sampled envelope</option></select></label>
  <button id="${prefix}-history-csv" disabled>All snapshots CSV</button><button id="${prefix}-envelope-csv" disabled>Envelope CSV</button>
  </div><p id="${prefix}-history-note" class="small muted distribution-history-note"></p>`;

const escape=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const fmt=x=>Number(x).toPrecision(6);
export const sampleDescription=p=>`snapshot ${p.index} · time ${fmt(p.time)} T${p.side?` · forcing ${p.side}`:''}`;

export function renderHistory(target,history,{scope,kind,selected,unit,select}) {
  target.className='plot-chart';
  if(!history.peak){target.textContent='No values available for this quantity in the computed history.';return;}
  let xmin=Infinity,xmax=-Infinity,lo=0,hi=0;
  for(const s of history.stations){xmin=Math.min(xmin,s.t0??s.t,s.t1??s.t);xmax=Math.max(xmax,s.t0??s.t,s.t1??s.t);if(s.min){lo=Math.min(lo,s.min.value);hi=Math.max(hi,s.max.value);}}
  const pad=(hi-lo||1)*.12;lo-=pad;hi+=pad;
  const width=Math.max(320,target.clientWidth||770),right=width-20;
  const X=x=>72+(x-xmin)/(xmax-xmin||1)*(right-72),Y=y=>180-(y-lo)/(hi-lo)*160;
  let svg=`<svg viewBox="0 0 ${width} 215" role="group" aria-label="${scope==='overlay'?'All computed snapshot distributions':'Sampled distribution envelope'}">`;
  for(let i=0;i<5;i++){const y=lo+(hi-lo)*i/4,x=xmin+(xmax-xmin)*i/4;svg+=`<path d="M72 ${Y(y)}H${right}" class="plot-grid"/><text x="62" y="${Y(y)+4}" text-anchor="end">${y.toPrecision(3)}</text><text x="${X(x)}" y="205" text-anchor="middle">${x.toPrecision(3)}</text>`;}
  svg+=`<path d="M72 ${Y(0)}H${right}" class="plot-zero"/>`;
  const path=points=>{
    let d='',previous=null;
    for(const p of points){
      if(!p||p.value===null){previous=null;continue;}
      if(kind==='sections')d+=`M${X(p.t0)} ${Y(p.value)}H${X(p.t1)}`;
      else if(kind==='impulses')d+=`M${X(p.t)} ${Y(0)}V${Y(p.value)}`;
      else {d+=`${previous&&previous.t!==p.t?'L':'M'}${X(p.t)} ${Y(p.value)}`;if(!previous)d+=`h0`;}
      previous=p;
    }
    return d;
  };
  const marker=(p,cls,label)=>`<circle cx="${X(p.t)}" cy="${Y(p.value)}" r="3.5" class="${cls}" data-snapshot="${p.index}" tabindex="0" role="button" aria-label="${escape(label)}"><title>${escape(label)}</title></circle>`;
  if(scope==='overlay'){
    const series=[...history.series.filter(s=>s.index!==selected),...history.series.filter(s=>s.index===selected)];
    for(const s of series){
      const label=sampleDescription(s),points=s.samples.filter(p=>p.value!==null);
      svg+=`<g class="distribution-trace${s.index===selected?' selected':''}" data-snapshot="${s.index}" tabindex="0" role="button" aria-label="${escape(label)}"><title>${escape(label)}</title><path d="${path(s.samples)}"/>`;
      // Mark isolated points as well as the current snapshot; no invisible singleton traces.
      for(const p of points)if(s.index===selected||kind==='impulses'||(!s.samples[p.station-1]||s.samples[p.station-1].value===null)&&(!s.samples[p.station+1]||s.samples[p.station+1].value===null))svg+=`<circle cx="${X(p.t)}" cy="${Y(p.value)}" r="2.5"/>`;
      svg+='</g>';
    }
  }else{
    for(const k of ['min','max']){
      svg+=`<path class="distribution-${k}" d="${path(history.stations.map(s=>s[k]))}"/>`;
      for(const s of history.stations)if(s[k]){const p=s[k];svg+=marker(p,`distribution-${k}`,`${k}: ${fmt(p.value)} ${unit} at t=${fmt(p.t)} · ${sampleDescription(p)}`);}
    }
  }
  target.innerHTML=svg+'</svg>';
  const activate=e=>{const point=e.target.closest('[data-snapshot]');if(point)select(Number(point.dataset.snapshot));};
  target.onclick=activate;
  target.onkeydown=e=>{if((e.key==='Enter'||e.key===' ')&&e.target.closest('[data-snapshot]')){e.preventDefault();activate(e);}};
}

export function historyNote(history,unit) {
  const p=history.peak;
  return `${history.total} snapshots · ${history.stations.length} material stations. ${p?`Largest sampled |value|: ${fmt(p.value)} ${unit} at t=${fmt(p.t)} · ${sampleDescription(p)}. `:''}${history.missing?`${history.missing} unavailable values; envelopes use only available samples. `:''}Minima and maxima are sampled, not bounds between time steps or stations. Refine time and space to resolve peaks. Select a trace or extremum to inspect its snapshot. Blue = minimum; gold = maximum; green = current overlay.`;
}

export function createHistoryView(prefix,getState,download,select,getSelected) {
  const $=suffix=>document.getElementById(`${prefix}-${suffix}`);
  let config=null,cache=null,viewGeneration=0;
  async function history(){
    const trajectory=getState().trajectory;
    const key=JSON.stringify([config.field,config.beam,config.quantity,config.unit]);
    if(cache?.trajectory===trajectory&&cache.key===key)return cache.data??cache.promise;
    cache?.controller.abort();
    const entry=cache={trajectory,key,controller:new AbortController()},settings={...config};
    entry.promise=(async()=>{
      const accumulator=distributionAccumulator(settings.field,settings.beam,settings.value),source=timeHistory(trajectory);let index=0;
      for await(const snapshot of source.scan({signal:entry.controller.signal,onProgress:(done,total)=>{
        if(cache===entry)$('history-note').textContent=`Reading distributions: ${done}/${total} snapshots…`;
      }}))accumulator.add(snapshot,index++);
      return entry.data=accumulator.result();
    })();
    return entry.promise;
  }
  $('history-csv').onclick=async()=>{
    if(!config||!getState().trajectory)return;
    const {field}=config,columns={elements:sectionColumns,strips:stripColumns,body_shoulders:shoulderColumns}[field];
    const source=timeHistory(getState().trajectory),pieces=[new Blob([csvLine(['snapshot_index (0-based)','time [input T]','step [input T]','forcing_side','beam_station_index (0-based)',...columns.map(c=>c[0])])+'\n'])];
    let lines=[],index=0;$('history-csv').disabled=true;
    try{
      for await(const snapshot of source.scan({onProgress:(done,total)=>{$('history-note').textContent=`Exporting distributions: ${done}/${total} snapshots…`;}})){
        for(const line of snapshotCSV(snapshot,index++,field,columns)){
          lines.push(line);if(lines.length===128){pieces.push(new Blob([lines.join('\n')+'\n']));lines=[];}
        }
      }
      if(lines.length)pieces.push(new Blob([lines.join('\n')+'\n']));
      download(`openswing-${field}-history.csv`,new Blob(pieces,{type:'text/csv'}),'text/csv');
      $('history-note').textContent=`Exported ${source.count} snapshots.`;
    }catch(error){$('history-note').textContent=error.message;}
    finally{$('history-csv').disabled=!getState().trajectory;}
  };
  $('envelope-csv').onclick=async()=>{
    if(!config||!getState().trajectory)return;
    const settings={...config};
    try{download(`openswing-${settings.field}-envelope.csv`,envelopeCSV(await history(),settings.beam,settings.quantity,settings.unit),'text/csv');}
    catch(error){$('history-note').textContent=error.message;}
  };
  function update(next,target){
    const token=++viewGeneration;
    config=next;
    const {trajectory}=getState(),available=!!next&&!!trajectory&&timeHistory(trajectory).count>0;
    $('scope').disabled=!available;
    $('history-csv').disabled=!available;$('envelope-csv').disabled=!available;
    $('history-note').textContent='';
    if(!available){$('scope').value='current';cache?.controller.abort();cache=null;return false;}
    $('history-csv').title=`All beams, all snapshots: ${next.field==='elements'?'section loads and strains':next.field==='strips'?'distributed aerodynamic loads':'concentrated body shoulder forces'}, in raw input units.`;
    $('envelope-csv').title='Selected beam and quantity, in displayed units, with each sampled extremum’s snapshot and time.';
    if($('scope').value==='current'){if(cache&&!cache.data){cache.controller.abort();cache=null;}return false;}
    target.textContent='Reading computed distributions…';
    history().then(data=>{
      if(token!==viewGeneration||getState().trajectory!==trajectory)return;
      renderHistory(target,data,{...next,scope:$('scope').value,selected:getSelected(),select:index=>{if(!getState().busy)select(index);}});
      $('history-note').textContent=historyNote(data,next.unit);
    }).catch(error=>{if(token===viewGeneration&&error.name!=='AbortError'){target.textContent=error.message;$('envelope-csv').disabled=true;}});
    return true;
  }
  return {update};
}
