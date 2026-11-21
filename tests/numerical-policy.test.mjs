import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {DEFAULT_NUMERICS,SOURCE_NUMERICS,SECTION_NUMERICS,COUPLED_NUMERICS,numericalSelection,selectedNumerics,numericalMode,selectionAllowsMode,sameNumerics,numericalRequest,assertNumericalIdentity,structuralPolicyNote} from '../web/numerical-policy.js';
import {validateConfiguration,parseProject,emptyProject,changeCase} from '../web/project-data.js';
import {sealSolution,verifySolution,validateSolution,kernelFingerprint} from '../web/solution-data.js';
import {captureSettings,applySettings,settingFields} from '../web/case-settings.js';
import {structureSampleDescription,structureExportRows} from '../web/structure-results.js';
import {sensorStrainDescription} from '../web/sensor-results.js';

const configuration=()=>({source:'Name\nOriginal\nEnd\n',filename:'original.asw',mesh:4,fields:{mode:'structural'},controls:{},powers:{},circulation:{},derivative_parameters:[],constraints:[],equilibrium:{state:null,enabled:false,label:''}});
const state=(numerics=SOURCE_NUMERICS)=>({format:'openswing-equilibrium',version:1,positions:[[0,0,0]],identity:{...numerics},circulation:[]});
async function sourceSolution(numerics=SOURCE_NUMERICS){
  const mode=numericalMode(numerics),c={...configuration(),fields:{mode},numerics:{...numerics}},p={format:'openswing-kernel-provenance',version:1,modules:{'source_discrete.py':'a'.repeat(64)},runtime:{pyodide:'test',python:'test',numpy:'test',scipy:'test'}};
  p.fingerprint=await kernelFingerprint(p);
  return sealSolution({id:'source',name:'Source static',created_at:'2026-10-26T00:00:00Z',kind:mode,configuration:c,
    data:{analysis:mode==='mounted'?'mounted_static':'structural_static',converged:true,residual:1e-12,...(mode==='structural'?{structural_only:true}:{}),strips:[],numerics:{...numerics},structural_operator:numerics.structural_operator,
      equilibrium_state:state(numerics),mass_properties:{mass:2},limitations:[],software_provenance:p,
      request:{action:'solve',mode,source:c.source,numerics:{...numerics}}},
    auxiliary:{},view:{active_tab:'tab-structure'},provenance:p});
}

test('only complete supported pairs are accepted; absent defaults stay omitted',()=>{
  assert.equal(numericalSelection(undefined),'midpoint');assert.equal(numericalSelection(DEFAULT_NUMERICS),'midpoint');
  assert.equal(numericalSelection(SOURCE_NUMERICS),'aswing');assert.equal(selectedNumerics('midpoint'),undefined);
  assert.deepEqual(selectedNumerics('aswing'),SOURCE_NUMERICS);assert(sameNumerics(undefined,DEFAULT_NUMERICS));
  for(const value of [null,[],{},'aswing',{beam_interpolation:'drela-segspl-v1'},{...SOURCE_NUMERICS,extra:true},
    {...SOURCE_NUMERICS,structural_operator:'midpoint-v1'},{...SOURCE_NUMERICS,beam_interpolation:'future'}])assert.throws(()=>numericalSelection(value));
  assert.throws(()=>selectedNumerics('future'));
  const old=configuration(),text=JSON.stringify(old);assert.equal(JSON.stringify(validateConfiguration(old)),text);
  assert(!Object.hasOwn(validateConfiguration(old),'numerics'));
});

test('parse, mesh and edit requests share the selected policy; old-project inspection overrides it',()=>{
  for(const action of ['inspect','distribution','edit_distribution','canonical_asw']){
    const input={action,source:'literal',panels:4,beam:1,name:'chord'},before=structuredClone(input);
    assert.deepEqual(numericalRequest(input,SOURCE_NUMERICS),{...input,numerics:SOURCE_NUMERICS});
    assert.deepEqual(input,before);
    assert.deepEqual(numericalRequest({...input,numerics:undefined},SOURCE_NUMERICS),input);
    assert.deepEqual(numericalRequest({...input,numerics:DEFAULT_NUMERICS},SOURCE_NUMERICS),input);
  }
  assert.deepEqual(numericalRequest({action:'discard_frequency',session:'old'},SOURCE_NUMERICS),{action:'discard_frequency',session:'old'});
});

