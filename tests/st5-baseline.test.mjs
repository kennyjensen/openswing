// These tests exercise only configuration data; no worker, Vite or browser.
// Execution remains held with the other Node tests after the UserLAnd failures.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {st5Examples,isST5Example,st5BaselineConfiguration} from '../web/st5-baseline.js';
import {validateConfiguration,emptyProject,changeCase,parseProject} from '../web/project-data.js';
import {SECTION_NUMERICS} from '../web/numerical-policy.js';

const read = path => readFileSync(new URL('../'+path,import.meta.url),'utf8');
const provenance = JSON.parse(read('docs/validation/isae-st5-browser-presets-sources.json'));
const base = JSON.parse(read('examples/isae-st5-source-static-project.json')).cases[0].configuration;
function prior(key) {
  const value=structuredClone(base);
  value.filename=`${key}.asw`;value.source=read(`examples/${key}.asw`);
  value.mesh=7;delete value.numerics;
  Object.assign(value.fields,{mode:'mounted','static-gravity-mode':'custom',
    'static-gravity-z':'-2','strut-mode':'wire','derivatives-enable':true,'feedback-enabled':true});
  value.constraints=[{variable:'alpha',quantity:'CL',target:0.5}];
  value.derivative_parameters=['alpha'];
  value.equilibrium={enabled:true,label:'unrelated equilibrium',state:{}};
  value.circulation=Object.fromEntries(Object.keys(st5Examples[key].mesh.beams).map(k=>[k,'4']));
  return value;
}

for(const entry of provenance.cases) {
  test(`${entry.key}: comparison setup equals reviewed physical inputs and can be saved`,async()=>{
    const plan=JSON.parse(read(entry.reference_plan)),before=prior(entry.key),original=structuredClone(before);
    const next=await st5BaselineConfiguration(before,entry.key);
    assert.equal(next.source,read(plan.source));
    assert.equal(next.source,read(`public/examples/${entry.key}.asw`));
    assert.deepEqual(next.mesh,plan.meshes[0].panels);
    assert.deepEqual(next.numerics,SECTION_NUMERICS);
    assert.equal(next.fields.mode,'structural');
    assert.equal(next.fields['static-gravity-mode'],'file');
    assert.equal(next.fields['strut-mode'],'bilateral');
    assert.equal(next.fields['feedback-enabled'],false);
    assert.equal(next.fields['derivatives-enable'],false);
    assert.deepEqual(next.constraints,[]);assert.deepEqual(next.derivative_parameters,[]);
    assert.deepEqual(next.equilibrium,{state:null,enabled:false,label:''});
    for(const name of ['controls','powers','circulation'])
      assert(Object.values(next[name]).every(v=>v==='0'));
    assert.deepEqual(before,original,'do not mutate the current or saved workspace');
    assert.equal(next.fields['static-gravity-z'],'-2','inactive custom gravity text is retained');
    assert.deepEqual(validateConfiguration(next),next);
    const project=changeCase(emptyProject(),'add',{id:'st5',name:'ST-5 comparison',configuration:next});
    assert.deepEqual(parseProject(JSON.stringify(project)).cases[0].configuration,next);
    next.mesh.beams['1'].nodes[1]+=0.01;
    assert.deepEqual(st5Examples[entry.key].mesh,plan.meshes[0].panels,'mesh edits cannot alter the preset');
  });
}

test('reject changed, renamed, or unrelated source without mutating it',async()=>{
  const key=provenance.cases[0].key;
  const edited=prior(key);edited.source+='\n# edited source\n';
  const original=structuredClone(edited);
  await assert.rejects(st5BaselineConfiguration(edited,key),/source has changed/);
  assert.deepEqual(edited,original);
  const renamed=prior(key);renamed.filename='custom.asw';
  await assert.rejects(st5BaselineConfiguration(renamed,key),/original ST-5/);
  for(const other of ['', 'constructor', '__proto__', 'isae-sa12-plain-wing']) {
    assert.equal(isST5Example(other),false);
    await assert.rejects(st5BaselineConfiguration(prior(key),other),/original ST-5/);
  }
});

test('capture inputs before asynchronous source hashing yields',async()=>{
  const key=provenance.cases[0].key,before=prior(key),source=before.source;
  const pending=st5BaselineConfiguration(before,key);
  before.source='changed during verification';before.fields['static-gravity-z']='100';
  const result=await pending;
  assert.equal(result.source,source);assert.equal(result.fields['static-gravity-z'],'-2');
});
