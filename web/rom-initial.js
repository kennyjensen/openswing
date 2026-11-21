const $=id=>document.getElementById(id);
const fmt=x=>Number.isFinite(x)?x.toPrecision(6):'—';
export const initialRomSettings=`
<details class="advanced" id="rom-initial-settings"><summary>Initial disturbances and free response</summary>
  <label class="field-label" for="rom-initial-profiles">Physical initial profiles · JSON array</label><textarea id="rom-initial-profiles" rows="6" spellcheck="false">[]</textarea>
  <div class="file-actions"><button id="rom-initial-open">Import profiles</button><button id="rom-initial-save">Export profiles</button><input id="rom-initial-file" type="file" accept=".json,application/json" hidden></div>
  <label class="field-label" for="rom-initial-times">Free-response times · input T, comma separated</label><input id="rom-initial-times" value="0, 0.05, 0.1, 0.2, 0.5, 1">
  <label class="field-label" for="rom-initial-shift">Laplace damping σ · 1/input T</label><input id="rom-initial-shift" type="number" min="0" step="any" value="0">
  <p class="small muted" id="rom-initial-import-note">Use the same physical profiles as Initial disturbances in Frequency response. Omitted fields are zero. The full system checks constraints before projecting onto the selected modes. Times and spectra describe linear free motion about the saved base. The source archive includes examples/initial-spring.json.</p>
</details>`;
export const initialRomResults=`
<section id="rom-initial-results" hidden>
  <h3>Initial disturbance comparison</h3>
  <div class="time-toolbar"><label>Profile<select id="rom-initial-profile"></select></label><label>Output<select id="rom-initial-output"></select></label><label>Display<select id="rom-initial-display"><option value="time">Free-response history</option><option value="spectrum">One-sided spectrum</option></select></label><button id="rom-initial-csv">Comparison CSV</button></div>
  <p class="small muted" id="rom-initial-summary"></p><p class="small muted" id="rom-initial-unit"></p>
  <div class="plot-chart" id="rom-initial-plot"></div>
  <div class="derivative-table-wrap"><table id="rom-initial-table"><thead></thead><tbody></tbody></table></div>
</section>`;

