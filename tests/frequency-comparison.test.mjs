import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {canonicalTrace,traceKey,frequencyValue,frequencySeries,traceInfo,comparisonCSV} from '../web/frequency-data.js';
import {comparisonGroups,comparisonFigure} from '../web/frequency-comparison.js';
const study=JSON.parse(readFileSync('docs/validation/frequency-refinement.json','utf8'));
const actual=name=>study.cases.find(c=>c.specification.name===name).result.result;
const close=(a,b,tol=1e-9)=>assert.ok(Math.abs(a-b)<tol,`${a} != ${b}`);
const selection=(result,inputName,key='force',component=2,group='global',station=null)=>({inputName,group,key,component,station,display:'response'});
function rows(text){return text.trimEnd().split('\n').map(line=>{const cells=[];let field='',quoted=false;for(let i=0;i<line.length;i++){const c=line[i];if(c==='"'){if(quoted&&line[i+1]==='"'){field+='"';i++;}else quoted=!quoted;}else if(c===','&&!quoted){cells.push(field);field='';}else field+=c;}cells.push(field);return cells;});}

test('separate convected gust traces retain analytical complex force and spatial phase',()=>{
  const r=actual('gust_phase'),before=JSON.stringify(r),traces=r.inputs.map(c=>selection(r,c.name));
  const groups=comparisonGroups(r,traces);assert.equal(groups.length,1);assert.equal(groups[0].traces.length,2);
  for(const [i,t] of groups[0].traces.entries())for(const v of t.data){const amplitude=2.45*(i?Math.sin(Math.PI*.6):Math.cos(Math.PI*.6));close(v.real,amplitude*Math.cos(-v.omega*.12));close(v.imag,amplitude*Math.sin(-v.omega*.12));close(v.phase,(i?0:180)-v.omega*.12*180/Math.PI);}
  assert.equal(JSON.stringify(r),before);
});

test('harmonic transfers, initial spectra and unlike output units have separate axis groups',()=>{
  const r=actual('initial_spectra'),s=r.inputs.map(c=>selection(r,c.name,'displacement',1,'nodes',r.base.nodes.length-1));
  const groups=comparisonGroups(r,s);assert.equal(groups.length,2);assert.equal(groups[0].traces.length,1);assert.equal(groups[1].traces.length,2);
  assert.match(groups[1].unit,/input T/);assert.match(groups[1].traces[0].label,/σ=0.7/);
  assert.equal(comparisonGroups(r,[...s,{...s[0],key:'velocity'}]).length,3);
});

test('physical sensor station metadata and imaginary acceleration survive exports',()=>{
  const r=actual('initial_spectra'),s=selection(r,r.inputs[1].name,'acceleration_sensor',1,'sensors',1),info=traceInfo(r,s);
  assert.match(info.station,/Sensor 2/);assert.match(info.label,/Specific|acceleration sensor/);
  const csv=rows(comparisonCSV(r,[s]));assert.equal(csv.length,r.samples.length+1);assert.equal(csv[1][8],info.station);assert.equal(csv[1][9],info.unit);
  for(let i=0;i<r.samples.length;i++)close(Number(csv[i+1][14]),r.samples[i].responses[1].output.sensors[1].acceleration_sensor.imag[1],1e-14);
});

test('free-flight DC is an explicit export gap while finite-frequency displacement remains −1/ω²',()=>{
  const r=actual('free_dc_gap'),s=selection(r,r.inputs[0].name,'position_earth',0,'frame'),data=frequencySeries(r,s),csv=rows(comparisonCSV(r,[s]));
  assert.ok(data[0].error);assert.equal(data[0].phase,null);assert.equal(csv[1][13],'');assert.match(csv[1].at(-1),/Singular|singular|ill-conditioned/);
  for(const v of data.slice(1))close(v.real,-1/v.omega**2);
});

const fixture=()=>({inputs:[{name:'a',unit:'N',kind:'power'},{name:'b',unit:'N',kind:'power'}],base:{nodes:[]},samples:[170,-170,null,-170,0,170].map((phase,index)=>({omega:index,responses:[{output:{global:{force:{real:phase===null?null:phase===0?0:Math.cos(phase*Math.PI/180),imag:phase===null?null:phase===0?0:Math.sin(phase*Math.PI/180)}}}},{output:{global:{force:{real:Math.cos(-index*Math.PI/6),imag:Math.sin(-index*Math.PI/6)}}}}]}))});

