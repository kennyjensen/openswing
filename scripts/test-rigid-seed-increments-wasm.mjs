import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {loadPyodide} from 'pyodide';

const directory=process.argv[2]??'artifacts/isae/rigid-seed-increments-20261030';
const native=JSON.parse(await readFile(path.join(directory,'seed-native.json'),'utf8'));
const py=await loadPyodide({indexURL:path.resolve('public/runtime')});
await py.loadPackage(['numpy','scipy']);py.FS.mkdirTree('/home/pyodide/openswing');
for(const [name,hash] of Object.entries(native.module_hashes)){
  const bytes=await readFile(`public/kernel/${name}`);
  assert.equal(createHash('sha256').update(bytes).digest('hex'),hash);
  py.FS.writeFile(`/home/pyodide/openswing/${name}`,bytes);
}
await py.runPythonAsync('from openswing.bridge import run_json');
let comparisons=0,maximumScaledError=0;
let relativeCirculationComparisons=0,maximumRelativeCirculationError=0;
function close(a,b,label){
  assert.equal(typeof a,'number',label);assert(Number.isFinite(a),label);
  const error=Math.abs(a-b)/Math.max(1,Math.abs(b));
  comparisons++;maximumScaledError=Math.max(maximumScaledError,error);
  assert(error<2e-8,`${label}: ${a} vs ${b}`);
}
const results=[];
for(const [index,fixture] of native.cases.entries()){
  py.globals.set('request_json',JSON.stringify(fixture.request));
  const result=JSON.parse(await py.runPythonAsync('run_json(request_json)'));
  results.push(result);
  assert(result.converged&&result.residual<1e-10);
  const seed=result.circulation_solver.initialization;
  assert(seed.seed_attempt.accepted&&!seed.cold_fallback);
  assert.deepEqual(seed.initial_circulation,fixture.request.initial_circulation);
  assert.equal(seed.coordinates,'dimensionless increment from supplied coefficients');
  for(const key of ['force','moment','CL','CD','CDi','Cm','efficiency']){
    const a=[result[key]].flat(),b=[fixture.result[key]].flat();
    assert.equal(a.length,b.length);
    b.forEach((v,i)=>close(a[i],v,`${index}/${key}/${i}`));
  }
  assert.equal(result.strips.length,fixture.result.strips.length);
  fixture.result.strips.forEach((strip,i)=>{
    for(const key of ['circulation','cl','cm','force','moment']){
      const a=[result.strips[i][key]].flat(),b=[strip[key]].flat();
      b.forEach((v,j)=>close(a[j],v,`${index}/strip/${i}/${key}/${j}`));
    }
  });
  if(fixture.request.condition.alpha===0){
    assert.equal(result.efficiency,0);
    assert(result.strips.every(strip=>Math.abs(strip.circulation)<1e-300));
  }else if(Math.abs(fixture.request.condition.alpha)<1e-10){
    const scale=Math.max(...fixture.result.strips.map(strip=>Math.abs(strip.circulation)));
    assert(scale>0);
    fixture.result.strips.forEach((strip,i)=>{
      const error=Math.abs(result.strips[i].circulation-strip.circulation)/scale;
      relativeCirculationComparisons++;maximumRelativeCirculationError=Math.max(maximumRelativeCirculationError,error);
      assert(error<2e-8);
    });
  }
}
await writeFile(path.join(directory,'seed-wasm.json'),JSON.stringify({passed:true,module_hashes:native.module_hashes,
  comparisons,maximumScaledError,relativeCirculationComparisons,maximumRelativeCirculationError,tolerance:2e-8,results},null,2)+'\n');
console.log(`${comparisons} seeded WASM comparisons and ${relativeCirculationComparisons} relative circulation checks pass; max scaled difference ${maximumScaledError}.`);
