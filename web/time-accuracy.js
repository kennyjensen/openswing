const $=id=>document.getElementById(id);
export const accuracySettings=prefix=>`
<details class="advanced" id="${prefix}-accuracy-settings"><summary>Time-step accuracy check</summary>
  <label class="checkbox"><input id="${prefix}-accuracy-enabled" type="checkbox"><span>Refine steps using a temporal discrepancy check</span></label>
  <div id="${prefix}-accuracy-fields" hidden>
    <div class="fields"><label>Relative tolerance<input id="${prefix}-accuracy-rtol" type="number" min="0" max="0.1" step="any" value="0.001"></label><label>Scaled absolute tolerance<input id="${prefix}-accuracy-atol" type="number" min="0" max="0.1" step="any" value="0.000001"></label></div>
    <label>Minimum trial step <span>input T · blank uses an automatic limit</span><input id="${prefix}-accuracy-minimum" type="number" min="0" step="any"></label>
  </div>
  <p class="small muted">Compares one step with two half steps, including motion, loads and rates. Accepts the refined endpoint without extrapolation. Absolute tolerance uses the model's physical scales, recorded in JSON. This adds computation; tighter tolerances and independent mesh/step refinement remain necessary. It is a local discrepancy check, not a bound on total trajectory error.</p>
</details>`;

export function createTimeAccuracy(prefix,onEdit=()=>{}){
  const name=key=>`${prefix}-accuracy-${key}`;
  function refresh(){$(name('fields')).hidden=!$(name('enabled')).checked;}
  for(const key of ['enabled','rtol','atol','minimum'])$(name(key)).addEventListener('input',()=>{refresh();onEdit();});
  $(name('enabled')).addEventListener('change',refresh);
  return {options(){
    if(!$(name('enabled')).checked)return null;
    const rtol=Number($(name('rtol')).value),atol=Number($(name('atol')).value);
    if(!$(name('rtol')).value.trim()||!$(name('atol')).value.trim()||!Number.isFinite(rtol)||!Number.isFinite(atol)||rtol<0||rtol>.1||atol<=0||atol>.1)throw new Error('Enter 0–0.1 for relative tolerance and a positive scaled absolute tolerance no greater than 0.1.');
    const value={rtol,atol},minimum=$(name('minimum')).value.trim();
    if(minimum){value.minimum_step=Number(minimum);if(!Number.isFinite(value.minimum_step)||value.minimum_step<=0)throw new Error('Minimum trial step must be positive.');}
    return value;
  },restore(value){
    $(name('enabled')).checked=value!=null;$(name('rtol')).value=value?.rtol??.001;
    $(name('atol')).value=value?.atol??.000001;$(name('minimum')).value=value?.minimum_step??'';refresh();
  }};
}