test('phase unwrap is independent for every trace and resets at missing or zero output',()=>{
  const r=fixture(),s=selection(r,'a','force',null),a=frequencySeries(r,s),b=frequencySeries(r,{...s,inputName:'b'});
  assert.deepEqual(a.map(v=>v.phase).map(v=>v==null?v:Math.round(v)),[170,190,null,-170,null,170]);
  b.forEach((v,i)=>close(v.phase,-i*30));assert.equal(a[4].magnitude,0);assert.equal(a[4].db,null);assert.ok(a[2].error);
  close(frequencySeries(r,s,false)[1].phase,-170);
});

test('standalone SVG never connects phase gaps and excludes DC only on a log axis',()=>{
  const r=fixture(),s=selection(r,'a','force',null),group=comparisonGroups(r,[s])[0];
  const linear=comparisonFigure(group),log=comparisonFigure(group,{log:true});
  assert.doesNotMatch(log,/NaN|Infinity|undefined/);assert.match(log,/unwrapped per trace/);assert.match(log,/Zero frequency is omitted/);assert.match(comparisonFigure(comparisonGroups(r,[s],false)[0]),/wrapped ±180°/);assert.match(linear,/data-frequency="0"/);assert.doesNotMatch(log,/data-frequency="0"/);
  const paths=[...linear.matchAll(/<path d="([^"]*)" class="curve"/g)].map(m=>m[1]);
  assert.equal((paths[1].match(/M/g)??[]).length,3);assert.match(linear,/role="button"/);assert.match(linear,/xmlns="http:\/\/www.w3.org\/2000\/svg"/);
});

test('broken-loop traces use the matched response for each forcing channel',()=>{
  const r=actual('closed_loop'),traces=r.inputs.map(c=>canonicalTrace(r,{...selection(r,c.name),display:'broken_loop'}));
  assert.equal(traces[0].key,'power.1');assert.equal(traces[1].key,'measurements_RY[2]');
  const groups=comparisonGroups(r,traces);assert.equal(groups.length,1);assert.equal(groups[0].unit,'dimensionless');
  r.samples.forEach(p=>traces.forEach((s,i)=>{const value=frequencyValue(r,p,s),expected=p.responses[i].broken_loop;if(expected.available){close(value.real,expected.value.real,1e-13);close(value.imag,expected.value.imag,1e-13);}else assert.ok(value.error);}));
});

test('unmatched broken-loop forcing remains a gap instead of borrowing another response',()=>{
  const r=actual('gust_phase'),s=canonicalTrace(r,{...selection(r,r.inputs[0].name),display:'broken_loop'});
  assert.equal(s.key,'');assert.ok(frequencySeries(r,s).every(v=>v.error));assert.match(rows(comparisonCSV(r,[s]))[1].at(-1),/matching/);
});

test('trace identity distinguishes physical components and stations, ignoring display controls',()=>{
  const s=selection(null,'a','force',0,'sensors',0);assert.equal(traceKey(s),traceKey({...s,log:true,db:true,sample:4}));
  assert.notEqual(traceKey(s),traceKey({...s,station:1}));assert.notEqual(traceKey(s),traceKey({...s,component:1}));
});

test('hidden traces do not enter figures; zero and undefined values have distinct CSV statuses',()=>{
  const r=fixture(),s=selection(r,'a','force',null);assert.equal(comparisonGroups(r,[s,{...s,inputName:'b',visible:false}])[0].traces.length,1);
  const csv=rows(comparisonCSV(r,[s]));assert.match(csv[3].at(-1),/undefined/);assert.match(csv[5].at(-1),/resolved zero/);assert.equal(csv[5][15],'0');assert.equal(csv[5][16],'');assert.equal(csv[5][17],'');
});

test('input labels are escaped in standalone SVG and remain literal in CSV',()=>{
  const r=fixture(),name='a <tag> & "quoted", test';r.inputs[0].name=name;const s=selection(r,name,'force',null),svg=comparisonFigure(comparisonGroups(r,[s])[0]);
  assert.doesNotMatch(svg,/<tag>/);assert.match(svg,/&lt;tag&gt;/);assert.equal(rows(comparisonCSV(r,[s]))[1][2],name);
});

test('fresh refined grids preserve exact previous per-trace values without modifying the report',()=>{
  const r=actual('gust_phase'),s=selection(r,r.inputs[0].name),before=JSON.stringify(r),coarse={...r,samples:r.samples.filter((_,i)=>i%2===0)};
  for(const old of frequencySeries(coarse,s,false)){const current=frequencySeries(r,s,false).find(v=>v.omega===old.omega);for(const key of ['real','imag','magnitude','db','phase'])assert.equal(current[key],old[key]);}
  comparisonCSV(r,[s]);comparisonFigure(comparisonGroups(r,[s])[0]);assert.equal(JSON.stringify(r),before);
});

