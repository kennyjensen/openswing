import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {sealSolution,verifySolution,validateSolution} from '../web/solution-data.js';
import {parseProject} from '../web/project-data.js';
const read=name=>JSON.parse(readFileSync(new URL(`./fixtures/source-moving-time-browser-${name}.json`,import.meta.url),'utf8'));
const data=read('result'),project=read('project');
const record=()=>({id:'captured-time',name:'Captured moving time',created_at:'2026-10-26T15:08:00Z',kind:'time',
  configuration:structuredClone(project.cases[0].configuration),data:structuredClone(data),auxiliary:{},view:{active_tab:'tab-time'},provenance:structuredClone(data.software_provenance)});

test('actual browser time result seals and restores without inventing equilibrium packets',async()=>{
  assert.equal(data.snapshots.length,5);
  assert(data.snapshots.every(s=>!Object.hasOwn(s,'equilibrium_state')));
  assert(data.snapshots.every(s=>s.restart.accepted_method.accepted_inputs.identity.structural_operator===data.structural_operator));
  const before=JSON.stringify(record()),sealed=await sealSolution(record());
  assert.equal(JSON.stringify(record()),before);
  const encoded=JSON.stringify({...project,solutions:[sealed],selected_solution:sealed.id});
  const restored=parseProject(encoded);await verifySolution(restored.solutions[0]);
  assert.deepEqual(restored.solutions[0],sealed);
  assert.equal(JSON.stringify(restored.solutions[0].data),JSON.stringify(data));
  assert(restored.solutions[0].data.snapshots.every(s=>!Object.hasOwn(s,'equilibrium_state')));
});

test('actual time identities remain binding in global, per-snapshot and accepted contexts',async()=>{
  const sealed=await sealSolution(record());
  for(const mutate of [
    s=>delete s.data.restart_context.identity,
    s=>s.data.restart_context.identity.structural_operator='midpoint-v1',
    s=>s.data.snapshots[2].restart_context={...structuredClone(s.data.restart_context),identity:{}},
    s=>delete s.data.snapshots[2].restart,
    s=>delete s.data.snapshots[2].restart.accepted_method.accepted_inputs.identity,
    s=>s.data.snapshots[2].restart.accepted_method.accepted_inputs.identity.structural_operator='midpoint-v1',
  ]){const changed=structuredClone(sealed);mutate(changed);assert.throws(()=>validateSolution(changed));}
  const owned=structuredClone(sealed);owned.data.snapshots[2].restart_context=structuredClone(owned.data.restart_context);
  assert.doesNotThrow(()=>validateSolution(owned));
});

test('captured browser fixtures retain exact original bytes',()=>{
  for(const [name,hash] of Object.entries({result:'b54c66b6054c48e073a6d7a04615ced637edcd18d95e64874c9d9e64fac79814',project:'f9516f5dee6e6da0a897269b270ffcaaf31da21f35d5094ff3b6a17fefb5fe2c'}))
    assert.equal(createHash('sha256').update(readFileSync(new URL(`./fixtures/source-moving-time-browser-${name}.json`,import.meta.url))).digest('hex'),hash);
});
