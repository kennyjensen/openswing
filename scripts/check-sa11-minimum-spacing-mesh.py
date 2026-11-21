"""Bounded spacing/refinement, default-control and bundled-example checks."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import signal
import sys

resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,evaluate_aerodynamics
from openswing.geometry import model_meshes
from openswing.frozen_influence import lifting_geometry
from openswing.bridge import dispatch

out=ROOT/'artifacts/isae/sa11-minimum-spacing-20261108'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=read(out/'plan.json')
for name,digest in plan['pins'].items():assert sha(ROOT/name)==digest,name
model=parse_asw((out/'model.asw').read_text());base=read(out/'mesh-import.json')['panels']
rows=[];first=None
for count in (16,32,64,128,512):
    settings=deepcopy(base)
    for key in ('2','3'):settings['beams'][key]['count']=count
    meshes=model_meshes(model,settings);g=lifting_geometry(meshes,np.array([1.,0.,0.]))
    assert [len(m.tm) for m in meshes]==[32,16,16]
    minimum=min(float(m.length.min()) for m in meshes[1:])
    assert minimum>=plan['minimum_spacing']-3e-12
    if first is None:first={k:v.copy() for k,v in g.items()}
    delta=max(float(np.max(abs(g[k]-first[k]))) for k in g)
    assert delta<3e-12
    d=g['hv'][32]-g['b'][31];distance=float(np.linalg.norm(d-np.array([max(d[0],0.),0.,0.])))
    assert distance>.00334
    rows.append(dict(requested_intervals=count,actual_intervals=[len(m.tm) for m in meshes],
                     minimum_winglet_interval=minimum,maximum_geometry_change=delta,root_receiver_ray_distance=distance))

# The default path must still reproduce the earlier explicit-mesh solution.
prior=ROOT/'artifacts/isae/sa11-winglet-spacing-20261108'
condition=FlightCondition(**read(prior/'plan.json')['condition'])
control_mesh=model_meshes(model,dict(default=16,beams=read(prior/'uniform-32-mesh.json')))
control=evaluate_aerodynamics(model,condition,control_mesh)
with np.load(prior/'uniform-32/state.npz') as saved:
    for field,key in [('circulation','gamma'),('relative_velocity','velocity'),('cl','cl')]:
        np.testing.assert_array_equal(np.array([s[field] for s in control['strips']]),saved[key])

# The importable settings also work on the normal selectable +4-degree model.
source=ROOT/'examples/isae-sa11-wingtip-up.asw'
inspected=dispatch(dict(action='inspect',source=source.read_text(),panels=base))
assert inspected['mesh_discretization']['settings']==base
assert [b['panels'] for b in inspected['mesh_discretization']['beams']]==[32,16,16]
stock=parse_asw(source.read_text());stock_mesh=model_meshes(stock,base);smokes=[]
for alpha in (0.,5.):
    result=evaluate_aerodynamics(stock,FlightCondition(speed=272.,alpha=alpha,mach=272/340.21,freeze_influences=True),stock_mesh)
    smokes.append(dict(alpha=alpha,speed=272.,converged=result['converged'],maximum_normal_mach=max(s['normal_mach'] for s in result['strips']),
                       CL=result['CL'],CD=result['CD'],Cm_origin=result['Cm_origin']))
path=out/'mesh-verification.json';assert not path.exists()
path.write_text(json.dumps(dict(verified_utc=datetime.now(timezone.utc).isoformat(),refinement=rows,
    default_control='Exact gamma, velocity and section CL replay on previous explicit uniform32 mesh.',
    bundled_example_smoke=smokes,bundled_example_sha256=sha(source),plan_sha256=sha(out/'plan.json'),
    script_sha256=sha(Path(__file__)),primary_passes_added=0),indent=2)+'\n')
signal.alarm(0)
print(json.dumps(dict(refinement=rows,bundled_example_smoke=smokes,default_control='exact replay'),indent=2))
