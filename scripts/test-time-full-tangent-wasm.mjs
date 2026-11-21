// Source BDF matrix parity and dense Newton callback in the shipped WASM runtime.
import {loadPyodide} from 'pyodide';
import {readFile,readdir,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import assert from 'node:assert/strict';

assert.equal(process.argv.length,3,'Provide a new output directory.');
const output=path.resolve(process.argv[2]);await mkdir(output,{recursive:false});
const sha=b=>createHash('sha256').update(b).digest('hex');
const began=performance.now(),modules={};
const py=await loadPyodide({indexURL:path.resolve('public/runtime')});
await py.loadPackage(['numpy','scipy']);py.FS.mkdirTree('/home/pyodide/openswing');
for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py')).sort()){
  const b=await readFile('openswing/'+name);modules[name]=sha(b);
  for(const folder of ['public/kernel','dist/kernel'])
    assert.equal(sha(await readFile(folder+'/'+name)),modules[name],folder+'/'+name);
  py.FS.writeFile('/home/pyodide/openswing/'+name,b);
}
const sourcePath='examples/source-airflow-check.asw';
const source=await readFile(sourcePath,'utf8');py.globals.set('source',source);
const report=JSON.parse(await py.runPythonAsync(`
import json
import numpy as np
from scipy.sparse import csc_matrix
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.source_airflow import SourceAirflowNetwork
from openswing.hinge_history import at_network
from openswing.time_integration import TimeSystem,TimeState,bdf_coefficients,full_tangent,newton
from openswing.time_tangent import attach_mechanical_columns
n=SourceAirflowNetwork(parse_asw(source,beam_interpolation='drela-segspl-v1'),4,
    FlightCondition(speed=20,alpha=3,mach=0,controls={1:.2}),[0,0,-9.81],[])
system=TimeSystem(n)
x=np.zeros(n.size);x[n.gamma_start:n.operating_start]=.02
r,q,*_,gamma=n.unpack(x)
z=np.zeros_like(r)
state=TimeState(0.,x,r,q,z.copy(),z.copy(),-n.condition.speed*n.condition.vectors()[0],
    np.zeros(3),np.zeros(3),np.eye(3),gamma,hinge_charts=at_network(n,q))
system.source_time.bind(state)
values=system.guess(state,.01);coefficients=bdf_coefficients(.01)
calls=[0]
def f(v,data=None):
    calls[0]+=1
    return system.residual(v,state,None,.01,coefficients,
        **({} if data is None else dict(_mechanical_data=data[0])))
attach_mechanical_columns(system,f,lambda v,d:f(v,d))
base=f(values);columns,_=f.direct_mechanical_columns(values)
calls[0]=0;actual=full_tangent(f,values,base);used=calls[0]
assert used==len(values)-len(columns)+1
expected=full_tangent(f,values,base,direct_mechanics=False)
remaining=np.setdiff1d(np.arange(len(values)),columns)
np.testing.assert_array_equal(actual[:,remaining],expected[:,remaining])
error=float(np.max(abs(actual-expected)/(1+abs(expected))))
assert error<=2e-7
def g(v):return np.array([v[0]**2+v[1]-5,v[0]+2*v[1]-4])
g.direct_mechanical_columns=lambda v:(np.array([1]),csc_matrix([[1.],[2.]]))
solution,_,iterations,builds=newton(g,np.array([1.8,1.1]),1e-12)
np.testing.assert_allclose(solution,[2,1],atol=1e-12,rtol=0)
json.dumps(dict(status='PASS',scope='Source BDF complete matrix and nonlinear Newton callback; no full FFWT or UI validation',
    matrix_size=len(values),direct_columns=len(columns),residual_calls=used,scaled_matrix_error=error,
    root=solution.tolist(),root_residual=float(max(abs(g(solution)))),iterations=iterations,builds=builds))
`));
Object.assign(report,{modules,source_path:sourcePath,source_sha256:sha(Buffer.from(source)),seconds:(performance.now()-began)/1000});
await writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({...report,modules:undefined}));
