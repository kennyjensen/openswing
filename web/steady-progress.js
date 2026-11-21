import {PROJECT_LIMIT} from './project-data.js';
import {nextSteadyRequest,progressRecord,validateSteadyProgress} from './steady-progress-data.js';
const $=id=>document.getElementById(id);

export const steadyProgressSettings=`
<details id="steady-progress-settings" class="advanced">
  <summary>Resumable equilibrium</summary>
  <p class="small muted">Advance one accepted load step at a time, then save progress or continue. Each step can take time. Results become available only when the full-load equilibrium converges.</p>
  <div class="time-toolbar"><button id="steady-progress-start" type="button">Start resumable solve</button><button id="steady-progress-next" type="button" disabled>Advance one load step</button></div>
  <p id="steady-progress-status" class="small muted" role="status">No unfinished solve.</p>
  <div class="time-toolbar"><button id="steady-progress-save" type="button" disabled>Save solve progress</button><button id="steady-progress-open" type="button">Load solve progress</button><button id="steady-progress-restore" type="button" disabled>Restore saved solve settings</button><button id="steady-progress-clear" type="button" disabled>Clear progress</button></div>
  <input id="steady-progress-file" type="file" accept=".json,application/json" hidden>
  <p class="small muted">Saving includes the aircraft and its solve settings. Loading restores them. Resume checks the model, settings, kernel version and physical residual. Cancel preserves the last finished load step; an interrupted step is discarded. Unfinished progress is separate from a saved equilibrium and cannot launch time response.</p>
</details>`;

export function createSteadyProgress({getState,run,loadCase,download,showError}) {
  let saved=null,completed=false,importing=false;
  const ready=()=>!getState().busy&&!getState().dirty&&!!getState().model&&!importing;
  function refresh() {
    const supported=['mounted','structural'].includes($('mode').value),idle=ready();
    $('steady-progress-start').disabled=!idle||!supported;
    $('steady-progress-next').disabled=!idle||!supported||!saved;
    $('steady-progress-open').disabled=!idle;
    $('steady-progress-save').disabled=!saved;
    $('steady-progress-restore').disabled=!idle||!saved;
    $('steady-progress-clear').disabled=!idle||!saved;
    const packet=saved?.checkpoint;
    $('steady-progress-status').textContent=packet
      ?`Unfinished · ${(100*packet.load_fraction).toFixed(2)}% applied load · ${packet.accepted_load_steps} accepted steps · residual ${packet.physical_residual.toExponential(3)}. Save progress to retain it after closing this page.`
      :completed?'Full-load equilibrium converged. The normal result and saved-equilibrium controls are now available.'
      :supported?'No unfinished solve. Start from current inputs without feedback, derivatives or a loaded initial equilibrium.'
      :'Select structural static or mounted equilibrium, or load saved solve progress.';
  }
  async function restore(record) {
    if(!ready())return;
    importing=true;refresh();
    try {await loadCase(record.configuration);saved=record;completed=false;refresh();}
    finally {importing=false;refresh();}
  }
  $('steady-progress-start').onclick=()=>run('start').catch(showError);
  $('steady-progress-next').onclick=()=>run('resume').catch(showError);
  $('steady-progress-save').onclick=()=>{if(saved)download('openswing-equilibrium-progress.json',JSON.stringify(saved,null,2),'application/json');};
  $('steady-progress-open').onclick=()=>$('steady-progress-file').click();
  $('steady-progress-file').onchange=async event=>{
    const file=event.target.files[0];if(!file)return;
    try {if(file.size>PROJECT_LIMIT)throw new Error('Solve-progress file exceeds 64 MiB.');await restore(validateSteadyProgress(JSON.parse(await file.text())));}
    catch(error){showError(error);}finally{event.target.value='';}
  };
  $('steady-progress-restore').onclick=()=>{if(saved)restore(structuredClone(saved)).catch(showError);};
  $('steady-progress-clear').onclick=()=>{if(ready()){saved=null;completed=false;refresh();}};
  refresh();
  return {
    refresh,
    request(base,action){
      if(action==='resume'&&!saved)throw new Error('Load or start a resumable equilibrium first.');
      return nextSteadyRequest(base,action==='resume'?saved:null);
    },
    pending(configuration,request,result){saved=progressRecord(configuration,request,result);completed=false;$('steady-progress-settings').open=true;refresh();},
    complete(){saved=null;completed=true;refresh();},
    invalidate(){completed=false;refresh();},
  };
}
