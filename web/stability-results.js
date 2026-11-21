import {isQuiescentResult} from './quiescent-settings.js';
const $=id=>document.getElementById(id);
const fmt=x=>Number.isFinite(x)?x.toPrecision(7):'—';
const csv=row=>row.map(x=>'"'+String(x??'').replaceAll('"','""')+'"').join(',');
export const stabilityPane=`
<details id="stability-settings" class="advanced"><summary>Stability progression and boundaries</summary>
  <p class="small muted">Recompute the saved modal configuration at a sequence of operating points. Inspect root paths and refine sign-changing instability brackets. Each point retains its equilibrium, modes and diagnostics.</p>
  <div class="fields"><label>Sweep parameter<input id="stability-parameter" value="speed" list="stability-parameters"></label><label>Parameter values, comma separated<input id="stability-values" value="30, 40, 50"></label></div>
  <datalist id="stability-parameters"><option value="speed"><option value="alpha"><option value="beta"><option value="altitude_m"><option value="density"><option value="target.0"></datalist>
  <p class="small muted">Speed uses input L/T; angles use degrees; atmospheric altitude uses metres. The API also accepts control.N, power.N and zero-based target.N in the saved operating constraints. A prescribed variable cannot also be a trim unknown.</p>
  <label class="checkbox"><input id="stability-warm" type="checkbox" checked><span>Continue from the saved modal equilibrium and preceding points</span></label>
  <label class="checkbox"><input id="stability-adaptive" type="checkbox"><span>Subdivide uncertain tracking intervals</span></label>
  <div class="fields"><label>Maximum subdivision depth<input id="stability-depth" type="number" min="0" max="12" value="4"></label><label>Extra tracking points<input id="stability-extra" type="number" min="0" max="256" value="16"></label></div>
  <p class="small muted">Smaller steps can recover a failed local correction or a unique mode match. Point budgets bound the extra work. Unresolved intervals remain gaps; local continuation does not establish branch uniqueness or follow folds.</p>
  <label class="checkbox"><input id="stability-refine" type="checkbox" checked><span>Refine instability brackets</span></label>
  <div class="fields"><label>Relative parameter tolerance<input id="stability-tolerance" type="number" min="0.00000001" max="0.05" step="any" value="0.0001"></label><label>Absolute parameter tolerance<input id="stability-absolute" type="number" min="0" step="any" value="0"></label><label>Minimum shape assurance<input id="stability-assurance" type="number" min="0.01" max="1" step="any" value="0.6"></label><label>Refinement iterations<input id="stability-iterations" type="number" min="1" max="60" value="24"></label></div>
  <div class="time-toolbar"><button id="stability-build" disabled>Run stability sweep</button><button id="stability-json" disabled>Sweep JSON</button><button id="stability-csv" disabled>Root paths CSV</button></div>
  <p id="stability-summary" class="small muted">Run coupled eigenmodes to establish the sweep configuration.</p>
  <div id="stability-result" hidden>
    <div class="time-toolbar"><label>Root branch<select id="stability-branch"></select></label><label>Computed operating point<select id="stability-point"></select></label><button id="stability-inspect">Inspect point modes</button></div>
    <p id="stability-coverage" class="small muted"></p>
    <div id="stability-root-plot" class="plot-chart"></div><div id="stability-growth-plot" class="plot-chart"></div>
    <div class="derivative-table-wrap"><table id="stability-path"><thead><tr><th>Parameter</th><th>Real σ</th><th>Imaginary ω</th><th>Damping ratio</th><th>Shape assurance</th></tr></thead><tbody></tbody></table></div>
    <p class="field-label">Instability brackets</p><div class="derivative-table-wrap"><table id="stability-boundaries"><thead><tr><th>Branch</th><th>Type / direction</th><th>Status</th><th>Bracket</th><th>Computed value</th><th>σ</th><th>ω</th></tr></thead><tbody></tbody></table></div>
    <p id="stability-gaps" class="small muted"></p>
  </div>
  <p class="small muted">Mode identity can become ambiguous near repeated roots or a changing search window. Gaps are not connected. A crossing is an instability candidate of the computed frozen model; inspect its shape, constitutive damping and base drift. Unreturned modes and crossings between samples can be missed. Refine the speed grid, mode count, shift, mesh and numerical tolerances before drawing a flutter conclusion.</p>
</details>`;

