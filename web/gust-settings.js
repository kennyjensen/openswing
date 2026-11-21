const $=id=>document.getElementById(id);
const axes=['x','y','z'];
const vector=(key,label,values)=>`<p class="small muted">${label}</p><div class="fields motion-fields">${axes.map((axis,i)=>`<label>${axis}<input id="gust-${key}-${axis}" type="number" step="any" value="${values[i]}"></label>`).join('')}</div>`;

export const gustSettings=`
<details class="advanced" id="gust-settings"><summary>Earth-coordinate gust field</summary>
  <label class="field-label" for="gust-kind">Field</label><select id="gust-kind">
    <option value="none">Off · still atmosphere</option><option value="uniform">Uniform velocity</option>
    <option value="cosine">One-minus-cosine pulse</option><option value="sinusoid">Sinusoidal wave</option>
    <option value="expression">Spatial / time expressions</option><option value="custom">Superposition / custom JSON</option>
  </select>
  <div id="gust-common" hidden>${vector('amplitude','Earth velocity / amplitude · input L/T',[0,0,1])}</div>
  <div id="gust-cosine" hidden>
    ${vector('origin','Leading plane passes through · Earth coordinates, input L',[-3,0,0])}
    ${vector('normal','Direction from onset to peak · normalized internally',[-1,0,0])}
    <div class="fields"><label>Gradient length H <span>input L · peak at H, ends at 2H</span><input id="gust-length" type="number" min="0" step="any" value="3"></label>
    <label>Propagation speed <span>along normal · input L/T</span><input id="gust-speed" type="number" step="any" value="0"></label></div>
  </div>
  <div id="gust-sinusoid" hidden>
    ${vector('wavevector','Wavevector k · radians / input L',[-1,0,0])}
    <div class="fields"><label>Angular frequency ω <span>rad / input T</span><input id="gust-omega" type="number" step="any" value="0"></label><label>Phase φ <span>radians</span><input id="gust-phase" type="number" step="any" value="0"></label></div>
    <p class="small muted">Velocity = amplitude × sin(k·position − ωt + φ). Zero ω gives a frozen spatial wave.</p>
  </div>
  <div id="gust-expression" hidden>
    ${axes.map((axis,i)=>`<label class="field-label" for="gust-expr-${axis}">Earth velocity ${axis} · input L/T</label><input id="gust-expr-${axis}" type="text" spellcheck="false" value="${i===2?'exp(-((x+6)/2)**2)':0}">`).join('')}
    <p class="small muted">Variables x, y, z (Earth position), t (time); constants pi, e. Arithmetic + − * / **; sin, cos, exp, tanh, sqrt, abs, minimum, maximum, clip, where. Comparisons such as x &lt; 0 are allowed inside where. Expressions must stay finite. Refine the mesh and time step to resolve the field.</p>
  </div>
  <div id="gust-custom" hidden><label class="field-label" for="gust-json">OpenSwing field specification</label><textarea id="gust-json" spellcheck="false" aria-label="Gust JSON">{"type":"sum","fields":[{"type":"uniform","velocity":[0,0,1]}]}</textarea></div>
  <div id="gust-active" hidden>
    <div class="fields"><label>Field time <span>input T · steady analysis & preview</span><input id="gust-time" type="number" step="any" value="0"></label></div>
    <p class="small muted">The moving and deforming aircraft samples this Earth field. Aircraft x points aft; level forward flight travels toward negative Earth X. Time response starts at t = 0. Coefficients retain the still-atmosphere speed reference.</p>
    <p class="small muted">Empirical circulation lag; no exact short-wavelength gust transfer function. Body-source strengths, wake alignment and the ground correction of the gust remain approximate. See the solver report.</p>
  </div>
  <div class="constraint-actions"><button id="gust-open" type="button">Import field</button><button id="gust-save" type="button">Export JSON</button><button id="gust-save-legacy" type="button">Export .gust</button></div>
  <input id="gust-file" type="file" accept=".json,.gust,application/json,text/plain" hidden>
  <p class="small muted">OpenSwing JSON or ASWING type 5 with zero spanwise slope. Legacy export supports a frozen vertical cosine pulse along negative Earth X. Other catalog types and slant conventions remain unverified.</p>
  <p id="gust-import-note" class="small muted" aria-live="polite"></p>
  <details id="gust-preview-settings"><summary>Preview an Earth-X profile</summary>
    <div class="fields"><label>X start <span>input L</span><input id="gust-xmin" type="number" step="any" value="-15"></label><label>X end <span>input L</span><input id="gust-xmax" type="number" step="any" value="5"></label><label>Y <span>input L</span><input id="gust-y" type="number" step="any" value="0"></label><label>Z <span>input L</span><input id="gust-z" type="number" step="any" value="0"></label></div>
    <label class="field-label" for="gust-component">Velocity component</label><select id="gust-component"><option value="2">Earth z</option><option value="1">Earth y</option><option value="0">Earth x</option></select>
    <button id="gust-preview" type="button">Sample field</button><p id="gust-preview-note" class="small muted">Evaluate the same field used by the solver at 201 points.</p><div id="gust-plot" class="plot-chart"></div>
  </details>
</details>`;

