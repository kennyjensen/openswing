import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {tableRows,inspectBodeCSV,importFrequencyOverlay} from '../web/frequency-overlay-data.js';
import {traceKey,traceInfo,frequencySeries,comparisonCSV} from '../web/frequency-data.js';
import {comparisonGroups,comparisonFigure} from '../web/frequency-comparison.js';
const study=JSON.parse(readFileSync('docs/validation/custom-trim.json','utf8'));
const result=study.cases.find(c=>c.specification.name==='saved_frequency').result.frequency;
const selection={display:'response',inputName:result.inputs[0].name,group:'sensors',key:'displacement_body',component:1,station:1};
const options={mode:'table',label:'Independent analytical oscillator',delimiter:'comma',skip:1,format:'polar_deg',frequencyUnit:'cycles',responseScale:.001};
const imported=(text,settings={},s=selection,r=result)=>({...importFrequencyOverlay(text,{...options,...settings},r,s),id:1});
const close=(a,b,tolerance=3e-12)=>assert.ok(Math.abs(a-b)<=tolerance*Math.max(1,Math.abs(b)),`${a} != ${b}`);
function exact(w){const a=500-2*w*w,b=10*w,d=a*a+b*b;return {real:a/d,imag:-b/d};}

test('independent millimetre/Newton data in Hz reproduces the oscillator including resonance and a retained gap',()=>{
  const text=readFileSync('examples/oscillator-bode.csv','utf8'),o=imported(text),data=frequencySeries(result,o);
  assert.equal(data.length,21);assert.ok(data[11].error);assert.equal(data[11].phase,null);
  for(const [i,p] of data.entries()){close(p.omega,2*Math.PI*i/4);if(i===11)continue;const ref=exact(p.omega);close(p.real,ref.real);close(p.imag,ref.imag);}
  assert.equal(o.source.responseScale,.001);assert.equal(o.source.frequencyUnit,'cycles');
});

test('time units and the negative harmonic convention match independent complex mechanics and saved native results',()=>{
  const source=result.samples.map(p=>{const ref=exact(p.omega);return `${p.omega*60},${ref.real*1000},${-ref.imag*1000}`;}).join('\n');
  const o=imported(source,{skip:0,format:'rectangular',frequencyUnit:'radians',timeScale:60,convention:'negative'});
  o.samples.forEach((p,i)=>{const ref=exact(p.omega),native=result.samples[i].responses[0].output.sensors[1].displacement_body;close(p.real,ref.real);close(p.imag,ref.imag);close(p.real,native.real[1],2e-10);close(p.imag,native.imag[1],2e-10);close(p.omega,result.samples[i].omega);});
});

test('decibels use amplitude ratios, phase units and a signed unit multiplier exactly once',()=>{
  const o=imported('0,20,1.5707963267948966\n1,-Infinity,NA',{skip:0,format:'db_rad',frequencyUnit:'radians',responseScale:-.001});
  close(o.samples[0].real,0);close(o.samples[0].imag,-.01);
  const z=frequencySeries(result,o)[1];assert.equal(z.magnitude,0);assert.equal(z.phase,null);assert.equal(z.db,null);assert.ok(!z.error);
});

test('zero magnitude needs no phase; missing, malformed and infinite measurements have different meanings',()=>{
  const o=imported('0,0,\n1,NA,NA\n2,1,\n3,NaN,1\n4,null,-',{skip:0});
  assert.equal(o.samples[0].real,0);assert.ok(o.samples.slice(1).every(p=>p.error));
  for(const row of ['0,NA,broken','0,Infinity,0','0,1,Infinity','0,-1,0'])assert.throws(()=>imported(row,{skip:0}),/finite|nonnegative/);
});

test('Fortran exponent tables, column remapping, comments and quoted CSV retain numerical meaning',()=>{
  const o=imported('# reference\nlabel real omega imag\n10 2D-3 0D0 -3d-4 ! sample\n11 1d-3 1d1 -4D-4',{delimiter:'whitespace',skip:1,columns:[3,2,4],format:'rectangular',frequencyUnit:'radians',responseScale:1});
  assert.deepEqual(o.samples,[{omega:0,real:.002,imag:-.0003},{omega:10,real:.001,imag:-.0004}]);
  assert.deepEqual(tableRows('\uFEFF"a, b","quoted ""name"""\r\n"two\nlines",3\r\n').map(r=>r.cells),[['a, b','quoted "name"'],['two\nlines','3']]);
  assert.equal(tableRows('1;2;3','semicolon')[0].cells.length,3);assert.equal(tableRows('1\t2\t3','tab')[0].cells.length,3);
  assert.throws(()=>tableRows('"x'),/Unclosed/);assert.throws(()=>tableRows('"x"text,1'),/Unexpected/);
});

test('ambiguous grids, incomplete maps, invalid conversions and numerical overflow cannot create an overlay',()=>{
  for(const text of ['-1,1,0','NaN,1,0','0,1,0\n0,2,0','2,1,0\n1,2,0','0,1',''])assert.throws(()=>imported(text,{skip:0}));
  for(const settings of [{timeScale:0},{timeScale:-1},{responseScale:0},{columns:[1,1,2]},{columns:[1,2,129]},{skip:.5},{format:'power-db'},{convention:'cosine'},{frequencyUnit:'rpm'}])assert.throws(()=>imported('0,1,0',{skip:0,...settings}));
  assert.throws(()=>imported('0,10000,0',{skip:0,format:'db_deg'}),/overflows/);
  assert.throws(()=>imported('0,-10000,0',{skip:0,format:'db_deg'}),/underflows/);
  assert.throws(()=>imported('1e-300,1,0',{skip:0,timeScale:1e300}),/underflow/);
  assert.throws(()=>imported('0,1.7e308,1.7e308',{skip:0,format:'rectangular',responseScale:1}),/overflows/);
});

