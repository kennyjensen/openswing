import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {isSA12Example,sa12BaselineConfiguration} from '../web/sa12-baseline.js';
import {validateConfiguration,emptyProject,changeCase,parseProject} from '../web/project-data.js';
import {DEFAULT_NUMERICS,numericalSelection} from '../web/numerical-policy.js';

const read=path=>readFileSync(new URL('../'+path,import.meta.url),'utf8');
const planSource=read('artifacts/isae/sa12-current-pilot-20261108/plan.json');
assert.equal(createHash('sha256').update(planSource).digest('hex'),'3100337987a55d3eaa3f49a0e036c099d93b2907793cc70602f2eb754445c862');
const plan=JSON.parse(planSource);
const prior=key=>({source:read(`examples/${key}.asw`),filename:`${key}.asw`,
  mesh:{default:16,beams:{'1':{nodes:[-1,-.2,0,.2,1]}}},
  numerics:{beam_interpolation:'drela-segspl-v1',structural_operator:'drela-steady-coupled-v1'},
  fields:{mode:'mounted',speed:'150',alpha:'12',beta:'6',stall:false,'gust-kind':'uniform',
    'freeze-influences':true,'position-earth-z':'20','attitude-elevation':'3',
    'derivatives-enable':true,'feedback-enabled':true,'time-forcing':'retained inactive time input'},
  controls:{'1':'4'},powers:{'1':'50'},circulation:{'1':'8'},
  constraints:[{variable:'alpha',quantity:'CL',target:.5}],derivative_parameters:['alpha'],
  equilibrium:{enabled:true,label:'old equilibrium',state:{format:'openswing-equilibrium',version:1,positions:[]}},
});

for(const [key,id] of [['isae-sa12-plain-wing','No_Flap-h05-a8'],['isae-sa12-slotted-flap','Flap-h05-a-0']]) {
  test(`${key} baseline matches the pinned physical pilot inputs`,()=>{
    const before=prior(key),original=structuredClone(before),actual=sa12BaselineConfiguration(before,key);
    const reference=plan.cases.find(c=>c.id===id),settings=reference.job.settings,f=actual.fields;
    assert.equal(actual.source,read(reference.job.model_path));
    assert.equal(actual.source,read(`public/examples/${key}.asw`));
    assert.equal(actual.mesh,settings.panels);
    assert.equal(numericalSelection(actual.numerics),'midpoint');
    assert.equal(DEFAULT_NUMERICS.beam_interpolation,settings.beam_interpolation);
    for(const [field,setting] of [['speed','speed'],['alpha','alpha'],['beta','beta'],['density','density'],
      ['pg-mach','mach'],['stall-factor','stall_factor'],['stall-width','stall_width'],
      ['wake-core-ratio','wake_core_ratio'],['body-added-mass','body_added_mass_factor'],['ground-effect','ground_effect']])
      assert.ok(Number(f[field])===settings[setting],`${field} differs from pilot`);
    for(const [field,setting] of [['stall','stall'],['freeze-influences','freeze_influences'],['aero-lag','aero_lag']])
      assert.equal(f[field],settings[setting]);
    for(const [prefix,axes,setting] of [['position-earth',['x','y','z'],'position_earth'],
      ['ground-normal',['x','y','z'],'ground_normal'],['attitude',['bank','elevation','heading'],'attitude']])
      axes.forEach((axis,i)=>assert.ok(Number(f[`${prefix}-${axis}`])===settings[setting][i]));
    assert.equal(f.mode,'rigid');assert.equal(f['density-mode'],'custom');assert.equal(f['mach-mode'],'fixed');
    assert.equal(f['gust-kind'],'none');assert.equal(f['fourier-wake-diagnostic'],false);
    for(const prefix of ['rates','acceleration','angular_acceleration'])
      for(const axis of ['x','y','z'])assert.equal(f[`${prefix}-${axis}`],'0');
    assert.deepEqual(actual.constraints,[]);assert.deepEqual(actual.equilibrium,{state:null,enabled:false,label:''});
    for(const name of ['controls','powers','circulation'])assert.deepEqual(actual[name],{'1':'0'});
    assert.equal(f['derivatives-enable'],false);assert.equal(f['feedback-enabled'],false);
    assert.deepEqual(actual.derivative_parameters,[]);
    assert.equal(f['time-forcing'],original.fields['time-forcing']);
    assert.deepEqual(before,original,'applying a baseline must not mutate the prior workspace');
    assert.deepEqual(validateConfiguration(actual),actual);
    const saved=changeCase(emptyProject(),'add',{id:'sa12',name:'SA-12 baseline',configuration:actual});
    assert.deepEqual(parseProject(JSON.stringify(saved)).cases[0].configuration,actual);
  });
}

test('only a currently selected matching SA-12 example can receive the preset',()=>{
  for(const key of ['rectangular','isae-sa11-wing-alone','__proto__','constructor','']) {
    assert.equal(isSA12Example(key),false);
    assert.throws(()=>sa12BaselineConfiguration(prior('isae-sa12-plain-wing'),key),/original SA-12/);
  }
  assert.throws(()=>sa12BaselineConfiguration(prior('isae-sa12-plain-wing'),'isae-sa12-slotted-flap'),/original SA-12/);
});
