import {frameConstraintFields,bindFrameConstraints,frameOptions} from './dynamic-frame.js';
import { trajectoryGeometry } from './time-results.js';
const $=id=>document.getElementById(id);
const fmt=x=>x==null?'—':x.toPrecision(6);
export const modeSettings=`
<div id="mode-settings" hidden>
  <label class="field-label" for="modal-frame">Modal frame</label><select id="modal-frame"><option value="fixed">Fixed aircraft frame</option><option value="prescribed">Prescribed accelerations</option><option value="free">Free flight · six dynamic accelerations</option><option value="mixed">Mixed motion · per axis</option></select>
  <input id="modal-ordinary-frame" type="hidden" value="fixed">
  ${frameConstraintFields('modal')}
  <label class="checkbox"><input id="modal-vacuum" type="checkbox"><span>Vacuum · omit aerodynamic loads</span></label>
  <label class="checkbox"><input id="modal-quiescent" type="checkbox"><span>Still air · zero mean flow</span></label>
  <div id="modal-fluid-slot"><div id="quiescent-fluid-settings"><div class="fields" id="modal-quiescent-density-field" hidden><label>Still-air density <span>input M / L³</span><input id="modal-quiescent-density" type="number" min="0" step="any" value="1.225"></label></div>
  </div></div>
  <div class="fields"><label>Mode count<input id="modal-count" type="number" min="1" max="100" step="1" value="12"></label><label>Shift real <span>1/input T</span><input id="modal-shift-real" type="number" step="any" value="-0.01"></label><label>Shift imaginary <span>rad/input T</span><input id="modal-shift-imag" type="number" step="any" value="0"></label></div>
  <label class="field-label" for="modal-method">Eigenvalue solver</label><select id="modal-method"><option value="full_shift_invert" selected>ASWING · shifted Arnoldi</option><option value="dense">Dense · closest roots to shift</option><option value="shift_invert">Reduced pencil · Arnoldi</option></select>
  <details class="advanced"><summary>Linearization and export</summary><div class="fields"><label>Difference step<input id="modal-step" type="number" min="0.0000001" max="0.001" step="any" value="0.00001"></label><label>Rank tolerance<input id="modal-rank" type="number" min="0.000000000001" max="0.00001" step="any" value="0.000000001"></label></div><label class="checkbox"><input id="modal-matrices" type="checkbox"><span>Include full A and M matrices in JSON</span></label></details>
</div>`;
export const modeTransport=`
<div id="mode-transport" class="time-transport" hidden>
  <button id="modal-play">Play phase</button><input id="modal-phase" type="range" min="0" max="360" step="1" value="0" aria-label="Mode phase"><output id="modal-phase-label">0°</output>
  <label>View<select id="modal-view"><option value="body">Body frame</option><option value="earth">Earth frame</option></select></label>
  <label>Scale, % span<input id="modal-amplitude" type="number" min="0" max="20" step="0.1" value="2" aria-label="Mode display scale percent span"></label>
</div>`;
export const modePane=`
<div id="pane-modes" class="tab-pane mode-pane" role="tabpanel" aria-labelledby="tab-modes" hidden>
  <div id="modal-roots" class="plot-chart"></div>
</div>`;

const shapeMaxima=new WeakMap();
export function modeDisplayScale(output,amplitude,earth=false){
  const delta=output[earth?'earth_geometry':'geometry'];
  if(shapeMaxima.has(delta)){const maximum=shapeMaxima.get(delta);return maximum>1e-12?amplitude/maximum:0;}
  let maximum=0;
  for(const b of delta)for(const field of ['axis','quads']){
    const real=b[field].real.flat(Infinity),imag=b[field].imag.flat(Infinity);
    for(let i=0;i<real.length;i+=3)maximum=Math.max(maximum,Math.hypot(...real.slice(i,i+3),...imag.slice(i,i+3)));
  }
  shapeMaxima.set(delta,maximum);
  return maximum>1e-12?amplitude/maximum:0;
}

// Saved eigenvectors/base are immutable. This is a display-only linear sum.
export function modeGeometry(result,index,phase,amplitude,earth=false,normalize=true) {
  const base=result.base,mode=result.modes[index],key=earth?'earth_geometry':'geometry';
  let beams=base.geometry,attachments=base.attachments,ground=base.ground_plane;
  if(earth)({beams,attachments,ground}=trajectoryGeometry(beams,attachments,{...base,frame:base.modal_base},true));
  const c=Math.cos(phase),s=Math.sin(phase),delta=mode.output[key];
  const scale=normalize?modeDisplayScale(mode.output,amplitude,earth):amplitude;
  const add=(a,r,i)=>Array.isArray(a)?a.map((v,k)=>add(v,r[k],i[k])):a+scale*(r*c-i*s);
  beams=beams.map((b,j)=>({...b,quads:add(b.quads,delta[j].quads.real,delta[j].quads.imag),axis:add(b.axis,delta[j].axis.real,delta[j].axis.imag),
    // Older saved modes have only normal-section geometry. Never display a
    // motionless projected skin over a moving beam when its derivative is absent.
    streamwise_quads:b.streamwise_quads&&delta[j].streamwise_quads?
      add(b.streamwise_quads,delta[j].streamwise_quads.real,delta[j].streamwise_quads.imag):undefined}));
  const da=mode.output[earth?'earth_attachments':'attachments'];
  attachments=attachments.map((a,j)=>({...a,segments:add(a.segments,da[j].segments.real,da[j].segments.imag)}));
  return {beams,attachments,ground,scale};
}

