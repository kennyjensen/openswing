import {isQuiescentResult} from './quiescent-settings.js';
import {frameInputs} from './dynamic-frame.js';
import {initialRomSettings,initialRomResults,createRomInitial} from './rom-initial.js';
import {physicalOutputSettings,createPhysicalRomOutputs} from './rom-outputs.js';
import {sensorFieldAvailable} from './sensor-results.js';
const $=id=>document.getElementById(id);
const fmt=x=>Number.isFinite(x)?x.toPrecision(6):'—';
export function defaultSensorRomOutputs(sensor){
  if(!sensor)return 'V, A, B, Ax, Ay, Az, Wx, Wy, Wz';
  return [['position_earth',['RX','RY','RZ']],['velocity_earth',['UX','UY','UZ']],['acceleration_sensor',['Ax','Ay','Az']]]
    .filter(([field])=>sensorFieldAvailable(sensor,field)).flatMap(([,names])=>names.map(name=>`${name}[${sensor.index}]`)).join(', ');
}
export const romPane=`
<details id="rom-settings" class="advanced">
  <summary>Reduced-order model</summary>
  <p class="small muted">Select modes and inputs, then build a real matrix model about this modal base. Complex modes include their conjugate partner. Compare the reduced and full responses over your frequency range before using the model.</p>
  <label class="field-label" for="rom-modes">Retained modes · select multiple as needed</label><select id="rom-modes" multiple size="4"></select>
  <label class="field-label" for="rom-inputs">Inputs · select multiple as needed</label><select id="rom-inputs" multiple size="4"></select>
  <label class="field-label" for="rom-outputs">Output measurements · comma separated</label><textarea id="rom-outputs" rows="2" spellcheck="false"></textarea>
  <p class="small muted">Global V, A, B, Ax/Ay/Az, Wx/Wy/Wz, RX/RY/RZ, UX/UY/UZ; add [sensor number] for a sensor, such as Ay[2]. Positions and velocities use Earth axes; accelerometers use the selected sensor axes. Angles use degrees.</p>
  ${physicalOutputSettings}
  <label class="field-label" for="rom-frequencies">Comparison frequencies · rad/input T, comma separated</label><input id="rom-frequencies" value="0, 1, 3, 10, 30, 100">
  ${initialRomSettings}
  <div class="time-toolbar"><button id="rom-build" disabled>Build reduced model</button><button id="rom-json" disabled>ROM JSON</button><button id="rom-text" disabled>Matrix text</button><button id="rom-legacy" disabled>ASWING .rom</button></div>
  <p id="rom-legacy-note" class="small muted"></p>
  <p id="rom-summary" class="small muted">Run an aerodynamic modal analysis first.</p>
  <div id="rom-results" hidden>
    <div class="time-toolbar"><label>Input<select id="rom-input"></select></label><label>Output<select id="rom-output"></select></label></div>
    <p id="rom-unit" class="small muted"></p><div id="rom-plot" class="plot-chart"></div>
    <div class="derivative-table-wrap"><table id="rom-comparison"><thead><tr><th>ω [rad/T]</th><th>Full real</th><th>Full imaginary</th><th>Reduced real</th><th>Reduced imaginary</th><th>Absolute error</th></tr></thead><tbody></tbody></table></div>
    <details><summary>Real matrices and equations</summary><pre id="rom-matrices"></pre></details>
    ${initialRomResults}
    <p class="small muted">Initial profiles, projected states and histories are included in ROM JSON; matrix text includes initial states. ASWING .rom exports contain the driven matrix model.</p>
  </div>
  <p class="small muted">Direct constraint and acceleration response is retained separately from the selected modes. Truncation can omit unstable modes. JSON includes the complete state maps and comparisons. The annotated .rom export uses SI physical quantities, with actuator settings in file units; physical sample, custom command/gust/frame and global Earth-velocity labels are OpenSwing extensions. Rate-dependent input feedthrough requires JSON or matrix text. Convected gusts and defective modes require the full descriptor analysis.</p>
</details>`;

