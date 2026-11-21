import {canonicalTrace,traceKey,traceInfo,frequencySeries,comparisonCSV,displayResponseUnit} from './frequency-data.js';
import {overlayPane,createFrequencyOverlays} from './frequency-overlays.js';
import {OVERLAY_LIMITS} from './frequency-overlay-data.js';
import {plotColors as colors} from './plot-colors.js';
import {plotAxis} from './frequency-axes.js';
const $=id=>document.getElementById(id);
const esc=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&apos;');
const fmt=value=>Number.isFinite(value)?value.toPrecision(5):'—';
const style=index=>({color:colors[index%colors.length],dash:['','7 3','2 3','9 3 2 3'][Math.floor(index/colors.length)%4]});
const wrap=(text,length=100)=>String(text).match(new RegExp(`.{1,${length}}(?:\\s|$)|.{1,${length}}`,'gu'))??[''];

export const comparisonPane=`
<details id="frequency-comparison" class="advanced"><summary>Compare inputs, outputs and stations</summary>
  <div class="time-toolbar"><button id="frequency-compare-current" disabled>Add current response</button><button id="frequency-compare-stations" disabled>Add all stations</button><button id="frequency-compare-clear" disabled>Clear comparison</button><button id="frequency-compare-csv" disabled>Comparison CSV</button></div>
  <div class="time-toolbar"><label>First input<select id="frequency-compare-first"></select></label><label>Last input<select id="frequency-compare-last"></select></label><button id="frequency-compare-range" disabled>Add input range</button></div>
  <p class="small muted">Add outputs with the selectors above, or compare a range of independently forced gust modes. Curves are grouped by response units and spectrum type. They are not summed. Phase unwraps independently and restarts after gaps or zero responses. Click a point to inspect its input and frequency. Charts scroll horizontally on narrow screens.</p>
  ${overlayPane}
  <p id="frequency-compare-status" class="small muted" role="status">Run a frequency analysis to compare responses.</p>
  <div id="frequency-compare-traces"></div><div id="frequency-compare-plots"></div>
</details>`;

export function comparisonGroups(result,selections,unwrap=true){
  const groups=new Map();
  selections.forEach((s,index)=>{
    if(s.visible===false)return;
    const info=traceInfo(result,s),trace={...info,data:frequencySeries(result,info.selection,unwrap),index,...style(index)};
    if(s.overlay)trace.dash='5 4';
    if(!groups.has(info.groupKey))groups.set(info.groupKey,{kind:info.kind,unit:info.unit,unwrap,traces:[]});
    groups.get(info.groupKey).traces.push(trace);
  });
  return [...groups.values()];
}

