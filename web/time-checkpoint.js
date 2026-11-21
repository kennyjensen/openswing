import {accuracySettings,createTimeAccuracy} from './time-accuracy.js';
import {validateCheckpointPacket,checkpointRecord} from './saved-state-data.js';
import {timeHistory} from './time-history-source.js';
const $=id=>document.getElementById(id);
export const timeCheckpointPane=`
<details id="time-checkpoint-settings" class="advanced"><summary>Continue a computed trajectory</summary>
  <p class="small muted">Save the selected snapshot or use it to append steps. A checkpoint preserves motion, controller states, the previous BDF state and original forcing offsets. It uses the saved trajectory settings and requires the same ASW source.</p>
  <div class="time-toolbar"><button id="time-checkpoint-save" disabled>Save selected checkpoint</button><button id="time-checkpoint-use" disabled>Use selected state</button><button id="time-checkpoint-open">Load checkpoint</button><button id="time-checkpoint-clear" disabled>Clear checkpoint</button></div>
  <input id="time-checkpoint-file" type="file" accept=".json,application/json" hidden>
  <p id="time-checkpoint-status" class="small muted">No checkpoint loaded.</p>
  <div class="fields"><label>Additional duration [input T]<input id="time-continue-duration" type="number" min="0.000001" step="any" value="0.1"></label><label>Maximum step [input T]<input id="time-continue-step" type="number" min="0.000001" step="any" value="0.01"></label></div>
  <label>Integration method<select id="time-continue-order"><option value="2">BDF2</option><option value="1">BDF1</option><option value="5">Radau IIA</option></select></label>
  ${accuracySettings('time-continue')}
  <label class="checkbox"><input id="time-continue-replace" type="checkbox"><span>Replace the future forcing table</span></label>
  <textarea id="time-continue-forcing" aria-label="Continuation forcing table" spellcheck="false" hidden></textarea>
  <p class="small muted">Keep the table unchanged to retain BDF history. A replacement must start no later than the checkpoint time. BDF methods restart with BDF1; Radau needs no predecessor. Table values become zero after its last sample, including relative channels. Relative (+) channels keep their original reference values. Imported checkpoints produce a new segment; continuing a selected state keeps the earlier snapshots and replaces later ones.</p>
  <button id="time-continue" disabled>Continue loaded state</button>
  <p class="small muted">This OpenSwing checkpoint is separate from steady-equilibrium JSON and ASWING .pnt/.set files. Continuation checks the physical state and, when recorded, the equations of the accepted numerical step. Initial and older checkpoints provide physical-state checks only. Compatible motion-history changes retain separate before/after states at the same time. The after state restarts integration without changing the retained physical motion. Velocity or pose jumps requiring an impulse are rejected. Older saved-history checkpoints retain their original smooth-table restrictions.</p>
</details>`;

export function checkpointAt(trajectory,index){
  const snapshot=timeHistory(trajectory)?.peek(index);
  if(!snapshot?.restart)throw new Error('The selected result has no time checkpoint. Run a new time analysis.');
  return checkpointRecord(snapshot.restart,snapshot.restart_context??trajectory.restart_context);
}

export function createTimeCheckpoints(getState,getIndex,run,download,showError){
  let loaded=null,parent=null,parentIndex=null,busy=false,label='';
  const accuracy=createTimeAccuracy('time-continue');
  function refresh(){
    const trajectory=getState().trajectory,available=!!timeHistory(trajectory)?.peek(getIndex())?.restart;
    $('time-checkpoint-save').disabled=!available||busy;$('time-checkpoint-use').disabled=!available||busy;
    $('time-checkpoint-clear').disabled=!loaded||busy;$('time-continue').disabled=!loaded||busy||!getState().model||getState().dirty;
    $('time-checkpoint-status').textContent=loaded?`${label} · t = ${loaded.state.time.toPrecision(7)} input T. ${parent?'Earlier snapshots will be retained.':'Continuation produces a new time segment.'}`:'No checkpoint loaded.';
  }
  function load(data,name,from=null,index=null){
    if(data?.analysis==='time_response')data=checkpointAt(data,data.snapshots.length-1);
    loaded=validateCheckpointPacket(data);label=name;parent=from;parentIndex=index;
    $('time-continue-step').value=loaded.context.method.maximum_step;$('time-continue-order').value=loaded.context.method.order;
    accuracy.restore(loaded.context.method.accuracy??null);
    $('time-continue-forcing').value=loaded.context.setup.forcing;$('time-continue-replace').checked=false;$('time-continue-forcing').hidden=true;refresh();
  }
  $('time-checkpoint-save').onclick=()=>{try{download('openswing-time-checkpoint.json',JSON.stringify(checkpointAt(getState().trajectory,getIndex()),null,2),'application/json');}catch(e){showError(e);}};
  $('time-checkpoint-use').onclick=()=>{try{const trajectory=getState().trajectory,index=getIndex();load(checkpointAt(trajectory,index),'Selected computed state',trajectory,index);}catch(e){showError(e);}};
  $('time-checkpoint-clear').onclick=()=>{loaded=parent=null;parentIndex=null;refresh();};
  $('time-checkpoint-open').onclick=()=>$('time-checkpoint-file').click();
  $('time-checkpoint-file').onchange=async event=>{const file=event.target.files[0];if(!file)return;try{load(JSON.parse(await file.text()),file.name);}catch(e){showError(e);}finally{event.target.value='';}};
  $('time-continue-replace').onchange=()=>{$('time-continue-forcing').hidden=!$('time-continue-replace').checked;};
  $('time-continue').onclick=async()=>{
    if(!loaded||busy)return;
    const options={duration:Number($('time-continue-duration').value),dt:Number($('time-continue-step').value),order:Number($('time-continue-order').value)};
    try{options.accuracy=accuracy.options();}catch(error){showError(error);return;}
    if($('time-continue-replace').checked)options.forcing=$('time-continue-forcing').value;
    if(!(options.duration>0&&options.dt>0)){showError(new Error('Continuation duration and time step must be positive.'));return;}
    busy=true;refresh();
    try{await run(structuredClone(loaded),options,parent,parentIndex);}catch(e){showError(e);}finally{busy=false;refresh();}
  };
  return {refresh};
}