test('nearly constant physical gain does not expand roundoff into a full-height curve',()=>{
  const r=fixture();r.samples=r.samples.slice(0,2);r.samples.forEach((p,i)=>p.responses[0].output.global.force={real:1+i*1e-12,imag:0});
  const svg=comparisonFigure(comparisonGroups(r,[selection(r,'a','force',null)])[0],{gainLog:false}),ys=[...svg.matchAll(/data-frequency="\d+" cx="[^"]*" cy="([^"]*)"/g)].map(m=>Number(m[1]));
  assert.ok(Math.abs(ys[1]-ys[0])<1e-6);
  const labels=[...svg.matchAll(/<text x="76"[^>]*>([^<]*)<\/text>/g)].slice(0,5).map(m=>m[1]);assert.equal(new Set(labels).size,5);
});

const displayGroup=(magnitudes=[.1,1,10],phases=[-90,-10,0])=>({
  kind:'Transfer',unit:'rad/input T / (file flap setting)',unwrap:true,
  traces:[{index:0,label:'Yaw',selection:{inputName:'F3',group:'frame',key:'rates',component:2},color:'#abc',dash:'',
    data:magnitudes.map((magnitude,index)=>({index,omega:2*Math.PI*[.1,1,10][index],magnitude,
      db:magnitude>0?20*Math.log10(magnitude):null,phase:phases[index]}))}]
});
const plot=(svg,field)=>svg.match(new RegExp(`<g data-plot="${field}"[^>]*>(.*?)</g>`,'s'))?.[1]??'';
const coordinates=(svg,axis)=>[...svg.matchAll(new RegExp(`<circle[^>]* c${axis}="([^"]*)"`,'g'))].map(m=>Number(m[1]));

test('absolute magnitude defaults to logarithmic gain with decade and lighter minor grids on both axes',()=>{
  const group=displayGroup(),svg=comparisonFigure(group,{log:true,frequencyUnits:'cycles'}),magnitude=plot(svg,'magnitude');
  assert.match(svg,/<g data-plot="magnitude" data-axis-scale="log">/);
  assert.match(svg,/<g data-plot="phase" data-axis-scale="linear">/);
  assert.match(svg,/f \[cycles\/input T\]/);
  assert.match(svg,/\.grid-minor\{stroke:#293a35;stroke-width:\.6\}/);
  for(const axis of ['x','y']){
    for(const value of [.1,1,10])assert.match(magnitude,new RegExp(`class="grid grid-major" data-axis="${axis}" data-tick-value="${value}"`));
    for(const value of [.2,.3,.4,.5,.6,.7,.8,.9,2,3,4,5,6,7,8,9])assert.match(magnitude,new RegExp(`class="grid grid-minor" data-axis="${axis}" data-tick-value="${value}"`));
  }
  for(const axis of ['x','y']){const values=coordinates(magnitude,axis);close(values[1]-values[0],values[2]-values[1],1e-10);}
  for(const value of ['0.1','1','10'])assert.match(magnitude,new RegExp(`>${value}</text>`));
});

test('linear magnitude and dB retain linear gain and unchanged linear phase',()=>{
  const group=displayGroup(),log=comparisonFigure(group),linear=comparisonFigure(group,{gainLog:false}),db=comparisonFigure(group,{db:true});
  assert.match(linear,/<g data-plot="magnitude" data-axis-scale="linear">/);
  assert.match(db,/<g data-plot="db" data-axis-scale="linear">/);
  assert.deepEqual(coordinates(plot(log,'phase'),'y'),coordinates(plot(linear,'phase'),'y'));
  assert.deepEqual(coordinates(plot(log,'phase'),'y'),coordinates(plot(db,'phase'),'y'));
  const ys=coordinates(plot(linear,'magnitude'),'y');close((ys[2]-ys[1])/(ys[1]-ys[0]),10,1e-10);
  const dbYs=coordinates(plot(db,'db'),'y');close(dbYs[1]-dbYs[0],dbYs[2]-dbYs[1],1e-10);
});

test('log magnitude zero stays a gap while linear magnitude preserves its zero sample',()=>{
  const group=displayGroup([1,0,10],[0,null,45]),log=comparisonFigure(group),linear=comparisonFigure(group,{gainLog:false});
  const gain=plot(log,'magnitude'),linearGain=plot(linear,'magnitude');
  assert.doesNotMatch(gain,/data-frequency="1"/);assert.match(linearGain,/data-frequency="1"/);
  assert.equal((gain.match(/class="curve"/g)??[]).length,1);
  assert.equal((gain.match(/<path d="([^"]*)" class="curve"/)?.[1].match(/M/g)??[]).length,2);
  assert.match(log,/Zero magnitudes are gaps.*CSV retains the original values/);
  const zero=comparisonFigure(displayGroup([0,0,0],[null,null,null]));
  assert.match(zero,/No finite positive magnitude/);assert.doesNotMatch(zero,/NaN|Infinity|data-frequency=/);
});

test('display frequency and angular units leave raw data, sample identity and CSV unchanged',()=>{
  const group=displayGroup([1,2,3]),before=JSON.stringify(group);
  group.traces.push({...structuredClone(group.traces[0]),index:1,label:'External yaw',dash:'5 4'});
  const withOverlay=JSON.stringify(group),degrees=comparisonFigure(group,{log:true,frequencyUnits:'cycles',angleUnits:'degrees',selected:{...group.traces[0].selection,sample:1}});
  assert.match(degrees,/\[deg\/input T \/ \(file flap setting\)\]/);
  assert.match(degrees,/Magnitude · logarithmic=57\.296/);
  assert.equal((plot(degrees,'magnitude').match(/Magnitude · logarithmic=57\.296/g)??[]).length,4); // aria label and title for both traces
  const db=comparisonFigure(group,{db:true,angleUnits:'degrees'});
  assert.match(db,/Gain \[dB\]=35\.162/);
  assert.equal(JSON.stringify(group),withOverlay);
  const radians=comparisonFigure(JSON.parse(before),{log:true,frequencyUnits:'radians'});
  assert.match(radians,/ω \[rad\/input T\]/);assert.match(radians,/\[rad\/input T/);
  assert.equal((plot(degrees,'magnitude').match(/data-frequency="1"/g)??[]).length,2);
  assert.match(plot(degrees,'magnitude'),/data-trace="0" data-frequency="1"[^>]* r="5"/);
  const r={inputs:[{name:'F3',unit:'file flap setting',kind:'control'}],base:{nodes:[]},samples:[.1,1,10].map((f,i)=>({omega:2*Math.PI*f,
    responses:[{output:{frame:{rates_body:{real:[0,0,i+1],imag:[0,0,-i]}}}}]}))};
  const s=selection(r,'F3','rates_body',2,'frame'),csv=comparisonCSV(r,[s]),raw=JSON.stringify(r);
  assert.match(csv,/rad\/T/);
  comparisonFigure(comparisonGroups(r,[s])[0],{log:true,frequencyUnits:'cycles',angleUnits:'degrees'});
  assert.equal(comparisonCSV(r,[s]),csv);assert.equal(JSON.stringify(r),raw);
  const nonAngular=displayGroup();nonAngular.unit='input F / rad';
  assert.match(comparisonFigure(nonAngular,{angleUnits:'degrees'}),/\[input F \/ rad\]/);
});

test('section transfers and initial spectra retain radians, load density and unavailable archive samples',()=>{
  const out={strips:[{beam:2,t:.5,cm:{real:.1,imag:-.2},f_aero:{real:3,imag:4},f_reac:{real:-5,imag:2},da_eff:{real:.02,imag:-.03}}]};
  const r={base:{nodes:[]},inputs:[{name:'flap',unit:'file flap setting'},{name:'initial',kind:'initial',unit:'profile amplitude',laplace_shift:1}],samples:[{omega:2,responses:[{output:out},{output:out}]},{omega:3,responses:[{output:{strips:[{beam:2,t:.5}]}},{output:{strips:[{beam:2,t:.5,da_eff:null}]}}]}]};
  const before=JSON.stringify(r);
  for(const [key,unit] of [['cm','dimensionless'],['f_aero','input F/L'],['f_reac','input F/L'],['da_eff','rad']]){
    const s=selection(r,'flap',key,null,'strips',0),v=frequencyValue(r,r.samples[0],s),table=rows(comparisonCSV(r,[s]));
    assert.equal(v.real,out.strips[0][key].real);assert.equal(v.imag,out.strips[0][key].imag);
    assert.equal(traceInfo(r,s).unit,`${unit} / (file flap setting)`);
    assert.equal(traceInfo(r,{...s,inputName:'initial'}).unit,`${unit} · input T / (profile amplitude)`);
    assert.equal(Number(table[1][13]),v.real);assert.equal(Number(table[1][14]),v.imag);
    assert.equal(table[2][13],'');assert.match(table[2].at(-1),/unavailable|undefined/);
  }
  assert.equal(JSON.stringify(r),before);
});
