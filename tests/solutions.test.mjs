import {test} from 'node:test';
import assert from 'node:assert/strict';
import {emptyProject,validateProject,parseProject,changeCase} from '../web/project-data.js';
import {sealSolution,verifySolution,validateSolution,portableResult,kernelFingerprint,solutionChecksum,continuedHistorySources} from '../web/solution-data.js';
const configuration=()=>({source:'Name\nOriginal\nEnd\n',filename:'original.asw',mesh:4,fields:{mode:'rigid'},controls:{},powers:{},circulation:{},derivative_parameters:[],constraints:[],equilibrium:{state:null,enabled:false,label:''}});
const provenance=()=>({format:'openswing-kernel-provenance',version:1,modules:{'aero.py':'b'.repeat(64)},runtime:{pyodide:'test',python:'test',numpy:'test',scipy:'test'}});
async function solution(){const c=configuration(),p=provenance();p.fingerprint=await kernelFingerprint(p);return sealSolution({id:'solution-a',name:'Cruise',created_at:'2026-10-06T00:00:00Z',kind:'rigid',configuration:c,data:{analysis:'rigid_steady',converged:true,residual:1e-12,strips:[{circulation:2.5}],force:[1,2,3],mass_properties:{mass:5},limitations:[],request:{action:'solve',mode:'rigid',source:c.source,condition:{speed:12}},software_provenance:p},auxiliary:{},view:{active_tab:'tab-loading'},provenance:p});}
test('version-1 projects upgrade without inventing computed solutions',()=>{
  const p=emptyProject();p.version=1;delete p.solutions;delete p.selected_solution;
  const restored=parseProject(JSON.stringify(p));assert.equal(restored.version,2);assert.deepEqual(restored.solutions,[]);assert.equal(restored.selected_solution,null);
  assert.throws(()=>validateProject({...p,solutions:[]}),/version 2/);
});
test('saved values, inputs and provenance survive portable projects independently of case edits',async()=>{
  const s=await solution();let p=changeCase(emptyProject(),'add',{id:'case',name:'Inputs',configuration:configuration()});p={...p,solutions:[s],selected_solution:s.id};
  const restored=parseProject(JSON.stringify(p));await verifySolution(restored.solutions[0]);assert.deepEqual(restored,p);
  const removed=changeCase(p,'delete',{id:'case'});assert.deepEqual(removed.solutions,[s]);assert.equal(removed.selected_solution,s.id);
  s.data.strips[0].circulation=9;assert.equal(restored.solutions[0].data.strips[0].circulation,2.5);
});
test('checksums detect numerical, request, context and view corruption before display',async()=>{
  const s=await solution();
  for(const mutate of [x=>x.data.force[0]=9,x=>x.data.request.condition.speed=99,x=>x.configuration.fields.mode='mounted',x=>x.view.active_tab='tab-report']){
    const changed=structuredClone(s);mutate(changed);await assert.rejects(verifySolution(changed),/checksum mismatch/);
  }
  await verifySolution({...s,name:'Renamed'});
  const changed=structuredClone(s);changed.configuration.source+='\n';assert.throws(()=>validateSolution(changed),/do not match/);
});
test('nonfinite data, incompatible kinds, incomplete histories, duplicate records and missing provenance fail',async()=>{
  const s=await solution();
  for(const mutate of [x=>x.data.force[0]=NaN,x=>x.kind='time',x=>x.data.mass_properties=null,x=>x.provenance.fingerprint='bad',x=>x.data.software_provenance.runtime.pyodide='changed',x=>x.data.frequency_session='old-worker',x=>x.extra=true]){
    const changed=structuredClone(s);mutate(changed);assert.throws(()=>validateSolution(changed));
  }
  assert.throws(()=>validateProject({...emptyProject(),solutions:[s,s]}),/unique/);
  assert.throws(()=>validateProject({...emptyProject(),selected_solution:'missing'}),/missing/);
});
test('portable frequency results preserve all samples and gaps while dropping only the live worker handle',()=>{
  const r={frequency_session:'worker-owned',frequency_refinement:{retained_samples:2},samples:[{omega:1,converged:true},{omega:2,converged:false,error:'pole'}],request:{retain_frequency:true}};
  const saved=portableResult(r);assert.equal(r.frequency_session,'worker-owned');assert.equal(saved.frequency_session,undefined);assert.deepEqual(saved.samples,r.samples);assert.deepEqual(saved.request,r.request);
});
test('the numerical fingerprint is checked independently of the solution checksum',async()=>{
  const s=await solution();s.provenance.modules['aero.py']='c'.repeat(64);s.data.software_provenance=structuredClone(s.provenance);s.checksum=await solutionChecksum(s);
  await assert.rejects(verifySolution(s),/fingerprint/);
});
test('branching a time history retains old numerical origins without relabeling them as the new kernel',()=>{
  const a={fingerprint:'old'},b={fingerprint:'new'},parent={snapshots:Array(5),software_provenance:a},segment={snapshots:Array(3),software_provenance:b};
  const sources=continuedHistorySources(parent,1,segment);
  assert.deepEqual(sources,[{start_snapshot:0,end_snapshot:2,software_provenance:a},{start_snapshot:2,end_snapshot:4,software_provenance:b}]);
  const extended=continuedHistorySources({...segment,snapshots:Array(4),history_sources:sources},2,segment);
  assert.deepEqual(extended,[{start_snapshot:0,end_snapshot:2,software_provenance:a},{start_snapshot:2,end_snapshot:5,software_provenance:b}]);
  assert.deepEqual(continuedHistorySources({...parent,history_sources:sources},0,segment),[{start_snapshot:0,end_snapshot:1,software_provenance:a},{start_snapshot:1,end_snapshot:3,software_provenance:b}]);
  assert.equal(sources[1].end_snapshot,4);
});