test('source policy cannot leak into aerodynamic, dynamic or auxiliary calculations',()=>{
  const input={action:'solve',mode:'structural',source:'literal',gravity:null};
  assert.deepEqual(numericalRequest(input,SOURCE_NUMERICS),{...input,numerics:SOURCE_NUMERICS});
  for(const request of [{...input,mode:'mounted'},{...input,mode:'rigid'},
    ...['time','modes','frequency','launch_time','resume_time','flow','stability','rom'].map(action=>({action,source:'literal'}))]){
    assert.throws(()=>numericalRequest(request,SOURCE_NUMERICS),/structural static/);
    assert.deepEqual(numericalRequest(request,undefined),request);
  }
});

test('project configuration and loaded equilibrium must use matching policies',()=>{
  const c={...configuration(),numerics:{...SOURCE_NUMERICS}};
  c.equilibrium={state:state(),enabled:true,label:'Source'};
  assert.deepEqual(validateConfiguration(c),c);
  const p=changeCase(emptyProject(),'add',{id:'source',name:'Source',configuration:c});
  assert.deepEqual(parseProject(JSON.stringify(p)),p);
  for(const mutate of [v=>v.fields.mode='mounted',v=>delete v.numerics,v=>delete v.equilibrium.state.identity,
    v=>v.equilibrium.state.identity.structural_operator='midpoint-v1',v=>v.equilibrium.state.launch={},v=>v.numerics={...SOURCE_NUMERICS,unknown:true}]){
    const bad=structuredClone(c);mutate(bad);assert.throws(()=>validateConfiguration(bad));
  }
  assert.doesNotThrow(()=>assertNumericalIdentity(undefined,{}));
});

test('new computed source solutions retain request/configuration/identity and reject mismatches before display',async()=>{
  const saved=await sourceSolution(),encoded=JSON.stringify(saved);
  const p={...emptyProject(),solutions:[saved],selected_solution:'source'};
  const restored=parseProject(JSON.stringify(p)).solutions[0];
  await verifySolution(restored);assert.equal(JSON.stringify(restored),encoded);
  for(const mutate of [v=>delete v.configuration.numerics,v=>delete v.data.request.numerics,v=>delete v.data.numerics,
    v=>v.data.request.mode='mounted',v=>v.data.request.action='launch_time',v=>delete v.data.equilibrium_state,
    v=>v.data.structural_operator='midpoint-v1',v=>v.data.equilibrium_state.launch={},
    v=>delete v.data.equilibrium_state.identity.structural_operator,
    v=>v.data.equilibrium_state.identity.beam_interpolation='natural-v1']){
    const bad=structuredClone(saved);mutate(bad);assert.throws(()=>validateSolution(bad));
  }
});

test('source interval estimates and one-sided endpoints retain distinct plot/export meanings',()=>{
  const meta={strain_source:'source_discrete_constitutive'};
  assert.match(structureSampleDescription(meta,4),/interval constitutive estimates/);
  assert.match(structureSampleDescription(meta,4),/not point samples/);
  assert.match(structureSampleDescription({},4),/material midpoint samples/);
  const elements=[{beam:1,t:.5,t0:0,t1:1,length:1,strain:[0,.3,0],endpoint_traces:[
    {t:0,side:'right',strain:[0,.1,0]},{t:1,side:'left',strain:[0,.5,0]}]},
    {beam:1,t:1.5,t0:1,t1:2,length:1,strain:[0,.8,0],endpoint_traces:[
      {t:1,side:'right',strain:[0,.7,0]},{t:2,side:'left',strain:[0,.9,0]}]}];
  const before=structuredClone(elements),rows=structureExportRows({structure:meta,elements});
  assert.equal(rows.length,6);assert.deepEqual(rows.filter(r=>r.t===1).map(r=>[r.side,r.strain[1]]),[['left',.5],['right',.7]]);
  assert.equal(rows[0].sample_location,'element constitutive average');assert.equal(rows[1].sample_location,'one-sided endpoint section');
  assert.deepEqual(elements,before);assert.equal(structureExportRows({structure:{},elements}),elements);
  assert.equal(sensorStrainDescription({strain_sample_location:'one-sided sensor anchor section'}),'Strain/stress use the one-sided sensor anchor section.');
  assert.equal(sensorStrainDescription({}),'Strain/stress use the adjacent material midpoint.');
});

