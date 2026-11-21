import {colorBeamPlot} from './plot-colors.js';
import {renderBeamDistribution} from './beam-distribution-plot.js';
import {linearStructureSamples,spanRange} from './linear-span.js';

const quantities = [
  ['shell.axial_strain_bound','Axial strain bound','µε',1e6],
  ['shell.axial_strain','Signed strain at shell point','µε',1e6],
  ['shell.shear_stress','Signed torsional shear stress','stress',1],
  ['shell.shear_stress_abs','Absolute torsional shear stress','stress',1],
  ['axial_strain_tension','Axial strain at tension axis','µε',1e6],
  ...['c','s','n'].map((a,i)=>[`strain.${i}`,`${a==='s'?'Axial':'Shear'} strain ${a} at reference axis`,'µε',1e6]),
  ...['c','s','n'].map((a,i)=>[`curvature_change.${i}`,`Curvature change ${a}`,'rad / input L',1]),
  ...['c','s','n'].map((a,i)=>[`force_local.${i}`,`Internal force ${a}`,'input F',1]),
  ...['c','s','n'].map((a,i)=>[`moment_axes.${i}`,`${a==='s'?'Torsion':'Bending moment'} ${a} at ${a==='s'?'elastic':'tension'} axis`,'input F·L',1]),
  ['distributed_gravity.normal','Normal gravity load per length','input F / input L',1],
];
const get=(row,path)=>path.split('.').reduce((v,k)=>v?.[k],row);
const dampedSourceStructure=meta=>meta?.strain_source==='source_discrete_damped_constitutive';
const normalGravity=key=>key==='distributed_gravity.normal';
export const sourceStructure=meta=>meta?.strain_source==='source_discrete_constitutive'||dampedSourceStructure(meta);
export function structureSampleDescription(meta,count,key=''){
  if(normalGravity(key))return `${count} interval gravity loads per material length · projected onto the physical midpoint normal. Concentrated weights and support reactions are separate.`;
  if(dampedSourceStructure(meta))return `${count} interval constitutive estimates · endpoint-averaged section axes. Mechanical strains include the material-rate correction. Dots locate intervals, not point samples; damped endpoint mechanical strains are unavailable.`;
  return sourceStructure(meta)?`${count} interval constitutive estimates · endpoint-averaged section axes. Lines mark each element’s extent; dots locate intervals and are not point samples.`:
    `${count} material midpoint samples · local c, s, n axes. Lines mark each element’s extent; dots are the sampled values.`;
}
export function structureExportRows(result){
  if(!sourceStructure(result.structure))return result.elements;
  return result.elements.flatMap(e=>[{...e,sample_location:'element constitutive average'},
    ...(e.endpoint_traces??[]).map(trace=>{
      const row={...e,...trace,sample_location:'one-sided endpoint section'};
      // The interval load is not a nodal load sample. Keep endpoint CSV cells blank.
      delete row.distributed_gravity;
      return row;
    })]);
}

export function structureMissingDescription(key,missing,count){
  if(!missing)return '';
  const reason=normalGravity(key)?'Normal gravity loading is available in new ASWING structural-static results. Other policies and older saved results do not contain this output.':
    key.startsWith('shell.shear_stress')?'Supply positive Atshell (enclosed area × thickness); zero is missing, negative is invalid.':
    'Supply Cshell and/or Nshell in the .asw file to locate the material point.';
  return `${missing} of ${count} samples unavailable. ${reason}`;
}

export const structureOptions = '<optgroup label="Structure">'+quantities.map(([key,name])=>`<option value="structure:${key}">${name}</option>`).join('')+'</optgroup>';
export const structureUnits = '<label hidden>Units<select id="structure-stress-unit"><option value="input">Input F/L²</option><option value="Pa">Pa</option><option value="MPa">MPa</option></select></label>';
export const structureDetails = '<div id="structure-details" hidden><p id="structure-missing" class="small muted" hidden></p></div>';

export function createStructureResults(getState) {
  const $=id=>document.getElementById(id);
  function render(linear=null) {
    const {result,model}=getState(),meta=result?.structure;
    for(const id of ['plot-title','plot-unit','structure-missing'])$(id).replaceChildren();
    $('structure-missing').hidden=true;
    if(!meta) {$('plot').textContent='Run a structural analysis to view this property.';return;}
    colorBeamPlot($('plot'),model.beams,$('plot-beam').value);
    const rows=result.elements.filter(e=>e.beam===Number($('plot-beam').value));
    const key=$('plot-quantity').value.slice('structure:'.length);
    $('plot-quantity').querySelector('option[value="structure:distributed_gravity.normal"]').disabled=!rows.some(e=>Number.isFinite(e.distributed_gravity?.normal));
    let [,name,unit,scale]=quantities.find(q=>q[0]===key);
    const stress=unit==='stress',toPa=meta.units.stress_to_pa;
    $('structure-stress-unit').disabled=!stress;
    $('structure-stress-unit').closest('label').hidden=!stress;
    for(const o of $('structure-stress-unit').options)o.disabled=o.value!=='input'&&toPa==null;
    if(toPa==null)$('structure-stress-unit').value='input';
    if(stress) {const choice=$('structure-stress-unit').value;unit=choice==='input'?'input F/L²':choice;scale=choice==='input'?1:toPa/(choice==='MPa'?1e6:1);}
    $('plot-title').textContent=name;
    $('plot-unit').textContent=`${unit} · t`;
    const samples=linear?linearStructureSamples(rows,linear,key,scale):rows.map(r=>({...r,value:get(r,key)==null?null:get(r,key)*scale}));
    const missing=samples.filter(r=>!Number.isFinite(r.value)).length;
    $('structure-missing').textContent=linear?'Some animated values are unavailable in this result.':structureMissingDescription(key,missing,rows.length);
    $('structure-missing').hidden=!missing;
    renderBeamDistribution($('plot'),samples,{kind:'sections',label:name,unit,domain:rows.flatMap(row=>[row.t0,row.t1]),
      range:linear?spanRange(samples):null,hoverKey:`${$('plot-beam').value}:structure:${key}:${unit}`,
      emptyMessage:linear?'No animated values in this result. Run the analysis again.':undefined});
  }
  return {render};
}
