const $=id=>document.getElementById(id);
const fmt=x=>Number.isFinite(x)?x.toPrecision(7):'—';
const option=(select,value,text)=>{const item=document.createElement('option');item.value=value;item.textContent=text;select.append(item);};
export const romFilePane=`
<div id="pane-romfiles" class="tab-pane mode-pane" role="tabpanel" aria-labelledby="tab-romfiles" hidden>
  <label class="field-label" for="romfile-file">Open an ASWING .rom file</label><input id="romfile-file" type="file" accept=".rom,text/plain">
  <p class="small muted">Inspect the printed modes and input/output matrices independently of the current aircraft. Complex pairs are completed automatically. Imported files contain perturbations, without the aircraft baseline or a full-model comparison.</p>
  <label class="field-label" for="romfile-frequencies">Angular frequencies · comma separated, in the file's inverse-time unit</label><input id="romfile-frequencies" value="0, 1, 10, 30, 100">
  <div class="time-toolbar"><button id="romfile-evaluate" disabled>Evaluate response</button><button id="romfile-json" disabled>Real model JSON</button><button id="romfile-save" disabled>Normalized .rom</button><button id="romfile-original" disabled>Original file</button></div>
  <p id="romfile-summary" class="small muted">No ROM file loaded.</p>
  <div id="romfile-results" hidden>
    <div class="time-toolbar"><label>Input<select id="romfile-input"></select></label><label>Output<select id="romfile-output"></select></label><label>Printed mode<select id="romfile-mode"></select></label></div>
    <p id="romfile-units" class="small muted"></p>
    <div id="romfile-gain" class="plot-chart"></div><div id="romfile-phase" class="plot-chart"></div>
    <div class="derivative-table-wrap"><table id="romfile-response"><thead><tr><th>ω</th><th>Real</th><th>Imaginary</th><th>Magnitude</th><th>Phase [deg]</th></tr></thead><tbody></tbody></table></div>
    <p id="romfile-pole" class="small muted"></p><div class="derivative-table-wrap"><table id="romfile-modal"><thead><tr><th>Printed quantity</th><th>Unit</th><th>Real</th><th>Imaginary</th></tr></thead><tbody></tbody></table></div>
    <details><summary>Real input/output matrices</summary><pre id="romfile-matrices"></pre></details>
  </div>
  <p class="small muted">Response is C(iωI−A)⁻¹B+D for the printed matrix model. ASWING's additional Bode reconstruction corrections require data absent from this file. Unspecified input units stay unspecified; unknown labels retain their original meaning. Import does not validate the originating simulation.</p>
</div>`;

