// Explicitly mapped external spectra. No response interpolation, fitting or
// solver-state mutation occurs here. All stored samples use exp(+iωt), rad/T
// and the chosen target's numerical response units.
import {traceInfo} from './frequency-data.js';

export const OVERLAY_LIMITS={bytes:2*1024*1024,rows:10000,columns:128,traces:64};
const fail=message=>{throw new Error(message);};
const finite=(text,name)=>{
  const value=String(text??'').trim();
  if(!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?$/.test(value))fail(`${name} must be a finite number.`);
  const number=Number(value.replace(/[dD]/,'e'));
  if(!Number.isFinite(number))fail(`${name} must be a finite number.`);
  return number;
};
const missing=value=>/^(?:|na|nan|null|-)$/i.test(String(value??'').trim());

export function tableRows(text,delimiter='comma'){
  if(typeof text!=='string'||new TextEncoder().encode(text).length>OVERLAY_LIMITS.bytes)fail('Overlay file exceeds 2 MiB.');
  text=text.replace(/^\uFEFF/,'').replace(/\r\n?/g,'\n');
  if(delimiter==='whitespace')return text.split('\n').map((line,i)=>({line:i+1,cells:line.replace(/[#!].*$/,'').trim().split(/\s+/)})).filter(r=>r.cells[0]);
  const separator={comma:',',tab:'\t',semicolon:';'}[delimiter];
  if(!separator)fail('Choose comma, tab, semicolon or whitespace columns.');
  const rows=[];let cells=[],field='',quoted=false,closed=false,line=1,start=1;
  const fieldEnd=()=>{cells.push(field);field='';closed=false;if(cells.length>OVERLAY_LIMITS.columns)fail('Overlay table exceeds 128 columns.');};
  const rowEnd=()=>{fieldEnd();if(cells.some(c=>c.trim()))rows.push({line:start,cells});cells=[];start=line+1;};
  for(let i=0;i<text.length;i++){
    const c=text[i];
    if(quoted){if(c==='"'){if(text[i+1]==='"'){field+='"';i++;}else {quoted=false;closed=true;}}else field+=c;if(c==='\n')line++;continue;}
    if(c===separator)fieldEnd();
    else if(c==='\n'){rowEnd();line++;}
    else if(c==='"'){if(field.trim()||closed)fail(`Unexpected quote on line ${line}.`);field='';quoted=true;}
    else if(closed){if(!/\s/.test(c))fail(`Unexpected text after a quoted field on line ${line}.`);}
    else field+=c;
  }
  if(quoted)fail('Unclosed quoted field in overlay CSV.');
  if(field||cells.length||closed)rowEnd();
  return rows;
}

export function inspectBodeCSV(text){
  const rows=tableRows(text),header=rows[0]?.cells;
  if(!header||!['display','formula','input','output group','output','omega [rad/T]','Laplace damping [1/T]','status'].every(name=>header.includes(name)))fail('Expected an OpenSwing Bode or comparison CSV header. Use Numeric table for other files.');
  if(new Set(header).size!==header.length)fail('CSV header has duplicate column names.');
  const at=name=>header.indexOf(name),real=at('real')>=0?at('real'):header.findIndex(v=>v.startsWith('real [')),imag=at('imag')>=0?at('imag'):header.findIndex(v=>v.startsWith('imag ['));
  if(real<0||imag<0)fail('CSV must contain real and imaginary response columns.');
  const entries=new Map();
  for(const row of rows.slice(1)){
    if(row.cells.length!==header.length)fail(`Line ${row.line} has ${row.cells.length} columns; expected ${header.length}.`);
    const read=name=>row.cells[at(name)]??'',formula=read('formula');
    const kind={'x/u':'Unit input transfer','1 - u/x':'Broken loop · 1 − u/x','X(s) / profile amplitude':'Initial-state spectrum'}[formula];
    if(!kind)fail(`Unknown response formula on line ${row.line}.`);
    const unit=read('response unit')||header[real].slice(6,-1),sigma=finite(read('Laplace damping [1/T]'),'Laplace damping');
    if(!unit)fail(`Missing response unit on line ${row.line}.`);
    const fields=['input','input unit','output group','output','component','station index','station','source','source label','source mapping','series id'];
    const key=JSON.stringify([kind,unit,sigma,...fields.map(read)]);
    if(!entries.has(key)){
      if(entries.size>=OVERLAY_LIMITS.traces)fail('CSV exceeds 64 series.');
      const label=`${read('source label')?read('source label')+' · ':''}${read('input')} → ${read('output group')}.${read('output')}${read('component')!==''?'.'+read('component'):''}${read('station index')!==''?' · station '+read('station index'):''}`;
      entries.set(key,{kind,unit,sigma,label,rows:[],metadata:Object.fromEntries(fields.map(k=>[k,read(k)]))});
    }
    const entry=entries.get(key);entry.rows.push({...row,frequency:row.cells[at('omega [rad/T]')],first:row.cells[real],second:row.cells[imag],status:read('status')});
    if(entry.rows.length>OVERLAY_LIMITS.rows)fail('Overlay series exceeds 10000 samples.');
  }
  if(!entries.size)fail('CSV has no data rows.');
  return [...entries.values()];
}

export function importFrequencyOverlay(text,options,result,selection){
  if(!result||!selection?.key)fail('Select a computed response before importing an overlay.');
  const target=traceInfo(result,selection),label=String(options.label??'').trim();
  if(!label||label.length>160)fail('Enter an overlay label of 1–160 characters.');
  const timeScale=finite(options.timeScale??1,'Source time unit'),responseScale=finite(options.responseScale??1,'Response multiplier');
  if(timeScale<=0||responseScale===0)fail('Source time unit must be positive and response multiplier must be nonzero.');
  const convention=options.convention??'positive';
  if(!['positive','negative'].includes(convention))fail('Choose exp(+iωt) or exp(−iωt).');
  let rows,format,frequencyUnit,provenance;
  if(options.mode==='bode'){
    const entries=inspectBodeCSV(text),index=Number(options.series??0);
    if(!Number.isInteger(index)||!entries[index])fail('Choose a CSV series.');
    const entry=entries[index];rows=entry.rows;format='rectangular';frequencyUnit='radians';
    if(entry.kind!==target.kind||entry.unit!==target.unit)fail(`CSV series is ${entry.kind} [${entry.unit}]; selected target is ${target.kind} [${target.unit}]. Select a matching response, or explicitly map the columns as a Numeric table.`);
    const sigma=entry.sigma/timeScale,targetSigma=target.input?.laplace_shift??0;
    if(Math.abs(sigma-targetSigma)>1e-12*Math.max(1,Math.abs(sigma),Math.abs(targetSigma)))fail('CSV Laplace damping does not match the selected response after time conversion.');
    provenance={series:index,seriesLabel:entry.label,metadata:entry.metadata};
  }else if(options.mode==='table'){
    format=options.format??'rectangular';frequencyUnit=options.frequencyUnit??'radians';
    if(!['rectangular','polar_deg','polar_rad','db_deg','db_rad'].includes(format))fail('Choose a supported complex-response format.');
    if(!['radians','cycles'].includes(frequencyUnit))fail('Choose radians or cycles per source time unit.');
    const columns=options.columns??[1,2,3],skip=Number(options.skip??0);
    if(!Array.isArray(columns)||columns.length!==3||!columns.every(v=>Number.isInteger(v)&&v>=1&&v<=128)||new Set(columns).size!==3)fail('Enter three distinct column numbers from 1 to 128.');
    if(!Number.isInteger(skip)||skip<0||skip>10000)fail('Header rows must be an integer from 0 to 10000.');
    rows=tableRows(text,options.delimiter??'whitespace').slice(skip).filter(r=>!r.cells[0].trimStart().match(/^[#!]/)).map(row=>{
      if(row.cells.length<Math.max(...columns))fail(`Line ${row.line} does not contain all three mapped columns.`);
      return {...row,frequency:row.cells[columns[0]-1],first:row.cells[columns[1]-1],second:row.cells[columns[2]-1]};
    });
    provenance={columns:[...columns],skip,delimiter:options.delimiter??'whitespace'};
  }else fail('Choose OpenSwing CSV or Numeric table.');
  if(!rows.length||rows.length>OVERLAY_LIMITS.rows)fail('An overlay requires 1–10000 samples.');
  let previous=-1;
  const samples=rows.map(row=>{
    const frequency=finite(row.frequency,`Frequency on line ${row.line}`),omega=frequency*(frequencyUnit==='cycles'?2*Math.PI:1)/timeScale;
    if(!Number.isFinite(omega)||omega<0||omega<=previous||frequency>0&&omega===0)fail(`Frequencies must be finite, nonnegative and strictly increasing without underflow; check line ${row.line}.`);
    previous=omega;
    const gap=()=>({omega,error:row.status&&!row.status.startsWith('resolved')?row.status:`Missing external response on line ${row.line}.`});
    const db=format.startsWith('db_'),zeroDB=db&&/^-infinity$/i.test(String(row.first).trim());
    const a=missing(row.first)?null:zeroDB?-Infinity:finite(row.first,`Response on line ${row.line}`);
    const b=missing(row.second)?null:finite(row.second,`Imaginary part or phase on line ${row.line}`);
    if(a===null)return gap();
    if(format!=='rectangular'&&!db&&a<0)fail(`Magnitude must be nonnegative on line ${row.line}.`);
    const magnitude=db?10**(a/20):a;
    if(b===null&&!(format!=='rectangular'&&magnitude===0))return gap();
    const phase=format.endsWith('_deg')?(b??0)*Math.PI/180:(b??0);
    const real=responseScale*(format==='rectangular'?a:magnitude*Math.cos(phase));
    const imag=responseScale*(convention==='negative'?-1:1)*(format==='rectangular'?b:magnitude*Math.sin(phase));
    if(!Number.isFinite(real)||!Number.isFinite(imag)||!Number.isFinite(Math.hypot(real,imag)))fail(`Response conversion overflows on line ${row.line}.`);
    if((a!==0||format==='rectangular'&&b!==0)&&real===0&&imag===0&&!zeroDB&&!(format!=='rectangular'&&a===0))fail(`Response conversion underflows on line ${row.line}.`);
    if(row.status&&!row.status.startsWith('resolved'))fail(`Line ${row.line} has numerical response data but an unresolved status.`);
    return {omega,real,imag};
  });
  const s=target.selection;
  return {overlay:true,display:s.display,inputName:s.inputName,group:s.group,key:s.key,component:s.component,station:s.station,
    label,targetLabel:target.label,stationLabel:target.station,kind:target.kind,unit:target.unit,
    input:structuredClone(target.input),source:{filename:String(options.filename??'local data'),mode:options.mode,...provenance,format,frequencyUnit,timeScale,responseScale,convention},samples};
}
