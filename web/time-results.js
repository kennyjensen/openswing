import { timeCheckpointPane } from './time-checkpoint.js';
import { feedbackUnit } from './feedback-results.js';
import { sensorQuantities } from './sensor-results.js';
import { timeInitialSettings,createTimeInitial } from './time-initial.js';
import { accuracySettings,createTimeAccuracy } from './time-accuracy.js';
import { actuatorSettings,parseActuatorTargets } from './time-actuators.js';
import { actuatorHistoryQuantities,actuatorHistoryValue,forcingHistoryValue } from './time-target-results.js';
import {timePhase,timePlotSegments} from './time-timeline.js';
import {timeHistory} from './time-history-source.js';
import {createHistorySelection} from './time-history-selection.js';
import {exportTimeHistory} from './time-history-export.js';
const $=id=>document.getElementById(id);
const get=(object,path)=>path.split('.').reduce((value,key)=>value?.[key],object);
const csv=row=>row.map(value=>'"'+String(value??'').replaceAll('"','""')+'"').join(',');

export const timeSettings=`
<div id="time-settings" hidden>
  <div class="fields">
    <label>Duration <span>input T</span><input id="time-duration" type="number" value="0.2" min="0.000001" step="any"></label>
    <label>Maximum step <span>input T</span><input id="time-step" type="number" value="0.01" min="0.000001" step="any"></label>
  </div>
  <label class="field-label" for="time-frame">Frame motion</label>
  <select id="time-frame"><option value="prescribed">Prescribed body accelerations</option><option value="free">Free flight · force/moment constraints</option><option value="mixed">Mixed motion · per axis</option></select>
  <div id="time-load-settings" hidden>
    <p class="small muted">Choose which accelerations are solved from net-load targets. Other components use the prescribed acceleration fields.</p>
    ${['Fx','Fy','Fz','Mx','My','Mz'].map((label,i)=>`<div class="time-load-row"><label>${i<3?'Translation':'Rotation'} ${'xyz'[i%3]}<select data-time-load="${label}" aria-label="${label} motion constraint"><option value="prescribed">Prescribe ${i<3?'A':'G'}${'xyz'[i%3]}</option><option value="load" ${i===0?'selected':''}>Solve from ${label}</option></select></label><label data-time-target-label="${label}">Net ${label} <span>${i<3?'input F':'input F·L'}</span><input data-time-target="${label}" aria-label="Net ${label} target" type="number" step="any" value="0"></label></div>`).join('')}
    <p class="small muted">Net loads include inertial reaction. With no external x force, a positive Fx target gives negative ax. Moments use the ASW moment reference; accelerations use the acceleration reference.</p>
  </div>
  <label class="field-label" for="time-order">Time integration</label>
  <select id="time-order"><option value="2">BDF2 · second order</option><option value="1">BDF1 · first order</option><option value="5">Radau IIA · constrained motion</option></select>
  ${accuracySettings('time')}
  <p class="small muted">Start from a trimmed equilibrium, or solve an initial equilibrium from the current flight inputs.</p>
  ${timeInitialSettings}
  ${actuatorSettings}
  <details class="advanced" id="forcing-settings"><summary>Open-loop forcing table</summary>
    <div class="constraint-actions"><button id="forcing-open" type="button">Open table</button><button id="forcing-save" type="button">Save table</button><button id="forcing-pulse" type="button">Flap pulse</button><button id="forcing-clear" type="button">Clear</button></div>
    <input id="forcing-file" type="file" hidden>
    <textarea id="time-forcing" aria-label="ASWING time-forcing table" spellcheck="false" placeholder="time +F1&#10;0 0&#10;0.2 1"></textarea>
    <p class="small muted">ASWING table: time, then F1, F2… for flaps or E1, E2… for engines. Prefix + for increments from the initial settings. Cubic interpolation; doubled times create jumps or slope breaks. Start no later than the initial time (normally 0; saved states can start later). After the last table time, applied values become zero, including + channels; extend the table to retain a setting. The final sample uses its tabulated value. Blank keeps settings constant.</p>
    <p class="small muted">Ax/Ay/Az (input L/T²) and Gx/Gy/Gz (deg/T²) prescribe frame accelerations or active actuator targets. Fx/Fy/Fz (input F) and Mx/My/Mz (input F·L) prescribe active frame or actuator load targets. L (lift at N=1, input F), Ar (radial acceleration, input L/T²), and the airflow, rate, position, attitude and explicit Earth-vector labels listed under time targets require their active inverse actuator target, unless the label belongs to a selected controller command. Such targets retain the trajectory equations; a table does not directly overwrite the frame state. Multiplier (*) and adder (+) rows apply to data columns. Selected controller measurement commands are available. Atmospheric altitude stays fixed. Configure gusts under Earth-coordinate gust field.</p>
  </details>
</div>`;

