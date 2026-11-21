// Current Python sources in offline Node/Pyodide; no UI or distributed-build claim.
// Usage: timeout --kill-after=5s 120s node scripts/test-null-point-objects-wasm.mjs NEW_OUTPUT_DIR
import assert from 'node:assert/strict';
import {readFile, readdir, writeFile, mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {syncBuiltinESMExports} from 'node:module';
import http from 'node:http';
import https from 'node:https';
import net from 'node:net';
import tls from 'node:tls';
import dgram from 'node:dgram';
import path from 'node:path';

const script=fileURLToPath(import.meta.url), root=path.resolve(path.dirname(script),'..');
assert.equal(process.argv.length,3,'Supply one new evidence directory.');
const output=path.resolve(process.argv[2]);
await mkdir(output,{recursive:false});
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const pin=async file=>{const bytes=await readFile(file);return {path:file,bytes:bytes.length,sha256:sha(bytes)};};
const save=(name,value)=>writeFile(path.join(output,name),JSON.stringify(value,null,2)+'\n');
const revision='f62943df20e9e4d7d9f50e070477b22426b5f865';
const cache=path.join(root,'.reference/isae-validation',revision);
const inputSpecs=[
  ['AE1','4 - Aeroelasticity/AE - Aeroelastic Cases/AE-1-S Pazy Wing - Steady Deflection/Pazy_wing.asw',
    '5086107d412ebf8f43ef75173fe553914fb074dd7dca3b93f7bd56ab365c17c8'],
  ['ST2 bending','3 - Structure/CASE - ST2 Pazy_Wing/Pazy_wing_bending_bench.asw',
    '63050f789d1c17bb7d61c2a9c10b30d0bfc2c7ef58b75c443fba817d6b1cf1c1'],
  ['ST2 torsion','3 - Structure/CASE - ST2 Pazy_Wing/Pazy_wing_torsion_bench.asw',
    'c180191f4d3ce2169d3829d85073b0277d6ce6699257a071c7abe58904335aab']
];
const started=performance.now(), attempts=[];
const report={status:'PREPARING',scope:'Current source modules loaded directly into offline Node/Pyodide. This does not test browser UI, public/kernel, dist, downloadable bundles or their freshness.',
  planned:{standalone_equilibrium_solves:0,case_groups:6,process_cap_seconds:120},
  network_attempts:attempts,checks:[],node:process.version,repository_builds:0,downloads:0};
let pins=[];
try{
  const moduleNames=(await readdir(path.join(root,'openswing'))).filter(n=>n.endsWith('.py')).sort();
  assert(moduleNames.includes('point_objects.py'));
  const moduleBytes={},modules={};
  for(const name of moduleNames){
    const file=path.join(root,'openswing',name),bytes=await readFile(file);
    moduleBytes[name]=bytes;modules[name]=sha(bytes);
    pins.push({path:file,bytes:bytes.length,sha256:modules[name]});
  }
  const runtimeNames=(await readdir(path.join(root,'public/runtime'))).sort();
  assert(runtimeNames.includes('pyodide.asm.wasm'));
  assert(runtimeNames.some(n=>n.startsWith('numpy-')&&n.endsWith('.whl')));
  assert(runtimeNames.some(n=>n.startsWith('scipy-')&&n.endsWith('.whl')));
  const helperPath=path.join(root,'tests/test_source_coupled.py');
  const helperSource=await readFile(helperPath,'utf8');
  const inputs=[];
  for(const [name,relative,expected] of inputSpecs){
    const file=path.join(cache,relative),bytes=await readFile(file);
    assert.equal(sha(bytes),expected,name+' original source pin');
    const sourcePin={path:file,bytes:bytes.length,sha256:expected};pins.push(sourcePin);
    inputs.push({name,source:bytes.toString('utf8'),pin:sourcePin});
  }
  const otherFiles=[script,helperPath,...runtimeNames.map(n=>path.join(root,'public/runtime',n)),
    ...['package.json','pyodide.mjs','pyodide.asm.mjs','pyodide-lock.json'].map(n=>path.join(root,'node_modules/pyodide',n))];
  pins.push(...await Promise.all(otherFiles.map(pin)));
  const plan={...report,modules,module_count:moduleNames.length,pins,
    equations:'Exact zero elimination under steady Eqs.95–96/164 and unsteady Eqs.46–47; no legacy executable parity assertion.',
    equality_gate:'Exactly identical finite residual arrays for same-runtime baseline versus null-augmented model; no fitted or widened tolerance.',
    helper_scope:'Extract only source() and trial() AST function definitions from pinned test_source_coupled.py; no pytest or test suite execution.',
    inputs:inputs.map(({name,pin})=>({name,pin}))};
  await save('plan.json',plan);
  report.modules=modules;report.module_count=moduleNames.length;report.plan=await pin(path.join(output,'plan.json'));
  const block=kind=>(...args)=>{
    const description=args.map(v=>typeof v==='string'?v:v?.href||v?.hostname||typeof v).join(' ');
    attempts.push({kind,description});throw Error('Network disabled: '+kind+' '+description);
  };
  globalThis.fetch=block('fetch');
  http.request=block('http.request');http.get=block('http.get');
  https.request=block('https.request');https.get=block('https.get');
  net.connect=block('net.connect');net.createConnection=block('net.createConnection');
  net.Socket.prototype.connect=block('Socket.connect');tls.connect=block('tls.connect');
  dgram.createSocket=block('dgram.createSocket');
  globalThis.WebSocket=class{constructor(...args){block('WebSocket')(...args);}};
  syncBuiltinESMExports();report.network_blocker_installed=true;report.status='RUNNING';
  await save('report.json',report);
  const {loadPyodide}=await import('pyodide');
  const py=await loadPyodide({indexURL:path.join(root,'public/runtime')});
  await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');
  for(const name of moduleNames)py.FS.writeFile('/home/pyodide/openswing/'+name,moduleBytes[name]);
  py.globals.set('original_inputs_json',JSON.stringify(inputs));
  py.globals.set('helper_source',helperSource);
  report.pyodide_version=py.version;
  const encoded=await py.runPythonAsync(`
import ast, json, hashlib, sys, time
import numpy as np
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.geometry import model_meshes, attachment_geometry
from openswing.network import StaticNetwork
from openswing.source_coupled import SourceCoupledNetwork
from openswing.linear_dynamics import DynamicSystem
from openswing.point_objects import active_weights, null_weight

tree=ast.parse(helper_source)
tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('source','trial')]
assert len(tree.body)==2
exec(compile(tree,'pinned-source-fixtures.py','exec'))
inputs=json.loads(original_inputs_json)
checks=[]
def record(name,**details):
 checks.append(dict(name=name,passed=True,**details));print('WASM PASS',name,flush=True)
def equality(a,b):
 a,b=np.asarray(a),np.asarray(b)
 assert a.shape==b.shape and np.all(np.isfinite(a)) and np.all(np.isfinite(b))
 np.testing.assert_array_equal(a,b)
 return dict(scalars=int(a.size),maximum_absolute_difference=float(np.max(abs(a-b),initial=0.)))
def parse(text):return parse_asw(text,beam_interpolation='drela-segspl-v1')

# Literal AE1 has valid .55 sensors and two fully null .558 Weight records.
text=inputs[0]['source'];m=parse(text)
assert hashlib.sha256(text.encode()).hexdigest()==inputs[0]['pin']['sha256']
assert [r[1] for r in m.records['weight']]==[.558,.558]
assert all(null_weight(r) for r in m.records['weight']) and active_weights(m)==[]
mesh=model_meshes(m,{'default':80,'beams':{'1':{'count':80,'spacing':'uniform'}}})[0]
assert mesh.t1[-1]==.55 and .52 in mesh.t1
n=SourceCoupledNetwork(m,4,FlightCondition(speed=10,alpha=5,density=1.23,mach=0),None,[])
residual=n.residual(np.zeros(n.size),1.)
assert np.all(np.isfinite(residual)) and n.weights==[] and m.dumps()==text
record('literal AE1 unchanged mesh and finite source-coupled residual',
 mesh_intervals=len(mesh.tm),residual_scalars=len(residual),maximum_absolute_residual=float(np.max(abs(residual))),
 converged_equilibrium_claimed=False,raw_weight_stations=[float(r[1]) for r in m.records['weight']])

first='1 2 .4 1 .3 2 .002 .003 .01 -.02 .03 .2 .3 .4 .01 -.02 .03'
second='1 3 -.2 2 .1 3 .004 .006 -.02 .01 -.01 .3 .4 .5 -.02 .01 -.01'
null='1 99 1 -4 -20 0'
extras=['Weight\\n'+first+'\\n'+second+'\\nEnd\\n',
 'Weight\\n'+null+'\\n'+first+'\\n1 1.37 -.8 7 -30 -0\\n'+second+'\\n'+null+'\\nEnd\\n']
def condition():return FlightCondition(speed=8,alpha=4,beta=2,density=1.2,mach=0,
 controls={1:.15},ground_effect=1,position_earth=[0,0,30])
for cls in (StaticNetwork,SourceCoupledNetwork):
 models=[parse(source()+extra) for extra in extras]
 original_text=[z.dumps() for z in models]
 networks=[cls(z,4,condition(),[1,-2,-10],[]) for z in models]
 a,b=networks;x=trial(a)
 assert a.size==b.size and len(b.weights)==2 and len(models[1].records['weight'])==5
 assert b.inertia_model.source_point_indices==[1,3]
 metric=equality(a.residual(x,.6),b.residual(x,.6))
 for network in networks:
  r,q,*_=network.unpack(x)
  assert len(network.point_positions(r,q))==2
  assert len([o for o in attachment_geometry(network.model) if o['kind']=='weight'])==2
 assert [z.dumps() for z in models]==original_text
 record(cls.__name__+' mixed active/null aerodynamic residual and point order',**metric,
  active_point_count=2,raw_augmented_point_count=5,original_active_row_numbers=[2,4])
 if cls is StaticNetwork:
  systems=[DynamicSystem(network,x,'fixed') for network in networks]
  assert systems[0].size==systems[1].size
  rng=np.random.default_rng(512)
  state,rate=rng.normal(0,1e-4,(2,systems[0].size))
  metric=equality(systems[0].residual(state,rate),systems[1].residual(state,rate))
  assert np.linalg.norm(state)>0 and np.linalg.norm(rate)>0
  record('mixed active/null complete dynamic residual',**metric,state_and_rate_nonzero=True)

# Every physical coefficient keeps an invalid anchor active, including tiny values.
rejected=[]
for field in range(5,17):
 model=parse(source()+'Weight\\n'+null+'\\nEnd\\n')
 model.records['weight'][0][field]=1e-200
 assert not null_weight(model.records['weight'][0])
 try:model_meshes(model,4)
 except ValueError as exc:assert 'outside' in str(exc);rejected.append(field)
 else:raise AssertionError('Nonzero invalid anchor accepted')
record('all twelve nonzero physical fields retain outside-domain rejection',fields=rejected,value=1e-200)
original_rejections=[]
for entry in inputs[1:]:
 model=parse(entry['source'])
 assert all(not null_weight(r) for r in model.records['weight'])
 try:model_meshes(model,4)
 except ValueError as exc:assert 'outside' in str(exc);original_rejections.append(entry['name'])
 else:raise AssertionError('Active original ST2 anchor accepted')
 assert model.dumps()==entry['source']
record('literal loaded ST2 bending/torsion anchors still reject',cases=original_rejections)
assert len(checks)==6
json.dumps(dict(checks=checks,python=sys.version,
 loaded_module_paths={name:mod.__file__ for name,mod in sys.modules.items() if name.startswith('openswing.')},
 standalone_equilibrium_solves=0),allow_nan=False)
`);
  const result=JSON.parse(encoded);report.checks=result.checks;report.python=result.python;
  report.loaded_module_paths=result.loaded_module_paths;report.standalone_equilibrium_solves=result.standalone_equilibrium_solves;
  assert.equal(report.checks.length,6);assert(report.checks.every(c=>c.passed));
  assert.equal(attempts.length,0,'Offline test attempted network access.');
  report.status='PASS';
}catch(error){
  report.status='FAIL';report.error=String(error?.stack||error);process.exitCode=1;
}finally{
  report.elapsed_seconds=(performance.now()-started)/1000;
  report.pins_unchanged=true;report.pin_failures=[];
  for(const expected of pins){
    const actual=await pin(expected.path);
    if(actual.sha256!==expected.sha256||actual.bytes!==expected.bytes){report.pins_unchanged=false;report.pin_failures.push({expected,actual});}
  }
  if(!report.pins_unchanged){report.status='FAIL';process.exitCode=1;}
  await save('report.json',report);
  await save('receipt.json',{status:report.status,report:await pin(path.join(output,'report.json')),
    plan:report.plan,script:await pin(script),pins_unchanged:report.pins_unchanged,
    process_pid:process.pid,exit_code:process.exitCode||0,network_attempts:attempts.length,
    standalone_equilibrium_solves:0,scope:report.scope});
  console.log(JSON.stringify({status:report.status,checks:report.checks.length,modules:report.module_count,
    seconds:report.elapsed_seconds,network_attempts:attempts.length,pins_unchanged:report.pins_unchanged,output}));
  if(report.error)console.error(report.error);
}
