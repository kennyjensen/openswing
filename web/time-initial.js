const $=id=>document.getElementById(id);
export const timeInitialSettings=`
<details id="time-initial-settings" class="advanced"><summary>Initial physical disturbance</summary>
  <label class="checkbox"><input id="time-initial-enable" type="checkbox"><span>Disturb the loaded saved equilibrium</span></label>
  <p class="small muted">Load or use a computed equilibrium, then specify physical increments below. Omitted fields are zero. The solver preserves displacement, rotation, velocity, circulation, flight-frame and controller-state increments while completing the initial loads and accelerations. Incompatible constraints are rejected. New time forcing starts after this initial state.</p>
  <label class="field-label" for="time-initial-profile">Physical state · JSON</label>
  <textarea id="time-initial-profile" rows="7" spellcheck="false">{"beam_fields":[{"beam":1,"displacement":[[0,0,0,0],[2,0,0.002,0]],"velocity":[[0,0,0,0],[2,0,0.01,0]]}]}</textarea>
  <div class="file-actions"><button id="time-initial-open" type="button">Import disturbance</button><button id="time-initial-save" type="button">Export disturbance</button><input id="time-initial-file" type="file" accept=".json,application/json" hidden></div>
  <p class="small muted">Beam tables use [t,x,y,z] rows and both exact beam endpoints. Displacement uses input L, rotation radians, velocity L/T, rates radians/T and circulation L²/T. Frame attitude_rad adds radians to the saved bank/elevation/heading. Feedback integrals and states use their declared physical units. The example above fits the instrumented spring. Import one profile from a linear initial-response study to compare the same physical disturbance.</p>
  <div class="fields"><label>Derivative spacing <span>scaled time</span><input id="time-initial-spacing" type="number" value=".01" min=".001" max=".03" step="any"></label><label>Rank tolerance<input id="time-initial-rank" type="number" value="1e-7" min="1e-9" max="1e-5" step="any"></label></div>
  <p class="small muted">Choose Radau IIA above for constrained motion with nonzero initial velocity. BDF startup can give a reaction transient whose peak does not converge.</p>
  <p id="time-initial-note" class="small muted">Initialization checks local uniqueness and spacing refinement; refine these settings and the time step. Switching boundaries and unresolved constraints may prevent initialization.</p>
</details>`;

export function createTimeInitial(download,changed,showError){
  function profile(value=JSON.parse($('time-initial-profile').value)){
    if(Array.isArray(value)){if(value.length!==1)throw new Error('Import a single initial profile; choose one entry from the array.');value=value[0];}
    if(value?.kind==='initial')value=value.state;
    if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('Initial disturbance must be a physical state object.');
    return value;
  }
  $('time-initial-open').onclick=()=>$('time-initial-file').click();
  $('time-initial-file').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;$('time-initial-profile').value=JSON.stringify(profile(JSON.parse(await file.text())),null,2);$('time-initial-enable').checked=true;changed();$('time-initial-note').textContent='Imported physical disturbance. Enable a loaded saved equilibrium and run time response to check its constraints.';}catch(error){showError(error);}finally{e.target.value='';}};
  $('time-initial-save').onclick=()=>{try{download('openswing-time-disturbance.json',JSON.stringify(profile(),null,2),'application/json');}catch(error){showError(error);}};
  for(const id of ['time-initial-enable','time-initial-profile','time-initial-spacing','time-initial-rank'])$(id).addEventListener('input',changed);
  return {options(){
    if(!$('time-initial-enable').checked)return {};
    for(const id of ['time-initial-spacing','time-initial-rank'])if(!$(id).value||!$(id).checkValidity())throw new Error('Enter valid initial derivative spacing and rank tolerance.');
    return {disturbance:profile(),initial_difference_step:Number($('time-initial-spacing').value),initial_rank_tolerance:Number($('time-initial-rank').value)};
  }};
}
