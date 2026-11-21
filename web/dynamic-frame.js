const $=id=>document.getElementById(id);
const axes=['x','y','z'];

export function frameConstraintFields(prefix){
  return `<div id="${prefix}-load-settings" hidden>
    <p class="small muted">Choose which accelerations follow net-load targets. Other accelerations keep their prescribed values. Mixed motion retains velocity, position and attitude dynamics.</p>
    ${['force','moment'].flatMap((kind,j)=>axes.map(axis=>{
      const label=(j?'M':'F')+axis,acc=(j?'G':'A')+axis;
      return `<div class="time-load-row"><label>${j?'Rotation':'Translation'} ${axis}<select id="${prefix}-load-${label}" aria-label="${prefix} ${axis} ${j?'rotation':'translation'} constraint"><option value="prescribed">Prescribe ${acc}</option><option value="load" ${label==='Fx'?'selected':''}>Solve from ${label}</option></select></label><label id="${prefix}-target-label-${label}" hidden>Net ${label}<span>input F${j?'·L':''}</span><input id="${prefix}-target-${label}" aria-label="${prefix} net ${label} target" type="number" step="any" value="0"></label></div>`;
    })).join('')}
    <p class="small muted">Net loads include inertia. With no external x force, a positive Fx target gives negative ax. Moments use the ASW moment reference; linear acceleration uses its own reference. Fixed frame holds the entire frame state; mixed motion allows drift under prescribed accelerations.</p>
  </div>`;
}

export function bindFrameConstraints(prefix,onEdit){
  const rows=['F','M'].flatMap(kind=>axes.map(axis=>kind+axis));
  function visibility(){
    $(`${prefix}-load-settings`).hidden=$(`${prefix}-frame`).value!=='mixed';
    for(const label of rows)$(`${prefix}-target-label-${label}`).hidden=$(`${prefix}-load-${label}`).value!=='load';
  }
  $(`${prefix}-frame`).addEventListener('input',visibility);
  for(const label of rows)for(const type of ['load','target'])$(`${prefix}-${type}-${label}`).addEventListener('input',()=>{visibility();onEdit();});
  visibility();
}

export function frameOptions(prefix){
  const frame=$(`${prefix}-frame`).value;
  if(frame!=='mixed')return {frame};
  const load_targets={};
  for(const kind of ['F','M'])for(const axis of axes){
    const label=kind+axis;if($(`${prefix}-load-${label}`).value!=='load')continue;
    const input=$(`${prefix}-target-${label}`);
    if(!input.value.trim()||!input.checkValidity()||!Number.isFinite(Number(input.value)))throw new Error('Enter finite values for the selected net-load targets.');
    load_targets[`${kind==='F'?'force':'moment'}.${axis}`]=Number(input.value);
  }
  if(!Object.keys(load_targets).length)throw new Error('Select at least one net-load target for mixed motion.');
  return {frame,load_targets};
}

export function frameInputs(frame,targets={}){
  if(frame==='fixed')return [];
  return ['force','moment'].flatMap((kind,j)=>axes.map(axis=>{
    const quantity=`${kind}.${axis}`;
    return frame==='free'||Object.hasOwn(targets,quantity)?`target.${quantity}`:`${j?'angular_acceleration':'acceleration'}.${axis}`;
  }));
}