export function createStabilityResults(build,inspect,download,showError){
  let base=null,result=null,busy=false,revision=0;
  const buttons=()=>{$('stability-build').disabled=!base||busy||base.vacuum||isQuiescentResult(base);for(const id of ['stability-json','stability-csv'])$(id).disabled=!result;};
  function clear(){result=null;revision++;$('stability-result').hidden=true;$('stability-summary').textContent=isQuiescentResult(base)?'Stability sweeps are unavailable for still-air modal results.':base?'Sweep configuration uses the saved modal analysis. Changes require a new sweep.':'Run coupled eigenmodes to establish the sweep configuration.';buttons();}
  function setBase(value){base=value;clear();}
  const row=(table,values)=>{const tr=document.createElement('tr');for(const value of values){const td=document.createElement('td');td.textContent=value;tr.append(td);}$(table).querySelector('tbody').append(tr);};
  const option=(id,value,label)=>{const o=document.createElement('option');o.value=value;o.textContent=label;$(id).append(o);};
  const roots=branch=>branch.samples.map(s=>{const p=result.points[s.point],r=p.roots[s.root];return {x:p.value,re:r.eigenvalue[0],im:r.eigenvalue[1],point:p.index,match:s.match};});
  function plot(id,paths,title,xLabel,yLabel){
    const points=paths.flatMap(p=>p.points);let xmin=Math.min(...points.map(p=>p.x)),xmax=Math.max(...points.map(p=>p.x)),ymin=Math.min(0,...points.map(p=>p.y)),ymax=Math.max(0,...points.map(p=>p.y));
    if(!points.length){$(id).replaceChildren();return;}
    const dx=.08*(xmax-xmin||Math.abs(xmax)||1),dy=.08*(ymax-ymin||1);xmin-=dx;xmax+=dx;ymin-=dy;ymax+=dy;
    const X=x=>90+600*(x-xmin)/(xmax-xmin),Y=y=>160-135*(y-ymin)/(ymax-ymin);
    let svg=`<svg viewBox="0 0 760 205" role="img" aria-label="${title}">`;
    for(let i=0;i<5;i++){const x=xmin+(xmax-xmin)*i/4,y=ymin+(ymax-ymin)*i/4;svg+=`<text x="${X(x)}" y="180" text-anchor="middle">${x.toPrecision(3)}</text><text x="80" y="${Y(y)+4}" text-anchor="end">${y.toPrecision(3)}</text><path d="M90 ${Y(y)}H690" class="plot-grid"/>`;}
    if(xmin<0&&xmax>0)svg+=`<path d="M${X(0)} 25V160" class="plot-grid"/>`;
    paths.forEach(path=>{svg+=`<polyline points="${path.points.map(p=>`${X(p.x)},${Y(p.y)}`).join(' ')}" class="plot-line" opacity="${path.selected?1:.25}"/>`;for(const p of path.points)svg+=`<circle cx="${X(p.x)}" cy="${Y(p.y)}" r="${path.selected?4:2}" class="section-point"/>`;});
    $(id).innerHTML=svg+`<text x="390" y="202" text-anchor="middle">${xLabel} · vertical: ${yLabel}</text></svg>`;
  }
  function render(){
    if(!result)return;const index=Number($('stability-branch').value),branch=result.branches[index];$('stability-path').querySelector('tbody').replaceChildren();
    if(!branch){$('stability-root-plot').replaceChildren();$('stability-growth-plot').replaceChildren();return;}
    const rows=roots(branch);for(const r of rows)row('stability-path',[fmt(r.x),fmt(r.re),fmt(r.im),fmt(Math.hypot(r.re,r.im)?-r.re/Math.hypot(r.re,r.im):null),fmt(r.match?.assurance)]);
    plot('stability-root-plot',result.branches.map(b=>({points:roots(b).map(r=>({x:r.re,y:r.im})),selected:b.index===index})),'Stability root progression','Real σ [1/T]','Imaginary ω [rad/T]');
    plot('stability-growth-plot',[{points:rows.map(r=>({x:r.x,y:r.re})),selected:true}],'Root growth across operating points','Parameter','Growth σ [1/T]');
  }
  function show(data){
    result=data;$('stability-result').hidden=false;
    const active=data.points.filter(p=>p.superseded_by===undefined);
    const timeScale=active.find(p=>p.converged)?.result.diagnostics.time_scale??1;
    const growing=active.filter(p=>p.roots.some(r=>r.eigenvalue[0]>data.settings.growth_tolerance*Math.max(Math.hypot(...r.eigenvalue),timeScale))).length;
    $('stability-summary').textContent=`${active.filter(p=>p.converged).length}/${active.length} points solved · ${data.branches.length} root branches · ${data.boundaries.filter(b=>b.status==='resolved').length}/${data.boundaries.length} boundaries refined · ${data.gaps.length} tracking gaps · ${growing} points with growing roots. Parameter: ${data.parameter} [${data.parameter_unit}]. ${data.subdivisions?.length??0} inserted tracking points; ${data.points.length-active.length} earlier attempts superseded.`;
    $('stability-coverage').textContent=data.spectrum_complete?'All finite roots were returned at every computed point. This does not rule out crossings between sampled points.':'Only part of the finite spectrum was returned, or a point failed. Absence of a crossing does not establish stability.';
    for(const id of ['stability-branch','stability-point'])$(id).replaceChildren();
    data.branches.forEach(b=>option('stability-branch',b.index,`Branch ${b.index+1} · ${b.samples.length} grid points`));
    active.filter(p=>p.converged).sort((a,b)=>a.value-b.value).forEach(p=>option('stability-point',p.index,`${fmt(p.value)} · ${p.kind}`));
    $('stability-inspect').disabled=!data.points.some(p=>p.converged);
    $('stability-boundaries').querySelector('tbody').replaceChildren();
    for(const b of data.boundaries)row('stability-boundaries',[b.branch+1,`${b.kind} · ${b.direction}`,b.status,b.bracket.map(fmt).join(' … '),fmt(b.value),...b.eigenvalue.map(fmt)]);
    if(!data.boundaries.length)row('stability-boundaries',['—','No sign-changing bracket in the tracked samples.','—','—','—','—','—']);
    $('stability-gaps').textContent=[...data.gaps.map(g=>`${fmt(data.points[g.left].value)} → ${fmt(data.points[g.right].value)}: ${g.reason}`),...active.filter(p=>!p.converged).map(p=>`${fmt(p.value)}: ${p.error}`),...data.boundaries.filter(b=>b.reason).map(b=>`Branch ${b.branch+1}: ${b.reason}`)].join(' ');
    if(data.boundaries.length){$('stability-branch').value=data.boundaries[0].branch;$('stability-point').value=data.boundaries[0].point;}
    render();buttons();
  }
  for(const id of ['stability-warm','stability-adaptive','stability-depth','stability-extra','stability-parameter','stability-values','stability-refine','stability-tolerance','stability-absolute','stability-assurance','stability-iterations'])$(id).addEventListener('input',clear);
  $('stability-branch').onchange=render;
  $('stability-build').onclick=async()=>{
    if(!base||isQuiescentResult(base)||busy)return;const current=revision;busy=true;buttons();$('stability-summary').textContent='Solving operating points and matching eigenmodes…';
    try{
      const text=$('stability-values').value.split(',');if(text.some(v=>!v.trim()))throw new Error('Enter at least two comma-separated parameter values.');
      const options={warm_start:$('stability-warm').checked,adaptive:$('stability-adaptive').checked,max_subdivisions:Number($('stability-depth').value),max_extra_points:Number($('stability-extra').value),parameter:$('stability-parameter').value.trim(),values:text.map(Number),refine:$('stability-refine').checked,parameter_rtol:Number($('stability-tolerance').value),parameter_atol:Number($('stability-absolute').value),min_assurance:Number($('stability-assurance').value),max_iterations:Number($('stability-iterations').value)};
      const data=await build(base,options);if(revision===current)show(data);
    }catch(error){if(revision===current){clear();$('stability-summary').textContent='Stability sweep stopped.';showError(error);}}
    finally{busy=false;buttons();}
  };
  $('stability-inspect').onclick=()=>{if(result)inspect(result,Number($('stability-point').value));};
  $('stability-json').onclick=()=>download('openswing-stability.json',JSON.stringify(result,null,2),'application/json');
  $('stability-csv').onclick=()=>download('openswing-root-paths.csv',[csv(['branch',`parameter ${result.parameter} [${result.parameter_unit}]`,'real [1/T]','imag [rad/T]','point','shape assurance','distance','assignment margin']),...result.branches.flatMap(b=>roots(b).map(r=>csv([b.index+1,r.x,r.re,r.im,r.point,r.match?.assurance,r.match?.distance,r.match?.margin])))].join('\n')+'\n','text/csv');
  return {setBase,capture:()=>result?structuredClone(result):null,restore:data=>{if(data)show(structuredClone(data));}};
}