export function createRomFileView(rpc,download,showError){
  let text='',filename='imported.rom',result=null,revision=0,busy=false,dirty=false;
  const buttons=()=>{for(const id of ['romfile-json','romfile-save','romfile-original'])$(id).disabled=!result||(id==='romfile-json'&&dirty);$('romfile-evaluate').disabled=!text||busy;};
  function row(table,values){const tr=document.createElement('tr');for(const value of values){const td=document.createElement('td');td.textContent=value;tr.append(td);}$(table).querySelector('tbody').append(tr);}
  function modal(){
    if(!result)return;
    const m=result.model,k=Number($('romfile-mode').value),mode=m.modes[k];
    $('romfile-pole').textContent=`Printed mode ${mode.index}: λ = ${fmt(mode.eigenvalue[0])} + i(${fmt(mode.eigenvalue[1])}) / ${m.time_unit}. ${mode.eigenvalue[0]>0?'Growing':mode.eigenvalue[0]<0?'Decaying':'Neutral'} pole. Values below retain the file's mode normalization.`;
    $('romfile-modal').querySelector('tbody').replaceChildren();
    m.outputs.forEach((x,j)=>row('romfile-modal',[x.name,x.unit,fmt(m.matrices.C.real[j][k]),fmt(m.matrices.C.imag[j][k])]));
    m.state_names.forEach((x,j)=>row('romfile-modal',[`Eigenvector: ${x}`,'not recorded',fmt(m.matrices.V.real[j][k]),fmt(m.matrices.V.imag[j][k])]));
  }
  function chart(id,rows,key,title){
    const values=rows.filter(r=>r[key]!=null),last=Math.max(...rows.map(r=>r.w),1),max=Math.max(...values.map(r=>r[key]),0),min=Math.min(...values.map(r=>r[key]),0),span=max-min||1;
    const X=x=>85+620*x/last,Y=y=>155-125*(y-min)/span;
    let svg=`<svg viewBox="0 0 760 205" role="img" aria-label="${title}">`;
    for(let k=0;k<5;k++){const x=last*k/4,y=min+span*k/4;svg+=`<text x="${X(x)}" y="178" text-anchor="middle">${x.toPrecision(3)}</text><text x="75" y="${Y(y)+4}" text-anchor="end">${y.toPrecision(3)}</text><path d="M85 ${Y(y)}H705" class="plot-grid"/>`;}
    let points=[];const draw=()=>{if(points.length)svg+=`<polyline points="${points.join(' ')}" class="plot-line"/>`;points=[];};
    for(const r of rows){if(r[key]==null){draw();continue;}points.push(`${X(r.w)},${Y(r[key])}`);}draw();
    for(const r of values)svg+=`<circle cx="${X(r.w)}" cy="${Y(r[key])}" r="3" class="section-point"/>`;
    $(id).innerHTML=svg+'<text x="395" y="201" text-anchor="middle">'+title+' · angular frequency</text></svg>';
  }
  function render(){
    $('romfile-response').querySelector('tbody').replaceChildren();
    $('romfile-gain').replaceChildren();$('romfile-phase').replaceChildren();
    if(!result)return;
    modal();const m=result.model,i=Number($('romfile-input').value),j=Number($('romfile-output').value);
    if(!m.inputs.length||!m.outputs.length){$('romfile-units').textContent='This file has no selected input/output channels; its autonomous matrices and mode data remain available.';return;}
    $('romfile-units').textContent=`${m.outputs[j].name} [${m.outputs[j].unit}] per ${m.inputs[i].unit??'unspecified input unit'} · ω in rad/${m.time_unit}. Phase is undefined at zero magnitude. ${dirty?'Frequency settings changed; evaluate again.':''}`;
    if(dirty)return;
    const rows=result.samples.map(s=>{
      if(!s.converged){row('romfile-response',[fmt(s.omega),s.error,'—','—','—']);return {w:s.omega};}
      const re=s.response.real[j][i],im=s.response.imag[j][i],gain=Math.hypot(re,im),phase=gain?Math.atan2(im,re)*180/Math.PI:null;
      row('romfile-response',[fmt(s.omega),fmt(re),fmt(im),fmt(gain),fmt(phase)]);return {w:s.omega,gain,phase};
    });
    chart('romfile-gain',rows,'gain','Imported ROM magnitude');chart('romfile-phase',rows,'phase','Imported ROM phase [deg]');
  }
  async function evaluate(){
    if(!text||busy)return;busy=true;const current=revision;buttons();$('romfile-summary').textContent='Reading modal matrices and evaluating the response…';
    try{
      const entries=$('romfile-frequencies').value.split(',');if(entries.some(s=>!s.trim()))throw new Error('Enter a nonempty comma-separated frequency list.');
      const data=await rpc({action:'rom_import',text,frequencies:entries.map(Number)});
      if(current!==revision)return;
      result=data;dirty=false;const m=data.model;$('romfile-results').hidden=false;
      $('romfile-summary').textContent=`${m.name} · ${m.modes.length} printed modes · ${data.real_matrices.A.length} real states · ${m.inputs.length} inputs · ${m.outputs.length} outputs · ${data.samples.filter(s=>s.converged).length}/${data.samples.length} frequencies resolved.`;
      for(const id of ['romfile-input','romfile-output','romfile-mode'])$(id).replaceChildren();
      m.inputs.forEach((x,i)=>option($('romfile-input'),i,x.name));m.outputs.forEach((x,i)=>option($('romfile-output'),i,x.name));m.modes.forEach((x,i)=>option($('romfile-mode'),i,`Mode ${x.index}: ${fmt(x.eigenvalue[0])} + i(${fmt(x.eigenvalue[1])})`));
      $('romfile-matrices').textContent=JSON.stringify(data.real_matrices,null,2);render();
    }catch(error){if(current===revision){result=null;$('romfile-results').hidden=true;$('romfile-summary').textContent='ROM could not be evaluated.';showError(error);}}
    finally{busy=false;if(current!==revision)$('romfile-summary').textContent='File or frequency settings changed; evaluate again.';buttons();}
  }
  $('romfile-file').onchange=async event=>{
    const file=event.target.files[0];if(!file)return;
    revision++;const current=revision;result=null;$('romfile-results').hidden=true;buttons();
    const loaded=await file.text();if(current!==revision)return;text=loaded;filename=file.name;await evaluate();
  };
  $('romfile-frequencies').oninput=()=>{revision++;dirty=true;buttons();render();};
  $('romfile-evaluate').onclick=evaluate;
  $('romfile-input').onchange=$('romfile-output').onchange=render;$('romfile-mode').onchange=modal;
  $('romfile-json').onclick=()=>download('openswing-imported-rom.json',JSON.stringify(result,null,2),'application/json');
  $('romfile-save').onclick=()=>download('openswing-normalized.rom',result.normalized_text);
  $('romfile-original').onclick=()=>download(filename,result.model.source);
}