export const timeTransport=`
<div id="time-transport" class="time-transport" hidden>
  <button id="time-play" type="button">Play</button>
  <input id="time-scrub" type="range" min="0" max="0" value="0" step="1" aria-label="Time snapshot">
  <output id="time-current" aria-live="off"></output>
  <label>Playback<select id="time-play-speed"><option value="0.1">0.1 T/s</option><option value="1" selected>1 T/s</option><option value="10">10 T/s</option></select></label>
  <label>View<select id="time-view"><option value="body">Body frame</option><option value="earth">Earth frame</option></select></label>
</div>`;

export const timePane=`
<div id="pane-time" class="tab-pane time-pane" role="tabpanel" aria-labelledby="tab-time" hidden>
  ${timeCheckpointPane}
  <p id="time-summary" class="small muted">Select nonlinear time response, then run an analysis.</p>
  <div class="time-toolbar"><label>Quantity<select id="time-quantity" aria-label="Time-history quantity"></select></label><label id="time-node-field" hidden>Node<select id="time-node" aria-label="Time-history node"></select></label><label id="time-sensor-field" hidden>Sensor<select id="time-sensor" aria-label="Time-history sensor"></select></label><button id="time-csv" disabled>History CSV</button></div>
  <p id="time-unit" class="small muted"></p><div id="time-plot" class="plot-chart"></div>
  <div class="time-toolbar"><button id="time-archive-open">Open complete history</button><button id="time-archive-save" disabled>Save complete history</button><input id="time-archive-file" type="file" accept=".oswh" hidden><span id="time-archive-status" class="small muted" role="status"></span></div>
</div>`;

const baseQuantities=[
  ['CL','Lift coefficient','dimensionless'],['CD','Drag coefficient','dimensionless'],
  ['CDi','Trefftz induced drag (frozen wake)','dimensionless'],['CDi_near','Near-field vortex drag','dimensionless'],
  ['efficiency','Span efficiency (frozen wake)','dimensionless'],
  ['CLi','Trefftz lift coefficient','dimensionless'],['CYi','Trefftz side force coefficient','dimensionless'],
  ['Cm','Pitch moment coefficient','dimensionless'],['max_displacement','Maximum elastic displacement','input L'],
  ...['x','y','z'].flatMap((axis,i)=>[
    [`applied_force.${i}`,`Net body force ${axis}`,'input F'],
    [`applied_moment.${i}`,`Net moment ${axis} about reference`,'input F L'],
    [`support_force.${i}`,`Support force ${axis}`,'input F'],
    [`support_moment.${i}`,`Support moment ${axis} about reference`,'input F L'],
    [`frame.position_earth.${i}`,`Earth position ${axis}`,'input L'],
    [`frame.velocity_origin_body.${i}`,`Origin body velocity ${axis}`,'input L/T'],
    [`frame.rates_body.${i}`,`Body rotation rate ${axis}`,'rad/input T'],
    [`frame.acceleration_reference_body.${i}`,`Reference acceleration ${axis}`,'input L/T²'],
    [`frame.angular_acceleration_body.${i}`,`Body angular acceleration ${axis}`,'rad/input T²'],
    [`node.displacement.${i}`,`Node elastic displacement ${axis}`,'input L'],
    [`node.velocity.${i}`,`Node local velocity ${axis}`,'input L/T'],
  ]),
  ...['bank','elevation','heading'].map((name,i)=>[`frame.attitude.${i}`,name[0].toUpperCase()+name.slice(1),'deg']),
  ...['x','y','z'].map((axis,i)=>[`gust.reference_velocity_body.${i}`,`Gust at reference, body ${axis}`,'input L/T']),
  ['residual','Normalized nonlinear residual','dimensionless'],
];

