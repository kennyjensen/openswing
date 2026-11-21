import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {isDaedalusSource,daedalusDefaultMesh,daedalusMeshConfiguration} from '../web/daedalus-mesh.js';

const source=readFileSync(new URL('../examples/dae.asw',import.meta.url),'utf8');
const before=()=>({source,filename:'my-dae.asw',mesh:16,
  fields:{speed:'21.982',alpha:'3.1',mode:'frequency'},controls:{2:'-1.2',3:'0'},
  constraints:[{variable:'alpha',quantity:'force.z',target:0}],
  equilibrium:{enabled:true,label:'old trim',state:{positions:[[1,2,3]]}}});

test('Daedalus defaults require the named five-beam model, not a filename or partial match',()=>{
  assert.equal(isDaedalusSource(source),true);
  assert.equal(isDaedalusSource(source.replaceAll('\n','\r\n')),true);
  for(const candidate of [null,'',source.replace('Daedalus HPA','Other aircraft'),
    source.replace('Beam 5','Beam 6'),source+'\nBeam 6\nExtra surface\nEnd\n']){
    assert.equal(isDaedalusSource(candidate),false);
    assert.equal(daedalusDefaultMesh(candidate),null);
  }
});

test('uniform component settings remain independent across imports and edits',()=>{
  const first=daedalusDefaultMesh(source),second=daedalusDefaultMesh(source);
  assert.deepEqual(Object.values(first.beams).map(b=>b.count),[48,12,10,16,8]);
  assert.ok(Object.values(first.beams).every(b=>b.spacing==='uniform-breaks'));
  first.beams['5'].count=64;
  assert.equal(second.beams['5'].count,8);
  assert.equal(daedalusDefaultMesh(source).beams['5'].count,8);
});

test('explicit remeshing preserves the flight configuration and clears the incompatible equilibrium',()=>{
  const old=before(),copy=structuredClone(old),next=daedalusMeshConfiguration(old);
  assert.deepEqual(old,copy);
  assert.deepEqual(next.mesh,daedalusDefaultMesh(source));
  assert.deepEqual(next.equilibrium,{state:null,enabled:false,label:''});
  for(const key of ['source','filename','fields','controls','constraints'])assert.deepEqual(next[key],old[key]);
  next.fields.speed='9';
  assert.equal(old.fields.speed,'21.982');
  assert.throws(()=>daedalusMeshConfiguration({...old,source:'Name\nOther\nEnd'}),/Daedalus/);
});