// Standalone SVG includes physical units, every legend label and real sample
// markers. Unit conversion is display-only; selection and CSV retain raw values.
// Missing/zero phase, nonpositive log gain and logarithmic DC break the paths.
export function comparisonFigure(group,{log=false,db=false,gainLog=true,frequencyUnits='radians',angleUnits='radians',selected=null}={}){
  const display=displayResponseUnit(group.unit,angleUnits),logGain=!db&&gainLog;
  const frequency=w=>frequencyUnits==='cycles'?w/(2*Math.PI):w;
  const frequencyLabel=frequencyUnits==='cycles'?'f [cycles/input T]':'ω [rad/input T]';
  const gain=v=>db?(Number.isFinite(v.db)?v.db+20*Math.log10(display.scale):null)
    :(Number.isFinite(v.magnitude)?v.magnitude*display.scale:null);
  const labels=group.traces.map(t=>wrap(`${t.index+1}. ${t.label}`,104));
  const unitLines=wrap(`[${display.unit}]${db?' · dB reference = one displayed response unit':''}`,105),headerExtra=Math.max(0,unitLines.length-2)*16;
  const legendHeight=labels.reduce((n,lines)=>n+lines.length*17+7,0),height=535+headerExtra+legendHeight;
  let svg=`<svg xmlns="http://www.w3.org/2000/svg" class="frequency-comparison-svg" fill="#bed2c8" font-family="monospace" font-size="12" viewBox="0 0 900 ${height}" role="img" aria-label="${esc(group.kind+' ['+display.unit+']')}"><rect width="900" height="${height}" fill="#142022"/><style>.frequency-comparison-svg text{font:12px monospace;fill:#bed2c8}.frequency-comparison-svg .grid{stroke:#354941;stroke-width:1}.frequency-comparison-svg .grid-minor{stroke:#293a35;stroke-width:.6}.frequency-comparison-svg .curve{fill:none;stroke-width:2;stroke-linejoin:round}.frequency-comparison-svg circle{cursor:pointer}.frequency-comparison-svg circle:focus{stroke:white;stroke-width:3;outline:none}</style>`;
  svg+=`<text x="85" y="22">${esc(group.kind)}</text>`;
  unitLines.forEach((line,i)=>svg+=`<text x="85" y="${40+i*16}">${esc(line)}</text>`);
  const xAxis=plotAxis(group.traces.flatMap(t=>t.data.map(v=>frequency(v.omega))),{scale:log?'log':'linear'});
  const X=w=>85+xAxis.position(frequency(w))*750;
  for(const [plot,field,title] of [[0,db?'db':'magnitude',db?'Gain [dB]':`Magnitude${logGain?' · logarithmic':''}`],[1,'phase',`Phase [deg] · ${group.unwrap===false?'wrapped ±180°':'unwrapped per trace'}`]]){
    const top=75+headerExtra+plot*210,logY=plot===0&&logGain;
    const value=v=>plot===0?gain(v):v.phase;
    const valid=v=>Number.isFinite(value(v))&&(!logY||value(v)>0)&&Number.isFinite(X(v.omega));
    const points=group.traces.flatMap(t=>t.data).filter(valid);
    svg+=`<g data-plot="${field}" data-axis-scale="${logY?'log':'linear'}">`;
    svg+=`<text x="85" y="${top-9}">${title}</text>`;
    if(!points.length){svg+=`<text x="85" y="${top+60}">No finite ${logY?'positive ':''}${title.toLowerCase()} samples on this axis.</text></g>`;continue;}
    const yAxis=plotAxis(points.map(value),{scale:logY?'log':'linear'}),Y=v=>top+140-yAxis.position(v)*140;
    for(const tick of xAxis.ticks){
      const x=85+tick.position*750;
      svg+=`<path d="M${x} ${top}V${top+140}" class="grid grid-${tick.major?'major':'minor'}" data-axis="x" data-tick-value="${tick.value}" fill="none"/>`;
      if(tick.label)svg+=`<text x="${x}" y="${top+163}" text-anchor="middle">${esc(tick.label)}</text>`;
    }
    for(const tick of yAxis.ticks){
      const y=top+140-tick.position*140;
      svg+=`<path d="M85 ${y}H835" class="grid grid-${tick.major?'major':'minor'}" data-axis="y" data-tick-value="${tick.value}" fill="none"/>`;
      if(tick.label)svg+=`<text x="76" y="${y+4}" text-anchor="end">${esc(tick.label)}</text>`;
    }
    for(const t of group.traces){
      let path='',connected=false,markers='';
      for(const v of t.data){
        if(!valid(v)){connected=false;continue;}
        path+=`${connected?'L':'M'}${X(v.omega)} ${Y(value(v))} `;connected=true;
        const active=selected&&traceKey(t.selection)===traceKey(selected)&&v.index===selected.sample;
        const label=`${t.label}; ω=${fmt(v.omega)} rad/input T; ${title}=${fmt(value(v))}`;
        markers+=`<circle data-trace="${t.index}" data-frequency="${v.index}" cx="${X(v.omega)}" cy="${Y(value(v))}" r="${active?5:3}" fill="${t.color}" stroke="${active?'white':t.color}" tabindex="0" role="button" aria-label="${esc(label)}"><title>${esc(label)}</title></circle>`;
      }
      svg+=`<path d="${path}" class="curve" fill="none" stroke-width="2" stroke-linejoin="round" stroke="${t.color}" stroke-dasharray="${t.dash}" pointer-events="none"/>${markers}`;
    }
    svg+=`<text x="460" y="${top+183}" text-anchor="middle">${frequencyLabel}${log?' · logarithmic':''}</text></g>`;
  }
  let y=490+headerExtra;
  group.traces.forEach((t,i)=>{svg+=`<path d="M85 ${y-4}H113" stroke="${t.color}" stroke-width="3" stroke-dasharray="${t.dash}"/>`;for(const line of labels[i]){svg+=`<text x="122" y="${y}">${esc(line)}</text>`;y+=17;}y+=7;});
  svg+=`<text x="85" y="${y+12}">Lines connect samples; external curves are dashed; gaps are retained.${log?' Zero frequency is omitted on this log axis.':''}</text>`;
  if(logGain)svg+=`<text x="85" y="${y+29}">Zero magnitudes are gaps on the logarithmic gain axis; CSV retains the original values.</text>`;
  return svg+'</svg>';
}

