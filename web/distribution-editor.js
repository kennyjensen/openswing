import {colorBeamPlot} from './plot-colors.js';
import {createDistributionPointEditor} from './distribution-point-editor.js';
import {distributionSegments} from './distribution-spline.js';
export const distributionPane = `
<div id="pane-distributions" class="distribution-pane">
  <div class="distribution-tools">
    <label>Beam<select id="distribution-beam"></select></label>
    <label>Property<select id="distribution-name"></select></label>
    <label id="distribution-custom-field" hidden>Property name<input id="distribution-custom-name" spellcheck="false"></label>
    <button id="distribution-undo" disabled>Undo</button>
  </div>
  <p id="distribution-status" role="status"></p>
  <div class="distribution-layout">
    <div><div class="distribution-table-wrap"><table id="distribution-table"><thead><tr><th>Station t</th><th>Value</th><th>Points</th></tr></thead><tbody></tbody></table></div>
      <div class="distribution-tools"><label>Multiply values<input id="distribution-scale" type="number" step="any" value="1"></label><label>Add to values<input id="distribution-offset" type="number" step="any" value="0"></label></div>
      <div class="distribution-tools"><label>Property symmetry<select id="distribution-symmetry"><option value="keep">Keep current station convention</option><option value="independent">Make left and right independent</option><option value="positive">Mirror the positive half</option></select></label></div>
    </div>
    <div class="distribution-plot-panel">
      <div class="distribution-plot-tools"><button id="distribution-edit" type="button" aria-label="Edit points" title="Edit points" aria-pressed="false" aria-controls="distribution-plot"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><path d="m16 3 5 5-12 12-6 1 1-6Z M13 6l5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path></svg></button></div>
      <div id="distribution-plot" class="distribution-plot"></div><p id="distribution-plot-note" class="small muted"></p>
    </div>
  </div>
</div>`;

