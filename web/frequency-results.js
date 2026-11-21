import {frameConstraintFields,bindFrameConstraints,frameOptions,frameInputs} from './dynamic-frame.js';
import {complexGain,unitFor,frequencyValue,frequencySeries,displayResponseUnit} from './frequency-data.js';
import {plotAxis} from './frequency-axes.js';
export {complexGain} from './frequency-data.js';
import {comparisonPane,createFrequencyComparison} from './frequency-comparison.js';
import { sensorFields } from './sensor-results.js';
import { modeGeometry } from './mode-results.js';
import { parseInitialProfiles } from './solver-json.js';
import {constrainedRateHelp,rateLabel,controlInputLabel,baseConditionSummary} from './frequency-frame-help.js';
import {frequencyCycleUnit,frequencySampleLabel,frequencyPlaybackPhase} from './frequency-playback.js';
const $=id=>document.getElementById(id);
const fmt=x=>Number.isFinite(x)?x.toPrecision(6):'—';
const csv=row=>row.map(x=>'"'+String(x??'').replaceAll('"','""')+'"').join(',');
export const frequencySettings=`
<div id="frequency-settings" hidden>
  <div id="frequency-fluid-slot"></div>
  <label class="field-label" for="frequency-frame">Response frame</label><select id="frequency-frame"><option value="fixed">Fixed aircraft · body motion held fixed</option><option value="prescribed">Prescribed accelerations</option><option value="free" selected>Free flight · six dynamic accelerations</option><option value="mixed">Mixed motion · per axis</option></select>
  ${frameConstraintFields('frequency')}
  <div class="fields"><label>Start f <span id="frequency-start-unit">Hz</span><input id="frequency-start" type="number" min="0" step="any" value="0.1" data-frequency-unit="cycles"></label><label>End f <span id="frequency-end-unit">Hz</span><input id="frequency-end" type="number" min="0" step="any" value="10" data-frequency-unit="cycles"></label><label>Samples<input id="frequency-count" type="number" min="2" max="200" step="1" value="21"></label></div>
  <label class="field-label" for="frequency-spacing">Frequency spacing</label><select id="frequency-spacing"><option value="log">Logarithmic · start above zero</option><option value="linear">Linear · allows zero</option></select>
  <label class="field-label" for="frequency-inputs">Response inputs</label><select id="frequency-inputs"><option value="all">Declared flaps, engines and gusts</option><option value="controls">Declared flaps and engines</option><option value="gust">Gusts only</option><option value="frame">Frame loads and accelerations</option><option value="initial">Initial disturbances only</option></select>
  <details id="frequency-gust-settings" class="advanced"><summary>Harmonic gust family</summary>
    <div class="fields">${['x','y','z'].map((axis,i)=>`<label>Earth direction ${axis}<input id="frequency-gust-${axis}" type="number" step="any" value="${i===2?1:0}"></label>`).join('')}<label>Largest span mode n<input id="frequency-span-mode" type="number" min="0" step="1" value="0"></label></div>
    <label class="field-label" for="frequency-parity">Span variation</label><select id="frequency-parity"><option value="cosine">Cosine · n = 0 through maximum</option><option value="sine">Sine · n = 1 through maximum</option><option value="both">Cosine and sine families</option></select>
    <label class="field-label" for="frequency-wave">Streamwise variation</label><select id="frequency-wave"><option value="convected">Frozen Earth field · convected by flight</option><option value="uniform">Uniform in streamwise direction · temporal</option></select>
    <p class="small muted">Direction is normalized. Gust amplitude uses input L/T. Span wavenumber is 2πn / reference span along the loaded body y direction projected normal to the flight path. Phase is zero at the loaded body origin. Each span mode is a separate input.</p>
  </details>
  <details id="frequency-initial-settings" class="advanced"><summary>Initial disturbances</summary>
    <label class="field-label" for="frequency-initial">Physical initial profiles · JSON array</label><textarea id="frequency-initial" rows="6" spellcheck="false">[]</textarea>
    <div class="fields"><label>Laplace damping σ <span>1/input T</span><input id="frequency-initial-shift" type="number" min="0" step="any" value="0"></label><label>Constraint rank tolerance<input id="frequency-initial-rank" type="number" min="1e-12" max="1e-5" step="any" value="1e-9"></label></div>
    <div class="file-actions"><button id="frequency-initial-open">Import profiles</button><button id="frequency-initial-save">Export profiles</button><input id="frequency-initial-file" type="file" accept=".json,application/json" hidden></div>
    <p id="frequency-initial-note" class="small muted">Add initial inputs with kind: "initial", name and state. State supports beam_fields tables [t,x,y,z], exact nodes, physical circulation, frame motion and controller integrals/states. Omitted dynamic fields are zero; incompatible constraints are rejected. Profiles use file units and radians. The source archive includes examples/initial-spring.json.</p>
    <p class="small muted">Profiles are added to the selected harmonic inputs, or used alone with Initial disturbances only. Spectra integrate the response from t=0 with exp(−(σ+iω)t), so output units include one extra time unit. σ=0 requires decay; increase σ above the reported growth rate for neutral or unstable systems. Spectra do not define a periodic motion animation.</p>
  </details>
  <details class="advanced"><summary>Linearization and export</summary><div class="fields"><label>Difference step<input id="frequency-step" type="number" min="0.0000001" max="0.001" step="any" value="0.00001"></label></div><label class="checkbox"><input id="frequency-matrices" type="checkbox"><span>Include full A, M and B matrices in JSON</span></label></details>

</div>`;
export const frequencyTransport=`
<div id="frequency-transport" class="time-transport" hidden>
  <button id="frequency-play">Play</button><input id="frequency-phase" type="range" min="0" max="360" step="any" value="0" aria-label="Harmonic response phase"><output id="frequency-phase-label">0°</output>
  <label>View<select id="frequency-view"><option value="body">Body frame</option><option value="earth">Earth frame</option></select></label>
  <label>Playback<select id="frequency-playback"><option value="model">Model time · 1 T/s</option><option value="inspection">Phase inspection · 4 s/cycle</option></select></label>
  <label>Input amplitude<input id="frequency-amplitude" type="number" min="0" step="any" value="1" aria-label="Harmonic input amplitude"></label><span id="frequency-amplitude-unit" class="small muted"></span>
</div>`;
export const frequencyPane=`
<div id="pane-frequency" class="tab-pane mode-pane" role="tabpanel" aria-labelledby="tab-frequency" hidden>
  <p id="frequency-summary" class="small muted">Select frequency response, then run an analysis.</p>
  <p id="frequency-base-condition" class="small" hidden></p>
  <div class="time-toolbar"><label>Input<select id="frequency-input"></select></label><label>Output group<select id="frequency-group"><option value="global">Global forces and coefficients</option><option value="nodes">Structural nodes</option><option value="sections">Section loads and strains</option><option value="strips">Aerodynamic strips</option><option value="frame">Flight frame</option><option value="operating">Operating variables and controls</option><option value="sensors">Sensors</option><option value="feedback">Controller</option></select></label><label>Output<select id="frequency-quantity"></select></label><label id="frequency-station-label">Station<select id="frequency-station"></select></label></div>
  <div class="time-toolbar"><label>Display<select id="frequency-display"><option value="response">Response · x/u</option><option value="broken_loop">Broken loop · 1 − u/x</option></select></label><label>Gain scale<select id="frequency-gain"><option value="absolute">Magnitude · logarithmic</option><option value="linear">Magnitude · linear</option><option value="db">20 log₁₀ magnitude · dB</option></select></label><label>Phase<select id="frequency-phase-mode"><option value="unwrap">Unwrapped</option><option value="wrap">±180°</option></select></label><label>Frequency axis<select id="frequency-axis"><option value="log">Logarithmic</option><option value="linear">Linear</option></select></label><label>Frequency units<select id="frequency-units"><option value="cycles">Cycles / input T · Hz when T = s</option><option value="radians">Radians / input T</option></select></label><label>Angular response units<select id="frequency-angle-units"><option value="degrees">Degrees</option><option value="radians">Radians</option></select></label><button id="frequency-csv" disabled>Bode CSV</button></div>
  <p id="frequency-unit" class="small muted"></p><div id="frequency-frame-notice" hidden><p id="frequency-frame-explanation" class="small muted"></p></div><div id="frequency-gain-plot" class="plot-chart"></div><div id="frequency-phase-plot" class="plot-chart"></div>
  <div class="time-toolbar"><label>Frequency and shape<select id="frequency-sample"></select></label></div><p id="frequency-detail" class="small muted"></p>
  ${comparisonPane}
  <details id="frequency-refinement" class="advanced"><summary>Add samples or extend the frequency range</summary>
    <div class="time-toolbar"><label>Start ω [rad/T]<input id="frequency-add-start" type="number" min="0" step="any" value="10"></label><label>End ω [rad/T]<input id="frequency-add-end" type="number" min="0" step="any" value="30"></label><label>Samples<input id="frequency-add-count" type="number" min="2" max="200" step="1" value="11"></label><label>Spacing<select id="frequency-add-spacing"><option value="linear">Linear</option><option value="log">Logarithmic</option></select></label><button id="frequency-add-range" disabled>Add range</button></div>
    <div class="time-toolbar"><label>Additional ω values [rad/T]<input id="frequency-add-values" type="text" placeholder="0, 12, 15.5, 16, 120"></label><button id="frequency-add-list" disabled>Add listed frequencies</button></div>
    <p id="frequency-add-status" class="small muted" role="status">Run a frequency analysis to enable refinement.</p>
  </details>
</div>`;