function option(select,value,label,selected=false){const o=document.createElement('option');o.value=value;o.textContent=label;o.selected=selected;select.append(o);}
export function createRomResults(run,download,showError,getModel){
  let base=null,result=null,inputs=[],revision=0,running=false;
  function clear(){result=null;revision++;$('rom-results').hidden=true;$('rom-json').disabled=$('rom-text').disabled=$('rom-legacy').disabled=true;$('rom-legacy-note').textContent='';}
  const initial=createRomInitial(download,()=>{clear();$('rom-summary').textContent='Initial profiles changed; build again to update comparisons and exports.';});
  const physical=createPhysicalRomOutputs(()=>{clear();$('rom-summary').textContent='Physical outputs changed; build again to update comparisons and exports.';});
  function setBase(value){
    clear();base=value;$('rom-modes').replaceChildren();$('rom-inputs').replaceChildren();
    physical.setBase(isQuiescentResult(value)?null:value);
    $('rom-build').disabled=!base||base.vacuum||isQuiescentResult(base)||running;
    $('rom-summary').textContent=isQuiescentResult(base)?'ROM generation is unavailable for still-air modal results.':base?.vacuum?'ROM input/output generation currently requires an aerodynamic modal base.':base?'Choose retained modes and measurements, then build the reduced model.':'Run an aerodynamic modal analysis first.';
    if(!base||isQuiescentResult(base))return;
    base.modes.forEach((m,i)=>option($('rom-modes'),i,`${i+1}: ${fmt(m.eigenvalue[0])} + i(${fmt(m.eigenvalue[1])})`,i===0));
    inputs=[...getModel().controls.map(k=>({spec:`control.${k}`,label:`Flap ${k}`})),...getModel().engine_controls.map(e=>({spec:`power.${e.index}`,label:`Engine ${e.index}`})),
      ...frameInputs(base.frame_mode,base.frame_load_targets).map(spec=>({spec,label:spec.replaceAll('.',' ')})),
      ...(base.controller?.signals??[]).map(name=>({spec:`command.${name}`,label:`Command ${name}`})),
      ...['x','y','z'].map((axis,i)=>({spec:{kind:'gust',wave:'uniform',name:`uniform Earth ${axis}`,direction:[0,0,0].map((_,j)=>i===j?1:0)},label:`Uniform gust · Earth ${axis}`}))];
    inputs.forEach((input,i)=>option($('rom-inputs'),i,input.label,i===0));
    $('rom-outputs').value=defaultSensorRomOutputs(base.base.sensors.at(-1));
  }
  function render(){
    if(!result)return;
    if(!result.inputs.length){$('rom-unit').textContent='No periodic inputs selected; see the initial disturbance comparison below.';$('rom-plot').replaceChildren();$('rom-comparison').querySelector('tbody').replaceChildren();return;}
    const i=Number($('rom-input').value),j=Number($('rom-output').value),unit=`${result.outputs[j].unit} / ${result.inputs[i].unit}`;
    const error=result.diagnostics.maximum_normalized_transfer_errors?.[j]?.[i];
    $('rom-unit').textContent=`${result.outputs[j].name} [${unit}] · magnitude: reduced line, full circles. Maximum error / maximum full magnitude on this grid: ${error==null?'undefined for a near-zero response':fmt(error)}.`;
    const body=$('rom-comparison').querySelector('tbody');body.replaceChildren();
    const rows=result.samples.map(s=>{if(!s.converged)return {w:s.omega,error:s.error};const r=[s.reduced.real[j][i],s.reduced.imag[j][i]],f=[s.full.real[j][i],s.full.imag[j][i]];return {w:s.omega,r,f,e:s.absolute_error[j][i],rm:Math.hypot(...r),fm:Math.hypot(...f)};});
    for(const row of rows){const tr=document.createElement('tr');for(const value of row.error?[fmt(row.w),row.error,'—','—','—','—']:[row.w,...row.f,...row.r,row.e].map(fmt)){const td=document.createElement('td');td.textContent=value;tr.append(td);}body.append(tr);}
    const valid=rows.filter(r=>!r.error),max=Math.max(...valid.flatMap(r=>[r.rm,r.fm]),1e-30),end=Math.max(...rows.map(r=>r.w),1e-30);
    const X=x=>80+620*x/end,Y=y=>160-130*y/max;
    let svg='<svg viewBox="0 0 760 205" role="img" aria-label="Reduced and full response magnitude comparison">';
    for(let k=0;k<=4;k++){const x=end*k/4,y=max*k/4;svg+=`<text x="${X(x)}" y="182" text-anchor="middle">${x.toPrecision(3)}</text><text x="70" y="${Y(y)+4}" text-anchor="end">${y.toPrecision(3)}</text><path d="M80 ${Y(y)}H700" class="plot-grid"/>`;}
    // Keep singular frequency gaps visible; do not bridge them with a line.
    let segment=[];const draw=()=>{if(segment.length)svg+=`<polyline points="${segment.join(' ')}" class="plot-line"/>`;segment=[];};
    for(const row of rows){if(row.error){draw();continue;}segment.push(`${X(row.w)},${Y(row.rm)}`);}draw();
    for(const row of valid)svg+=`<circle cx="${X(row.w)}" cy="${Y(row.fm)}" r="3.5" class="section-point"/>`;
    $('rom-plot').innerHTML=svg+'<text x="390" y="201" text-anchor="middle">Angular frequency [rad/input T]</text></svg>';
  }
  function show(data){
      result=data;$('rom-results').hidden=false;$('rom-json').disabled=$('rom-text').disabled=false;
      $('rom-legacy').disabled=!data.legacy_export;$('rom-legacy-note').textContent=data.legacy_export_error??'The .rom file contains complex mode representatives and the complete direct input/output matrix; selected full-state eigenvector rows remain in JSON.';
      $('rom-summary').textContent=`${data.diagnostics.dimension} real states from ${data.diagnostics.finite_dimension} finite states (${data.diagnostics.full_dimension} full coordinates) · ${data.inputs.length} periodic inputs · ${data.outputs.length} outputs · ${data.inputs.length?`${data.samples.filter(s=>s.converged).length}/${data.samples.length} comparison frequencies resolved`:'free response only'}. All exported matrices use the file time unit.`;
      $('rom-input').replaceChildren();$('rom-output').replaceChildren();data.inputs.forEach((x,i)=>option($('rom-input'),i,x.name));data.outputs.forEach((x,i)=>option($('rom-output'),i,x.name));
      $('rom-matrices').textContent=data.equations.join('\n')+'\n\n'+JSON.stringify(data.matrices,null,2);render();initial.setResult(data);
  }
  $('rom-build').onclick=async()=>{
    if(!base||isQuiescentResult(base)||running)return;
    clear();const current=revision;running=true;$('rom-build').disabled=true;$('rom-summary').textContent='Building matrices and comparing with the full response…';
    try{
      const frequencies=$('rom-frequencies').value.split(',').map(v=>Number(v.trim()));
      if(!$('rom-frequencies').value.trim()||$('rom-frequencies').value.split(',').some(x=>!x.trim()))throw new Error('Enter comparison frequencies separated by commas.');
      const options={selected:[...$('rom-modes').selectedOptions].map(o=>Number(o.value)),inputs:[...$('rom-inputs').selectedOptions].map(o=>inputs[Number(o.value)].spec),outputs:[...$('rom-outputs').value.split(',').map(s=>s.trim()).filter(Boolean),...physical.specifications()],frequencies,...initial.options()};
      const data=await run(options);
      if(current!==revision)return;
      show(data);
    }catch(error){if(current===revision){$('rom-summary').textContent='Reduced model could not be generated.';showError(error);}}
    finally{running=false;$('rom-build').disabled=!base||base.vacuum||isQuiescentResult(base);}
  };
  for(const id of ['rom-modes','rom-inputs','rom-outputs','rom-frequencies'])$(id).addEventListener('input',()=>{clear();$('rom-summary').textContent='ROM settings changed; build again to update the comparison and exports.';});
  $('rom-input').onchange=$('rom-output').onchange=render;
  $('rom-json').onclick=()=>download('openswing-rom.json',JSON.stringify(result,null,2),'application/json');
  $('rom-text').onclick=()=>download('openswing-rom.txt',result.text_export);
  $('rom-legacy').onclick=()=>download('openswing.rom',result.legacy_export);
  return {setBase,capture:()=>result?structuredClone(result):null,restore:data=>{if(data){physical.restore(data.outputs);$('rom-outputs').value=data.outputs.filter(o=>!o.selector).map(o=>o.name).join(', ');show(structuredClone(data));}}};
}