export function createGustSettings(rpc,onEdit,download,showError,isBusy,workspaceRevision=()=>0) {
  let revision=0,importSequence=0;
  const num=id=>{const el=$('gust-'+id),value=Number(el.value);if(!el.value.trim()||!Number.isFinite(value)||!el.checkValidity())throw new Error(`Enter a valid gust ${id}.`);return value;};
  const vec=key=>axes.map(a=>num(`${key}-${a}`));
  function specification() {
    const type=$('gust-kind').value;
    if(type==='none')return null;
    if(type==='uniform')return {type,velocity:vec('amplitude')};
    if(type==='cosine'){
      const length=num('length');if(length<=0)throw new Error('Gust gradient length must be positive.');
      return {type,amplitude:vec('amplitude'),origin:vec('origin'),normal:vec('normal'),length,speed:num('speed')};
    }
    if(type==='sinusoid')return {type,amplitude:vec('amplitude'),wavevector:vec('wavevector'),omega:num('omega'),phase:num('phase')};
    if(type==='expression')return {type,components:axes.map(a=>$('gust-expr-'+a).value)};
    try{return JSON.parse($('gust-json').value);}catch{throw new Error('The gust specification must be valid JSON.');}
  }
  function refresh() {
    const kind=$('gust-kind').value;
    for(const name of ['cosine','sinusoid','expression','custom'])$('gust-'+name).hidden=kind!==name;
    $('gust-common').hidden=!['uniform','cosine','sinusoid'].includes(kind);
    $('gust-active').hidden=kind==='none';
  }
  function previewEdit() {revision++;$('gust-plot').replaceChildren();$('gust-preview-note').textContent='Sample again to update the field preview.';}
  function edit() {previewEdit();$('gust-import-note').textContent='';onEdit();}
  for(const el of $('gust-settings').querySelectorAll('input:not([type=file]),select,textarea'))el.addEventListener('input',el.closest('#gust-preview-settings')?previewEdit:edit);
  $('gust-kind').addEventListener('change',refresh);
  $('gust-open').onclick=()=>$('gust-file').click();
  $('gust-file').onchange=async()=>{
    const file=$('gust-file').files[0];if(!file)return;
    const sequence=++importSequence,current=revision,workspace=workspaceRevision();
    const unchanged=()=>sequence===importSequence&&current===revision&&workspace===workspaceRevision()&&!isBusy();
    try {
      if(isBusy())throw new Error('Wait for the current analysis before importing a gust field.');
      if(file.size>32768)throw new Error('Gust files must be at most 32 KiB.');
      const text=await file.text();if(!unchanged())return;
      const imported=await rpc({action:'gust_import',text});
      if(!unchanged())return;
      if(imported.legacy){
        const spec=imported.gust;
        $('gust-kind').value='cosine';
        for(const key of ['amplitude','origin','normal'])axes.forEach((axis,i)=>{$(`gust-${key}-${axis}`).value=String(spec[key][i]);});
        $('gust-length').value=String(spec.length);$('gust-speed').value=String(spec.speed);
      }else{
        $('gust-kind').value='custom';$('gust-json').value=JSON.stringify(imported.gust,null,2);
      }
      refresh();edit();
      $('gust-import-note').textContent=imported.legacy?`Imported ${file.name}. ${imported.legacy.scope}`:`Imported ${file.name} as an OpenSwing field.`;
    }catch(e){if(sequence===importSequence&&current===revision&&workspace===workspaceRevision())showError(e);}
    finally{if(sequence===importSequence)$('gust-file').value='';}
  };
  $('gust-save').onclick=()=>{try{download('openswing-gust.json',JSON.stringify(specification()??{type:'none'},null,2)+'\n','application/json');}catch(e){showError(e);}};
  $('gust-save-legacy').onclick=async()=>{
    const current=revision,workspace=workspaceRevision();
    try {
      const exported=await rpc({action:'gust_export',gust:specification()});
      if(current!==revision||workspace!==workspaceRevision())return;
      download('openswing-type5.gust',exported.text,'text/plain');
    }catch(e){if(current===revision&&workspace===workspaceRevision())showError(e);}
  };
  $('gust-preview').onclick=async()=>{
    if(isBusy())return;
    const current=revision;
    try {
      const lo=num('xmin'),hi=num('xmax'),y=num('y'),z=num('z'),time=num('time'),axis=Number($('gust-component').value);
      if(hi<=lo)throw new Error('Gust preview X end must exceed X start.');
      const positions=Array.from({length:201},(_,i)=>[lo+(hi-lo)*i/200,y,z]);
      $('gust-preview').disabled=true;$('gust-preview-note').textContent='Sampling field…';
      const {velocity}=await rpc({action:'gust_sample',gust:specification(),positions,time});
      if(current!==revision)return;
      const values=velocity.map(v=>v[axis]);let min=Math.min(...values),max=Math.max(...values);
      const margin=(max-min||Math.max(Math.abs(max),1))*.1;min-=margin;max+=margin;
      const X=x=>48+300*(x-lo)/(hi-lo),Y=v=>142-124*(v-min)/(max-min);
      let svg='<svg viewBox="0 0 370 185" role="img" aria-label="Sampled gust velocity along Earth X">';
      for(let i=0;i<3;i++){const x=lo+(hi-lo)*i/2,v=min+(max-min)*i/2;svg+=`<path class="plot-grid" d="M48 ${Y(v)}H348"/><text x="43" y="${Y(v)+4}" text-anchor="end">${v.toPrecision(3)}</text><text x="${X(x)}" y="161" text-anchor="middle">${x.toPrecision(3)}</text>`;}
      svg+=`<polyline class="plot-line" points="${positions.map((p,i)=>`${X(p[0])},${Y(values[i])}`).join(' ')}"/><text x="198" y="179" text-anchor="middle">Earth X [input L]</text></svg>`;
      $('gust-plot').innerHTML=svg;
      $('gust-preview-note').textContent=`Earth ${axes[axis]} velocity [input L/T], t = ${time} T, Y = ${y}, Z = ${z}. Sampled range ${Math.min(...values).toPrecision(5)} to ${Math.max(...values).toPrecision(5)}. Narrow features need finer sampling.`;
    }catch(e){showError(e);}finally{$('gust-preview').disabled=false;}
  };
  refresh();
  return {condition:mode=>({gust:specification(),time:mode==='time'||$('gust-kind').value==='none'?0:num('time')})};
}
