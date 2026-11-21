import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseProject} from '../web/project-data.js';

const text=path=>readFileSync(new URL(path,import.meta.url),'utf8');
const projectText=text('../examples/dae-level-flight-project.json');
const project=parseProject(projectText);
const main=text('../web/main.js');

test('published Daedalus cases use exact values accepted by static dropdowns',()=>{
  // Numeric equality is insufficient for an HTML select ("1.0" !== "1").
  const selects=[...main.matchAll(/<select\b[^>]*id="([^"]+)"[^>]*>([\s\S]*?)<\/select>/g)]
    .filter(([,id,html])=>id!=='example'&&!html.includes('${'))
    .map(([,id,html])=>[id,[...html.matchAll(/<option\b[^>]*value="([^"]*)"/g)].map(m=>m[1])]);
  for(const entry of project.cases)for(const [id,choices] of selects){
    if(!choices.length||!Object.hasOwn(entry.configuration.fields,id))continue;
    assert.ok(choices.includes(entry.configuration.fields[id]),`${entry.id}: ${id}`);
  }
  assert.ok(selects.some(([id,choices])=>id==='body-added-mass'&&choices.includes('1')));
});

test('Daedalus Bode case releases trim targets and preserves the checked physical state',()=>{
  assert.equal(text('../public/examples/dae-level-flight-project.json'),projectText);
  const bode=project.cases.find(c=>c.id==='dae-level-bode').configuration;
  const trim=project.cases.find(c=>c.id==='dae-level-trim').configuration;
  assert.deepEqual(bode.constraints,[]);
  assert.equal(trim.constraints.length,7);
  assert.equal(bode.fields.mode,'frequency');
  assert.equal(bode.fields['frequency-frame'],'free');
  assert.equal(bode.fields['frequency-inputs'],'controls');
  assert.equal(bode.fields['frequency-count'],'41');
  assert.equal(bode.fields['frequency-spacing'],'log');
  assert.ok(Math.abs(Number(bode.fields['frequency-start'])/(2*Math.PI)-.1)<1e-14);
  assert.ok(Math.abs(Number(bode.fields['frequency-end'])/(2*Math.PI)-10)<1e-14);
  assert.equal(bode.equilibrium.enabled,true);
  assert.deepEqual(bode.equilibrium,trim.equilibrium);
  assert.deepEqual(bode.equilibrium.state,JSON.parse(text('../artifacts/daedalus-regular-mesh-20261114/trim-1/state.json')));
  assert.deepEqual(bode.mesh,bode.equilibrium.state.launch.panels);
  assert.deepEqual(bode.mesh,JSON.parse(text('../web/daedalus-mesh.json')));
  assert.equal(bode.source,text('../examples/dae.asw'));
});

test('rendered control inputs accept the fractional settings in both checked Daedalus cases',()=>{
  // Exercise the actual generated inputs without starting the aircraft kernel.
  // Number inputs default to a whole-number grid unless their step allows more.
  const start=main.indexOf('    for (const control of model.controls) {');
  const end=main.indexOf("    $('powers').replaceChildren();",start);
  assert.ok(start>=0&&end>start);
  const render=new Function('document','$','model','oldControls','resetResult',main.slice(start,end));
  const element=()=>({children:[],dataset:{},value:'',step:'',
    append(child){this.children.push(child);},addEventListener(){}});
  const accepts=input=>{
    const value=Number(input.value);
    if(input.value===''||!Number.isFinite(value))return false;
    if(input.step==='any')return true;
    const step=Number(input.step)||1,units=value/step;
    return Math.abs(units-Math.round(units))<1e-10;
  };
  for(const entry of project.cases){
    const controls=entry.configuration.controls;
    // Both initial loading and re-inspection of an edited model use this renderer.
    for(const oldControls of [{},controls]){
      const container=element();
      render({createElement:element},id=>{assert.equal(id,'controls');return container;},
        {controls:Object.keys(controls)},oldControls,()=>{});
      assert.equal(container.children.length,Object.keys(controls).length);
      for(const label of container.children){
        const input=label.children[0],saved=controls[input.dataset.control];
        assert.ok(accepts(input),`${entry.id}: initial ${label.textContent}`);
        // applySettings restores the saved text exactly; do not round the trim.
        input.value=saved;
        assert.equal(Number(input.value),Number(saved));
        assert.ok(accepts(input),`${entry.id}: ${label.textContent} = ${saved}`);
        input.value='';assert.equal(accepts(input),false);
      }
    }
  }
});

test('operating-condition errors identify the invalid field and browser reason',()=>{
  const start=main.indexOf("      const label=input.labels?.[0]?.textContent.trim()");
  const end=main.indexOf('      if(stack)throw error;',start);
  assert.ok(start>=0&&end>start);
  const errorFor=new Function('input',main.slice(start,end)+'return error;');
  const input={labels:[{textContent:'Flap 2'}],value:'-8.825752955534778',
    validationMessage:'Please enter a valid value.',getAttribute(){return null;}};
  assert.equal(errorFor(input).message,'Check Flap 2: Please enter a valid value.');
  input.value='';
  assert.equal(errorFor(input).message,'Check Flap 2: A value is required.');
  input.labels=[];input.id='speed';
  assert.equal(errorFor(input).message,'Check speed: A value is required.');
});
