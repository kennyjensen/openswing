const $=id=>document.getElementById(id);
export const demoController={outputs:[{actuator:'E1',terms:[
  {input:'RY[2]',gain:-200},{input:'UY[2]',gain:-20},{input:'RY[2]',gain:-100,mode:'integral'}]}]};
export const lagController={parameters:{kp:200,kd:20,tau:.05},
  outputs:[{actuator:'E1',expression:"state('lag')"}],
  states:[{name:'lag',initial:0,scale:10,unit:'file engine setting',
    rate:"(command('E1')-parameter('kp')*error('RY[2]')-parameter('kd')*error('UY[2]')-state('lag'))/parameter('tau')"}]};
export const feedbackSettings=`
<details id="feedback-settings" class="advanced" hidden><summary>Feedback control</summary>
  <label class="checkbox"><input id="feedback-enabled" type="checkbox"> Enable closed-loop control</label>
  <p class="small muted">Commands and measured errors drive flap or engine settings in equilibrium, time, modal and Bode analyses.</p>
  <label class="field-label" for="feedback-definition">Controller definition</label>
  <textarea id="feedback-definition" rows="9" spellcheck="false" aria-label="Controller definition"></textarea>
  <div class="file-actions"><button id="feedback-demo" type="button">Spring–mass PI example</button><button id="feedback-lag-demo" type="button">Actuator-lag example</button><button id="feedback-import" type="button">Import</button><button id="feedback-save" type="button">Save JSON</button></div>
  <input id="feedback-file" type="file" accept=".json,.con,text/plain" hidden>
  <p class="small muted">The example uses Engine 1 and Sensor 2 in the instrumented spring–mass model. Gains use file units; angle channels use degrees. Time tables can command selected measurements, such as +RY[2]. Default commands hold initial measured values.</p>
  <p class="small muted">A .con import preserves its gain tables and requires explicit input/output bindings and unit factors in the definition. See the source README for the binding format. Scheduled gains use true airspeed and density.</p>
  <p class="small muted">In equilibrium, each integrated error must have zero rate. Operating constraints can solve a Command variable for a trim target; the controlled actuator remains set by the law. Default commands come from the loaded structure at the prescribed operating settings. Modal and Bode analyses retain the resulting trim, then hold its commands fixed.</p>
  <p class="small muted">Custom outputs can use an expression or an implicit residual. Internal states have explicit rate equations, scales and unit labels. Time startup holds their initial values; equilibrium solves zero rates. The lag example adds a 0.05-input-T actuator response to the spring–mass model. See the source README for expression syntax.</p>
  <label class="field-label" for="feedback-harmonic">Bode measurement commands</label>
  <input id="feedback-harmonic" type="text" placeholder="RY[2], Ey" aria-label="Bode measurement commands">
  <p class="small muted">Comma-separated selected measurements add unit command inputs to the Bode sweep. Declared actuator inputs become commanded settings for controlled actuators.</p>
</details>`;
export const feedbackPane=`
<div id="pane-feedback" class="tab-pane" role="tabpanel" aria-labelledby="tab-feedback" hidden>
 <p id="feedback-summary" class="small muted">Enable feedback for equilibrium, time, mode or frequency analysis.</p>
 <button id="feedback-csv" disabled>Controller CSV</button>
 <div id="feedback-table" class="derivative-table-wrap"></div>
 <p class="small muted">Error = measured − commanded. Actuator outputs and state rates follow the controller definition. Saturation and anti-windup apply only when explicitly defined. Check eigenmodes for closed-loop stability and refine both mesh and time/tangent steps.</p>
</div>`;
const csv=row=>row.map(x=>'"'+String(x??'').replaceAll('"','""')+'"').join(',');
const fmt=x=>Number.isFinite(x)?x.toPrecision(7):'—';
export function feedbackUnit(metadata,key){
  if(key.startsWith('state_rates_'))return (metadata?.state_units?.[key.slice(12)]??'file units')+' / input T';
  if(key.startsWith('states_'))return metadata?.state_units?.[key.slice(7)]??'file units';
  const split=key.indexOf('_'),group=key.slice(0,split),name=key.slice(split+1);
  const unit=/^[FE]\d+$/.test(name)?(name[0]==='F'?'file flap setting':'file engine setting'):metadata?.units?.[name]??'file units';
  return group==='integrals'?unit+' · input T':unit;
}
export function createFeedbackSettings(onEdit,download,showError){
  const definition=()=>{try{return JSON.parse($('feedback-definition').value);}catch{throw new Error('Controller definition must be valid JSON.');}};
  $('feedback-definition').value=JSON.stringify(demoController,null,2);
  for(const id of ['feedback-enabled','feedback-definition','feedback-harmonic'])$(id).addEventListener('input',onEdit);
  $('feedback-demo').onclick=()=>{$('feedback-definition').value=JSON.stringify(demoController,null,2);$('feedback-enabled').checked=true;onEdit();};
  $('feedback-lag-demo').onclick=()=>{$('feedback-definition').value=JSON.stringify(lagController,null,2);$('feedback-enabled').checked=true;onEdit();};
  $('feedback-save').onclick=()=>{try{download('openswing-controller.json',JSON.stringify(definition(),null,2)+'\n','application/json');}catch(error){showError(error);}};
  $('feedback-import').onclick=()=>$('feedback-file').click();
  $('feedback-file').onchange=async()=>{
    const file=$('feedback-file').files[0];if(!file)return;
    try{
      const text=await file.text();let value;
      if(file.name.toLowerCase().endsWith('.con')){
        let previous={};try{previous=definition();}catch{}
        value={con:text,bindings:previous.bindings??{outputs:{},inputs:{},outside:'error'},commands:previous.commands??{}};
      }else value=JSON.parse(text);
      $('feedback-definition').value=JSON.stringify(value,null,2);$('feedback-enabled').checked=true;onEdit();
    }catch(error){showError(error);}finally{$('feedback-file').value='';}
  };
  function commands(){
    if(!$('feedback-enabled').checked)return [];
    try{
      const value=definition(),names=new Set();
      for(const row of value.outputs??[]){names.add(row.actuator);for(const term of row.terms??[])names.add(term.input);}
      const expressions=[...(value.outputs??[]).flatMap(row=>[row.expression,row.residual]),...(value.states??[]).map(row=>row.rate)];
      for(const source of expressions)if(typeof source==='string'){
        for(const match of source.matchAll(/\b(?:measurement|error|integral|command)\(\s*(['"])([A-Za-z]+(?:\[[1-9]\d*\])?|[FE][1-9]\d*)\1\s*\)/g))names.add(match[2]);
      }
      for(const row of Object.values(value.bindings?.outputs??{}))names.add(row.actuator);
      for(const row of Object.values(value.bindings?.inputs??{}))names.add(row.input);
      return [...names].filter(name=>typeof name==='string'&&name.length).map(name=>['command.'+name,'Command '+name]);
    }catch{return [];}
  }
  return {commands,options:()=>$('feedback-enabled').checked?definition():null,
    inputs:()=>$('feedback-enabled').checked?$('feedback-harmonic').value.split(',').map(s=>s.trim()).filter(Boolean).map(s=>'command.'+s):[]};
}

export function createFeedbackResults(getState,onEdit,download,showError,getModeIndex=()=>0){
  const settings=createFeedbackSettings(onEdit,download,showError);
  let context=null,identity=null;
  function current(){
    const state=getState();
    if(state.frequency){
      const input=Number($('frequency-input').value),sample=state.frequency.samples[Number($('frequency-sample').value)];
      return {data:sample?.responses[input]?.output.feedback,metadata:state.frequency.controller,complex:true,
        label:'Harmonic controller perturbation · ω='+fmt(sample?.omega)+' rad/input T · '+(state.frequency.inputs[input]?.name??''),normalization:'per unit '+(state.frequency.inputs[input]?.unit??'input')};
    }
    if(state.modal){
      const index=getModeIndex();
      return {data:state.modal.modes[index]?.output.feedback,metadata:state.modal.controller,complex:true,label:'Mode '+(index+1)+' · controller perturbation',normalization:'per saved right eigenvector'};
    }
    const report=state.result?.feedback;
    return {data:report,metadata:state.trajectory?.controller??state.result?.controller,complex:false,
      label:state.trajectory?'Computed controller state · t='+fmt(state.result?.time):'Steady controller equilibrium',normalization:'physical file units'};
  }
  function rows(){
    if(!context.data)return [];
    const flat=context.complex?context.data:Object.fromEntries(Object.entries(context.data).flatMap(([group,values])=>Object.entries(values).map(([name,value])=>[group+'_'+name,value])));
    return Object.entries(flat).map(([key,value])=>({key,unit:feedbackUnit(context.metadata,key),real:context.complex?value?.real:value,imag:context.complex?value?.imag:null}));
  }
  function render(){
    const next=current();if(next.data===identity)return;identity=next.data;context=next;
    $('feedback-table').replaceChildren();$('feedback-csv').disabled=!context.data;
    $('feedback-summary').textContent=context.data?context.label+' · '+context.normalization+'. Values are independent of playback scale and phase.':'No controller result. Enable feedback, then run equilibrium, time, mode or Bode analysis.';
    if(!context.data)return;
    const table=document.createElement('table'),head=table.createTHead().insertRow();
    for(const name of ['Signal','Unit',context.complex?'Real':'Value',...(context.complex?['Imaginary']:[])]){const cell=document.createElement('th');cell.textContent=name;head.append(cell);}
    const body=table.createTBody();
    for(const row of rows()){const tr=body.insertRow();const name=row.key.startsWith('state_rates_')?'state rates · '+row.key.slice(12):row.key.replace('_',' · ');for(const value of [name,row.unit,fmt(row.real),...(context.complex?[fmt(row.imag)]:[])])tr.insertCell().textContent=value;}
    $('feedback-table').append(table);
  }
  $('feedback-csv').onclick=()=>download('openswing-controller.csv',[csv(['context','normalization','signal','unit','real',...(context.complex?['imaginary']:[])]),...rows().map(r=>csv([context.label,context.normalization,r.key,r.unit,r.real,...(context.complex?[r.imag]:[])]))].join('\n')+'\n','text/csv');
  return {render,...settings};
}
