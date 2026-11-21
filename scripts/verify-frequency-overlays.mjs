// Independent x/F = 1/(k - mω² + icω) reference, distinct from the UI importer.
import assert from 'node:assert/strict';
import {readFile,writeFile,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {importFrequencyOverlay,inspectBodeCSV} from '../web/frequency-overlay-data.js';
import {comparisonCSV} from '../web/frequency-data.js';
const hash=async path=>createHash('sha256').update(await readFile(path)).digest('hex');
const nativePath='docs/validation/custom-trim.json',wasmPath='docs/validation/custom-trim-wasm.json';
const native=JSON.parse(await readFile(nativePath,'utf8')),wasm=JSON.parse(await readFile(wasmPath,'utf8'));
for(const record of [native,wasm])for(const [path,digest] of Object.entries(record.source_sha256))assert.equal(await hash(path),digest,`Changed baseline source: ${path}`);
assert.equal(await hash(nativePath),wasm.study_sha256);
for(const [path,digest] of Object.entries(wasm.runtime_sha256))assert.equal(await hash(`public/runtime/${path}`),digest,`Changed runtime: ${path}`);
const result=native.cases.find(c=>c.specification.name==='saved_frequency').result.frequency;
const selection={display:'response',inputName:result.inputs[0].name,group:'sensors',key:'displacement_body',component:1,station:1};
const exact=w=>{const a=500-2*w*w,b=10*w,d=a*a+b*b;return {real:a/d,imag:-b/d};};
const grid=Array.from({length:121},(_,i)=>i/4),cases=[];
function check(name,text,options,expected=exact){
  const overlay={...importFrequencyOverlay(text,{mode:'table',label:name,delimiter:'comma',...options},result,selection),id:cases.length+1};
  let maximumAbsoluteError=0,checks=0,gaps=0;
  for(const p of overlay.samples){if(p.error){gaps++;continue;}const ref=expected(p.omega);for(const key of ['real','imag']){maximumAbsoluteError=Math.max(maximumAbsoluteError,Math.abs(p[key]-ref[key]));checks++;}}
  assert.ok(maximumAbsoluteError<1e-14);
  const csv=comparisonCSV(result,[selection,overlay]),entries=inspectBodeCSV(csv);assert.equal(entries.length,2);
  const copy=importFrequencyOverlay(csv,{mode:'bode',series:1,label:'reimport'},result,selection);
  // CSV/JSON may print IEEE -0 as 0; both represent the same complex response.
  assert.deepEqual(JSON.parse(JSON.stringify(copy.samples)),JSON.parse(JSON.stringify(overlay.samples)));
  cases.push({name,samples:overlay.samples.length,finiteComponentChecks:checks,gaps,maximumAbsoluteError,conversion:overlay.source,csvRoundTrip:true});
  return overlay;
}
check('polar_hz_millimetres',await readFile('examples/oscillator-bode.csv','utf8'),{skip:1,format:'polar_deg',frequencyUnit:'cycles',responseScale:.001,filename:'examples/oscillator-bode.csv'});
check('rectangular_minutes_negative_convention',grid.map(w=>{const z=exact(w);return [60*w,1000*z.real,-1000*z.imag].join(',');}).join('\n'),{format:'rectangular',timeScale:60,responseScale:.001,convention:'negative'});
check('decibels_radians',grid.map(w=>{const z=exact(w);return [w,20*Math.log10(1000*Math.hypot(z.real,z.imag)),Math.atan2(z.imag,z.real)].join(',');}).join('\n'),{format:'db_rad',responseScale:.001});
const fromNative=importFrequencyOverlay(comparisonCSV(result,[selection]),{mode:'bode',label:'saved native reference'},result,selection);
let nativeError=0;for(const p of fromNative.samples){const ref=exact(p.omega);for(const key of ['real','imag'])nativeError=Math.max(nativeError,Math.abs(p[key]-ref[key]));}
assert.ok(nativeError<2e-10);
const files=['web/frequency-data.js','web/frequency-comparison.js','web/frequency-overlays.js','web/frequency-overlay-data.js','web/frequency-results.js','web/style.css','tests/frequency-overlays.test.mjs','tests/frequency-comparison.test.mjs','tests/browser/frequency-overlays.spec.js','tests/browser/frequency-comparison.spec.js','examples/oscillator-bode.csv','scripts/verify-frequency-overlays.mjs'];
files.push(...(await readdir('openswing')).filter(n=>n.endsWith('.py')).map(n=>'openswing/'+n));
const report={description:'Local external Bode data conversion and immutable comparison. Independent original oscillator, m=2 kg, c=10 N s/m, k=500 N/m. Existing native/WASM evidence is hash-verified and reused; the numerical kernel is unchanged. This script does not rerun the numerical solver.',
  source_sha256:Object.fromEntries(await Promise.all(files.sort().map(async p=>[p,await hash(p)]))),
  reused_baselines:{[nativePath]:await hash(nativePath),[wasmPath]:await hash(wasmPath)},nativeReferenceComponentChecks:6,maximumAbsoluteNativeReferenceError:nativeError,cases};
await writeFile('docs/validation/frequency-overlays.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({cases:cases.length,componentChecks:cases.reduce((n,c)=>n+c.finiteComponentChecks,0),gaps:cases.reduce((n,c)=>n+c.gaps,0),maximumAbsoluteError:Math.max(...cases.map(c=>c.maximumAbsoluteError)),nativeError,sourceHashes:files.length}));