test('damped source exports preserve null endpoint strain and separate sensor stress sampling',()=>{
  const meta={strain_source:'source_discrete_damped_constitutive'};
  const description=structureSampleDescription(meta,1);
  assert.match(description,/interval constitutive estimates/);
  assert.match(description,/material-rate correction/);
  assert.match(description,/endpoint mechanical strains are unavailable/);
  assert.doesNotMatch(description,/material midpoint samples/);
  const elements=[{beam:1,t:.5,t0:0,t1:1,strain:[0,.3,0],curvature_change:[.1,.2,.3],
    shell:{strain_available:true,axial_strain:.4,shear_stress:7},endpoint_traces:[
      {t:0,side:'right',force_local:[1,2,3],strain:null,curvature_change:null,
        shell:{strain_available:false,axial_strain:null,shear_stress:8}},
      {t:1,side:'left',force_local:[4,5,6],strain:null,curvature_change:null,
        shell:{strain_available:false,axial_strain:null,shear_stress:9}}]}];
  const before=structuredClone(elements),rows=structureExportRows({structure:meta,elements});
  assert.equal(rows.length,3);assert.deepEqual(rows[0].strain,[0,.3,0]);
  assert.deepEqual(rows.slice(1).map(r=>[r.strain,r.curvature_change,r.shell.axial_strain,r.shell.shear_stress]),[[null,null,null,8],[null,null,null,9]]);
  assert.deepEqual(rows.slice(1).map(r=>r.force_local),[[1,2,3],[4,5,6]]);
  assert.deepEqual(elements,before);
  const sensor=sensorStrainDescription({strain_sample_location:'selected adjacent element constitutive average'});
  assert.match(sensor,/selected adjacent constitutive interval/);
  assert.match(sensor,/Shell shear stress uses total anchor torque/);
  assert.doesNotMatch(sensor,/material midpoint/);
});

test('a retained real historical project keeps sealed solution bytes and checksums',async()=>{
  const original=JSON.parse(await readFile(new URL('../examples/pazy-isae-wall-half-project.json',import.meta.url),'utf8'));
  assert(original.solutions.length>0);
  const restored=parseProject(JSON.stringify(original));
  for(let i=0;i<original.solutions.length;i++){
    assert.equal(JSON.stringify(restored.solutions[i]),JSON.stringify(original.solutions[i]));
    await verifySolution(restored.solutions[i]);
    assert(!Object.hasOwn(restored.solutions[i].configuration,'numerics'));
    assert(!Object.hasOwn(restored.solutions[i].data.request,'numerics'));
  }
});

test('selector is separate from historical generic fields and applies before setting events',()=>{
  const previous=globalThis.document,events=[];
  const select={id:'structural-equations',value:'midpoint',type:'select-one',tagName:'SELECT',dataset:{},closest:()=>null};
  const mode={id:'mode',value:'structural',type:'select-one',tagName:'SELECT',dataset:{},closest:()=>null,
    dispatchEvent:event=>events.push({type:event.type,selection:select.value})};
  globalThis.document={getElementById:id=>id==='mode'?mode:id==='structural-equations'?select:null,
    querySelectorAll:query=>query.includes('#model-configuration')?[mode,select]:[]};
  try{
    assert.deepEqual([...settingFields().keys()],['mode']);
    const c=configuration();assert.deepEqual(captureSettings(c),c);
    const source={...c,numerics:{...SOURCE_NUMERICS}};
    assert.deepEqual(captureSettings(source),source);
    const hooks={refreshDerivatives(){},addConstraint(){},clearConstraints(){},restoreEquilibrium(){}};
    applySettings(source,hooks);assert.equal(select.value,'aswing');assert(events.every(e=>e.selection==='aswing'));
    const section={...c,numerics:{...SECTION_NUMERICS}};
    events.length=0;assert.deepEqual(captureSettings(section),section);
    applySettings(section,hooks);assert.equal(select.value,'aswing-section');assert(events.every(e=>e.selection==='aswing-section'));
    const coupled={...c,fields:{mode:'mounted'},numerics:{...COUPLED_NUMERICS}};
    events.length=0;applySettings(coupled,hooks);assert.equal(select.value,'aswing-coupled');assert(events.every(e=>e.selection==='aswing-coupled'));
    events.length=0;applySettings(c,hooks);assert.equal(select.value,'midpoint');assert(events.every(e=>e.selection==='midpoint'));
  }finally{globalThis.document=previous;}
});

