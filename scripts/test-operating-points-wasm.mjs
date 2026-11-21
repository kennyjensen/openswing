import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {loadPyodide} from 'pyodide';

const directory=process.argv[2]??'artifacts/isae/operating-points-20261030';
const native=JSON.parse(await readFile(path.join(directory,'native.json'),'utf8'));
const saved=process.argv.includes('--saved')?JSON.parse(await readFile(path.join(directory,'wasm.json'),'utf8')):null;
if(saved)assert.deepEqual(saved.module_hashes,native.modules,'Retained WASM output must identify the same kernel sources.');
const py=saved?null:await loadPyodide({indexURL:path.resolve('public/runtime')});
if(py){await py.loadPackage(['numpy','scipy']);py.FS.mkdirTree('/home/pyodide/openswing');}
const names=JSON.parse(await readFile('public/kernel/manifest.json','utf8'));
assert.deepEqual([...names].sort(),Object.keys(native.modules).sort());
for(const name of names){
  const bytes=await readFile(`public/kernel/${name}`);
  assert.equal(createHash('sha256').update(bytes).digest('hex'),native.modules[name]);
  if(py)py.FS.writeFile(`/home/pyodide/openswing/${name}`,bytes);
}
if(py)await py.runPythonAsync('from openswing.bridge import run_json');
const scalars=['CL','CD','CDi','CDi_near','CDp','Cm','CY','Cl','Cn','efficiency','max_displacement'];
let comparisons=0,maximumScaledError=0;
function close(actual,expected,label){
  assert.equal(typeof actual,'number',label);assert(Number.isFinite(actual),label);
  const error=Math.abs(actual-expected)/Math.max(1,Math.abs(expected));
  maximumScaledError=Math.max(error,maximumScaledError);comparisons++;
  assert(error<=2e-8,`${label}: ${actual} vs ${expected}; scaled ${error}`);
}
const cases=[];
for(const [index,fixture] of native.cases.entries()){
  if(py)py.globals.set('request_json',JSON.stringify(fixture.request));
  const result=saved?saved.cases[index]:JSON.parse(await py.runPythonAsync('run_json(request_json)'));
  assert.equal(result.converged_points,fixture.result.converged_points);
  assert.equal(result.failed_points,fixture.result.failed_points);
  assert.equal(result.points.length,fixture.result.points.length);
  for(const [i,point] of result.points.entries()){
    const expected=fixture.result.points[i];assert.equal(point.converged,expected.converged);
    assert.deepEqual(point.condition,expected.condition);
    assert.deepEqual(point.initialization,expected.initialization);
    if(!point.converged){assert.equal(point.error.type,expected.error.type);assert(point.error.message.includes('Mach'));continue;}
    assert(point.result.residual<1e-7);
    for(const key of scalars)if(typeof expected.result[key]==='number')close(point.result[key],expected.result[key],`${index}/${i}/${key}`);
    for(const key of ['force','moment'])expected.result[key].forEach((value,j)=>close(point.result[key][j],value,`${index}/${i}/${key}/${j}`));
    close(point.actual_condition.alpha,expected.actual_condition.alpha,`${index}/${i}/alpha`);
    assert.equal(point.result.strips.length,expected.result.strips.length);
    expected.result.strips.forEach((strip,j)=>{
      for(const key of ['circulation','cl','cm'])close(point.result.strips[j][key],strip[key],`${index}/${i}/strip/${j}/${key}`);
      strip.force.forEach((value,k)=>close(point.result.strips[j].force[k],value,`${index}/${i}/strip/${j}/force/${k}`));
    });
    if(expected.result.equilibrium_state){
      for(const key of ['positions','rotations','internal_force','internal_moment','reactions','circulation']){
        const actualValues=point.result.equilibrium_state[key].flat(),expectedValues=expected.result.equilibrium_state[key].flat();
        assert.equal(actualValues.length,expectedValues.length);
        expectedValues.forEach((value,j)=>close(actualValues[j],value,`${index}/${i}/state/${key}/${j}`));
      }
    }
  }
  cases.push(result);
}
const report={passed:true,modules:names.length,module_hashes:native.modules,comparisons,maximumScaledError,tolerance:2e-8,
  verification:saved?'Rechecked retained final WASM output; zero new solves':'Fresh packaged WASM solves',cases};
await writeFile(path.join(directory,'wasm.json'),JSON.stringify(report,null,2)+'\n');
console.log(`Packaged WASM: ${comparisons} numerical comparisons pass; max scaled difference ${maximumScaledError}.`);
