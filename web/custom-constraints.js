import {sensorFields,sensorFieldAvailable} from './sensor-results.js';
export const customSettings=`<div id="custom-trim-settings" hidden>
  <p class="small muted">Custom equations drive an expression to the target above. Use sensor measurements, operating variables, net loads or aerodynamic coefficients. All numbers use file units. Choose a positive residual scale comparable to a meaningful change in the expression. These steady targets are released for dynamic response.</p>
  <div id="custom-trim-equations"></div>
  <details><summary>Expression reference</summary><p class="small muted">Examples: sensor("2.displacement_body.y"), sensor("2.strain.s"), variable("power.1"), load("force.z"), aero("CL"). Structural components use c/s/n; other vectors use x/y/z. Angles use degrees, angular rates use radians per input T. Arithmetic, pi, sin, cos, tan, asin, acos, atan, atan2, exp, log, sqrt, abs, minimum, maximum, clip and where are supported; trigonometric functions use radians. Strain/stress refer to the adjacent material midpoint. Undefined measurements and locally nonsmooth equations are rejected.</p></details>
</div>`;

export function createCustomConstraints(model,changed){
  const definitions=new WeakMap(),$=id=>document.getElementById(id);
  let next=1;
  function remember(row,c={}){
    const sensor=model()?.sensors?.at(-1)?.index??1;
    const names=new Set([...document.querySelectorAll('.constraint-row')].map(r=>definitions.get(r)?.name));
    while(names.has(`trim${next}`))next++;
    definitions.set(row,{name:c.quantity?.startsWith('user.')?c.quantity.slice(5):`trim${next++}`,
      expression:c.expression??`sensor("${sensor}.displacement_body.y")`,unit:c.unit??'input L',residual_scale:String(c.residual_scale??1)});
  }
  function refresh(){
    const rows=[...document.querySelectorAll('.constraint-row')].filter(r=>r.querySelector('.constraint-quantity').value==='user');
    $('custom-trim-settings').hidden=!rows.length;$('custom-trim-equations').replaceChildren();
    for(const row of rows){
      if(!definitions.has(row))remember(row);
      const value=definitions.get(row),fieldset=document.createElement('fieldset');fieldset.className='custom-trim-equation';
      const legend=document.createElement('legend');legend.textContent=`Custom target · solve ${row.querySelector('.constraint-variable').value}`;fieldset.append(legend);
      for(const [key,title] of [['name','Equation name'],['expression','Expression'],['unit','Expression units'],['residual_scale','Residual scale']]){
        const label=document.createElement('label');label.textContent=title;
        const input=document.createElement(key==='expression'?'textarea':'input');input.dataset.custom=key;input.value=value[key];input.required=true;
        if(key==='expression'){input.rows=3;input.spellcheck=false;}
        else {input.type=key==='residual_scale'?'number':'text';if(key==='residual_scale')input.step='any';}
        input.setAttribute('aria-label',title);input.addEventListener('input',()=>{value[key]=input.value;changed();});label.append(input);fieldset.append(label);
      }
      const label=document.createElement('label');label.textContent='Use a sensor measurement';const select=document.createElement('select');select.setAttribute('aria-label','Use a sensor measurement');
      const placeholder=document.createElement('option');placeholder.textContent='Choose a field to replace the expression';placeholder.value='';select.append(placeholder);
      for(const sensor of model()?.sensors??[])for(const [field,title,unit,axes] of sensorFields){
        if(!sensorFieldAvailable(sensor,field))continue;
        for(const [i,axis] of (axes??[null]).entries()){
          const component=axis===null?'':'.'+(['force_local','moment_local','strain','curvature_change'].includes(field)?'csn':'xyz')[i];
          const option=document.createElement('option');option.value=`${sensor.index}.${field}${component}`;option.dataset.unit=unit;
          option.textContent=`Sensor ${sensor.index} · ${title}${axis===null?'':' '+axis}`;select.append(option);
        }
      }
      select.onchange=()=>{if(!select.value)return;value.expression=`sensor("${select.value}")`;value.unit=select.selectedOptions[0].dataset.unit;refresh();changed();};label.append(select);fieldset.append(label);
      $('custom-trim-equations').append(fieldset);
    }
  }
  function read(row){
    if(row.querySelector('.constraint-quantity').value!=='user')return {};
    const value=definitions.get(row);
    if(!value||Object.values(value).some(v=>!v.trim()))throw new Error('Fill each custom equation, unit and residual scale.');
    return {quantity:'user.'+value.name,expression:value.expression,unit:value.unit,residual_scale:Number(value.residual_scale)};
  }
  return {remember,refresh,read};
}

export function customReport(result){
  const report=result.custom_trim;if(!report)return '';
  const rows=result.operating_constraints?.filter(c=>c.expression)??[];
  const saved=rows.length?rows:result.equilibrium_state?.launch?.released_constraints?.filter(c=>c.expression)??[];
  return '\nCUSTOM TRIM EQUATIONS\n'+saved.map(c=>`${c.quantity}: ${c.expression} [${c.unit}]\n  target ${c.target}; residual scale ${c.residual_scale}`).join('\n')+
    `\nOne-sided tangent check: ${report.one_sided_tangent_ratio.toPrecision(5)} (must be ≤ 1)\n${report.scope}\n${report.limitations.join('\n')}\n`;
}
