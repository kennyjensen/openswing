export const nodePane=`<div id="pane-nodes" class="distribution-pane">
  <div class="distribution-tools">
    <label>Beam<select id="node-beam"></select></label>
    <label>Distribution<select id="node-spacing"><option value="default">Default cosine count</option><option value="cosine">Cosine in arc length</option><option value="modified-cosine">Modified cosine in arc length</option><option value="uniform">Uniform in arc length</option><option value="uniform-breaks">Uniform between required stations</option><option value="custom">Explicit stations</option></select></label>
    <label id="node-count-label">Intervals<input id="node-count" type="number" min="4" max="1024" step="1" value="24"></label>
  </div>
  <div id="node-minimum-spacing" hidden>
    <div class="distribution-tools">
      <label>Minimum horseshoe spacing · L<input id="node-min-spacing" type="number" min="0" step="any" value="0" title="Distance along the beam in model length units. Zero disables the minimum."></label>
    </div>
  </div>
  <div id="node-custom" hidden><label class="field-label" for="node-stations">Node stations t, including both endpoints</label><textarea id="node-stations" rows="4" spellcheck="false"></textarea></div>
  <p id="node-status" role="status" class="small" hidden></p>
  <div id="node-plot" class="distribution-plot"></div>
  <div class="distribution-table-wrap"><table id="node-table"><thead><tr><th>Station t</th><th>s/L</th><th>θ / π</th><th>Required by</th></tr></thead><tbody></tbody></table></div>
</div>`;

