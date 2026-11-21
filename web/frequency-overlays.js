import {traceInfo,traceKey} from './frequency-data.js';
import {inspectBodeCSV,importFrequencyOverlay,OVERLAY_LIMITS} from './frequency-overlay-data.js';
const $=id=>document.getElementById(id);

export const overlayPane=`
<details id="frequency-overlay-settings" class="advanced"><summary>Overlay saved or measured data</summary>
  <div class="time-toolbar"><button id="frequency-overlay-open" disabled>Open local data</button><input id="frequency-overlay-file" type="file" accept=".csv,.txt,.dat,text/plain,text/csv" hidden><span id="frequency-overlay-filename" class="small muted">No file selected.</span></div>
  <p id="frequency-overlay-target" class="small muted"></p>
  <div class="time-toolbar"><label>Overlay label<input id="frequency-overlay-label" type="text" maxlength="160"></label><label>File format<select id="frequency-overlay-mode"><option value="bode">OpenSwing Bode / comparison CSV</option><option value="table">Numeric table · explicit columns</option></select></label></div>
  <label id="frequency-overlay-series-label" class="field-label">CSV series<select id="frequency-overlay-series"></select></label>
  <div id="frequency-overlay-mapping" hidden>
    <div class="time-toolbar"><label>Delimiter<select id="frequency-overlay-delimiter"><option value="whitespace">Whitespace</option><option value="comma">Comma</option><option value="tab">Tab</option><option value="semicolon">Semicolon</option></select></label><label>Header rows to skip<input id="frequency-overlay-skip" type="number" min="0" max="10000" step="1" value="0"></label></div>
    <div class="time-toolbar"><label>Frequency column<input id="frequency-overlay-column-w" type="number" min="1" max="128" step="1" value="1"></label><label>Real / magnitude column<input id="frequency-overlay-column-a" type="number" min="1" max="128" step="1" value="2"></label><label>Imaginary / phase column<input id="frequency-overlay-column-b" type="number" min="1" max="128" step="1" value="3"></label></div>
    <div class="time-toolbar"><label>Response columns<select id="frequency-overlay-format"><option value="rectangular">Real, imaginary</option><option value="polar_deg">Magnitude, phase [deg]</option><option value="polar_rad">Magnitude, phase [rad]</option><option value="db_deg">20 log₁₀ magnitude [dB], phase [deg]</option><option value="db_rad">20 log₁₀ magnitude [dB], phase [rad]</option></select></label><label>Source frequency<select id="frequency-overlay-frequency-unit"><option value="radians">Radians / source time unit</option><option value="cycles">Cycles / source time unit (Hz if seconds)</option></select></label></div>
  </div>
  <div class="time-toolbar"><label>One source time unit [input T]<input id="frequency-overlay-time-scale" type="number" min="0" step="any" value="1"></label><label>Response multiplier<input id="frequency-overlay-response-scale" type="number" step="any" value="1"></label><label>Source harmonic convention<select id="frequency-overlay-convention"><option value="positive">exp(+iωt)</option><option value="negative">exp(−iωt)</option></select></label></div>
  <p class="small muted">The selected response above sets the target units, station and spectrum type. Set the time conversion and multiply source responses into those numerical units, including the dB reference. For example, millimetres per newton to metres per newton uses 0.001. Initial spectra must use the selected Laplace damping. Numeric tables use 1-based columns; whitespace tables allow # or ! comments and Fortran D exponents. Blank, NA, NaN, null or - response fields remain gaps. Frequencies must increase. No interpolation is applied.</p>
  <pre id="frequency-overlay-source" class="overlay-source" hidden></pre>
  <div class="time-toolbar"><button id="frequency-overlay-preview" disabled>Preview overlay</button><button id="frequency-overlay-add" disabled>Add preview to comparison</button></div>
  <p id="frequency-overlay-status" class="small muted" role="status">Select a computed response and open a local data file.</p>
  <p id="frequency-overlay-detail" class="small muted" role="status"></p>
</details>`;