export function createModeResults(onView,onEdit) {
  let result=null,index=0,animation=null;
  bindFrameConstraints('modal',onEdit);
  function pause(){if(animation!==null)cancelAnimationFrame(animation);animation=null;$('modal-play').textContent='Play phase';}
  function geometry(){return modeGeometry(result,index,Number($('modal-phase').value)*Math.PI/180,Number($('modal-amplitude').value)/100*result.reference_span,$('modal-view').value==='earth');}
  function spanState(){
    const output=result?.modes[index]?.output;if(!output)return null;
    return {output,phase:Number($('modal-phase').value)*Math.PI/180,
      scale:modeDisplayScale(output,Number($('modal-amplitude').value)/100*result.reference_span,$('modal-view').value==='earth')};
  }
  function roots(){
    if(!result?.modes.length){$('modal-roots').replaceChildren();return;}
    const values=result.modes.map(m=>m.eigenvalue),xs=values.map(v=>v[0]),ys=values.map(v=>v[1]);
    let xmin=Math.min(0,...xs),xmax=Math.max(0,...xs),ymin=Math.min(0,...ys),ymax=Math.max(0,...ys);
    const xp=.15*(xmax-xmin||1),yp=.15*(ymax-ymin||1);xmin-=xp;xmax+=xp;ymin-=yp;ymax+=yp;
    const X=x=>80+(x-xmin)/(xmax-xmin)*495,Y=y=>520-(y-ymin)/(ymax-ymin)*495;
    const tick=(value,span)=>Math.abs(value)<1e-12*span?'0':value.toPrecision(3);
    let svg='<svg viewBox="0 0 600 600" role="group" aria-label="Eigenvalues in the complex plane">';
    for(let k=0;k<5;k++){const x=xmin+(xmax-xmin)*k/4,y=ymin+(ymax-ymin)*k/4;svg+=`<path d="M${X(x)} 25V520M80 ${Y(y)}H575" class="plot-grid"/><text x="${X(x)}" y="545" text-anchor="middle">${tick(x,xmax-xmin)}</text><text x="70" y="${Y(y)+4}" text-anchor="end">${tick(y,ymax-ymin)}</text>`;}
    svg+=`<path d="M${X(0)} 25V520M80 ${Y(0)}H575" class="plot-zero"/><text x="327.5" y="580" text-anchor="middle">Real σ [1/input T]</text><text transform="translate(18 272.5) rotate(-90)" text-anchor="middle">Imaginary ω [rad/input T]</text>`;
    values.forEach(([x,y],i)=>{svg+=`<circle data-mode="${i}" cx="${X(x)}" cy="${Y(y)}" r="${i===index?6:3.5}" class="${i===index?'modal-selected':'section-point'}" role="button" tabindex="0" aria-pressed="${i===index}" aria-label="Mode ${i+1}: ${fmt(x)}, ${fmt(y)}"><title>Mode ${i+1}: ${fmt(x)}, ${fmt(y)}</title></circle>`;});
    $('modal-roots').innerHTML=svg+'</svg>';
    $('modal-roots').querySelectorAll('[data-mode]').forEach(c=>{
      c.onclick=()=>select(Number(c.dataset.mode));
      c.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();select(Number(c.dataset.mode));$('modal-roots').querySelector(`[data-mode="${index}"]`).focus();}};
    });
  }
  function select(i,fit=false){
    if(!result||!Number.isInteger(i)||!result.modes[i])return;pause();index=i;
    roots();onView(fit);
  }
  function setResult(data){
    pause();result=data;index=0;$('mode-transport').hidden=!data?.modes.length;
    if(data?.modes.length){
      $('modal-phase').value=0;$('modal-phase-label').textContent='0°';select(0,true);
    }else roots();
  }
  for(const id of ['modal-frame','modal-vacuum','modal-quiescent','modal-quiescent-density','modal-count','modal-shift-real','modal-shift-imag','modal-method','modal-step','modal-rank','modal-matrices'])$(id).addEventListener('input',onEdit);
  function phase(){ $('modal-phase-label').textContent=`${Math.round(Number($('modal-phase').value))}°`;onView(false); }
  $('modal-phase').oninput=()=>{pause();phase();};
  $('modal-view').onchange=()=>{pause();onView(true);};
  $('modal-amplitude').oninput=()=>{if($('modal-amplitude').checkValidity()&&$('modal-amplitude').value)onView(false);};
  $('modal-play').onclick=()=>{
    if(animation!==null){pause();return;}if(!result)return;
    const start=performance.now(),p=Number($('modal-phase').value);$('modal-play').textContent='Pause';
    const frame=now=>{$('modal-phase').value=(p+(now-start)*.09)%360;phase();animation=requestAnimationFrame(frame);};animation=requestAnimationFrame(frame);
  };
  return {setResult,select,selectedIndex:()=>index,geometry,spanState,pause,playback:()=>({playing:animation!==null,durationMs:4000}),options:()=>({...($('modal-quiescent').checked?{frame:'fixed',vacuum:false,quiescent_density:Number($('modal-quiescent-density').value)}:{...frameOptions('modal'),vacuum:$('modal-vacuum').checked}),count:Number($('modal-count').value),shift:[Number($('modal-shift-real').value),Number($('modal-shift-imag').value)],method:$('modal-method').value,step:Number($('modal-step').value),rank_tolerance:Number($('modal-rank').value),matrices:$('modal-matrices').checked})};
}