const $=id=>document.getElementById(id);
export function createNodeEditor({context,rpc,commit,showError}){
  let defaultCount=48, overrides={}, model=null, busy=false, serial=0, changed=false;
  const pane=$('pane-nodes');
  function settings(){return Object.keys(overrides).length?{default:defaultCount,beams:structuredClone(overrides)}:defaultCount;}
  function clear(){overrides={};model=null;changed=false;++serial;}
  function refresh(){for(const e of pane.querySelectorAll('input,select,button,textarea'))e.disabled=busy||context().busy||context().dirty||!model;}
  function beam(){return model?.mesh_discretization.beams.find(b=>String(b.beam)===$('node-beam').value);}
  function message(value,error=false){const status=$('node-status');status.textContent=value;status.hidden=!value;status.classList.toggle('distribution-error',error);}
  function draft(){changed=true;message('');}
  function controls(){const mode=$('node-spacing').value;$('node-count-label').hidden=['default','custom'].includes(mode);$('node-minimum-spacing').hidden=['default','custom'].includes(mode);$('node-custom').hidden=mode!=='custom';}
  function load(){const b=beam();if(!b)return;changed=false;const spec=overrides[b.beam];$('node-spacing').value=!spec?'default':spec.nodes?'custom':spec.spacing;
    $('node-count').value=spec?.count??defaultCount;$('node-stations').value=(spec?.nodes??b.nodes.map(n=>n.t)).join('\n');
    $('node-min-spacing').value=spec?.min_spacing??0;controls();plot();
    message('');refresh();}
  function plot(){
    const b=beam();if(!b)return;
    const target=$('node-plot');target.replaceChildren();
    const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 560 205');svg.setAttribute('role','img');
    function add(tag,attrs,text){const e=document.createElementNS(ns,tag);for(const [key,v] of Object.entries(attrs))e.setAttribute(key,v);if(text!==undefined)e.textContent=text;svg.append(e);return e;}
    const x=f=>40+480*f;
    const requested=Number(document.querySelector(`[data-circulation-beam="${b.beam}"]`)?.value??0);
    const valid=Number.isInteger(requested)&&requested>=0&&requested<=512,k=valid?requested:0;
    svg.setAttribute('aria-label',`${b.name}: applied nodes${k>0?' and Fourier basis':''} in material coordinates`);
    const nodeY=k>0?145:105;
    add('path',{d:k>0?'M40 65 H520 M40 145 H520':'M40 105 H520',class:'distribution-axis'});
    if(k>0){for(const [mode,dash] of [[1,false],...(k===1?[]:[[k,true]])]){
      const length=Math.max(301,24*k);const points=Array.from({length},(_,i)=>{const f=i/(length-1),theta=Math.acos(2*f-1);return `${i?'L':'M'}${x(f)} ${65-40*Math.sin(mode*theta)}`;});
      add('path',{d:points.join(' '),class:'distribution-curve',...(dash?{'stroke-dasharray':'4 3'}:{})});
    }}
    if(!valid||k>0)add('text',{x:40,y:15},!valid?'Fourier count must be an integer from 0 to 512':`Fourier sin(θ)${k>1?` · dashed sin(${k}θ)`:''}`);
    for(const n of b.nodes){const c=add('circle',{cx:x(n.fraction),cy:nodeY,r:n.required.length?4:2.8,fill:n.required.length?'#e6b477':'#19ae94'});const title=document.createElementNS(ns,'title');title.textContent=`t ${n.t}; s/L ${n.fraction}; ${n.required.join(', ')||'mesh node'}`;c.append(title);}
    for(let i=0;i<=4;i++)add('text',{x:x(i/4),y:nodeY+29,'text-anchor':'middle'},String(i/4));
    add('text',{x:280,y:nodeY+52,'text-anchor':'middle'},'s/L');target.append(svg);
    const body=$('node-table').tBodies[0];body.replaceChildren();for(const n of b.nodes){const row=document.createElement('tr');for(const v of [n.t.toPrecision(8),n.fraction.toFixed(6),(n.theta/Math.PI).toFixed(6),n.required.join(', ')||'—']){const td=document.createElement('td');td.textContent=v;row.append(td);}body.append(row);}
  }
  async function apply(candidate){
    const s=context();if(busy||s.busy||s.dirty||!model)return;
    const source=s.source,revision=s.revision,token=++serial;busy=true;refresh();message('Updating…');
    try{const prepared=await rpc({action:'inspect',source,panels:candidate});
      if(token!==serial||source!==context().source||revision!==context().revision){if(token===serial)message('Settings changed; mesh not applied.',true);return;}
      const normalized=prepared.mesh_discretization.settings;overrides=typeof normalized==='number'?{}:normalized.beams;defaultCount=typeof normalized==='number'?normalized:normalized.default;
      await commit(source,prepared);
    }catch(error){if(token===serial){message('Mesh not applied: '+error.message.split('\n').filter(Boolean).at(-1),true);showError(error);}}
    finally{busy=false;refresh();}
  }
  function setModel(next){model=next;const selected=$('node-beam').value;$('node-beam').replaceChildren();for(const b of model.beams){const o=document.createElement('option');o.value=b.index;o.textContent=`${b.index}: ${b.name}`;$('node-beam').append(o);}if(model.beams.some(b=>String(b.index)===selected))$('node-beam').value=selected;load();}
  function save(){
    if(!changed||busy||context().busy||context().dirty||!model)return;
    const mode=$('node-spacing').value,beams=structuredClone(overrides),key=$('node-beam').value;
    if(mode==='default')delete beams[key];else beams[key]=mode==='custom'?{nodes:$('node-stations').value.trim().split(/[\s,]+/).map(Number)}:{count:Number($('node-count').value),spacing:mode};
    if(!['default','custom'].includes(mode)){
      const minimum=Number($('node-min-spacing').value);
      if(!$('node-min-spacing').value.trim()||!Number.isFinite(minimum)||minimum<0){message('Enter a nonnegative minimum spacing.',true);return;}
      if(minimum>0)beams[key].min_spacing=minimum;
    }
    return apply({default:defaultCount,beams});
  }
  $('node-beam').onchange=load;
  $('node-spacing').onchange=()=>{controls();draft();return save();};
  for(const id of ['node-count','node-stations','node-min-spacing']){$(id).oninput=draft;$(id).onchange=save;}
  return {settings,clear,setModel,refresh,plot,hasDraft:()=>changed||busy,
    restore(spec){++serial;changed=false;overrides=typeof spec==='number'?{}:structuredClone(spec.beams);defaultCount=typeof spec==='number'?spec:spec.default;}};
}