const $=id=>document.getElementById(id);
export function createDistributionEditor({context,rpc,commit,panels}) {
  let current=null, rows=[], busy=false, serial=0, draft=0, history=[], committing=null, loaded='', changed=false, editing=false, projection=null, pointEditor=null, plotted=null;
  const pane=$('pane-distributions');
  function message(text,error=false){$('distribution-status').textContent=text;$('distribution-status').classList.toggle('distribution-error',error);}
  function available(){const s=context();return current && s.model && !s.dirty && !s.busy && s.source===current.source;}
  function propertyName(){return $('distribution-name').value||$('distribution-custom-name').value.trim();}
  function selection(){return $('distribution-beam').value+':'+propertyName();}
  function refresh(){
    const disabled=busy||!available();
    for(const e of pane.querySelectorAll('button,input,select,textarea'))e.disabled=disabled;
    $('distribution-undo').disabled=disabled||!history.length;
    $('distribution-edit').disabled=disabled||loaded!==selection()||!projection;
    refreshPlotEditing();
    if(context().dirty)message('Apply ASW edits before editing properties.');
  }
  function invalidate(){
    changed=JSON.stringify(rows.map(r=>r.map(Number)))!==JSON.stringify(plotted?.points)
      ||rows.some(r=>r.some(v=>String(v).trim()===''))
      ||Number($('distribution-scale').value)!==1||Number($('distribution-offset').value)!==0||$('distribution-symmetry').value!=='keep';
    draft++;refresh();renderPoints();renderCurve();message('');
  }
  function canEdit(){return editing&&!busy&&available()&&loaded===selection();}
  function refreshPlotEditing(){
    const target=$('distribution-plot'),svg=target.querySelector('svg');
    const enabled=!!svg&&canEdit();
    // Put touch-action on the HTML hit-test ancestor too. Some mobile WebViews
    // ignore it on an SVG circle and otherwise turn captured drags into scrolls.
    target.classList.toggle('distribution-editing',enabled);
    if(!svg)return;
    svg.classList.toggle('distribution-editing',enabled);
    svg.setAttribute('role',enabled?'group':'img');
    for(const handle of svg.querySelectorAll('.distribution-point-handle')){
      handle.setAttribute('tabindex',enabled?'0':'-1');handle.setAttribute('aria-disabled',String(!enabled));
    }
    if(!enabled)pointEditor?.stop();
  }
  function renderPoints(){
    const svg=$('distribution-plot').querySelector('svg');if(!svg||!projection)return;
    const values=rows,ns='http://www.w3.org/2000/svg';
    let group=svg.querySelector('.distribution-points');
    if(!group){group=document.createElementNS(ns,'g');group.setAttribute('class','distribution-points');svg.append(group);}
    if(group.children.length!==values.length){
      group.replaceChildren();
      values.forEach((_,i)=>{
        const point=document.createElementNS(ns,'g');point.setAttribute('data-distribution-point',i);
        const dot=document.createElementNS(ns,'circle');dot.setAttribute('r',3.3);dot.setAttribute('class','distribution-point');
        const handle=document.createElementNS(ns,'circle');handle.setAttribute('r',5);handle.setAttribute('class','distribution-point-handle');handle.setAttribute('role','button');
        const title=document.createElementNS(ns,'title');handle.append(title);point.append(dot,handle);group.append(point);
      });
    }
    values.forEach((row,i)=>{
      const point=group.children[i],[t,value]=row.map(Number),valid=row.every(v=>String(v).trim()!==''&&Number.isFinite(Number(v)));
      point.setAttribute('visibility',valid?'visible':'hidden');if(!valid)return;
      point.setAttribute('transform',`translate(${projection.x(t)} ${projection.y(value)})`);
      const handle=point.querySelector('.distribution-point-handle'),label=`Station ${i+1}: t ${t}, value ${value}`;
      handle.setAttribute('aria-label',label);handle.querySelector('title').textContent=label;
    });
    refreshPlotEditing();
  }
  function renderCurve(){
    const group=$('distribution-plot').querySelector('.distribution-curves');if(!group||!plotted||!projection)return;
    const segments=changed?distributionSegments(rows,plotted,current.model.numerics?.beam_interpolation):plotted.segments;
    group.replaceChildren();
    for(const s of segments){
      const path=document.createElementNS('http://www.w3.org/2000/svg','path');
      path.setAttribute('class','distribution-curve');
      path.setAttribute('d',s.t.map((t,i)=>(i?'L':'M')+projection.x(t)+' '+projection.y(s.values[i])).join(' '));
      if(s.extrapolated)path.setAttribute('stroke-dasharray','5 3');
      group.append(path);
    }
  }
  function movePoint(index,point){
    rows[index]=point;
    const inputs=$('distribution-table').tBodies[0].rows[index].querySelectorAll('input');
    point.forEach((value,j)=>{inputs[j].value=value;});
    invalidate();
  }
  function renderRows(){
    const body=$('distribution-table').tBodies[0];body.replaceChildren();
    rows.forEach((row,i)=>{
      const tr=document.createElement('tr');
      row.forEach((value,j)=>{
        const td=document.createElement('td'),input=document.createElement('input');input.type='number';input.step='any';input.value=value;input.setAttribute('aria-label',`${j?'Value':'Station'} ${i+1}`);
        input.oninput=()=>{rows[i][j]=input.value;invalidate();};input.onchange=()=>save();td.append(input);tr.append(td);
      });
      const td=document.createElement('td');
      for(const [label,title,action,deleteStation=null] of [
        ['+',`Insert after station ${i+1}`,()=>{
          // A doubled station holds the two sides of a corner. Insert beyond
          // that pair; a third copy has no valid interpolation segment.
          let after=i;
          while(after+1<rows.length&&Number(rows[after+1][0])===Number(row[0]))after++;
          const left=rows[after],next=rows[after+1];
          rows.splice(after+1,0,next?left.map((v,j)=>(Number(v)+Number(next[j]))/2):[Number(left[0])+1,Number(left[1])]);
        }],
        ['',`Delete station ${i+1}`,()=>rows.splice(i,1),i],
      ]){
        const b=document.createElement('button');b.textContent=label;b.type='button';b.title=title;b.setAttribute('aria-label',title);
        if(!label){
          const ns='http://www.w3.org/2000/svg',icon=document.createElementNS(ns,'svg'),path=document.createElementNS(ns,'path');
          icon.setAttribute('viewBox','0 0 24 24');icon.setAttribute('aria-hidden','true');icon.setAttribute('focusable','false');
          path.setAttribute('d','M3 6h18 M9 6V3h6v3 M5 6l1 15h12l1-15 M10 10v7 M14 10v7');
          path.setAttribute('fill','none');path.setAttribute('stroke','currentColor');path.setAttribute('stroke-width','1.8');path.setAttribute('stroke-linecap','round');path.setAttribute('stroke-linejoin','round');
          icon.append(path);b.append(icon);
        }
        b.onclick=()=>{
          if(!available()||busy||loaded!==selection())return;
          const previous=rows.map(r=>[...r]);
          action();invalidate();renderRows();return save(deleteStation,previous);
        };td.append(b);
      }
      tr.append(td);body.append(tr);
    });renderPoints();refresh();
  }
  function plot(report,label){
    pointEditor?.destroy();pointEditor=null;plotted=report;
    const target=$('distribution-plot');target.replaceChildren();target.classList.remove('distribution-editing');projection=null;
    if(!report){$('distribution-plot-note').textContent=label;return;}
    const constantRigid=report.constant_rigid===true;
    colorBeamPlot(target,current.model.beams,$('distribution-beam').value);
    const all=report.segments.flatMap(s=>s.values).concat(report.points.map(p=>p[1]));
    const xs=report.points.map(p=>p[0]),xmin=Math.min(report.domain[0],...xs),xmax=Math.max(report.domain[1],...xs);
    let ymin=Math.min(...all),ymax=Math.max(...all);const pad=(ymax-ymin||Math.max(1,Math.abs(ymin)))*.08;ymin-=pad;ymax+=pad;
    const x=v=>50+(v-xmin)/(xmax-xmin||1)*490,y=v=>204-(v-ymin)/(ymax-ymin)*180;
    projection={x,y,xmin,xmax,ymin,ymax,station:px=>xmin+(px-50)*(xmax-xmin)/490,value:py=>ymin+(204-py)*(ymax-ymin)/180};
    const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 560 240');svg.setAttribute('role','img');svg.setAttribute('aria-label',constantRigid?`${label}: ${report.name} rigid throughout the beam; raw zero denotes infinite stiffness`:`${label}: ${report.name} spline against station t`);
    const add=(tag,attrs,content)=>{const e=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);if(content!==undefined)e.textContent=content;svg.append(e);return e;};
    add('path',{d:'M50 24 V204 H540',class:'distribution-axis'});
    const fmt=n=>Math.abs(n)>=1e5||(n!==0&&Math.abs(n)<1e-3)?n.toExponential(1):Number(n.toPrecision(4)).toString();
    for(let i=0;i<=4;i++){const t=xmin+(xmax-xmin)*i/4;add('text',{x:x(t),y:222,'text-anchor':'middle'},fmt(t));}
    for(const v of [ymin,(ymin+ymax)/2,ymax])add('text',{x:46,y:y(v)+4,'text-anchor':'end'},fmt(v));
    add('text',{x:295,y:239,'text-anchor':'middle'},'station t');add('text',{x:50,y:14},report.name+' · input units');
    add('g',{class:'distribution-curves'});
    target.append(svg);
    pointEditor=createDistributionPointEditor(svg,{points:()=>rows,projection,enabled:canEdit,
      mirrored:()=>plotted.mirrored,change:movePoint,complete:()=>save()});
    renderPoints();renderCurve();
    $('distribution-plot-note').textContent=constantRigid?'Rigid (zero denotes infinite stiffness)':`${report.mirrored?'Mirrored at t = 0':'Full station grid'}${report.segments.some(s=>s.extrapolated)?' · Dashed: extrapolated':''}`;
  }
  async function load(){
    if(!available()||busy)return;
    const token=++serial,source=current.source,beam=Number($('distribution-beam').value),name=propertyName(),meta=current.model.distributions.find(b=>b.beam===beam);
    loaded='';draft++;$('distribution-scale').value='1';$('distribution-offset').value='0';
    $('distribution-symmetry').value='keep';editing=false;$('distribution-edit').setAttribute('aria-pressed','false');
    busy=true;refresh();
    try{
      // The kernel canonicalizes property names and supplies all default values.
      if(meta.properties.includes(name)){
        const report=await rpc({action:'distribution',source,beam,name});
        if(token!==serial||source!==context().source||context().dirty)return;
        rows=report.points.map(row=>[...row]);changed=false;plot(report,'Loaded model');message('');
      }else{
        const defaults=current.model.distribution_defaults;
        if(!(name in defaults)&&name!=='chord'&&!/^dC[LMD]dF[1-9]\d*$/.test(name))throw new Error('Choose a documented property or an indexed flap derivative, such as dCLdF2.');
        const [lo,hi]=meta.domain,start=meta.lifting&&lo===-hi?0:lo;
        const value=defaults[name]??0;
        rows=[[start,name==='chord'?'':value],[hi,name==='chord'?'':value]];plot(null,'');
        message(name==='chord'?'Enter positive chord values. Adding chord makes this beam a lifting surface.':'New property initialized from its omitted-value default.');
      }
      loaded=selection();changed=false;renderRows();
    }catch(error){if(token===serial)message(error.message,true);}
    finally{if(token===serial){busy=false;refresh();}}
  }
  async function save(deleteStation=null,previousRows=null){
    if(!available()||busy||loaded!==selection()||!changed)return;
    const s=context(),token=++serial,version=draft,source=s.source,revision=s.revision;
    const valid=()=>token===serial&&version===draft&&source===context().source&&revision===context().revision&&available();
    busy=true;refresh();message('Updating…');
    try{
      const finite=v=>{if(String(v).trim()===''||!Number.isFinite(Number(v)))throw new Error('Enter finite numbers for every station, value, scale, and offset.');return Number(v);};
      const edit={points:rows.map(r=>r.map(finite)),multiplier:finite($('distribution-scale').value),adder:finite($('distribution-offset').value),symmetry:$('distribution-symmetry').value};
      if(deleteStation!==null)edit.delete_station=deleteStation;
      const result=await rpc({action:'edit_distribution',source,beam:Number($('distribution-beam').value),name:propertyName(),edit});
      if(!valid()){if(token===serial)message('Settings changed; edit not applied.',true);return;}
      const model=await rpc({action:'inspect',source:result.source,panels:panels()});
      if(!valid()){if(token===serial)message('Settings changed; edit not applied.',true);return;}
      await accept({source:result.source,model,report:result.distribution});
    }catch(error){if(token===serial){
      // A failed row operation must not leave a new grid masquerading as the
      // saved one, or shift the source indices used by the next trash click.
      if(previousRows&&valid()){rows=previousRows;invalidate();renderRows();}
      message('Edit not applied: '+error.message.split('\n').filter(Boolean).at(-1),true);
    }}
    finally{if(token===serial){busy=false;refresh();}}
  }
  async function undo(){
    if(!available()||busy)return;
    const target=history.at(-1);if(!target)return;
    const revision=context().revision,token=++serial;busy=true;refresh();message('Restoring…');
    try{
      const model=await rpc({action:'inspect',source:target.source,panels:panels()});
      if(token!==serial||revision!==context().revision||!available())return;
      await accept({source:target.source,model},true);
    }catch(error){if(token===serial)message(error.message,true);}
    finally{if(token===serial){busy=false;refresh();}}
  }
  async function accept(target,undo=false){
    const previous=current;
    committing={...target,selection:selection(),editing,focus:document.activeElement?.closest?.('[data-distribution-point]')?.getAttribute('data-distribution-point')};
    try{
      await commit(target.source,target.model);
      if(current.source===target.source&&!context().dirty){
        if(undo)history.pop();else history.push(previous);
        message('ASW updated.');
      }
    }finally{committing=null;refresh();}
  }
  function setModel(model,source){
    const own=source===committing?.source?committing:null;
    ++serial;busy=false;changed=false;
    if(source!==current?.source&&!own)history=[];
    current={model,source};
    const selected=$('distribution-beam').value;$('distribution-beam').replaceChildren();
    for(const b of model.distributions){const option=document.createElement('option');option.value=b.beam;option.textContent=`${b.beam}: ${b.name}`;$('distribution-beam').append(option);}
    if(model.distributions.some(b=>String(b.beam)===selected))$('distribution-beam').value=selected;
    catalog(!!own);
    if(own?.report&&own.selection===selection()){
      rows=own.report.points.map(row=>[...row]);loaded=selection();editing=own.editing;
      $('distribution-scale').value='1';$('distribution-offset').value='0';$('distribution-symmetry').value='keep';
      $('distribution-edit').setAttribute('aria-pressed',String(editing));
      plot(own.report,'Model');renderRows();
      if(own.focus!=null)$('distribution-plot').querySelectorAll('.distribution-point-handle')[Number(own.focus)]?.focus({preventScroll:true});
    }else load();
    refresh();
  }
  function catalog(keep=false){
    const meta=current.model.distributions.find(b=>b.beam===Number($('distribution-beam').value));
    const select=$('distribution-name'),previous=propertyName();
    const selected=keep||meta.properties.includes(previous)?previous:meta.properties.includes('chord')?'chord':meta.properties[0];
    const other=[...new Set([...current.model.distributions.flatMap(b=>b.properties),...Object.keys(current.model.distribution_defaults),'chord','dCLdF1','dCMdF1','dCDdF1'])].filter(name=>!meta.properties.includes(name));
    const option=name=>{const o=document.createElement('option');o.value=name;o.textContent=name;return o;};
    select.replaceChildren();
    for(const [label,names] of [['Defined in file',meta.properties],['Other properties',other]]){
      if(!names.length)continue;
      const group=document.createElement('optgroup');group.label=label;group.append(...names.map(option));select.append(group);
    }
    const custom=option('');custom.textContent='Other…';select.append(custom);
    select.value=[...meta.properties,...other].includes(selected)?selected:'';
    $('distribution-custom-name').value=select.value?'':selected??'';
    $('distribution-custom-field').hidden=!!select.value;
  }
  $('distribution-beam').onchange=()=>{catalog();load();};
  $('distribution-name').onchange=()=>{
    $('distribution-custom-field').hidden=!!$('distribution-name').value;
    if($('distribution-name').value)return load();
    $('distribution-custom-name').value='';refresh();message('');$('distribution-custom-name').focus();
  };
  $('distribution-custom-name').oninput=()=>{refresh();};
  const loadCustom=()=>{if(propertyName()&&loaded!==selection())return load();};
  $('distribution-custom-name').onchange=loadCustom;
  $('distribution-custom-name').onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();return loadCustom();}};
  for(const id of ['distribution-scale','distribution-offset']){$(id).oninput=invalidate;$(id).onchange=()=>save();}
  $('distribution-symmetry').onchange=()=>{invalidate();return save();};
  $('distribution-edit').onclick=()=>{
    if($('distribution-edit').disabled)return;
    editing=!editing;$('distribution-edit').setAttribute('aria-pressed',String(editing));refreshPlotEditing();
  };
  $('distribution-undo').onclick=undo;
  refresh();return {setModel,refresh,hasDraft:()=>changed||busy};
}
