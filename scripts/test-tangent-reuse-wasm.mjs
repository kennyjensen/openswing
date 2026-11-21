// Exact finite-difference cache equivalence in the shipped WASM runtime.
import {loadPyodide} from 'pyodide';
import {readFile, readdir} from 'node:fs/promises';
import path from 'node:path';
const py = await loadPyodide({indexURL:path.resolve('public/runtime')});
await py.loadPackage(['numpy','scipy']);
py.FS.mkdirTree('/home/pyodide/openswing');
for (const name of (await readdir('openswing')).filter(n=>n.endsWith('.py'))) {
  py.FS.writeFile(`/home/pyodide/openswing/${name}`,await readFile(`openswing/${name}`,'utf8'));
}
py.globals.set('flexible_source',await readFile('examples/flexible.asw','utf8'));
await py.runPythonAsync(`
import numpy as np
from openswing.tangent_influences import TangentInfluences, TangentLoads
from openswing.aero import horseshoe_velocity, FlightCondition
from openswing.asw import parse_asw
from openswing.ground import GroundPlane
from openswing.network import StaticNetwork
rng = np.random.default_rng(528)
a = rng.normal(size=(72,3)); b = a+rng.normal(size=(72,3))
points = rng.normal(size=(72,3)); core = rng.uniform(.01,.3,(72,72))
mask = np.eye(72,dtype=bool)
direction = np.array([1.,.12,-.08]); direction /= np.linalg.norm(direction)
checks = 0
for flag in [0,1,-1]:
    for coefficient in [0,.2]:
        pg = np.eye(3)+coefficient*np.outer(direction,direction)
        ground = GroundPlane(flag,[0,0,10],[10,20,30],[.1,-.2,1])
        cache = TangentInfluences()
        for change in ['base','receiver','source','both','core','exclude','all','base']:
            pp,aa,bb,cc,ee = [v.copy() for v in (points,a,b,core,mask)]
            if change in ['receiver','both']: pp[5,1] += .001
            if change in ['source','both']: aa[12,2] += .001; bb[13,0] -= .001
            if change == 'core': cc[2,3] += .01
            if change == 'exclude': ee[8,9] = True
            if change == 'all': aa += .001
            expected = horseshoe_velocity(pp[:,None,:],aa[None,:,:],bb[None,:,:],direction,pg,cc,ground,exclude_bound=ee)
            actual = cache.vortex('probe',pp,aa,bb,direction,pg,cc,ground,ee)
            np.testing.assert_array_equal(actual,expected)
            actual[:] = np.nan
            checks += 1
print(f'{checks} exact WASM vortex-pair comparisons passed',flush=True)
for dynamic in [False,True]:
    condition = FlightCondition(alpha=5,beta=2,mach=.2,rates=[.01,-.02,.03],ground_effect=1,position_earth=[0,0,10])
    net = StaticNetwork(parse_asw(flexible_source),8,condition,None,[])
    x = rng.normal(0,.001,net.size)
    x[net.gamma_start:net.operating_start] += .04
    options = dict(elastic_motion=tuple(rng.normal(0,.01,(4,net.nn,3)))) if dynamic else {}
    actual = net.jacobian(x,.7,**options)
    np.testing.assert_array_equal(actual,net._jacobian(x,.7,**options))
    checks += 1
    if not dynamic:
        cache = TangentLoads()
        net.jacobian(x,0.,_load_cache=cache)
        np.testing.assert_array_equal(net.jacobian(x,.7,_load_cache=cache),actual)
        checks += 1
print(f'{checks} exact WASM comparisons passed, including static, loaded and elastic-motion tangents',flush=True)
`);
