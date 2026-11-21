export const allocationSettings=`<div id="allocation-settings" hidden>
  <p class="small muted">Weighted control trim minimizes ½ Σ weight × (setting − preferred)² over every solved flap and engine. Force, moment and other physical targets remain exact equations. Add “Least-squares control effort” slots for redundant actuators. Settings use the file’s control units; weights do not impose actuator limits.</p>
  <div id="allocation-controls"></div>
</div>`;

export function createControlAllocation(changed){
  const costs=new Map(),$=id=>document.getElementById(id);
  const active=()=>[...document.querySelectorAll('.constraint-quantity')].some(e=>e.value==='minimum_control');
  const isControl=name=>name.startsWith('control.')||name.startsWith('power.');
  function remember(c){if(isControl(c.variable)&&(c.weight!==undefined||c.preferred!==undefined))costs.set(c.variable,{weight:String(c.weight??1),preferred:String(c.preferred??0)});}
  function refresh(preserve=true){
    if(!preserve)costs.clear();
    const enabled=active();$('allocation-settings').hidden=!enabled;$('allocation-controls').replaceChildren();
    if(!enabled)return;
    const selected=[...new Set([...document.querySelectorAll('.constraint-variable')].map(e=>e.value).filter(isControl))];
    for(const variable of selected){
      const settings=costs.get(variable)??{weight:'1',preferred:'0'};costs.set(variable,settings);
      const fieldset=document.createElement('fieldset');fieldset.className='allocation-control';fieldset.dataset.variable=variable;
      const legend=document.createElement('legend');legend.textContent=variable.replace('control.','Flap ').replace('power.','Engine ');fieldset.append(legend);
      const fields=document.createElement('div');fields.className='fields';
      for(const [key,title] of [['weight','Weight'],['preferred','Preferred setting']]){
        const label=document.createElement('label');label.textContent=title;
        const input=document.createElement('input');input.type='number';input.step='any';input.required=true;input.value=settings[key];input.dataset.cost=key;
        input.setAttribute('aria-label',`${legend.textContent} ${title.toLowerCase()}`);
        input.addEventListener('input',()=>{settings[key]=input.value;changed();});label.append(input);fields.append(label);
      }
      fieldset.append(fields);$('allocation-controls').append(fieldset);
    }
  }
  function read(variable){
    if(!active()||!isControl(variable))return {};
    const settings=costs.get(variable)??{weight:1,preferred:0};
    if(settings.weight===''||settings.preferred==='')throw new Error('Enter each control weight and preferred setting.');
    return {weight:Number(settings.weight),preferred:Number(settings.preferred)};
  }
  return {remember,refresh,read};
}

export function allocationReport(report){
  if(!report)return '';
  return `\nWEIGHTED CONTROL TRIM\nObjective ½ Σ w (setting − preferred)²: ${report.objective.toPrecision(9)}\nFree control directions: ${report.free_directions}\nPhysical equation residual: ${report.equality_residual.toExponential(4)}\nNormalized stationarity: ${report.normalized_stationarity.toExponential(4)}\nFeasible curvatures: ${report.reduced_curvatures.map(x=>x.toPrecision(6)).join(', ')}\n${report.controls.map(c=>`${c.variable}: ${c.actual.toPrecision(8)}; weight ${c.weight}; preferred ${c.preferred}`).join('\n')}\n${report.scope}\n${report.limitations.join('\n')}\n`;
}