test('general sections are a separate explicit policy with accurate static limits',()=>{
  assert.equal(numericalSelection(SECTION_NUMERICS),'aswing-section');
  assert.deepEqual(selectedNumerics('aswing-section'),SECTION_NUMERICS);
  assert(!sameNumerics(SECTION_NUMERICS,SOURCE_NUMERICS));
  assert.match(structuralPolicyNote('aswing-section'),/finite shear/);
  assert.match(structuralPolicyNote('aswing-section'),/Dynamic inertia and spin are unavailable/);
  assert.match(structuralPolicyNote('aswing'),/rigid shear/);
  assert.equal(structuralPolicyNote('midpoint'),'');
  assert.throws(()=>structuralPolicyNote('unknown'));
  assert.throws(()=>numericalSelection({...SECTION_NUMERICS,beam_interpolation:'natural-v1'}));
  for(const action of ['inspect','distribution','edit_distribution','canonical_asw','solve']){
    const input={action,source:'literal',...(action==='solve'?{mode:'structural'}:{})};
    assert.deepEqual(numericalRequest(input,SECTION_NUMERICS),{...input,numerics:SECTION_NUMERICS});
    assert.deepEqual(numericalRequest({...input,numerics:SOURCE_NUMERICS},SECTION_NUMERICS),{...input,numerics:SOURCE_NUMERICS});
    assert.deepEqual(numericalRequest({...input,numerics:undefined},SECTION_NUMERICS),input);
  }
  for(const action of ['time','modes','frequency','flow_survey','launch_time','rom','stability']){
    assert.throws(()=>numericalRequest({action,source:'literal'},SECTION_NUMERICS),/structural static/);
  }
  assert.throws(()=>numericalRequest({action:'solve',mode:'mounted',source:'literal'},SECTION_NUMERICS),/structural static/);
});

test('all four saved configuration policies reject cross-policy seeds',()=>{
  const policies=[undefined,SOURCE_NUMERICS,SECTION_NUMERICS,COUPLED_NUMERICS];
  for(const numerics of policies)for(const saved of policies){
    const c={...configuration(),fields:{mode:numericalMode(numerics)??'structural'},...(numerics?{numerics}:{}),
      equilibrium:{state:state(saved??DEFAULT_NUMERICS),enabled:true,label:'Saved'}};
    if(numerics===saved)assert.deepEqual(validateConfiguration(c),c);
    else assert.throws(()=>validateConfiguration(c),/numerical settings/);
  }
  const section={...configuration(),numerics:SECTION_NUMERICS};
  assert.deepEqual(validateConfiguration(section),section);
  assert.throws(()=>validateConfiguration({...section,fields:{mode:'mounted'}}),/structural static/);
  section.equilibrium={state:{...state(SECTION_NUMERICS),launch:{}},enabled:true,label:'Invalid'};
  assert.throws(()=>validateConfiguration(section),/dynamic launch/);
});

