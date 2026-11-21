// Offline current public/kernel verification; no UI, equilibrium or archive-parity claim.
// Run only after the source/public kernel freeze:
// timeout --kill-after=5s 120s node scripts/test-sensor-availability-wasm.mjs NEW_OUTPUT_DIR
import assert from 'node:assert/strict';
import {readFile,readdir,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {syncBuiltinESMExports} from 'node:module';
import http from 'node:http';
import https from 'node:https';
import net from 'node:net';
import tls from 'node:tls';
import dgram from 'node:dgram';
import path from 'node:path';

const script=fileURLToPath(import.meta.url),root=path.resolve(path.dirname(script),'..');
assert.equal(process.argv.length,3,'Supply one new evidence directory.');
const output=path.resolve(process.argv[2]);
await mkdir(output,{recursive:false});
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const pin=async file=>{const bytes=await readFile(file);return {path:file,bytes:bytes.length,sha256:sha(bytes)};};
const save=(name,value)=>writeFile(path.join(output,name),JSON.stringify(value,null,2)+'\n');
const moduleNames=async directory=>(await readdir(directory)).filter(name=>name.endsWith('.py')).sort();
const sourceDirectory=path.join(root,'openswing'),publicDirectory=path.join(root,'public/kernel');
const originalRelative='.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST1 High aspect ratio/Static_deflection/[45_0]_3a.asw';
const originalHash='dcfef35494730fa3976950f634a448592b2eeb0aff6e5e70894801c13964aade';
const started=performance.now(),attempts=[],pins=[];
const report={status:'PREPARING',scope:'Current public/kernel Python modules loaded into offline Node/Pyodide, with identical source-module hashes. This does not test browser UI, equilibrium convergence, archived ASWING output agreement, dist, downloadable bundles or hosted deployment.',
  planned:{standalone_equilibrium_solves:0,residual_evaluations:1,case_groups:6,nominal_intervals:4,process_cap_seconds:120},
  node:process.version,network_attempts:attempts,checks:[],repository_builds:0,downloads:0};
let names=[];
const fixture=String.raw`
import json, math, hashlib, sys
from pathlib import Path
import numpy as np
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.bridge import dispatch
from openswing.geometry import model_meshes, attachment_geometry
from openswing.inertia import Motion
from openswing.local_motion import LocalMotion
from openswing.sensors import measure_sensor
from openswing.source_discrete import SourceSectionNetwork

# This exact fixture can also run natively with input.json and an output path.
inputs=json.loads(original_input_json if 'original_input_json' in globals() else Path(sys.argv[1]).read_text())
checks=[]
def record(name,**details):
    checks.append(dict(name=name,passed=True,**details))
    print('PASS',name,flush=True)
def parse(text):
    return parse_asw(text,beam_interpolation='drela-segspl-v1')
def close(actual,expected):
    np.testing.assert_allclose(actual,expected,rtol=0.,atol=3e-14)

text=inputs['source']
assert hashlib.sha256(text.encode()).hexdigest()==inputs['pin']['sha256']
model=parse(text)
assert model.dumps()==text and len(model.records['sensor'])==1
row=model.records['sensor'][0]
np.testing.assert_array_equal(row,[1,1,-.22,0,-.22,0,1,1,1,1,1,1])
assert model.records['ground'][0][1]==.28
assert model.records['weight'][0][1]==-.28
assert model.records['weight'][0][5]==.4*9.81
inspect=dispatch(dict(action='inspect',source=text,panels=4,
    numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-steady-section-v1')))
sensor=inspect['sensors'][0]
assert sensor['axes_available'] is False and sensor['v_axis_available'] is True
assert 'parallel' in sensor['axes_unavailable_reason']
assert any('full triad' in warning for warning in inspect['diagnostics'])
assert model.diagnostics==[]
record('literal ST1 parse and inspect preserve source and distinguish nonfatal frame warning',
    source_sha256=inputs['pin']['sha256'],sensor_row=row.tolist(),inspected_sensor=sensor,
    inspection_warnings=inspect['diagnostics'],unrecognized_input_diagnostics=model.diagnostics)

mesh=model_meshes(model,4)[0]
stations=np.unique(np.r_[mesh.t0,mesh.t1])
assert -.22 in stations and -.28 in stations and .28 in stations
attachments=[entry for entry in attachment_geometry(model) if entry['kind']=='sensor']
assert len(attachments)==1 and len(attachments[0]['segments'])==1
close(attachments[0]['segments'][0],[[0,-.22,0],[0,-.22,0]])
assert attachments==[entry for entry in inspect['attachments'] if entry['kind']=='sensor']
network=SourceSectionNetwork(model,4,None,[0,0,-9.81],[])
sensor_node=network.node(1,-.22)
residual=network.residual(np.zeros(network.size),1.)
assert residual.size>0 and np.all(np.isfinite(residual))
assert model.dumps()==text
record('literal ST1 keeps mandatory sensor node and pylon with finite source structural residual',
    nominal_intervals=4,actual_intervals=len(mesh.tm),node_stations=stations.tolist(),
    sensor_node=int(sensor_node),attachments=attachments,residual_scalars=int(residual.size),
    maximum_absolute_residual=float(np.max(abs(residual))),
    residual_evaluations=1,equilibrium_convergence_claimed=False)

base='''Name
Independent sensor availability fixture
End
Units
L 1 m
T 1 s
M 1 kg
End
Constant
9.81 1.225 340
End
Reference
1 1 1
End
Beam 1
Beam
t x y z EIcc EInn GJ EA GKc GKn
0 0 0 0 100 100 100 1000 1000 1000
1 0 1 0 100 100 100 1000 1000 1000
End
'''
anchor=np.array([1.,2.,3.])
rotation=np.array([[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]])
local=LocalMotion(anchor,np.array([.2,-.1,.3]),np.array([0.,0.,.5]),
    np.array([-.1,.2,.4]),np.array([.02,-.03,.04]))
motion=Motion(np.array([0.,0.,.2]),np.array([.1,.2,.3]))
condition=FlightCondition(speed=13,mach=0,sensor_flow='full')
frame=dict(body_to_earth=np.eye(3),position_earth=np.array([4.,5.,6.]),
    velocity_origin_body=np.array([-10.,2.,-1.]))
def measure(directions):
    source=base+'Sensor\n1 1 .37 .3 .47 .2 '+directions+'\nEnd\n'
    model=parse(source)
    before=model.records['sensor'][0].copy()
    out=measure_sensor(model.records['sensor'][0],anchor,rotation,local,motion,
        model=model,condition=condition,gravity=np.array([0.,0.,-9.81]),
        airflow=np.array([3.,-4.,12.]),frame=frame)
    np.testing.assert_array_equal(model.records['sensor'][0],before)
    assert model.dumps()==source
    return out
dependent=('axes_body','axes_earth','alpha','beta','bank','air_velocity_sensor',
    'acceleration_sensor','angular_acceleration_sensor','rates_sensor')
parallel=measure('1 1 1 2 2 2')
assert parallel['axes_available'] is False and parallel['v_axis_available'] is True
assert all(parallel[field] is None for field in dependent)
assert parallel['speed']==13. and parallel['flow_singular'] is False
close(parallel['anchor_position_body'],[1,2,3])
close(parallel['position_body'],[.9,2.3,3.2])
close(parallel['position_earth'],[4.9,7.3,9.2])
close(parallel['velocity_earth'],[-10.41,2.03,-.7])
close(parallel['heading'],-135.)
close(parallel['elevation'],-math.degrees(math.atan2(1,math.sqrt(2))))
assert parallel['attitude_singular'] is False
record('independent parallel-A fixture retains speed GPS and V-axis angles',
    output=parallel,independent_position_earth=[4.9,7.3,9.2],
    independent_velocity_earth=[-10.41,2.03,-.7],scalar_absolute_gate=3e-14)

missing=measure('0 0 0 1 1 1')
assert missing['axes_available'] is False and missing['v_axis_available'] is False
assert all(missing[field] is None for field in (*dependent,'heading','elevation'))
assert missing['speed']==13. and missing['flow_singular'] is False
assert missing['attitude_singular'] is True
for field in ('position_body','position_earth','velocity_earth','anchor_position_body','displacement_body'):
    np.testing.assert_array_equal(missing[field],parallel[field])
record('missing-V fixture retains independent position velocity and scalar speed',output=missing)

valid=measure('1 0 0 0 0 1')
assert valid['axes_available'] is True and valid['v_axis_available'] is True
assert valid['axes_unavailable_reason'] is None
assert all(valid[field] is not None for field in dependent)
close(valid['axes_body'],rotation)
close(valid['air_velocity_sensor'],[-4,-3,12])
close(valid['speed'],13.)
close(valid['alpha'],math.degrees(math.atan2(12,-4)))
close(valid['beta'],math.degrees(math.atan2(3,math.hypot(4,12))))
close([valid['bank'],valid['elevation'],valid['heading']],[0,0,-90])
for field in ('position_earth','velocity_earth'):
    np.testing.assert_array_equal(valid[field],parallel[field])
for field in ('acceleration_sensor','angular_acceleration_sensor','rates_sensor'):
    assert np.all(np.isfinite(valid[field]))
record('valid-axis control retains projected measurements and original geometry',output=valid)

rejections=[]
for column in range(2,12):
    fields=['1','1','.37','.3','.47','.2','1','0','0','0','0','1']
    scales=['1']*10
    fields[column]='1e308';scales[column-2]='2'
    source=base+'Sensor\n* '+' '.join(scales)+'\n'+' '.join(fields)+'\nEnd\n'
    try:
        with np.errstate(over='ignore',invalid='ignore'):
            parse(source)
    except ValueError as error:
        assert 'finite' in str(error),str(error)
        rejections.append(dict(column_1based=column+1,error=str(error)))
    else:
        raise AssertionError('Nonfinite scaled sensor field was accepted: '+str(column))
record('all ten scaled sensor fields reject overflow across the full row',rejections=rejections)
assert len(checks)==6
comparable=dict(checks=checks,sensor_fixtures=dict(parallel=parallel,missing_v=missing,valid=valid),
    standalone_equilibrium_solves=0,residual_evaluations=1,original_source_unchanged=model.dumps()==text)
encoded=json.dumps(comparable,allow_nan=False)
if 'original_input_json' not in globals():
    Path(sys.argv[2]).write_text(encoded+'\n')
encoded
`;

try{
  names=await moduleNames(sourceDirectory);
  assert.deepEqual(await moduleNames(publicDirectory),names,'Source/public Python module inventories differ.');
  const bytes={},modules={};
  for(const name of names){
    const source=await pin(path.join(sourceDirectory,name)),publicPin=await pin(path.join(publicDirectory,name));
    assert.equal(publicPin.sha256,source.sha256,'Source/public module mismatch: '+name);
    assert.equal(publicPin.bytes,source.bytes,'Source/public module size mismatch: '+name);
    pins.push(source,publicPin);bytes[name]=await readFile(publicPin.path);modules[name]=source.sha256;
    assert.equal(sha(bytes[name]),publicPin.sha256,'Public module changed while loading: '+name);
  }
  report.module_count=names.length;report.modules=modules;report.source_public_identical=true;
  const originalPath=path.join(root,originalRelative),original=await readFile(originalPath);
  assert.equal(sha(original),originalHash,'Original ST1 input differs from its pinned bytes.');
  const originalPin={path:originalPath,bytes:original.length,sha256:originalHash};pins.push(originalPin);
  const input={source:original.toString('utf8'),pin:originalPin};
  await save('input.json',input);
  await writeFile(path.join(output,'fixture.py'),fixture);
  const runtimeNames=(await readdir(path.join(root,'public/runtime'))).sort();
  assert(runtimeNames.includes('pyodide.asm.wasm'));
  for(const packageName of ['numpy','scipy'])assert(runtimeNames.some(name=>name.startsWith(packageName+'-')&&name.endsWith('.whl')));
  pins.push(...await Promise.all([script,path.join(output,'input.json'),path.join(output,'fixture.py'),
    ...runtimeNames.map(name=>path.join(root,'public/runtime',name)),
    ...['package.json','pyodide.mjs','pyodide.asm.mjs','pyodide-lock.json'].map(name=>path.join(root,'node_modules/pyodide',name))].map(pin)));
  await save('plan.json',{...report,pins,module_names:names,
    input:originalPin,native_replay:'PYTHONPATH=REPOSITORY .venv/bin/python fixture.py input.json native-results.json',
    comparison_scope:'Fixture outputs can be compared across native and WASM runtimes. No native run is performed by this harness; the 3e-14 absolute fixture gate tests exact constructed geometry, not archived ASWING acceptance.'});
  report.plan=await pin(path.join(output,'plan.json'));pins.push(report.plan);
  const block=kind=>(...args)=>{
    const description=args.map(value=>typeof value==='string'?value:value?.href||value?.hostname||typeof value).join(' ');
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
  for(const name of names)py.FS.writeFile('/home/pyodide/openswing/'+name,bytes[name]);
  py.globals.set('original_input_json',JSON.stringify(input));
  report.pyodide_version=py.version;
  const result=JSON.parse(await py.runPythonAsync(fixture));
  await save('wasm-results.json',result);
  report.results=await pin(path.join(output,'wasm-results.json'));
  report.checks=result.checks;report.standalone_equilibrium_solves=result.standalone_equilibrium_solves;
  report.residual_evaluations=result.residual_evaluations;
  report.python=await py.runPythonAsync('sys.version');
  report.loaded_module_paths=JSON.parse(await py.runPythonAsync("json.dumps({name:mod.__file__ for name,mod in sys.modules.items() if name.startswith('openswing.')})"));
  assert.equal(report.checks.length,6);assert(report.checks.every(check=>check.passed));
  assert.equal(result.original_source_unchanged,true);
  assert.equal(attempts.length,0,'Offline test attempted network access.');
  report.status='PASS';
}catch(error){
  report.status='FAIL';report.error=String(error?.stack||error);process.exitCode=1;
}finally{
  report.elapsed_seconds=(performance.now()-started)/1000;
  report.pins_unchanged=true;report.pin_failures=[];
  for(const expected of pins){
    try{
      const actual=await pin(expected.path);
      if(actual.sha256!==expected.sha256||actual.bytes!==expected.bytes){report.pins_unchanged=false;report.pin_failures.push({expected,actual});}
    }catch(error){report.pins_unchanged=false;report.pin_failures.push({expected,error:String(error)});}
  }
  for(const directory of [sourceDirectory,publicDirectory]){
    try{assert.deepEqual(await moduleNames(directory),names);}catch(error){report.pins_unchanged=false;report.pin_failures.push({directory,error:String(error)});}
  }
  if(!report.pins_unchanged){report.status='FAIL';process.exitCode=1;}
  await save('report.json',report);
  await save('receipt.json',{status:report.status,report:await pin(path.join(output,'report.json')),
    plan:report.plan,results:report.results,script:await pin(script),pins_unchanged:report.pins_unchanged,
    source_public_identical:report.source_public_identical===true,module_count:report.module_count,
    process_pid:process.pid,exit_code:process.exitCode||0,network_attempts:attempts.length,
    standalone_equilibrium_solves:report.standalone_equilibrium_solves??null,
    residual_evaluations:report.residual_evaluations??null,scope:report.scope});
  console.log(JSON.stringify({status:report.status,checks:report.checks.length,modules:report.module_count,
    seconds:report.elapsed_seconds,network_attempts:attempts.length,pins_unchanged:report.pins_unchanged,output}));
  if(report.error)console.error(report.error);
}
