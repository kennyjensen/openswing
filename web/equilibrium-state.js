import {hasQuiescentEquilibrium} from './quiescent-settings.js';
import {validateEquilibriumPacket} from './saved-state-data.js';
const $=id=>document.getElementById(id);
export const equilibriumSettings=`
<details id="equilibrium-settings" class="advanced"><summary>Saved equilibrium</summary>
  <p class="small muted">Reuse a computed loaded state for steady, modal, Bode or time analysis. The ASW source and mesh must match exactly.</p>
  <div class="time-toolbar"><button id="equilibrium-open" type="button">Load equilibrium</button><button id="equilibrium-save" type="button" disabled>Save computed equilibrium</button><button id="equilibrium-use" type="button" disabled>Use computed equilibrium</button><button id="equilibrium-clear" type="button" disabled>Clear loaded equilibrium</button></div>
  <input id="equilibrium-file" type="file" accept=".json,application/json" hidden>
  <label class="checkbox"><input id="equilibrium-enable" type="checkbox" disabled><span>Start from loaded equilibrium</span></label>
  <p id="equilibrium-status" class="small muted">No equilibrium loaded.</p>
  <p id="equilibrium-help" class="small muted"></p>
</details>`;

export function createEquilibriumSettings(download,changed,showError){
  let loaded=null,computed=null,label='';
  function render(){
    const quiescent=($('mode').value==='modes'&&$('modal-quiescent')?.checked)||($('mode').value==='frequency'&&$('structural-equations')?.value==='aswing-still-air');
    const time=$('mode').value==='time',supported=!quiescent&&['mounted','structural','modes','frequency','time'].includes($('mode').value);
    $('equilibrium-help').textContent=time?'Time launch uses the saved flight condition, loads, frame pose and solved trim commands. Duration, step, frame mode, targets and forcing come from the time controls. Ordinary launches retain a snapshot before new forcing applies. A supported motion-history launch holds the saved physical state and completes its initial actuator settings and accelerations: snapshot 0 is this right state, with the original before-input snapshot retained separately. Saved history launches currently require one nonrotating Earth-velocity or Earth-position target, unchanged loads, no controller/gust and an explicit target table. Position tables must initially match both saved position and Earth velocity. New saved-history runs support compatible changes in table slope, replacement tables and zero cutoff through separate before/after states; incompatible position or velocity jumps are rejected. Older checkpoints retain their original smooth-table restrictions. Older files without launch setup must be recomputed.':'Steady, modal and Bode analyses use this as a physical guess and solve the full equilibrium again with current conditions and targets. Correction can fail near folds or follow another branch. OpenSwing JSON is not an ASWING .pnt file or time-history restart.';
    if(quiescent)$('equilibrium-help').textContent='Still-air modes solve their structural base from the current model, pose and gravity. Loaded equilibria, time launch and exported equilibrium reuse are unavailable for this medium. Ordinary loaded-state settings are retained for other analyses.';
    $('equilibrium-open').disabled=quiescent;
    $('equilibrium-enable').disabled=!loaded||!supported;
    $('equilibrium-use').disabled=!computed||quiescent;$('equilibrium-save').disabled=!computed||quiescent;$('equilibrium-clear').disabled=!loaded;
    $('equilibrium-status').textContent=loaded?`${label} · ${loaded.positions.length} nodes. ${quiescent?'This loaded state is retained but not used for still-air modes.':!supported?'Select structural or mounted equilibrium, eigenmodes, Bode or time response to use it.':$('equilibrium-enable').checked?'The next solve uses this loaded state.':'Loaded state is disabled.'}${time&&loaded.launch?.condition?` Saved aerodynamic lag: ${loaded.launch.condition.aero_lag===false?'disabled':'enabled'}. Saved wake core r/c: ${loaded.launch.condition.wake_core_ratio??0.25}. Saved influences: ${loaded.launch.condition.freeze_influences?'frozen':'current'}. Saved stall: ${loaded.launch.condition.stall===false?'disabled':'enabled'}, K_s=${loaded.launch.condition.stall_factor??40}, delta_cl=${loaded.launch.condition.stall_width??0.05}.`:''}`:'No equilibrium loaded.';
  }
  function extract(data){
    const seed=data?.equilibrium_state??data?.base?.equilibrium_state??data;
    if(hasQuiescentEquilibrium(data)||hasQuiescentEquilibrium(seed))throw new Error('Still-air modal equilibria cannot be loaded or reused for other analyses. Open the saved modal result to inspect it.');
    return validateEquilibriumPacket(seed);
  }
  function setLoaded(data,name){loaded=extract(data);label=name;$('equilibrium-enable').checked=true;changed();render();}
  $('equilibrium-open').onclick=()=>$('equilibrium-file').click();
  $('equilibrium-file').onchange=async event=>{const file=event.target.files[0];if(!file)return;try{setLoaded(JSON.parse(await file.text()),file.name);}catch(error){showError(error);}finally{event.target.value='';}};
  $('equilibrium-use').onclick=()=>{if(computed)setLoaded(computed,'Computed equilibrium');};
  $('equilibrium-save').onclick=()=>{if(computed)download('openswing-equilibrium.json',JSON.stringify(computed,null,2),'application/json');};
  $('equilibrium-clear').onclick=()=>{loaded=null;$('equilibrium-enable').checked=false;changed();render();};
  $('equilibrium-enable').onchange=()=>{changed();render();};
  $('mode').addEventListener('change',render);
  render();
  return {
    refresh:render,
    setComputed(seed){computed=seed&&!hasQuiescentEquilibrium(seed)?structuredClone(seed):null;render();},
    capture(){return {state:loaded?structuredClone(loaded):null,enabled:!!loaded&&$('equilibrium-enable').checked,label};},
    restore(value){loaded=value.state?extract(value.state):null;label=value.label;$('equilibrium-enable').checked=value.enabled;render();},
    initial(){return loaded&&$('equilibrium-enable').checked&&!$('equilibrium-enable').disabled?structuredClone(loaded):null;}
  };
}