test('general-section solutions preserve null dynamic data and reject mixed identities',async()=>{
  const saved=await sourceSolution(SECTION_NUMERICS);
  saved.data.mass_properties={mass:2,first_moment:[0,1,0],cg:[0,.5,0],inertia_cg:null,spin:null};
  const sealed=await sealSolution(saved),encoded=JSON.stringify(sealed);
  const project={...emptyProject(),solutions:[sealed],selected_solution:sealed.id};
  const restored=parseProject(JSON.stringify(project)).solutions[0];
  await verifySolution(restored);assert.equal(JSON.stringify(restored),encoded);
  for(const mutate of [v=>v.configuration.numerics=SOURCE_NUMERICS,
    v=>v.data.numerics=SOURCE_NUMERICS,v=>v.data.request.numerics=SOURCE_NUMERICS,
    v=>v.data.structural_operator=SOURCE_NUMERICS.structural_operator,
    v=>v.data.equilibrium_state.identity=SOURCE_NUMERICS,v=>delete v.data.equilibrium_state,
    v=>v.data.equilibrium_state.launch={},v=>v.data.request.action='launch_time']){
    const bad=structuredClone(sealed);mutate(bad);assert.throws(()=>validateSolution(bad));
  }
});

test('retained zero-offset source project keeps sealed bytes and policy when reopened',async()=>{
  const original=JSON.parse(await readFile(new URL('../examples/isae-st5-source-static-project.json',import.meta.url),'utf8'));
  assert(original.solutions.length>0);
  const restored=parseProject(JSON.stringify(original));
  for(let i=0;i<original.solutions.length;i++){
    assert.equal(JSON.stringify(restored.solutions[i]),JSON.stringify(original.solutions[i]));
    assert.deepEqual(restored.solutions[i].configuration.numerics,SOURCE_NUMERICS);
    await verifySolution(restored.solutions[i]);
  }
});

test('fourth pair permits mounted steady only and preserves its actual calculation options',()=>{
  assert.equal(numericalSelection(COUPLED_NUMERICS),'aswing-coupled');
  assert.deepEqual(selectedNumerics('aswing-coupled'),COUPLED_NUMERICS);
  assert.equal(numericalMode(COUPLED_NUMERICS),'mounted');
  assert.match(structuralPolicyNote('aswing-coupled'),/Mounted steady/);
  assert.match(structuralPolicyNote('aswing-coupled'),/Historical ASWING load sampling/);
  assert.throws(()=>numericalSelection({...COUPLED_NUMERICS,beam_interpolation:'natural-v1'}));
  for(const action of ['inspect','distribution','edit_distribution','canonical_asw']){
    const request={action,source:'literal',panels:4};
    assert.deepEqual(numericalRequest(request,COUPLED_NUMERICS),{...request,numerics:COUPLED_NUMERICS});
    assert.deepEqual(numericalRequest({...request,numerics:undefined},COUPLED_NUMERICS),request);
  }
  const request={action:'solve',mode:'mounted',source:'literal',condition:{speed:10,freeze_influences:true},operating_constraints:[{variable:'alpha',quantity:'CL',target:.4}],controller:null,derivatives:null,strut_mode:'bilateral'},before=structuredClone(request);
  assert.deepEqual(numericalRequest(request,COUPLED_NUMERICS),{...request,numerics:COUPLED_NUMERICS});
  assert.deepEqual(request,before);
  const stack={...request,action:'operating_points',operating_points:{points:[{condition:{alpha:2}}]}};
  assert.deepEqual(numericalRequest(stack,COUPLED_NUMERICS),{...stack,numerics:COUPLED_NUMERICS});
  assert.throws(()=>numericalRequest({...stack,mode:'rigid'},COUPLED_NUMERICS),/mounted aeroelastic/);
  for(const policy of [SOURCE_NUMERICS,SECTION_NUMERICS])assert.throws(()=>numericalRequest(stack,policy),/structural static/);
  for(const action of ['time','modes','frequency','launch_time','resume_time','flow_survey','stability','rom'])assert.throws(()=>numericalRequest({action,source:'literal'},COUPLED_NUMERICS),/mounted aeroelastic/);
});

test('policy and analysis compatibility is explicit across all modes',()=>{
  const policies=[undefined,SOURCE_NUMERICS,SECTION_NUMERICS,COUPLED_NUMERICS];
  const modes=['rigid','mounted','structural','time','modes','frequency'];
  for(const numerics of policies)for(const mode of modes){
    const selection=numericalSelection(numerics),allowed=numerics===undefined||mode===(numerics===COUPLED_NUMERICS?'mounted':'structural');
    assert.equal(selectionAllowsMode(selection,mode),allowed);
    const config={...configuration(),fields:{mode},...(numerics?{numerics}:{}),equilibrium:{state:null,enabled:false,label:''}};
    const request={action:'solve',mode,source:config.source};
    if(allowed){assert.deepEqual(validateConfiguration(config),config);assert.doesNotThrow(()=>numericalRequest(request,numerics));}
    else {assert.throws(()=>validateConfiguration(config));assert.throws(()=>numericalRequest(request,numerics));}
  }
  // This is also the rollback mode when a dirty/busy change is rejected.
  assert.equal(numericalMode(selectedNumerics('aswing-coupled')),'mounted');
  assert.equal(numericalMode(selectedNumerics('aswing-section')),'structural');
});

