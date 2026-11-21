const $=id=>document.getElementById(id);
export const physicalOutputSettings=`
<details class="advanced" id="rom-physical-settings"><summary>Beam loads, deformation and aerodynamic outputs</summary>
  <label class="field-label" for="rom-physical-field">Quantity</label><select id="rom-physical-field"></select>
  <div class="fields" id="rom-physical-location"><label>Beam<select id="rom-physical-beam"></select></label><label>Sample<select id="rom-physical-station"></select></label></div>
  <button id="rom-physical-add" disabled>Add output</button>
  <p class="small muted" id="rom-physical-note">Run a modal analysis to select physical outputs.</p>
  <ul id="rom-physical-selected"></ul>
  <p class="small muted">Each distributed output uses an exact sample on the solved mesh. Section resultants use local c/s/n axes; node and aerodynamic vectors use body axes. Spatial rotations and elastic incidence use radians. Unavailable quantities cannot be selected.</p>
</details>`;

const fieldId=f=>`${f.group}.${f.key}${f.component==null?'':'.'+f.component}`;
const label=item=>`${item.label??item.name}${item.selector?.group==='global'?'':item.selector?` · beam ${item.selector.beam} · t=${Number(item.selector.t).toPrecision(7)}`:''} [${item.unit}]`;
function option(select,value,text){const node=document.createElement('option');node.value=value;node.textContent=text;select.append(node);}

export function createPhysicalRomOutputs(onEdit){
  let catalog=null,fields=[],selected=[],beamNames=new Map();
  function renderSelected(){
    $('rom-physical-selected').replaceChildren();
    selected.forEach((item,i)=>{
      const li=document.createElement('li'),text=document.createElement('span'),button=document.createElement('button');
      text.textContent=label(item);button.textContent='Remove';button.type='button';button.setAttribute('aria-label','Remove '+label(item));
      button.onclick=()=>{selected.splice(i,1);renderSelected();onEdit();};li.append(text,' ',button);$('rom-physical-selected').append(li);
    });
  }
  const field=()=>fields.find(f=>fieldId(f)===$('rom-physical-field').value);
  function stations(){
    const f=field();$('rom-physical-station').replaceChildren();
    if(!f){$('rom-physical-add').disabled=true;return;}
    if(f.group==='global'){$('rom-physical-add').disabled=false;return;}
    const beam=Number($('rom-physical-beam').value);
    for(const row of catalog.stations[f.group].filter(r=>r.beam===beam&&r.available.includes(f.key)))
      option($('rom-physical-station'),row.index,`t = ${Number(row.t).toPrecision(7)} · sample ${row.index+1}`);
    $('rom-physical-add').disabled=!$('rom-physical-station').options.length;
  }
  function locations(){
    const f=field(),previous=$('rom-physical-beam').value;$('rom-physical-beam').replaceChildren();
    $('rom-physical-location').hidden=!f||f.group==='global';
    $('rom-physical-note').textContent=f?`${catalog.sampling[f.group]} Units: ${f.unit}.`:'Run a new modal analysis to select physical outputs.';
    if(f&&f.group!=='global'){
      const beams=[...new Set(catalog.stations[f.group].filter(r=>r.available.includes(f.key)).map(r=>r.beam))];
      beams.forEach(b=>option($('rom-physical-beam'),b,beamNames.get(b)??`Beam ${b}`));
      if(beams.some(b=>String(b)===previous))$('rom-physical-beam').value=previous;
    }
    stations();
  }
  function setBase(base){
    catalog=base?.rom_output_catalog??null;selected=[];fields=[];
    beamNames=new Map((base?.base.geometry??[]).map(b=>[b.index,`${b.name} (${b.index})`]));
    $('rom-physical-field').replaceChildren();
    if(catalog){
      const groupNames={nodes:'Node',sections:'Structure',strips:'Aerodynamics',global:'Global'};
      for(const f of catalog.fields){
        const enabled=f.group==='global'?catalog.global_available.includes(f.key):catalog.stations[f.group]?.some(r=>r.available.includes(f.key));
        if(!enabled)continue;
        for(const component of f.components.length?f.components.map((_,i)=>i):[null]){
          const row={...f,component,label:f.label+(component==null?'':' '+f.components[component])};fields.push(row);
          option($('rom-physical-field'),fieldId(row),`${groupNames[f.group]} · ${row.label}`);
        }
      }
    }
    if(fields.some(f=>fieldId(f)==='strips.f_aero'))$('rom-physical-field').value='strips.f_aero';
    renderSelected();locations();
  }
  $('rom-physical-field').onchange=locations;
  $('rom-physical-beam').onchange=stations;
  $('rom-physical-add').onclick=()=>{
    const f=field();if(!f)return;
    const selector={group:f.group,key:f.key};if(f.component!=null)selector.component=f.component;
    if(f.group!=='global'){
      const row=catalog.stations[f.group].find(r=>r.index===Number($('rom-physical-station').value));
      if(!row)return;Object.assign(selector,{index:row.index,beam:row.beam,t:row.t});
    }
    if(selected.some(item=>JSON.stringify(item.selector)===JSON.stringify(selector))){$('rom-physical-note').textContent='This output is already selected.';return;}
    selected.push({selector,label:f.label,unit:f.unit});renderSelected();onEdit();
  };
  return {setBase,specifications:()=>structuredClone(selected.map(item=>item.selector)),
    restore:outputs=>{selected=structuredClone((outputs??[]).filter(item=>item.selector));renderSelected();}};
}
