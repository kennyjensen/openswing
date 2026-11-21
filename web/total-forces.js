const escape=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const cell=([id,label,title])=>`<div class="force-cell" title="${escape(title)}"><span>${label}</span><span aria-hidden="true">=</span><b id="${id}">—</b></div>`;
const columns=[
  [['out-alpha','α','Angle of attack [deg]'],['out-beta','β','Sideslip [deg]'],['mach','M','Prandtl–Glauert Mach number']],
  [['out-p','pb/2v','Nondimensional roll rate, stability axes'],['out-q','qc/2v','Nondimensional pitch rate, stability axes'],['out-r','rb/2v','Nondimensional yaw rate, stability axes']],
  [['cl','CL','Lift coefficient'],['cy','CY','Side-force coefficient'],['cd','CD','Total drag coefficient'],['cdi','CDi','Trefftz induced-drag coefficient'],['cdp','CDp','Profile-drag coefficient']],
  [['roll','cl','Roll moment coefficient, forward/right/down body axes'],['pitch','cm','Pitch moment coefficient, forward/right/down body axes'],['yaw','cn','Yaw moment coefficient, forward/right/down body axes'],['efficiency','e','Span efficiency']],
];
export const totalForcesMarkup=`
  <div class="total-forces-grid">${columns.map(column=>`<div class="force-column">${column.map(cell).join('')}</div>`).join('')}</div>
  <div id="output-controls" class="output-controls" hidden></div>
  <details class="output-extra"><summary>Additional results</summary>
    <div class="output-extra-grid">${[
      ['cdi-near','CDi, near','Near-field vortex drag'],['cdbody','CDbody','Body pressure drag'],
      ['cdam','CDam','Apparent-mass drag'],['cdeng','CDeng','Engine contribution'],
      ['residual','Residual','Normalized solver residual'],['stalled','Stalled','Stalled sections / lifting sections'],
      ['mass','Mass','Mass [input M]'],['deflection','Deflection','Maximum displacement [input L]'],
    ].map(cell).join('')}</div>
    <p id="trefftz-note" class="results-note" hidden></p><p id="circulation-note" class="results-note" hidden></p>
  </details>`;

export function outputNumber(value,digits=4){
  if(!Number.isFinite(value))return '—';
  const text=Math.abs(value)>=1e7?value.toExponential(2):value.toFixed(digits);
  return Number(text)===0?(0).toFixed(digits):text;
}

export function flightOutputValues(result,condition,model){
  if(!result||!condition)return {alpha:null,beta:null,rates:[null,null,null],controls:[]};
  const actual=result.operating_values??{},pick=(key,fallback)=>Number.isFinite(actual[key])?actual[key]:fallback;
  const alpha=pick('alpha',condition.alpha),beta=pick('beta',condition.beta),speed=pick('speed',condition.speed);
  const rates=['x','y','z'].map((axis,i)=>pick(`rates.${axis}`,result.frame?.rates_body?.[i]??condition.rates?.[i]??0));
  const [,chord,span]=model?.reference?.[0]??[],a=alpha*Math.PI/180;
  // Same stability-axis rotation used for p/q/r in derivatives.py. Body x
  // points aft and z up; stability x points forward and z down.
  const stability=[-Math.cos(a)*rates[0]-Math.sin(a)*rates[2],rates[1],Math.sin(a)*rates[0]-Math.cos(a)*rates[2]];
  const normalized=stability.map((rate,i)=>speed>0&&Number.isFinite(i===1?chord:span)?rate*(i===1?chord:span)/(2*speed):null);
  const controls=(model?.controls??[]).map(index=>{
    const property=new RegExp(`^dC[LMD]dF${index}$`);
    const names=[...new Set((model.distributions??[]).filter(b=>b.properties?.some(k=>property.test(k))).map(b=>b.name).filter(Boolean))];
    const actuator=result.feedback?.actuators?.[`F${index}`];
    return {index,label:names.length?`${names.join(', ')} (F${index})`:`F${index}`,
      value:Number.isFinite(actuator)?actuator:pick(`control.${index}`,condition.controls?.[index]??0)};
  });
  return {alpha,beta,rates:normalized,controls};
}

export function renderFlightOutput(result,condition,model){
  const $=id=>document.getElementById(id),values=flightOutputValues(result,condition,model);
  for(const [id,value] of [['alpha',values.alpha],['beta',values.beta],...['p','q','r'].map((id,i)=>[id,values.rates[i]])])
    $('out-'+id).textContent=outputNumber(value,3);
  const controls=$('output-controls');controls.hidden=!values.controls.length;
  // ASW flap settings need not be degrees: the file's dCL/dF etc. define
  // their units. Keep actual control names and values without inventing units.
  controls.innerHTML=values.controls.map(control=>`<div class="force-cell" title="Control F${control.index} · file flap setting"><span>${escape(control.label)}</span><span aria-hidden="true">=</span><b>${outputNumber(control.value,2)}</b></div>`).join('');
}