export function createFrequencyOverlays(context,getResult,add){
  let source='',filename='',candidate=null,serial=0,targetKey='';
  const target=()=>{const result=getResult(),s=context();return result&&s?.key?traceInfo(result,s):null;};
  const key=()=>{const info=target();return info?JSON.stringify([traceKey(info.selection),info.unit,info.kind,info.input?.laplace_shift??0]):'';};
  const invalidate=message=>{candidate=null;$('frequency-overlay-add').disabled=true;if(message)$('frequency-overlay-status').textContent=message;};
  function series(){
    $('frequency-overlay-series').replaceChildren();
    if(!source||$('frequency-overlay-mode').value!=='bode')return;
    try{inspectBodeCSV(source).forEach((s,i)=>{const option=document.createElement('option');option.value=i;option.textContent=`${s.label} · ${s.kind} [${s.unit}]`;if(s.kind==='Initial-state spectrum')option.textContent+=` · σ=${s.sigma}`;$('frequency-overlay-series').append(option);});}
    catch(error){$('frequency-overlay-status').textContent=error.message;}
  }
  function refresh(){
    const current=key(),info=target();
    if(current!==targetKey){targetKey=current;invalidate('Target changed. Preview again before adding the overlay.');}
    $('frequency-overlay-open').disabled=!info;$('frequency-overlay-preview').disabled=!info||!source;
    $('frequency-overlay-target').textContent=info?`Target: ${info.label} · ${info.kind} [${info.unit}].`:'Select a computed response before importing data.';
    $('frequency-overlay-mapping').hidden=$('frequency-overlay-mode').value!=='table';$('frequency-overlay-series-label').hidden=$('frequency-overlay-mode').value!=='bode';
  }
  function options(){
    const numeric=id=>{const value=$(id).value;if(value.trim()==='')throw new Error('Fill all numerical mapping and conversion fields.');return Number(value);};
    return {filename,label:$('frequency-overlay-label').value,mode:$('frequency-overlay-mode').value,series:$('frequency-overlay-mode').value==='bode'?numeric('frequency-overlay-series'):0,
      delimiter:$('frequency-overlay-delimiter').value,skip:numeric('frequency-overlay-skip'),columns:['w','a','b'].map(k=>numeric(`frequency-overlay-column-${k}`)),format:$('frequency-overlay-format').value,frequencyUnit:$('frequency-overlay-frequency-unit').value,
      timeScale:numeric('frequency-overlay-time-scale'),responseScale:numeric('frequency-overlay-response-scale'),convention:$('frequency-overlay-convention').value};
  }
  $('frequency-overlay-open').onclick=()=>$('frequency-overlay-file').click();
  $('frequency-overlay-file').onchange=async event=>{
    const file=event.target.files[0],job=++serial;if(!file)return;
    source='';filename='';$('frequency-overlay-source').hidden=true;$('frequency-overlay-filename').textContent='Reading file…';invalidate('Reading local data…');refresh();
    try{
      if(file.size>OVERLAY_LIMITS.bytes)throw new Error('Overlay file exceeds 2 MiB.');
      const text=await file.text();if(job!==serial)return;
      source=text;filename=file.name;$('frequency-overlay-filename').textContent=filename;$('frequency-overlay-label').value=filename.slice(0,160);
      $('frequency-overlay-source').textContent=text.slice(0,2000).split(/\r?\n/).slice(0,8).join('\n');$('frequency-overlay-source').hidden=false;
      try{inspectBodeCSV(source);$('frequency-overlay-mode').value='bode';}catch{$('frequency-overlay-mode').value='table';}
      invalidate('File loaded. Check the target and conversions, then preview.');series();refresh();
    }catch(error){if(job===serial){$('frequency-overlay-filename').textContent='No file selected.';invalidate(error.message);refresh();}}
    finally{event.target.value='';}
  };
  for(const element of $('frequency-overlay-settings').querySelectorAll('input:not([type=file]),select'))element.addEventListener('input',()=>{invalidate('Mapping changed. Preview again before adding.');if(element.id==='frequency-overlay-mode')series();refresh();});
  $('frequency-overlay-preview').onclick=()=>{
    invalidate();
    try{
      candidate=importFrequencyOverlay(source,options(),getResult(),context());
      const resolved=candidate.samples.filter(p=>p.real!=null),first=resolved[0];
      $('frequency-overlay-status').textContent=`Preview: ${candidate.samples.length} samples, ${resolved.length} finite and ${candidate.samples.length-resolved.length} gaps; ω=${candidate.samples[0].omega.toPrecision(6)} to ${candidate.samples.at(-1).omega.toPrecision(6)} rad/input T.${first?` First finite response: ${first.real.toPrecision(6)} + i(${first.imag.toPrecision(6)}) [${candidate.unit}].`:''} Ready to add.`;
      $('frequency-overlay-add').disabled=false;
    }catch(error){invalidate(error.message);}
  };
  $('frequency-overlay-add').onclick=()=>{
    refresh();if(!candidate)return;
    try{add(candidate);invalidate(`Added ${candidate.label}. Comparison CSV includes converted values and source mapping.`);}catch(error){invalidate(error.message);}
  };
  return {refresh,reset(){serial++;invalidate('Analysis changed. Select a response and preview the local data again.');targetKey='';$('frequency-overlay-detail').textContent='';if(!source)$('frequency-overlay-filename').textContent='No file selected.';},inspect(trace,point){
    const p=trace.samples[point];$('frequency-overlay-detail').textContent=`External · ${trace.label}: ω=${p.omega.toPrecision(7)} rad/input T; ${p.error??`${p.real.toPrecision(7)} + i(${p.imag.toPrecision(7)}) [${trace.unit}]`}. Source: ${trace.source.filename}. No computed geometry is associated with this sample.`;
  }};
}
