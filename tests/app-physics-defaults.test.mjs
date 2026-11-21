import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {analysisStructuralSelection} from '../web/analysis-numerics.js';
import {defaultStrutMode,defaultBodyAddedMassFactor,validateSettings,captureSettings,applySettings} from '../web/case-settings.js';

test('analyses automatically select the documented beam formulation and physical medium',()=>{
  assert.equal(analysisStructuralSelection('structural'),'aswing-section');
  for(const mode of ['mounted','modes','frequency','time'])assert.equal(analysisStructuralSelection(mode),'aswing-airflow');
  assert.equal(analysisStructuralSelection('rigid'),'midpoint');
  assert.equal(analysisStructuralSelection('modes',{vacuum:true}),'aswing-vacuum');
  assert.equal(analysisStructuralSelection('frequency',{vacuum:true,frame:'free'}),'aswing-moving-vacuum');
  assert.equal(analysisStructuralSelection('time',{vacuum:true}),'aswing-moving-vacuum');
  assert.equal(analysisStructuralSelection('modes',{stillAir:true}),'aswing-still-air');
  assert.equal(analysisStructuralSelection('frequency',{stillAir:true}),'aswing-still-air');
  assert.throws(()=>analysisStructuralSelection('time',{stillAir:true}),/Still-air nonlinear/);
  assert.throws(()=>analysisStructuralSelection('modes',{vacuum:true,stillAir:true}),/either/);
  assert.equal(defaultStrutMode,'bilateral');
  assert.equal(defaultBodyAddedMassFactor,1);
});

test('legacy default settings restore without removed controls or mutation; alternatives are never relabelled',()=>{
  const project=JSON.parse(readFileSync(new URL('../examples/dae-level-flight-project.json',import.meta.url),'utf8'));
  const original=project.cases.find(c=>c.id==='dae-level-trim').configuration;
  const old=structuredClone(original);
  // These fields were added after this saved project.
  Object.assign(old.fields,{'fourier-wake-diagnostic':false,'time-actuators':'',
    'moving-velocity-x':'0','moving-velocity-y':'0','moving-velocity-z':'0',
    'operating-points-values':'-2, 0, 2, 4, 6, 8','operating-points-initialization':'cold',
    'static-gravity-mode':'file','static-gravity-x':'0','static-gravity-y':'0','static-gravity-z':'-9.81',
    'time-accuracy-enabled':false,'time-accuracy-rtol':'0.001','time-accuracy-atol':'0.000001','time-accuracy-minimum':''});
  const domFields={...old.fields};delete domFields['strut-mode'];delete domFields['body-added-mass'];
  delete domFields['operating-points-values'];delete domFields['operating-points-initialization'];
  const nodes=new Map(Object.entries(domFields).map(([id,value])=>[id,{id,type:typeof value==='boolean'?'checkbox':'text',
    value:typeof value==='string'?value:'',checked:value===true,tagName:'INPUT',dataset:{},closest:()=>null,dispatchEvent(){}}]));
  for(const id of ['frequency-start','frequency-end'])nodes.get(id).dataset.frequencyUnit='cycles';
  const derivatives=old.derivative_parameters.map(value=>({value,checked:true}));
  const previous=globalThis.document;
  globalThis.document={getElementById:id=>{assert.ok(nodes.has(id),'Removed or missing DOM control: '+id);return nodes.get(id);},
    querySelectorAll:selector=>selector.includes('#model-configuration')?[...nodes.values()]:selector.startsWith('#derivative-parameters')?derivatives:
      [['controls','control'],['powers','power'],['circulation','circulation-beam']].flatMap(([name,attr])=>
        selector==='[data-'+attr+']'?Object.entries(old[name]).map(([id,value])=>({value,getAttribute:()=>id})):[])};
  try{
    const before=JSON.stringify(old),clean=validateSettings(old);
    assert.equal(JSON.stringify(old),before);
    assert.equal(Object.hasOwn(clean.fields,'strut-mode'),false);
    assert.equal(Object.hasOwn(clean.fields,'body-added-mass'),false);
    assert.deepEqual(clean.numerics,old.numerics);
    assert.deepEqual(clean.equilibrium,old.equilibrium);
    applySettings(clean,{refreshDerivatives(){},addConstraint(){},clearConstraints(){},restoreEquilibrium(){}});
    for(const id of ['frequency-start','frequency-end'])assert.equal(Number(nodes.get(id).value),Number(old.fields[id])/(2*Math.PI));
    assert.deepEqual(captureSettings(clean),clean);
    const wire=structuredClone(old);wire.fields['strut-mode']='wire';
    assert.throws(()=>validateSettings(wire),/nondefault brace/);
    const doubled=structuredClone(old);doubled.fields['body-added-mass']='2';
    assert.throws(()=>validateSettings(doubled),/nondefault fuselage/);
  }finally{globalThis.document=previous;}
});

test('changing analysis clears incompatible equilibria, reinspects once and never falls back to midpoint structure',async()=>{
  const main=readFileSync(new URL('../web/main.js',import.meta.url),'utf8');
  const source=main.slice(main.indexOf('function selectedAnalysisDefaults()'),main.indexOf("$('mode').onchange"));
  const nodes=new Map(),$=id=>{if(!nodes.has(id))nodes.set(id,{value:'',checked:false});return nodes.get(id);};
  $('mode').value='mounted';$('modal-ordinary-frame').value='free';
  const state={restoring:false,busy:false,dirty:false,source:'aircraft'},calls=[];
  const view={hasDraft:()=>false},equilibrium={restore:value=>calls.push(['clear',value]),refresh(){}};
  const make=new Function('analysisStructuralSelection','$','state','nodeView','distributionView','equilibriumView','inspect','resetResult','refreshAnalysisVisibility','configureSourceFrequencyInputs','showError','status',
    "let structuralSelection='aswing-airflow',previousAnalysisMode='mounted';"+
    "const sourceVacuumSelected=()=>structuralSelection==='aswing-vacuum',sourceMovingVacuumSelected=()=>structuralSelection==='aswing-moving-vacuum',sourceStillAirSelected=()=>structuralSelection==='aswing-still-air';"+
    source+'return {change:changeAnalysisMode,selection:()=>structuralSelection};');
  const app=make(analysisStructuralSelection,$,state,view,view,equilibrium,async()=>calls.push(['inspect']),()=>{},()=>{},()=>{},e=>calls.push(['error',e.message]),()=>{});
  $('mode').value='structural';await app.change();
  assert.equal(app.selection(),'aswing-section');
  assert.deepEqual(calls.map(c=>c[0]),['clear','inspect']);calls.length=0;
  $('mode').value='mounted';await app.change();
  assert.equal(app.selection(),'aswing-airflow');assert.equal(calls.length,2);calls.length=0;
  $('mode').value='frequency';await app.change();
  assert.equal(app.selection(),'aswing-airflow');assert.equal(calls.length,0);
  state.restoring=true;$('mode').value='structural';await app.change();
  assert.equal(app.selection(),'aswing-airflow');assert.equal(calls.length,0);
  state.restoring=false;$('mode').value='mounted';await app.change();calls.length=0;
  state.busy=true;$('mode').value='structural';await app.change();
  assert.equal($('mode').value,'mounted');assert.equal(app.selection(),'aswing-airflow');
  assert.equal(calls[0][0],'error');
});