test('OpenSwing comparison CSV preserves computed/external identity, status, source mapping and exact complex values',()=>{
  const before=JSON.stringify(result),o=imported('0,2,0\n1,NA,NA\n2,1,-180',{skip:0,label:'comma, "quote"\nsecond line'}),other={...o,id:2};
  const text=comparisonCSV(result,[selection,o,other]),entries=inspectBodeCSV(text);assert.equal(entries.length,3);
  assert.equal(entries[1].metadata['source label'],o.label);assert.deepEqual(JSON.parse(entries[1].metadata['source mapping']),o.source);
  const copy=imported(text,{mode:'bode',series:1,timeScale:1,responseScale:1});
  copy.samples.forEach((p,i)=>{assert.equal(p.omega,o.samples[i].omega);if(p.error)assert.equal(p.error,o.samples[i].error);else {assert.equal(p.real,o.samples[i].real);assert.equal(p.imag,o.samples[i].imag);}});
  assert.notEqual(traceKey(o),traceKey(other));assert.equal(JSON.stringify(result),before);
});

test('single Bode CSV and old comparison headers remain readable',()=>{
  const unit=traceInfo(result,selection).unit;
  const header=['display','formula','input','output group','output','component','station index','omega [rad/T]','frequency [cycles/T]','Laplace damping [1/T]',`real [${unit}]`,`imag [${unit}]`,`magnitude [${unit}]`,'gain [dB]','phase [deg]','status'];
  const row=['response','x/u','power.1','sensors','displacement_body','1','1','0','0','0','.002','0','.002','','0','resolved'];
  const csv=[header,row].map(r=>r.map(c=>JSON.stringify(c)).join(',')).join('\n');
  const o=imported(csv,{mode:'bode',responseScale:1});assert.equal(o.samples[0].real,.002);
  const rows=tableRows(comparisonCSV(result,[selection])).map(r=>r.cells),remove=[19,20,21,22];
  const old=rows.map(r=>r.filter((_,i)=>!remove.includes(i)).map(c=>JSON.stringify(c)).join(',')).join('\n');
  assert.equal(inspectBodeCSV(old).length,1);assert.equal(imported(old,{mode:'bode',responseScale:1}).samples.length,3);
});

test('unit, spectral type and Laplace damping mismatches are rejected before plotting',()=>{
  const csv=comparisonCSV(result,[selection]);
  assert.throws(()=>imported(csv,{mode:'bode'}, {...selection,key:'strain'}),/selected target/);
  const modified=csv.replaceAll('"x/u"','"X(s) / profile amplitude"');
  assert.throws(()=>imported(modified,{mode:'bode'}),/selected target/);
  const shifted=JSON.parse(JSON.stringify(result));shifted.inputs[0].kind='initial';shifted.inputs[0].laplace_shift=.7;
  const initialCSV=comparisonCSV(shifted,[selection]);
  assert.throws(()=>imported(initialCSV,{mode:'bode',timeScale:2},selection,shifted),/Laplace damping/);
  const copied=imported(initialCSV,{mode:'bode',responseScale:1},selection,shifted);assert.equal(copied.input.laplace_shift,.7);
});

test('external plotting uses its own grid, resets phase after gaps and never changes the computed spectrum',()=>{
  const o=imported('0,1,170\n1,1,-170\n2,NA,NA\n3,1,-170\n4,0,NA\n5,1,170',{skip:0,responseScale:1,frequencyUnit:'radians',label:'<script> & "external"'});
  const before=JSON.stringify(result),groups=comparisonGroups(result,[selection,o]);assert.equal(groups.length,1);assert.equal(groups[0].traces[0].data.length,3);assert.equal(groups[0].traces[1].data.length,6);
  assert.deepEqual(groups[0].traces[1].data.map(p=>p.phase===null?null:Math.round(p.phase)),[170,190,null,-170,null,170]);
  const svg=comparisonFigure(groups[0],{log:true});assert.doesNotMatch(svg,/NaN|Infinity|<script>/);assert.match(svg,/&lt;script&gt;/);assert.match(svg,/external curves are dashed/);assert.doesNotMatch(svg,/data-frequency="0"/);
  assert.equal(comparisonGroups(result,[selection,{...o,visible:false}])[0].traces.length,1);assert.equal(JSON.stringify(result),before);
});

test('unresolved CSV rows cannot override their status with apparently valid numeric data',()=>{
  const text=comparisonCSV(result,[selection]).replaceAll('"resolved"','"failed solve"');
  assert.throws(()=>imported(text,{mode:'bode'}),/unresolved status/);
});

test('finite extreme external values do not overflow or erase the comparison axes',()=>{
  for(const [a,b,w] of [['1e-323','1e-323','1'],['0','1.7e308','1.7e308']]){
    const o=imported(`0,${a},0\n${w},${b},0`,{skip:0,format:'rectangular',responseScale:1,frequencyUnit:'radians'});
    for(const log of [false,true])assert.doesNotMatch(comparisonFigure(comparisonGroups(result,[o])[0],{log}),/NaN|Infinity/);
    assert.equal(o.samples[1].real,Number(b));
  }
});
