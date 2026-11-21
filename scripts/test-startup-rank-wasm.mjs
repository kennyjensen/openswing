// Test the built kernel in the same Pyodide/WASM runtime used by the browser.
import assert from 'node:assert/strict';
import {readFile,readdir,mkdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {loadPyodide} from 'pyodide';

const output=path.resolve(process.argv[2]??'artifacts/isae/ffwt4-startup-20261106/wasm');
await mkdir(output,{recursive:true});
const hash=data=>createHash('sha256').update(data).digest('hex');
const report={modules:{},scope:'Built-kernel WASM rank, initial-load prediction and complete source Newton matrix; no complete equilibrium or native comparison claim.'};
try{
  const py=await loadPyodide({indexURL:path.resolve('public/runtime')});
  await py.loadPackage(['numpy','scipy']);
  py.FS.mkdirTree('/home/pyodide/openswing');
  for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py'))){
    const bytes=await readFile('dist/kernel/'+name);
    assert.equal(hash(bytes),hash(await readFile('openswing/'+name)),name);
    report.modules[name]=hash(bytes);
    py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
  }
  const requestPath='artifacts/isae/rigid-attachment-production-20261106/flare20-n8/request.json';
  const bytes=await readFile(requestPath);report.request_sha256=hash(bytes);
  py.globals.set('request_json',bytes.toString('utf8'));
  const negative=await readFile('tests/fixtures/hinge-history/rank/flare20-air-n16-explicit-released-hinges.npz');
  report.released_matrix_sha256=hash(negative);py.FS.writeFile('/home/pyodide/released.npz',negative);
  const fixture=await readFile('tests/test_source_joints.py');
  report.synthetic_fixture_sha256=hash(fixture);
  py.globals.set('synthetic_fixture',fixture.toString('utf8'));
  const result=await py.runPythonAsync(`
import json, time, numpy as np
from scipy.sparse import csc_matrix
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,evaluate_aerodynamics
from openswing.source_airflow import SourceAirflowNetwork
from openswing.structured_static import (check_initial_rank,initial_load_step,
    equilibrate_rank_matrix,mechanical_svd_certificate)
request=json.loads(request_json)
model=parse_asw(request['source'],beam_interpolation='drela-segspl-v1')
n=SourceAirflowNetwork(model,request['panels'],FlightCondition(**request['condition']),None,[],steady_trim=True)
x=np.zeros(n.size)
flow=evaluate_aerodynamics(model,n.condition,n.meshes)
x[n.gamma_start:n.operating_start]=n.circulation_basis.encode(np.array([s['circulation'] for s in flow['strips'] if s['lifting']]))/n.gamma_scale
def forbidden(*args,**kwargs):
    raise AssertionError('Full finite-difference rebuild was unnecessary')
n.jacobian=forbidden
started=time.monotonic()
rank,matrix=check_initial_rank(n,x,retain_matrix=True)
rank_seconds=time.monotonic()-started
assert rank['method']=='block-triangular SVD certificate'
assert rank['mechanical_svd']['singular_ratio']>=1e-10
candidate,predictor=initial_load_step(n,x,matrix,.25,1e-12,np.deg2rad(5.))
assert predictor['applied'] and predictor['zero_load_residual']<=1e-12
assert np.isclose(candidate,3.2126387230230723e-6,rtol=1e-6,atol=0)
assert abs(candidate*predictor['rotation_rate_rad']-.9*np.deg2rad(5.))<=4*np.finfo(float).eps
assert not np.any(x[:n.gamma_start]) and model.dumps()==request['source']
for sigma in (0.,5e-11,1e-10,2e-10):
    gate=mechanical_svd_certificate(csc_matrix(np.diag([1.,sigma])))
    assert gate['certified']==(sigma>=1e-10)
released=np.load('/home/pyodide/released.npz')['altered_matrix'][:660,:660]
balanced,_=equilibrate_rank_matrix(csc_matrix(released))
assert not mechanical_svd_certificate(balanced)['certified']
print(json.dumps(dict(phase='startup_rank_and_prediction_passed',rank_seconds=rank_seconds,
    singular_ratio=rank['mechanical_svd']['singular_ratio'],initial_load=candidate)),flush=True)
# Reuse only the literal synthetic beam builder and trial-state generator,
# without importing pytest or replacing any production module in WASM.
import ast
tree=ast.parse(synthetic_fixture)
tree.body=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in ('source','trial')]
exec(compile(tree,'synthetic_source_fixture','exec'))
small=SourceAirflowNetwork(parse_asw(source(offsets=True,mass=True),beam_interpolation='drela-segspl-v1'),
    4,FlightCondition(speed=8.,alpha=4.,beta=2.,density=1.2,mach=0.,
        rates=[.1,-.2,.3],acceleration=[.2,-.1,.3],angular_acceleration=[-.1,.2,.1]),[1.,-2.,-10.],[])
state=trial(small);before=small.residual(state,.6).copy()
calls=small.nfev;started=time.monotonic()
optimized=small.jacobian(state,.6,_direct_geometry=True)
optimized_seconds=time.monotonic()-started;optimized_calls=small.nfev-calls
assert small.geometry_derivative_diagnostics['geometry_columns']==6*small.nn
assert small.mechanical_derivative_diagnostics['method'].startswith('direct source')
assert small.circulation_derivative_diagnostics['method']=='direct fixed-geometry blocks'
calls=small.nfev;started=time.monotonic()
original=small.jacobian(state,.6,_direct_geometry=False,_direct_mechanics=False,_direct_circulation=False)
original_seconds=time.monotonic()-started;original_calls=small.nfev-calls
scaled_error=float(np.max(abs(optimized-original)/(1+abs(original))))
assert optimized_calls<original_calls,(optimized_calls,original_calls)
print(json.dumps(dict(phase='full_tangent_assembled',optimized_calls=optimized_calls,
    original_calls=original_calls,original_forward_difference=scaled_error)),flush=True)
# The original forward stencil has O(h) truncation error (3.26e-6 on this
# fixture); it is a performance control, not an exact derivative reference.
# Check EVERY matrix column against centered complete physical differences,
# retaining the same 2e-6 derivative gate used by the native pose tests.
centered_error=0.
for j in range(small.size):
    h=3e-6*max(1.,abs(state[j]));p,m=state.copy(),state.copy();p[j]+=h;m[j]-=h
    column=(small.residual(p,.6)-small.residual(m,.6))/(2*h)
    centered_error=max(centered_error,float(np.max(abs(optimized[:,j]-column)/(1+abs(column)))))
assert centered_error<2e-6,centered_error
np.testing.assert_array_equal(small.residual(state,.6),before)
assert small.iteration_fields is None and small.tangent_influences is None
json.dumps(dict(status='PASS',rank_method=rank['method'],rank_seconds=rank_seconds,
    mechanical_singular_ratio=rank['mechanical_svd']['singular_ratio'],predictor=predictor,
    full_rebuilds=0,threshold_controls=4,explicit_release_rejected=True,
    source_full_tangent=dict(unknowns=small.size,optimized_seconds=optimized_seconds,
        original_seconds=original_seconds,optimized_calls=optimized_calls,original_calls=original_calls,
        original_scaled_error=scaled_error,centered_full_scaled_error=centered_error,
        centered_full_columns=small.size)))
`);
  Object.assign(report,JSON.parse(result));
}catch(error){report.status='FAIL';report.error=error.stack;process.exitCode=1;}
await writeFile(path.join(output,'runner-at-execution.mjs'),await readFile(new URL(import.meta.url)));
await writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({...report,modules:undefined}));