// Transform the actual sampled geometry; never alter the saved solver state.
export function trajectoryGeometry(beams,attachments,snapshot,earth=false) {
  let ground=snapshot.ground_plane;
  if(!earth)return {beams,attachments,ground};
  const {body_to_earth:R,position_earth:p}=snapshot.frame;
  const transform=x=>R.map((row,i)=>p[i]+row.reduce((sum,r,j)=>sum+r*x[j],0));
  beams=beams.map(b=>({...b,quads:b.quads.map(q=>q.map(transform)),axis:b.axis.map(s=>s.map(transform)),
    ...(b.streamwise_quads?{streamwise_quads:b.streamwise_quads.map(q=>q.map(transform))}:{})}));
  attachments=attachments.map(a=>({...a,segments:a.segments.map(s=>s.map(transform))}));
  if(ground?.flag)ground={...ground,normal_body:ground.normal_earth,offset:0};
  return {beams,attachments,ground};
}

export function createTimeResults(getState,onSelect,download,onEdit,onView,showError,getStartTime=()=>0,captureArchive=()=>null,openArchive=null) {
  const initial=createTimeInitial(download,onEdit,showError);
  const accuracy=createTimeAccuracy('time',onEdit);
  let trajectory=null,history=null,entries=null,index=0,animation=null,playGeneration=0,quantities=baseQuantities,cursor=null,plotX=null;
  let preparing=null,plotRead=null,rendering=Promise.resolve(),generation=0;
  const selection=createHistorySelection((snapshot,next,fit)=>{
    index=next;$('time-scrub').value=index;
    $('time-current').textContent=`t = ${snapshot.time.toPrecision(5)} T · ${timePhase(snapshot)} · ${index+1}/${history.count}`;
    onSelect(snapshot,fit);updateCursor();
  });
  function pause() {playGeneration++;selection.cancel();if(animation!==null)cancelAnimationFrame(animation);animation=null;$('time-play').textContent='Play';}
  function select(next,fit=false) {
    if(!history)return Promise.resolve(false);
    const target=Math.min(history.count-1,Math.max(0,Math.round(next)));
    if(!history.peek(target))$('time-current').textContent=`Loading snapshot ${target+1}/${history.count} · t = ${history.times[target].toPrecision(5)} T…`;
    return selection.select(history,target,fit);
  }
  const safeSelect=(next,fit=false)=>{
    const source=history;
    return select(next,fit).catch(error=>{if(history===source){$('time-scrub').value=index;$('time-current').textContent=`Snapshot could not be loaded. Still showing ${index+1}/${history.count}.`;showError(error);}return false;});
  };
  function updateCursor() {
    if(cursor&&history)cursor.setAttribute('d',`M${plotX(history.times[index])} 15V185`);
  }
  function value(s,key,nodeId=Number($('time-node').value),sensorId=Number($('time-sensor').value)) {
    if(key.startsWith('inverse.'))return actuatorHistoryValue(s,key);
    if(key.startsWith('forcing_values.'))return forcingHistoryValue(s,key);
    if(key.startsWith('actuator.'))return s.operating_values?.[key.slice('actuator.'.length)];
    if(key.startsWith('sensor.'))return get(s.sensors?.find(s=>s.index===sensorId),key.slice(7));
    if(!key.startsWith('node.'))return get(s,key);
    const id=nodeId,node=s.nodes.find(n=>n.index===id),axis=Number(key.split('.')[2]);
    if(!node)return null;
    return key.startsWith('node.displacement')?node.position[axis]-node.jig_position[axis]:s.local_velocity[id][axis];
  }
  function render(){rendering=draw().catch(error=>{if(error.name!=='AbortError')showError(error);});return rendering;}
  async function draw() {
    plotRead?.abort();const controller=plotRead=new AbortController();
    cursor=null;plotX=null;
    $('time-plot').replaceChildren();$('time-unit').textContent='';
    if(!trajectory||!entries)return;
    const source=history,current=trajectory;
    const key=$('time-quantity').value,quantity=quantities.find(q=>q[0]===key);
    $('time-node-field').hidden=!key.startsWith('node.');
    $('time-sensor-field').hidden=!key.startsWith('sensor.');
    if(!quantity)return;
    $('time-unit').textContent=`${quantity[1]} [${quantity[2]}] · time [input T]`;
    const nodeId=Number($('time-node').value),sensorId=Number($('time-sensor').value);
    const cacheKey=key.startsWith('node.')?`${key}|node=${nodeId}`:key.startsWith('sensor.')?`${key}|sensor=${sensorId}`:key;
    const data=await source.series(cacheKey,s=>value(s,key,nodeId,sensorId),{signal:controller.signal,
      onProgress:(done,total)=>{if(trajectory===current&&!controller.signal.aborted)$('time-plot').textContent=`Reading history: ${done}/${total} snapshots…`;}});
    if(controller.signal.aborted||trajectory!==current)return;
    const samples=entries.map((entry,i)=>[entry.time,data[i]]);
    const points=samples.filter(p=>Number.isFinite(p[1]));
    if(!points.length){$('time-plot').textContent='No values available.';return;}
    const values=points.map(p=>p[1]);
    let ymin=Math.min(...values),ymax=Math.max(...values);
    const pad=(ymax-ymin||Math.max(Math.abs(ymax),1))*.12;ymin-=pad;ymax+=pad;
    const width=Math.max(320,$('time-plot').clientWidth||770),right=width-20;
    const start=source.times[0],end=source.times.at(-1);
    const X=x=>72+(x-start)/(end-start||1)*(right-72),Y=y=>180-(y-ymin)/(ymax-ymin)*160;
    let svg=`<svg viewBox="0 0 ${width} 215" role="img" aria-label="Computed time history">`;
    for(let i=0;i<5;i++){const y=ymin+(ymax-ymin)*i/4,t=start+(end-start)*i/4;svg+=`<path d="M72 ${Y(y)}H${right}" class="plot-grid"/><text x="62" y="${Y(y)+4}" text-anchor="end">${Math.abs(y)<(ymax-ymin)*1e-10?0:y.toPrecision(3)}</text><text x="${X(t)}" y="205" text-anchor="middle">${t.toPrecision(3)}</text>`;}
    for(const segment of timePlotSegments(entries,data,trajectory.history_breaks??trajectory.forcing?.breaks??[]))
      svg+=`<polyline points="${segment.map(([t,y])=>`${X(t)},${Y(y)}`).join(' ')}" class="plot-line"/>`;
    // Connecting segments only guide the eye; playback selects these dots.
    for(const [t,y] of points)svg+=`<circle cx="${X(t)}" cy="${Y(y)}" r="2.5" class="section-point"><title>t=${t.toPrecision(7)}; value=${y.toPrecision(7)}</title></circle>`;
    svg+='<path class="time-cursor"/>';
    $('time-plot').innerHTML=svg+'</svg>';
    // Selection changes the cursor, not the retained curve. Rebuild the full
    // plot only for a new trajectory, quantity/station or container width.
    cursor=$('time-plot').querySelector('.time-cursor');plotX=X;updateCursor();
  }
  async function setTrajectory(result) {
    pause();preparing?.abort();plotRead?.abort();const token=++generation;
    preparing=new AbortController();trajectory=result;history=timeHistory(result);entries=null;index=0;cursor=null;plotX=null;
    $('time-plot').replaceChildren();$('time-unit').textContent='';
    $('time-current').textContent='';$('time-scrub').disabled=true;$('time-play').disabled=true;
    for(const id of ['time-quantity','time-node','time-sensor'])$(id).disabled=true;
    $('time-transport').hidden=!result;$('time-csv').disabled=!result;
    $('time-archive-save').disabled=true;$('time-archive-status').textContent='';
    if(!result){$('time-summary').textContent='Select nonlinear time response, then run an analysis.';return;}
    $('time-summary').textContent='Opening computed history…';$('time-csv').disabled=true;
    let first;
    try{
      const source=history,rows=await source.prepare({signal:preparing.signal,onProgress:(done,total)=>{if(token===generation)$('time-summary').textContent=`Reading history index: ${done}/${total} snapshots…`;}});
      if(token!==generation)return;
      entries=rows;
      first=history.peek(0)??await history.read(0);if(token!==generation)return;history.pin(0,first);
    }catch(error){if(error.name==='AbortError'||token!==generation)return;throw error;}
    $('time-summary').textContent=`${result.frame_mode==='free'?'Free flight':result.frame_mode==='mixed'?'Mixed motion':'Prescribed accelerations'} · ${result.accepted_steps} steps · ${result.rejected_steps} retries`;
    quantities=[...baseQuantities,...actuatorHistoryQuantities(result?.actuator_constraints??[]),...(result?.actuator_constraints??[]).map(c=>[
      'actuator.'+c.variable,'Solved '+c.variable.replace('control.','F').replace('power.','E'),c.variable.startsWith('control.')?'flap setting':'engine setting']),...(entries.some(entry=>entry.has_accuracy)?[
      ['accuracy.maximum_ratio','Temporal discrepancy / tolerance','dimensionless'],
      ['accuracy.trial_step','Time between reported endpoints','input T']]:[]),
      ...(first.body_shoulders??[]).flatMap((s,i)=>['x','y','z'].map((axis,k)=>[`body_shoulders.${i}.force.${k}`,`Shoulder beam ${s.beam}, t=${s.t}: force ${axis}`,'input F'])),...Object.entries(first.feedback??{}).flatMap(([group,values])=>Object.keys(values).map(name=>['feedback.'+group+'.'+name,'Controller: '+group+' '+name,feedbackUnit(result.controller,group+'_'+name)])),...(first.sensors?.length?sensorQuantities.map(([key,name,unit])=>[`sensor.${key}`,`Sensor: ${name}`,unit]):[]),...(result?.forcing.channels??[]).map(c=>[`forcing_values.${c.name}`,`Input ${c.name}`,c.unit])];
    $('time-quantity').replaceChildren();
    for(const [key,name] of quantities){const o=document.createElement('option');o.value=key;o.textContent=name;$('time-quantity').append(o);}
    if(!first.atmosphere)$('time-quantity').value='max_displacement';
    $('time-node').replaceChildren();$('time-sensor').replaceChildren();
    if(result){
      $('time-scrub').max=history.count-1;
      for(const n of first.nodes){const o=document.createElement('option');o.value=n.index;o.textContent=`Beam ${n.beam} · t=${n.t.toPrecision(4)}`;$('time-node').append(o);}
      for(const s of first.sensors??[]){const o=document.createElement('option');o.value=s.index;o.textContent=`Sensor ${s.index} · beam ${s.beam}`;$('time-sensor').append(o);}
      await select(0,true);if(token!==generation)return;
    }
    for(const id of ['time-quantity','time-node','time-sensor'])$(id).disabled=!$(id).options.length;
    $('time-csv').disabled=false;$('time-archive-save').disabled=false;$('time-scrub').disabled=false;$('time-play').disabled=false;await render();
  }
  $('time-play').onclick=async()=>{
    if(animation!==null){pause();return;}
    if(!history||!entries)return;
    if(index===history.count-1)await safeSelect(0);
    const token=++playGeneration,started=performance.now(),initial=history.times[index],speed=Number($('time-play-speed').value);
    $('time-play').textContent='Pause';
    const frame=async now=>{
      if(token!==playGeneration)return;
      const time=initial+(now-started)/1000*speed;
      let next=index;
      while(next<history.count-1&&history.times[next+1]<=time)next++;
      if(next!==index&&!(await safeSelect(next))){if(token===playGeneration)pause();return;}
      if(token!==playGeneration)return;
      if(time>=history.times.at(-1)){pause();return;}
      animation=requestAnimationFrame(frame);
    };
    animation=requestAnimationFrame(frame);
  };
  $('time-scrub').oninput=()=>{pause();void safeSelect(Number($('time-scrub').value));};
  $('time-play-speed').onchange=pause;
  $('time-view').onchange=()=>{pause();onView();};
  function frameSettings(){
    $('time-load-settings').hidden=$('time-frame').value!=='mixed';
    for(const select of document.querySelectorAll('[data-time-load]'))document.querySelector(`[data-time-target-label="${select.dataset.timeLoad}"]`).hidden=select.value!=='load';
  }
  $('time-frame').addEventListener('input',frameSettings);
  for(const element of document.querySelectorAll('[data-time-load],[data-time-target]'))element.addEventListener('input',()=>{frameSettings();onEdit();});
  frameSettings();
  function options(){
    const load_targets={};
    if($('time-frame').value==='mixed')for(const select of document.querySelectorAll('[data-time-load]')){
      if(select.value!=='load')continue;
      const label=select.dataset.timeLoad,input=document.querySelector(`[data-time-target="${label}"]`);
      if(!input.value.trim()||!input.checkValidity()||!Number.isFinite(Number(input.value)))throw new Error('Enter finite values for the selected net-load targets.');
      load_targets[(label[0]==='F'?'force.':'moment.')+label[1]]=Number(input.value);
    }
    if($('time-frame').value==='mixed'&&!Object.keys(load_targets).length)throw new Error('Select at least one net-load target for mixed motion.');
    return {duration:Number($('time-duration').value),dt:Number($('time-step').value),order:Number($('time-order').value),frame:$('time-frame').value,forcing:$('time-forcing').value,actuator_constraints:parseActuatorTargets($('time-actuators').value,getState().model),accuracy:accuracy.options(),...($('time-frame').value==='mixed'?{load_targets}:{}),...initial.options()};
  }
  for(const id of ['time-duration','time-step','time-frame','time-order','time-forcing','time-actuators'])$(id).addEventListener('input',onEdit);
  for(const id of ['time-quantity','time-node','time-sensor'])$(id).onchange=render;
  $('forcing-open').onclick=()=>$('forcing-file').click();
  $('forcing-file').onchange=async event=>{
    const revision=getState().revision,file=event.target.files[0];
    try {if(file){const text=await file.text();if(revision===getState().revision){$('time-forcing').value=text;onEdit();}}}catch(error){showError(error);}finally{event.target.value='';}
  };
  $('forcing-save').onclick=()=>download('openswing-forcing.txt',$('time-forcing').value);
  $('forcing-clear').onclick=()=>{$('time-forcing').value='';onEdit();};
  $('forcing-pulse').onclick=()=>{
    const id=getState().model?.controls[0],duration=Number($('time-duration').value);
    if(!id){showError(new Error('This model has no declared flap control.'));return;}
    if(!(duration>0)){showError(new Error('Set a positive duration first.'));return;}
    const start=getStartTime();
    $('time-forcing').value=`time +F${id}\n${start} 0\n${start+duration/4} 0\n${start+duration/4} 1\n${start+3*duration/4} 1\n${start+3*duration/4} 0\n${start+duration} 0\n`;onEdit();
  };
  $('time-csv').onclick=async()=>{
    if(!trajectory)return;
    const columns=quantities.filter(q=>!q[0].startsWith('node.')).map(q=>q[0].startsWith('sensor.')?[q[0],`${q[1]} (sensor ${$('time-sensor').value})`,q[2]]:q);
    const key=$('time-quantity').value;
    if(key.startsWith('node.')){const q=quantities.find(q=>q[0]===key);columns.push([key,`${q[1]} (${ $('time-node').selectedOptions[0].textContent})`,q[2]]);}
    const source=history,nodeId=Number($('time-node').value),sensorId=Number($('time-sensor').value);
    const pieces=[new Blob([csv(['time [input T]','forcing_side','step [input T]','nominal ODE order','snapshot phase',...columns.map(q=>`${q[1]} [${q[2]}]`)])+'\n'])];
    $('time-csv').disabled=true;let rows=[];
    try{
      for await(const s of source.scan()){
        rows.push(csv([s.time,s.forcing_side,s.step,s.order,timePhase(s),...columns.map(q=>value(s,q[0],nodeId,sensorId))]));
        if(rows.length===128){pieces.push(new Blob([rows.join('\n')+'\n']));rows=[];}
      }
      if(rows.length)pieces.push(new Blob([rows.join('\n')+'\n']));
      download('openswing-time.csv',new Blob(pieces,{type:'text/csv'}),'text/csv');
    }catch(error){showError(error);}finally{$('time-csv').disabled=!trajectory;}
  };
  $('time-archive-save').onclick=async()=>{
    if(!trajectory||getState().busy)return;
    const current=trajectory;pause();$('time-archive-save').disabled=true;
    try{
      const workbench=captureArchive();
      const summary=await exportTimeHistory(current,{workbench,download,onProgress:(done,total)=>{
        if(trajectory===current)$('time-archive-status').textContent=`Saving complete history: ${done}/${total} snapshots…`;
      }});
      if(trajectory===current)$('time-archive-status').textContent=`Saved ${summary.snapshots} complete snapshots (${(summary.bytes/1048576).toFixed(1)} MiB).`;
    }catch(error){if(error.name!=='AbortError'){showError(error);$('time-archive-status').textContent=error.message;}}
    finally{$('time-archive-save').disabled=!trajectory;}
  };
  $('time-archive-open').disabled=!openArchive;
  $('time-archive-open').onclick=()=>{if(!getState().busy)$('time-archive-file').click();};
  $('time-archive-file').onchange=async event=>{
    const file=event.target.files[0];event.target.value='';if(!file||!openArchive||getState().busy)return;
    try{await openArchive(file);}catch(error){showError(error);}
  };
  let lastWidth=0;
  new ResizeObserver(entries=>{const width=entries[0].contentRect.width;if(width!==lastWidth){lastWidth=width;if(width>0)render();}}).observe($('time-plot'));
  return {setTrajectory,pause,render,select:safeSelect,selectedIndex:()=>index,options,hasData:()=>Boolean(entries?.length),ready:()=>Promise.all([selection.ready(),rendering]),
    playback:()=>({playing:animation!==null,durationMs:history?1000*(history.times.at(-1)-history.times[index])/Number($('time-play-speed').value):0})};
}
