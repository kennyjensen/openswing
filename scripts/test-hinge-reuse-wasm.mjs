// One exact hinge equilibrium across a rotation-chart boundary in the shipped WASM runtime.
import {loadPyodide} from 'pyodide';
import {readFile, readdir, writeFile, mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import assert from 'node:assert/strict';

assert.equal(process.argv.length,3,'Provide a new output directory.');
const output=path.resolve(process.argv[2]);
await mkdir(output,{recursive:false});
const sha=b=>createHash('sha256').update(b).digest('hex');
const started=performance.now(), modules={};
const py=await loadPyodide({indexURL:path.resolve('public/runtime')});
await py.loadPackage(['numpy','scipy']);
py.FS.mkdirTree('/home/pyodide/openswing');
for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py')).sort()){
  const source=await readFile('openswing/'+name);
  modules[name]=sha(source);
  for(const folder of ['public/kernel','dist/kernel'])
    assert.equal(sha(await readFile(folder+'/'+name)),modules[name],folder+'/'+name);
  py.FS.writeFile('/home/pyodide/openswing/'+name,source);
}
const source=await readFile('tests/fixtures/hinge-history/source/dead-couple.asw','utf8');
py.globals.set('source',source);
const result=JSON.parse(await py.runPythonAsync(`
import json
import numpy as np
from openswing.asw import parse_asw
from openswing.network import StaticNetwork
from openswing.structured_static import equilibrate
from openswing.equilibrium_state import capture
n=StaticNetwork(parse_asw(source),4,None,[0,0,0],[dict(beam=2,t=2,moment=[200.,0,0])])
x,steps=equilibrate(n)
error=float(np.max(abs(n.residual(x))))
theta=np.deg2rad(200.);r,q,*_=n.unpack(x)
c,s=np.cos(theta),np.sin(theta)
position_error=float(np.max(abs(r[-1]-[0,2+2*c,2*s])))
rotation_error=float(np.max(abs(q[-1]-[[1,0,0],[0,c,-s],[0,s,c]])))
angle_error=abs(capture(n,x)['hinge_charts'][0]['angle_rad']-theta)
assert error<=1e-12
assert max(position_error,rotation_error,angle_error)<=2e-12
records=n.structured_iterations
reused=sum(t['matrix_reused'] for t in records)
crossings=[i for i,t in enumerate(records) if t.get('rotation_chart_changed')]
assert reused>0 and crossings
assert all(i+1==len(records) or not records[i+1]['matrix_reused'] for i in crossings)
maximum=max(t['accepted_load_rotation_increment_rad'] for t in n.continuation_diagnostics if t['accepted'])
assert maximum<=np.deg2rad(5)*(1+1e-12)
json.dumps(dict(status='PASS',scope='Exact 200-degree synthetic hinge; Pyodide runtime, not UI or ISAE agreement',
  residual=error,position_error=position_error,rotation_error=rotation_error,angle_error=angle_error,
  steps=steps,iterations=len(records),reused=reused,chart_crossings=crossings,
  maximum_load_rotation_increment=maximum))
`));
result.modules=modules;result.source_sha256=sha(Buffer.from(source));
result.seconds=(performance.now()-started)/1000;
await writeFile(path.join(output,'report.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({...result,modules:undefined}));