// Physical unit input amplitude; unlike eigenmodes there is no shape normalization.
export function frequencyGeometry(result,sample,input,phase,amplitude,earth=false){
  const response=result.samples[sample]?.responses[input];
  if(!response?.output||result.inputs?.[input]?.kind==='initial')return null;
  return modeGeometry({base:result.base,modes:[response]},0,phase,amplitude,earth,false);
}
function option(select,value,label){const o=document.createElement('option');o.value=value;o.textContent=label;select.append(o);}
export function frequencyRange(start,end,count,log=false){
  if(![start,end,count].every(Number.isFinite)||end<=start||start<0||(log&&start===0)||!Number.isInteger(count)||count<2||count>200)throw new Error('Enter an increasing frequency range and 2–200 samples; logarithmic spacing needs a positive start.');
  return Array.from({length:count},(_,i)=>i===0?start:i===count-1?end:log?Math.exp(Math.log(start)+(Math.log(end)-Math.log(start))*i/(count-1)):start+(end-start)*i/(count-1));
}

export function createFrequencyResults(onView,onEdit,download,getModel,extend=()=>{},canRefine=()=>true,onError=()=>{}){
  let result=null,input=0,sample=0,animation=null,quantities=[];
  bindFrameConstraints('frequency',onEdit);
  const resolved=s=>Boolean(s?.responses[input]?.output);
  const initial=()=>result?.inputs[input]?.kind==='initial';
  const first=()=>result?.samples.find(resolved)?.responses[input]?.output;
  const broken=()=>$('frequency-display').value==='broken_loop';
  const matched=()=>result?.inputs[input].broken_loop_output;
  function selection(){
    const q=broken()?matched():quantity(),group=broken()?q?.group:$('frequency-group').value;
    return {display:broken()?'broken_loop':'response',inputName:result?.inputs[input]?.name,group,key:q?.key,component:q?.component??null,station:!broken()&&Array.isArray(first()?.[group])?Number($('frequency-station').value):null,
      sample,log:$('frequency-axis').value==='log',db:$('frequency-gain').value==='db',logMagnitude:$('frequency-gain').value==='absolute',frequencyUnits:$('frequency-units').value,angleUnits:$('frequency-angle-units').value,unwrap:$('frequency-phase-mode').value==='unwrap'};
  }
  function activateComparison(trace,index){
    const channel=result.inputs.findIndex(c=>c.name===trace.inputName);if(channel<0)return;
    pause();input=channel;$('frequency-input').value=input;$('frequency-display').value=trace.display;
    if(trace.group)$('frequency-group').value=trace.group;
    outputs(trace);if(trace.station!=null)$('frequency-station').value=trace.station;
    select(index);
  }
  const comparison=createFrequencyComparison(selection,activateComparison,download);

  function pause(){if(animation!==null)cancelAnimationFrame(animation);animation=null;$('frequency-play').textContent='Play';}
  function quantity(){return quantities[Number($('frequency-quantity').value)];}
  function unit(){if(broken())return 'dimensionless';const q=quantity();return q?`${unitFor($('frequency-group').value,q.key,result?.controller)}${initial()?' · input T':''} / (${result.inputs[input].unit})`:'';}
  function value(point){return frequencyValue(result,point,selection());}
  function series(){return frequencySeries(result,selection(),$('frequency-phase-mode').value==='unwrap');}
  function plotCurve(id,field,label){
    const data=series(),log=$('frequency-axis').value==='log',logY=field==='magnitude'&&$('frequency-gain').value==='absolute';
    const cycles=$('frequency-units').value==='cycles',factor=cycles?1/(2*Math.PI):1;
    const display=displayResponseUnit(unit(),$('frequency-angle-units').value);
    const value=p=>!Number.isFinite(p[field])?NaN:field==='magnitude'?p[field]*display.scale:field==='db'?p[field]+20*Math.log10(display.scale):p[field];
    const valid=p=>Number.isFinite(p.omega*factor)&&Number.isFinite(value(p))&&(!log||p.omega*factor>0)&&(!logY||value(p)>0);
    const points=data.filter(valid);
    $(id).replaceChildren();if(!points.length){$(id).textContent=logY&&data.some(p=>p.magnitude===0)?'Zero magnitude cannot be shown on a logarithmic axis. Choose Magnitude · linear to display zeros.':`No ${label.toLowerCase()} values available.`;return;}
    const xaxis=plotAxis(result.samples.map(p=>p.omega*factor),{scale:log?'log':'linear'});
    const yaxis=plotAxis(points.map(value),{scale:logY?'log':'linear'});
    const X=x=>85+xaxis.position(x*factor)*620,Y=y=>155-yaxis.position(y)*135;
    let svg=`<svg viewBox="0 0 760 205" role="img" aria-label="${label} versus ${cycles?'frequency':'angular frequency'}" data-x-scale="${xaxis.scale}" data-y-scale="${yaxis.scale}">`;
    for(const tick of xaxis.ticks){const x=85+tick.position*620;svg+=`<path d="M${x} 20V155" class="plot-grid ${tick.major?'plot-grid-major':'plot-grid-minor'}"/>`;if(tick.label)svg+=`<text data-axis="x" data-value="${tick.value}" x="${x}" y="178" text-anchor="middle">${tick.label}</text>`;}
    for(const tick of yaxis.ticks){const y=155-tick.position*135;svg+=`<path d="M85 ${y}H705" class="plot-grid ${tick.major?'plot-grid-major':'plot-grid-minor'}"/>`;if(tick.label)svg+=`<text data-axis="y" data-value="${tick.value}" x="75" y="${y+4}" text-anchor="end">${tick.label}</text>`;}
    let path='',connected=false;
    data.forEach((p,i)=>{if(!valid(p)){connected=false;return;}const y=value(p);path+=`${connected?'L':'M'}${X(p.omega)} ${Y(y)} `;connected=true;svg+=`<circle data-frequency="${i}" cx="${X(p.omega)}" cy="${Y(y)}" r="${sample===i?5:2.5}" class="${sample===i?'modal-selected':'section-point'}"><title>${cycles?'f':'ω'}=${fmt(p.omega*factor)}, ${fmt(y)}</title></circle>`;});
    svg+=`<path d="${path}" class="plot-line" pointer-events="none"/><text x="395" y="200" text-anchor="middle">${cycles?'f [cycles/input T; Hz when T = s]':'ω [rad/input T]'} · ${label}</text></svg>`;
    $(id).innerHTML=svg;$(id).querySelectorAll('[data-frequency]').forEach(c=>c.onclick=()=>select(Number(c.dataset.frequency)));
  }
  function plots(){
    for(const id of ['frequency-input','frequency-group','frequency-display','frequency-gain','frequency-phase-mode','frequency-axis','frequency-units','frequency-angle-units','frequency-sample'])$(id).disabled=!result;
    $('frequency-quantity').disabled=!result||!quantities.length;
    $('frequency-station').disabled=!result||!$('frequency-station').options.length;
    for(const id of ['frequency-gain-plot','frequency-phase-plot'])$(id).replaceChildren();
    const frameNote=constrainedRateHelp(result,selection());
    $('frequency-frame-notice').hidden=!frameNote;
    $('frequency-frame-explanation').textContent=frameNote;
    $('frequency-csv').textContent=broken()?'Broken-loop CSV':initial()?'Spectrum CSV':'Bode CSV';
    $('frequency-display').options[0].textContent=initial()?'Initial spectrum · X(s)':'Response · x/u';
    $('frequency-unit').textContent='';if(!result){comparison.render();return;}
    for(const id of ['frequency-group','frequency-quantity'])$(id).closest('label').hidden=broken();
    $('frequency-station-label').hidden=broken()||!Array.isArray(first()?.[$('frequency-group').value]);
    $('frequency-csv').disabled=!broken()&&!quantities.length;
    if(!broken()&&!quantities.length){
      $('frequency-unit').textContent=frameNote||'No recorded outputs. Choose another output group.';
      comparison.render();return;
    }
    const db=$('frequency-gain').value==='db',match=matched(),displayUnit=displayResponseUnit(unit(),$('frequency-angle-units').value);
    $('frequency-unit').textContent=broken()?(match?`1 − u/x · x: ${match.name} · u: ${result.inputs[input].name} · dimensionless`:'No matching output for broken-loop response.'):`Response [${displayUnit.unit}]${db?' · dB reference: 1':''}`;
    if(initial()&&!broken())$('frequency-unit').textContent=`Initial-state spectrum [${displayUnit.unit}] · σ = ${fmt(result.inputs[input].laplace_shift)} / T`;
    if($('frequency-axis').value==='log'&&result.samples.some(s=>s.omega===0))$('frequency-unit').textContent+=' Zero frequency is omitted on the logarithmic axis; choose Linear to display it.';
    plotCurve('frequency-gain-plot',db?'db':'magnitude',db?'Gain [dB]':'Magnitude');plotCurve('frequency-phase-plot','phase','Phase [deg]');comparison.render();
  }
  function stations(){
    const previous=$('frequency-station').value;$('frequency-station').replaceChildren();
    const group=$('frequency-group').value,rows=first()?.[group];$('frequency-station-label').hidden=!Array.isArray(rows);
    if(Array.isArray(rows))rows.forEach((r,i)=>{const s=group==='nodes'?result.base.nodes.find(n=>n.index===r.index):r;option($('frequency-station'),i,`${group==='sensors'?`Sensor ${s.index} · `:''}Beam ${s.beam} · t=${fmt(s.t)}`);});
    if([...$('frequency-station').options].some(o=>o.value===previous))$('frequency-station').value=previous;
    else if($('frequency-station').options.length)$('frequency-station').selectedIndex=$('frequency-station').options.length-1;
    plots();detail();
  }
  function sampleLabels(){
    if(!result)return;
    for(const [i,o] of [...$('frequency-sample').options].entries())o.textContent=frequencySampleLabel(result.samples[i].omega,$('frequency-units').value,getModel())+(resolved(result.samples[i])?'':' · unavailable');
  }
  function outputs(preferred=quantity()){
    if(result){
      sampleLabels();
      $('frequency-summary').textContent=`${result.samples.filter(resolved).length}/${result.samples.length} frequencies · ${result.inputs.length} inputs · ${result.frame_mode} frame`;
    }
    const previous=preferred?.key?preferred:quantity();let row=first()?.[$('frequency-group').value];
    // A body strip can precede a lifting strip. Discover available quantities
    // across the group while leaving unavailable station values as gaps.
    if(Array.isArray(row))row=Object.fromEntries(row.flatMap(r=>Object.entries(r).filter(([,v])=>v&&typeof v==='object'&&Object.hasOwn(v,'real'))));
    quantities=[];$('frequency-quantity').replaceChildren();
    for(const [key,v] of Object.entries(row??{})){
      if(!v||typeof v!=='object'||!Object.hasOwn(v,'real'))continue;
      const components=Array.isArray(v.real)?v.real.map((_,i)=>i):[null];
      for(const component of components){if(component!=null&&Array.isArray(v.real[component]))continue;const q={key,component};quantities.push(q);const group=$('frequency-group').value,axes=group==='sensors'?(sensorFields.find(f=>f[0]===key)?.[3]??[]):group==='sections'?['c','s','n']:['x','y','z'];const label=rateLabel(group,key,component)??`${key.replaceAll('_',' ')}${component==null?'':` ${axes[component]??component}`}`;option($('frequency-quantity'),quantities.length-1,`${label} [${unitFor(group,key,result?.controller)}]`);}
    }
    let index=quantities.findIndex(q=>q.key===previous?.key&&q.component===previous?.component);
    if(index<0)index=quantities.findIndex(q=>q.key==='CL');if(index>=0)$('frequency-quantity').value=index;
    $('frequency-quantity').disabled=!quantities.length;
    if(!quantities.length)option($('frequency-quantity'),'',$('frequency-group').value==='frame'&&result?.frame_mode==='fixed'?'Unavailable · aircraft motion held fixed':'No recorded outputs');
    $('frequency-csv').disabled=!quantities.length;
    stations();
  }
  function detail(){
    if(!result)return;
    const point=result.samples[sample],v=value(point),warning=point.gust_profiles[input]?.spatial_resolution_warning;
    const display=displayResponseUnit(unit(),$('frequency-angle-units').value);
    $('frequency-detail').textContent=`ω = ${fmt(point.omega)} rad/T · f = ${fmt(point.frequency)} cycles/T · `+(v?.error?`Unavailable: ${v.error}`:`Magnitude ${fmt(v.magnitude*display.scale)} [${display.unit}]`)+(warning?' · Gust under-resolved: refine the mesh.':'');
    $('frequency-transport').hidden=!resolved(point)||initial();$('frequency-amplitude-unit').textContent=result.inputs[input].unit;
    const clock=$('frequency-playback').value;
    $('frequency-play').disabled=!resolved(point)||initial()||(clock==='model'&&point.omega===0);
  }
  function select(index,fit=false){if(!result)return;pause();sample=index;$('frequency-sample').value=index;detail();plots();onView(fit);}
  function refresh(){
    const inputUnit=frequencyCycleUnit(getModel());
    for(const id of ['frequency-start-unit','frequency-end-unit'])$(id).textContent=inputUnit;
    const disabled=!result?.frequency_session||!canRefine();
    for(const e of $('frequency-refinement').querySelectorAll('input,select,button'))e.disabled=disabled;
  }
  function setResult(data,preserve=false){
    const picked=preserve&&result?{name:result.inputs[input].name,omega:result.samples[sample].omega,q:quantity(),station:$('frequency-station').value}:null;
    pause();result=data;comparison.setResult(data,preserve);input=0;sample=0;
    for(const id of ['frequency-input','frequency-sample','frequency-quantity','frequency-station'])$(id).replaceChildren();
    $('frequency-transport').hidden=!data;$('frequency-csv').disabled=!data;
    $('frequency-summary').textContent=data?`${data.samples.filter(s=>s.converged).length}/${data.samples.length} frequencies · ${data.inputs.length} inputs · ${data.frame_mode} frame`:'Select frequency response, then run an analysis.';
    $('frequency-base-condition').textContent=baseConditionSummary(data,getModel());
    $('frequency-base-condition').hidden=!data;
    $('frequency-detail').textContent='';
    const refinement=data?.frequency_refinement;
    $('frequency-add-status').textContent=!data?'Run a frequency analysis to enable refinement.':refinement?.linearization_reused?`${refinement.added_frequencies.length} new frequencies computed; ${refinement.retained_samples} existing samples retained; ${refinement.duplicate_frequencies.length} exact duplicates skipped.`:data.frequency_session?'Refinement is ready for this loaded analysis.':'This result has no active refinement session. Run the analysis again to add samples.';
    refresh();
    if(data){
      if(picked){input=Math.max(0,data.inputs.findIndex(c=>c.name===picked.name));sample=Math.max(0,data.samples.findIndex(s=>s.omega===picked.omega));}
      data.inputs.forEach((c,i)=>option($('frequency-input'),i,`${controlInputLabel(c,getModel())} [${c.unit}]`));
      data.samples.forEach((s,i)=>option($('frequency-sample'),i,frequencySampleLabel(s.omega,$('frequency-units').value,getModel())));
      $('frequency-input').value=input;
      if(!picked){$('frequency-phase').value=0;$('frequency-phase-label').textContent='0°';$('frequency-axis').value=data.request?.frequency_spacing??'log';}
      if(data.samples.some(s=>s.omega===0)&&$('frequency-axis').value==='log'){$('frequency-axis').value='linear';if(picked)$('frequency-add-status').textContent+=' Frequency axis changed to Linear to include zero.';}
      const valid=data.samples.findIndex(resolved);outputs(picked?.q);
      if(picked&&[...$('frequency-station').options].some(o=>o.value===picked.station))$('frequency-station').value=picked.station;
      select(picked?sample:valid<0?0:valid,!picked);
    }else plots();
  }
  function options(){
    const start=Number($('frequency-start').value),end=Number($('frequency-end').value),count=Number($('frequency-count').value),log=$('frequency-spacing').value==='log';
    const frequencies=frequencyRange(start,end,count,log).map(frequency=>2*Math.PI*frequency);
    const model=getModel(),inputs=[],motion=frameOptions('frequency');
    if(['all','controls'].includes($('frequency-inputs').value))inputs.push(...model.controls.map(k=>`control.${k}`),...model.engine_controls.map(k=>`power.${k.index}`));
    if(['all','gust'].includes($('frequency-inputs').value)){
      const maximum=Number($('frequency-span-mode').value),parity=$('frequency-parity').value,direction=['x','y','z'].map(a=>Number($(`frequency-gust-${a}`).value));
      if(!Number.isSafeInteger(maximum)||maximum<0)throw new Error('Largest span mode must be a nonnegative integer.');
      if(parity==='sine'&&maximum===0)throw new Error('Sine gusts need a largest span mode of at least one.');
      for(const symmetry of (parity==='both'?['cosine','sine']:[parity]))for(let n=symmetry==='sine'?1:0;n<=maximum;n++)inputs.push({kind:'gust',name:`gust ${symmetry} n=${n}`,direction,span_mode:n,symmetry,wave:$('frequency-wave').value});
    }
    if($('frequency-inputs').value==='frame'){
      if(motion.frame==='fixed')throw new Error('Choose prescribed, free or mixed motion for frame load and acceleration inputs.');
      inputs.push(...frameInputs(motion.frame,motion.load_targets));
    }
    const profiles=initialProfiles();inputs.push(...profiles);
    if($('frequency-inputs').value==='initial'&&!profiles.length)throw new Error('Enter or import at least one physical initial disturbance.');
    return {...motion,frequencies,inputs,initial_shift:Number($('frequency-initial-shift').value),initial_rank_tolerance:Number($('frequency-initial-rank').value),step:Number($('frequency-step').value),matrices:$('frequency-matrices').checked};
  }
  function initialProfiles(){return parseInitialProfiles($('frequency-initial').value);}
  $('frequency-initial-open').onclick=()=>$('frequency-initial-file').click();
  $('frequency-initial-save').onclick=()=>{try{download('openswing-initial-profiles.json',JSON.stringify(initialProfiles(),null,2),'application/json');$('frequency-initial-note').textContent='Exported physical initial profiles.';}catch(error){$('frequency-initial-note').textContent=error.message;}};
  $('frequency-initial-file').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;const profiles=parseInitialProfiles(await file.text());$('frequency-initial').value=JSON.stringify(profiles,null,2);onEdit();$('frequency-initial-note').textContent='Imported physical initial profiles. The solve will check mesh and dynamic constraints.';}catch(error){$('frequency-initial-note').textContent=error.message;}finally{e.target.value='';}};
  $('frequency-input').onchange=()=>{input=Number($('frequency-input').value);pause();outputs();onView(true);};
  // Display selectors only read the saved result. They must not invalidate
  // its continuation session or invoke the numerical-settings callback.
  $('frequency-group').onchange=()=>outputs();$('frequency-quantity').onchange=()=>{plots();detail();};$('frequency-station').onchange=()=>{plots();detail();};
  for(const id of ['frequency-gain','frequency-phase-mode','frequency-axis','frequency-units','frequency-angle-units'])$(id).onchange=plots;
  $('frequency-units').onchange=()=>{sampleLabels();plots();};
  $('frequency-angle-units').onchange=()=>{plots();detail();};
  async function addSamples(list){
    if(!result?.frequency_session||!canRefine())return;
    try{
      const finite=value=>{if(String(value).trim()===''||!Number.isFinite(Number(value)))throw new Error('Enter finite angular frequencies and sample counts.');return Number(value);};
      const frequencies=list?$('frequency-add-values').value.trim().split(/[,;\s]+/).map(finite):frequencyRange(...['start','end','count'].map(k=>finite($(`frequency-add-${k}`).value)),$('frequency-add-spacing').value==='log');
      if(frequencies.some(w=>w<0))throw new Error('Angular frequencies must be nonnegative.');
      $('frequency-add-status').textContent='Computing additional samples on the loaded dynamic model…';
      await extend(frequencies);
    }catch(error){$('frequency-add-status').textContent=error.message.split('\n').filter(Boolean).at(-1);onError(error);}
    finally{refresh();}
  }
  $('frequency-add-range').onclick=()=>addSamples(false);$('frequency-add-list').onclick=()=>addSamples(true);
  $('frequency-display').onchange=()=>{plots();detail();};
  $('frequency-sample').onchange=()=>select(Number($('frequency-sample').value));
  // Bind actual calculation inputs by identity, independent of responsive
  // DOM placement. Result selectors and file pickers cannot clear a solve.
  for(const name of ['frame','start','end','count','spacing','inputs','gust-x','gust-y','gust-z','span-mode','parity','wave','initial','initial-shift','initial-rank','step','matrices'])
    $(`frequency-${name}`).addEventListener('input',onEdit);
  $('frequency-inputs').addEventListener('change',()=>{$('frequency-gust-settings').hidden=!['all','gust'].includes($('frequency-inputs').value);});
  const phase=()=>{$('frequency-phase-label').textContent=`${Math.round(Number($('frequency-phase').value))}°`;onView(false);};
  $('frequency-phase').oninput=()=>{pause();phase();};$('frequency-view').onchange=()=>{pause();onView(true);};
  $('frequency-playback').onchange=()=>{pause();detail();};
  $('frequency-amplitude').oninput=()=>{if($('frequency-amplitude').value&&$('frequency-amplitude').checkValidity())onView(false);};
  $('frequency-play').onclick=()=>{
    if(animation!==null){pause();return;}if(!result)return;
    const start=performance.now(),p=Number($('frequency-phase').value),omega=result.samples[sample].omega,clock=$('frequency-playback').value;
    if(clock==='model'&&omega===0)return;
    $('frequency-play').textContent='Pause';
    const frame=now=>{$('frequency-phase').value=frequencyPlaybackPhase(p,now-start,omega,clock);phase();animation=requestAnimationFrame(frame);};animation=requestAnimationFrame(frame);
  };
  $('frequency-csv').onclick=()=>{
    const q=broken()?matched():quantity();if(!q&&!broken())return;const group=broken()?q?.group:$('frequency-group').value;
    download(broken()?'openswing-broken-loop.csv':initial()?'openswing-initial-spectrum.csv':'openswing-bode.csv',[csv(['display','formula','input','output group','output','component','station index','omega [rad/T]','frequency [cycles/T]','Laplace damping [1/T]',`real [${unit()}]`,`imag [${unit()}]`,`magnitude [${unit()}]`,'gain [dB]','phase [deg]','status']),...series().map(v=>csv([broken()?'broken loop':initial()?'initial spectrum':'response',broken()?'1 - u/x':initial()?'X(s) / profile amplitude':'x/u',result.inputs[input].name,group,q?.key,q?.component,$('frequency-station-label').hidden?'':$('frequency-station').value,v.omega,v.omega/(2*Math.PI),result.inputs[input].laplace_shift??0,v.real,v.imag,v.magnitude,v.db,v.phase,v.error??'resolved']))].join('\n')+'\n','text/csv');
  };
  return {setResult,pause,options,initial,refresh,captureComparison:comparison.capture,restoreComparison:comparison.restore,
    spanState:()=>!initial()&&result?.samples[sample]?.responses[input]?.output?
      {output:result.samples[sample].responses[input].output,phase:Number($('frequency-phase').value)*Math.PI/180,scale:Number($('frequency-amplitude').value)}:null,
    playback:()=>({playing:animation!==null,periodic:true,durationMs:$('frequency-playback').value==='inspection'?4000:2000*Math.PI/(result?.samples[sample]?.omega??0)}),
    geometry:()=>frequencyGeometry(result,sample,input,Number($('frequency-phase').value)*Math.PI/180,Number($('frequency-amplitude').value),$('frequency-view').value==='earth')};
}