test('coupled mounted solution roundtrip retains bytes and rejects cross-policy or dynamic reuse',async()=>{
  const saved=await sourceSolution(COUPLED_NUMERICS),encoded=JSON.stringify(saved);
  const restored=parseProject(JSON.stringify({...emptyProject(),solutions:[saved],selected_solution:saved.id})).solutions[0];
  await verifySolution(restored);assert.equal(JSON.stringify(restored),encoded);
  for(const mutate of [v=>v.configuration.fields.mode='structural',v=>v.configuration.numerics=SECTION_NUMERICS,
    v=>v.data.numerics=SOURCE_NUMERICS,v=>v.data.request.numerics=SECTION_NUMERICS,v=>delete v.data.request.numerics,
    v=>v.data.request.mode='structural',v=>v.data.request.action='time',v=>v.kind='structural',
    v=>v.data.structural_operator=SECTION_NUMERICS.structural_operator,v=>v.data.equilibrium_state.identity=SECTION_NUMERICS,
    v=>v.data.equilibrium_state.launch={},v=>delete v.data.equilibrium_state]){
    const bad=structuredClone(saved);mutate(bad);assert.throws(()=>validateSolution(bad));
  }
});

test('all source policies preserve version-2 hinge charts in saved configurations and sealed solutions',async()=>{
  for(const numerics of [SOURCE_NUMERICS,SECTION_NUMERICS,COUPLED_NUMERICS]){
    const candidate=await sourceSolution(numerics),hinged={...state(numerics),version:2,
      positions:[[0,0,0],[0,1,0]],identity:{...numerics,constraints:[
        {kind:'ground',type:0,a:0,b:null},{kind:'joint',type:3,a:0,b:1}]},
      hinge_charts:[{joint:1,angle_rad:400*Math.PI/180}]};
    candidate.configuration.equilibrium={state:structuredClone(hinged),enabled:true,label:'Lifted hinge'};
    candidate.data.equilibrium_state=structuredClone(hinged);
    const sealed=await sealSolution(candidate),encoded=JSON.stringify(sealed);
    const restored=parseProject(JSON.stringify({...emptyProject(),solutions:[sealed],selected_solution:sealed.id})).solutions[0];
    await verifySolution(restored);assert.equal(JSON.stringify(restored),encoded);
    assert.deepEqual(restored.data.equilibrium_state.hinge_charts,hinged.hinge_charts);
    assert.deepEqual(restored.configuration.equilibrium.state.hinge_charts,hinged.hinge_charts);
    for(const mutate of [v=>delete v.data.equilibrium_state.hinge_charts,
      v=>v.configuration.equilibrium.state.hinge_charts[0].joint=2,
      v=>v.data.equilibrium_state.hinge_charts[0].angle_rad=Infinity,
      v=>v.data.equilibrium_state.launch={}]){
      const bad=structuredClone(sealed);mutate(bad);assert.throws(()=>validateSolution(bad));
    }
  }
});

test('retained general-section source project keeps sealed bytes and policy when reopened',async()=>{
  const original=JSON.parse(await readFile(new URL('../examples/source-section-check-project.json',import.meta.url),'utf8'));
  assert(original.solutions.length>0);
  const restored=parseProject(JSON.stringify(original));
  for(let i=0;i<original.solutions.length;i++){
    assert.equal(JSON.stringify(restored.solutions[i]),JSON.stringify(original.solutions[i]));
    assert.deepEqual(restored.solutions[i].configuration.numerics,SECTION_NUMERICS);
    await verifySolution(restored.solutions[i]);
  }
});