export function createFrequencyComparison(context,activate,download){
  let result=null,traces=[],nextOverlay=1;
  const overlays=createFrequencyOverlays(context,()=>result,trace=>{
    if(traces.filter(t=>t.overlay).length>=OVERLAY_LIMITS.traces)throw new Error('Remove an overlay before adding more than 64 external curves.');
    traces.push({...structuredClone(trace),id:nextOverlay++,visible:true});render();
  });
  function choices(){
    for(const id of ['frequency-compare-first','frequency-compare-last']){
      const previous=$(id).value;$(id).replaceChildren();
      result?.inputs.forEach((c,i)=>{const option=document.createElement('option');option.value=i;option.textContent=`${i+1}. ${c.name} [${c.unit}]`;$(id).append(option);});
      if([...$(id).options].some(o=>o.value===previous))$(id).value=previous;
      else if(id.endsWith('last'))$(id).selectedIndex=$(id).options.length-1;
    }
  }
  function render(){
    const current=context(),visible=traces.filter(t=>t.visible!==false);
    overlays.refresh();
    for(const id of ['frequency-compare-current','frequency-compare-range'])$(id).disabled=!result||!current?.key&&current?.display!=='broken_loop';
    $('frequency-compare-stations').disabled=!result||current?.station==null||current.display==='broken_loop';
    $('frequency-compare-clear').disabled=!traces.length;$('frequency-compare-csv').disabled=!visible.length;
    for(const id of ['frequency-compare-first','frequency-compare-last'])$(id).disabled=!result;
    $('frequency-compare-status').textContent=!result?'Run a frequency analysis to compare responses.':`${visible.length} visible of ${traces.length} comparison traces. CSV contains every frequency, including gaps and zero.`+(current.log&&result?.samples.some(s=>s.omega===0)?' Zero frequency is omitted from log plots; choose a linear axis to display it.':'');
    $('frequency-compare-traces').replaceChildren();$('frequency-compare-plots').replaceChildren();if(!result)return;
    traces.forEach((t,i)=>{
      const row=document.createElement('div');row.className='frequency-trace';
      const label=document.createElement('label'),check=document.createElement('input'),text=document.createElement('span'),remove=document.createElement('button'),info=traceInfo(result,t);
      check.type='checkbox';check.checked=t.visible!==false;check.onchange=()=>{t.visible=check.checked;render();};
      text.textContent=`${i+1}. ${info.label} [${info.unit}]`;text.style.borderLeftColor=style(i).color;label.append(check,text);
      remove.textContent='Remove';remove.setAttribute('aria-label',`Remove ${info.label}`);remove.onclick=()=>{traces.splice(i,1);render();};row.append(label,remove);$('frequency-compare-traces').append(row);
    });
    comparisonGroups(result,traces,current.unwrap).forEach((group,i)=>{
      const section=document.createElement('section');section.className='frequency-comparison-group';
      const heading=document.createElement('h3');heading.textContent=`${group.kind} [${displayResponseUnit(group.unit,current.angleUnits).unit}]`;
      const chart=document.createElement('div');chart.className='frequency-comparison-chart';
      const svg=comparisonFigure(group,{log:current.log,db:current.db,gainLog:current.logMagnitude,
        frequencyUnits:current.frequencyUnits,angleUnits:current.angleUnits,selected:current});chart.innerHTML=svg;
      for(const point of chart.querySelectorAll('[data-trace]')){
        const select=()=>{const trace=traces[Number(point.dataset.trace)],sample=Number(point.dataset.frequency);if(trace.overlay)overlays.inspect(trace,sample);else activate(trace,sample);};
        point.onclick=select;point.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select();}};
      }
      const save=document.createElement('button');save.textContent='Export plot SVG';save.onclick=()=>download(`openswing-frequency-comparison-${i+1}.svg`,svg,'image/svg+xml');
      section.append(heading,chart,save);$('frequency-compare-plots').append(section);
    });
  }
  function add(selections){
    if(!result)return;const existing=new Set(traces.map(traceKey));
    for(const selection of selections){const s=canonicalTrace(result,selection),key=traceKey(s);if(!existing.has(key)){traces.push({...s,visible:true});existing.add(key);}}
    render();
  }
  $('frequency-compare-current').onclick=()=>add([context()]);
  $('frequency-compare-range').onclick=()=>{
    const first=Number($('frequency-compare-first').value),last=Number($('frequency-compare-last').value);
    if(first>last){$('frequency-compare-status').textContent='First input must precede or equal the last input.';return;}
    add(result.inputs.slice(first,last+1).map(c=>({...context(),inputName:c.name})));
  };
  $('frequency-compare-stations').onclick=()=>{
    const s=context(),input=result.inputs.findIndex(c=>c.name===s.inputName),rows=result.samples.find(p=>p.responses?.[input]?.output)?.responses[input].output[s.group];
    if(Array.isArray(rows))add(rows.map((_,station)=>({...s,station})));
  };
  $('frequency-compare-clear').onclick=()=>{traces=[];render();};
  $('frequency-compare-csv').onclick=()=>download('openswing-frequency-comparison.csv',comparisonCSV(result,traces.filter(t=>t.visible!==false),context().unwrap),'text/csv');
  return {render,capture:()=>structuredClone(traces),restore(value){traces=structuredClone(value??[]);nextOverlay=1+Math.max(0,...traces.filter(t=>t.overlay).map(t=>t.id));render();},setResult(data,preserve=false){result=data;if(!preserve){traces=[];overlays.reset();}choices();}};
}
