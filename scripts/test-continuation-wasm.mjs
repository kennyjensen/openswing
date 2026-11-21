import { loadPyodide } from 'pyodide';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
// Validate the packaged browser kernel, not an independently copied source tree.
const py=await loadPyodide({indexURL:path.resolve('dist/runtime')});
await py.loadPackage(['numpy','scipy']);
py.FS.mkdirTree('/home/pyodide/openswing');
for(const name of JSON.parse(await readFile('dist/kernel/manifest.json','utf8')))
  py.FS.writeFile(`/home/pyodide/openswing/${name}`,await readFile(`dist/kernel/${name}`,'utf8'));
py.globals.set('source',await readFile('dist/examples/rectangular.asw','utf8'));
await py.runPythonAsync(`
import json,numpy as np
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,AnalysisError,solve_rigid
from openswing.network import solve_static
from openswing.bridge import run_json
from openswing.stability import trace_spectrum
m=parse_asw(source)
a=solve_static(m,FlightCondition(speed=10,alpha=3,mach=0),4,gravity=[0,0,0])
seed=a['equilibrium_state']
assert max(abs(np.array(seed['circulation'])))>1
r=json.loads(run_json(json.dumps(dict(action='solve',mode='mounted',source=source,panels=4,
    gravity=[0,0,0],condition=dict(speed=30,alpha=5,mach=0),initial_state=seed))))
reference=solve_rigid(m,FlightCondition(speed=30,alpha=5,mach=0),4)
for key in ('CL','CD','force','moment'):np.testing.assert_allclose(r[key],reference[key],atol=1e-7)
assert r['equilibrium_initialization']['initialization']=='saved physical equilibrium'
print('Packaged WebAssembly nonzero-circulation seed and JSON warm solve match the rigid aerodynamic limit.')
def root(p):return dict(root=complex(p-1.5,3),vector=np.array([1.]),mode_index=0,real=False,scale=10.)
def tied(p):return ([root(p),root(p)] if p==1.5 else [root(p)]),{}
out=trace_spectrum(tied,[1.,2.],ambiguity_margin=0)
assert out['boundaries'][0]['status']=='unresolved'
assert 'uniquely' in out['boundaries'][0]['reason']
last=[None]
def limited(p):
    if last[0] is not None and p-last[0]>.3:raise AnalysisError('Local corrector radius')
    last[0]=p
    return [root(p)],{}
out=trace_spectrum(limited,[0.,1.],adaptive=True,refine=False,resample_after_subdivision=True)
assert out['converged'] and out['tracking_complete']
assert [out['points'][i]['value'] for i in out['tracking_points']]==[0.,.25,.5,.75,1.]
assert all('superseded_by' in p for p in out['points'] if not p['converged'])
print('Packaged WebAssembly adaptive retries preserve failed attempts; exact boundary ties remain unresolved.')
`);
// A state produced by native NumPy/SciPy must also load in the browser runtime.
const native=JSON.parse(await readFile(process.env.OPENSWING_CONTINUATION_EVIDENCE||'docs/validation/continuation.json','utf8')).cases.circular_arc;
py.globals.set('native_source',native.source);
py.globals.set('native_seed',JSON.stringify(native.meshes[0].points.at(-1).result.equilibrium_state));
await py.runPythonAsync(`
from openswing.network import StaticNetwork
from openswing.equilibrium_state import restore,capture
seed=json.loads(native_seed)
n=StaticNetwork(parse_asw(native_source),12,None,[0,0,0],[dict(beam=1,t=2,moment=[100,0,0])])
roundtrip=capture(n,restore(n,seed))
for key in ('positions','rotations','internal_force','internal_moment','reactions','circulation'):
    np.testing.assert_allclose(roundtrip[key],seed[key],rtol=1e-13,atol=1e-13)
print('Native large-rotation equilibrium restores in the packaged WebAssembly mesh without changing physical quantities.')
`);