function option(select,value,label){const o=document.createElement('option');o.value=value;o.textContent=label;select.append(o);}
export function createRomInitial(download,onEdit){
  let result=null;
  const profiles=()=>{const rows=JSON.parse($('rom-initial-profiles').value);if(!Array.isArray(rows)||rows.some(r=>!r||r.kind!=='initial'))throw new Error('Initial profiles must be a JSON array of kind: initial inputs.');return rows;};
  function options(){
    const initial_inputs=profiles();if(!initial_inputs.length)return {initial_inputs};
    const text=$('rom-initial-times').value;if(!text.trim()||text.split(',').some(x=>!x.trim()))throw new Error('Enter free-response times separated by commas.');
    return {initial_inputs,initial_times:text.split(',').map(Number),initial_shift:Number($('rom-initial-shift').value)};
  }
  function selection(){
    const profile=result?.initial_responses?.[Number($('rom-initial-profile').value)],j=Number($('rom-initial-output').value),spectrum=$('rom-initial-display').value==='spectrum';
    const unit=`${result?.outputs[j]?.unit??''}${spectrum?' · input T':''} / profile amplitude`;
    const rows=(spectrum?profile?.samples:profile?.time_samples)??[];
    return {profile,j,spectrum,unit,rows};
  }
  function render(){
    if(!result)return;const {profile,j,spectrum,unit,rows}=selection();
    $('rom-initial-unit').textContent=`${result.outputs[j].name} [${unit}] · ${spectrum?'magnitude':'signed perturbation'}: reduced line, full circles. The loaded base is unchanged.`;
    $('rom-initial-summary').textContent=!profile?.converged?`Unavailable: ${profile?.error??'no profile'}`:
      `Omitted initial dynamic norm / full norm: ${fmt(profile.projection.relative_dynamic_norm)} (scaled coordinates, not energy). `+
      (spectrum?(profile.spectrum_error??`Laplace spectrum at s = ${fmt(profile.laplace_shift)} + iω. Full-system growth bound: ${fmt(result.diagnostics.initial_conditions.spectral_abscissa)} / input T. Acceleration spectra include the initial-value boundary term.`):'Free evolution of the reduced model and the complete finite linear system; no nonlinear time integration.');
    const headings=spectrum?['ω [rad/T]','Full real','Full imaginary','Reduced real','Reduced imaginary','Absolute error']:['Time [input T]','Full','Reduced','Absolute error'];
    const head=$('rom-initial-table').querySelector('thead'),body=$('rom-initial-table').querySelector('tbody');head.replaceChildren();body.replaceChildren();
    const tr=document.createElement('tr');for(const name of headings){const th=document.createElement('th');th.textContent=name;tr.append(th);}head.append(tr);
    const points=rows.map(row=>{const x=spectrum?row.omega:row.time;if(!row.converged)return {x,error:row.error};const f=spectrum?[row.full.real[j],row.full.imag[j]]:[row.full[j]],r=spectrum?[row.reduced.real[j],row.reduced.imag[j]]:[row.reduced[j]];return {x,f,r,errorValue:row.absolute_error[j],fv:spectrum?Math.hypot(...f):f[0],rv:spectrum?Math.hypot(...r):r[0]};});
    for(const row of points){const tr=document.createElement('tr');for(const value of row.error?[fmt(row.x),row.error,...Array(headings.length-2).fill('—')]:[row.x,...row.f,...row.r,row.errorValue].map(fmt)){const td=document.createElement('td');td.textContent=value;tr.append(td);}body.append(tr);}
    const valid=points.filter(p=>!p.error);$('rom-initial-csv').disabled=!valid.length;
    if(!valid.length){$('rom-initial-plot').replaceChildren();return;}
    const start=Math.min(0,...valid.map(p=>p.x)),end=Math.max(...valid.map(p=>p.x),start+1e-30);
    let low=Math.min(0,...valid.flatMap(p=>[p.fv,p.rv])),high=Math.max(0,...valid.flatMap(p=>[p.fv,p.rv]));if(high===low)high=low+1;
    const X=x=>90+610*(x-start)/(end-start),Y=y=>165-135*(y-low)/(high-low);
    let svg='<svg viewBox="0 0 760 210" role="img" aria-label="Initial disturbance reduced and full response comparison">';
    for(let k=0;k<=4;k++){const x=start+(end-start)*k/4,y=low+(high-low)*k/4;svg+=`<text x="${X(x)}" y="186" text-anchor="middle">${x.toPrecision(3)}</text><text x="80" y="${Y(y)+4}" text-anchor="end">${y.toPrecision(3)}</text><path d="M90 ${Y(y)}H700" class="plot-grid"/>`;}
    let segment=[];const draw=()=>{if(segment.length)svg+=`<polyline points="${segment.join(' ')}" class="plot-line"/>`;segment=[];};
    for(const p of points){if(p.error){draw();continue;}segment.push(`${X(p.x)},${Y(p.rv)}`);}draw();
    for(const p of valid)svg+=`<circle cx="${X(p.x)}" cy="${Y(p.fv)}" r="3.5" class="section-point"/>`;
    $('rom-initial-plot').innerHTML=svg+`<text x="390" y="206" text-anchor="middle">${spectrum?'Angular frequency [rad/input T]':'Time [input T]'}</text></svg>`;
  }
  function setResult(value){result=value;$('rom-initial-results').hidden=!value?.initial_responses?.length;if(!value?.initial_responses?.length)return;
    $('rom-initial-profile').replaceChildren();$('rom-initial-output').replaceChildren();value.initial_responses.forEach((p,i)=>option($('rom-initial-profile'),i,p.name));value.outputs.forEach((p,i)=>option($('rom-initial-output'),i,p.name));render();}
  for(const id of ['rom-initial-profiles','rom-initial-times','rom-initial-shift'])$(id).addEventListener('input',onEdit);
  for(const id of ['rom-initial-profile','rom-initial-output','rom-initial-display'])$(id).onchange=render;
  $('rom-initial-open').onclick=()=>$('rom-initial-file').click();
  $('rom-initial-save').onclick=()=>{try{download('openswing-initial-profiles.json',JSON.stringify(profiles(),null,2),'application/json');}catch(e){$('rom-initial-import-note').textContent=e.message;}};
  $('rom-initial-file').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;const rows=JSON.parse(await file.text());if(!Array.isArray(rows)||rows.some(r=>!r||r.kind!=='initial'))throw new Error('Expected a JSON array of initial profiles.');$('rom-initial-profiles').value=JSON.stringify(rows,null,2);onEdit();$('rom-initial-import-note').textContent='Imported physical profiles. Build the ROM to check constraints and omitted motion.';}catch(e){$('rom-initial-import-note').textContent=e.message;}finally{e.target.value='';}};
  $('rom-initial-csv').onclick=()=>{const {profile,j,spectrum,unit,rows}=selection();const csv=values=>values.map(v=>'"'+String(v??'').replaceAll('"','""')+'"').join(',');
    const columns=['profile','output','display','unit',spectrum?'omega [rad/T]':'time [input T]','Laplace damping [1/T]','full real','full imaginary','reduced real','reduced imaginary','absolute error','status'];
    download('openswing-rom-initial.csv',[csv(columns),...rows.map(row=>csv([profile.name,result.outputs[j].name,spectrum?'initial spectrum':'free response',unit,spectrum?row.omega:row.time,spectrum?profile.laplace_shift:'',...(row.converged?(spectrum?[row.full.real[j],row.full.imag[j],row.reduced.real[j],row.reduced.imag[j]]:[row.full[j],0,row.reduced[j],0]):['','','','']),row.absolute_error?.[j],row.converged?'resolved':row.error]))].join('\n')+'\n','text/csv');};
  return {options,setResult};
}
