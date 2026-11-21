import {weightRecords,editWeight,deleteWeight,appendWeight,massDisplayUnits} from './mass-data.js';

export const massPane=`
<div id="mass-editor" class="editor-panel-content">
  <dl class="mass-summary">
    <div><dt>Total mass</dt><dd id="mass-total">—</dd></div>
    <div><dt>CG · x, y, z</dt><dd id="mass-cg">—</dd></div>
  </dl>
  <div class="mass-tools">
    <label>Point mass<select id="mass-item"></select></label>
    <div class="mass-record-actions">
    <button id="mass-add" type="button" title="Add point mass" aria-label="Add point mass">+</button>
    <button id="mass-delete" type="button" title="Delete point mass" aria-label="Delete point mass"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 10v7m4-7v7" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></button>
    <button id="mass-undo" type="button" disabled>Undo</button>
    </div>
  </div>
  <div id="mass-fields">
    <div class="fields mass-attachment"><label>Beam<select id="mass-beam" data-weight-column="0"></select></label><label>Station t<input id="mass-station" data-weight-column="1" type="number" step="any" required></label><label>Mass <span id="mass-unit"></span><input id="mass-value" data-weight-column="5" type="number" step="any" required></label></div>
    <div class="fields mass-position">${['x','y','z'].map((axis,i)=>`<label>${axis} <span data-mass-length-unit></span><input id="mass-${axis}" data-weight-column="${i+2}" type="number" step="any" required></label>`).join('')}</div>
    <details class="advanced mass-inertia"><summary>Point inertia <span id="mass-inertia-unit"></span></summary>
      <div class="fields">${['xx','yy','zz','xy','xz','yz'].map((axis,i)=>`<label${i>=3?' title="Product of inertia; the tensor entry has the opposite sign."':''}>I${axis}<input id="mass-i${axis}" data-weight-column="${i+11}" type="number" step="any" required></label>`).join('')}</div>
    </details>
  </div>
  <p id="mass-status" role="status"></p>
</div>`;

export function createMassEditor({context,rpc,commit,panels}){
  const $=id=>document.getElementById(id),pane=$('mass-editor');
  let current=null,records=[],selected=0,units=null,busy=false,serial=0,pending=null,history=[],draft=false,saving=Promise.resolve();
  const available=()=>current&&context().model&&!context().dirty&&!context().busy&&current.source===context().source;
  const message=(text,error=false)=>{const node=$('mass-status');node.textContent=text;node.classList.toggle('distribution-error',error);};
  function refresh(){
    const disabled=busy||!available();
    for(const node of pane.querySelectorAll('input,select,button'))node.disabled=disabled;
    $('mass-item').disabled=$('mass-delete').disabled=disabled||!records.length;
    $('mass-undo').disabled=disabled||!history.length;
    if(context().dirty)message('Apply ASW edits first.');
  }
  function fields(){
    const row=records[selected];$('mass-fields').hidden=!row;
    if(row)for(const node of pane.querySelectorAll('[data-weight-column]')){
      const column=Number(node.dataset.weightColumn);node.value=String(row.values[column]*units.factor(column));
    }
    draft=false;refresh();
  }
  function setModel(model,source){
    const own=pending?.source===source?pending:null;
    if(current?.source!==source&&!own)history=[];
    serial++;busy=false;current={model,source};units=massDisplayUnits(model);records=weightRecords(source).records;
    selected=Math.min(Math.max(0,own?.selected??selected),Math.max(0,records.length-1));
    const option=(select,value,text)=>{const o=document.createElement('option');o.value=value;o.textContent=text;select.append(o);};
    $('mass-item').replaceChildren();records.forEach((row,i)=>option($('mass-item'),i,`${i+1}: ${row.label}`));
    if(!records.length)option($('mass-item'),'','No point masses');else $('mass-item').value=selected;
    $('mass-beam').replaceChildren();for(const beam of model.beams)option($('mass-beam'),beam.index,`${beam.index}: ${beam.name}`);
    $('mass-unit').textContent=units.massLabel;$('mass-inertia-unit').textContent=units.inertiaLabel;
    for(const node of pane.querySelectorAll('[data-mass-length-unit]'))node.textContent=units.lengthLabel;
    const summary=model.mass_properties,fmt=value=>Number.isFinite(value)?Number(value.toPrecision(7)).toString():'—';
    $('mass-total').textContent=fmt(summary?.mass*units.mass)+' '+units.massLabel;
    $('mass-cg').textContent=summary?.cg?summary.cg.map(v=>fmt(v*units.length)).join(', ')+' '+units.lengthLabel:'—';
    fields();message('');if(own?.focus)$(own.focus)?.focus({preventScroll:true});
  }
  async function save(source,next=selected,undo=false){
    if(busy||!available())return;
    if(source===current.source){draft=false;message('');return;}
    const previous=current,token=++serial,revision=context().revision;
    busy=true;refresh();message('Updating…');
    try{
      const model=await rpc({action:'inspect',source,panels:panels()});
      if(token!==serial||revision!==context().revision||!available())return;
      pending={source,selected:next,focus:document.activeElement?.id};
      await commit(source,model);
      if(context().source===source&&!context().dirty){if(undo)history.pop();else history.push(previous);message('');}
    }catch(error){if(token===serial)message(error.message,true);}
    finally{if(token===serial||pending?.source===source){busy=false;pending=null;refresh();}}
  }
  const begin=(...args)=>saving=save(...args);
  function edit(node){
    if(!available()||busy)return;
    if(!node.checkValidity()||!node.value.trim()){message('Enter a valid value.',true);return;}
    try{
      const column=Number(node.dataset.weightColumn),value=Number(node.value)/units.factor(column),changes={[column]:value};
      if(column===0){
        const domain=current.model.distributions.find(b=>b.beam===value)?.domain;
        if(domain)changes[1]=Math.min(domain[1],Math.max(domain[0],records[selected].values[1]));
      }
      return begin(editWeight(current.source,selected,changes));
    }catch(error){message(error.message,true);}
  }
  for(const node of pane.querySelectorAll('[data-weight-column]')){
    node.oninput=()=>{draft=true;message('');};node.onchange=()=>edit(node);
  }
  $('mass-item').onchange=()=>{selected=Number($('mass-item').value);fields();message('');};
  $('mass-add').onclick=()=>{
    if(!available()||busy)return;
    const row=records[selected],beam=current.model.beams.find(b=>b.index===row?.values[0])??current.model.beams[0];
    const t=row?.values[1]??current.model.distributions.find(b=>b.beam===beam.index).domain[0],position=row?.values.slice(2,5)??beam.axis[0][0];
    return begin(appendWeight(current.source,{beam:beam.index,t,position}),records.length);
  };
  $('mass-delete').onclick=()=>{if(available()&&!busy&&records[selected])return begin(deleteWeight(current.source,selected),Math.max(0,selected-1));};
  $('mass-undo').onclick=()=>{if(available()&&!busy&&history.length)return begin(history.at(-1).source,selected,true);};
  refresh();return {setModel,refresh,ready:()=>saving,hasDraft:()=>draft||busy};
}
