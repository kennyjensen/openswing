"""Locate the audited strong pairs in mandatory and coarsened candidate nodes."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys

for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    assert os.environ.get(key)=='1'
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.geometry import model_meshes,mesh_breaks
OUT=ROOT/'artifacts/isae/sa11-extension-drag-pairs-20261108'
MESH=ROOT/'artifacts/isae/sa11-extension-mesh-limit-20261108'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=read(OUT/'plan.json');analysis=read(OUT/'analysis.json');parent=read(MESH/'plan.json')
assert analysis['verified'] and analysis['plan_sha256']==sha(OUT/'plan.json')
for path,digest in plan['pins'].items():assert sha(ROOT/path)==digest,path
rows=[]
for row in analysis['cases']:
    case=next(c for c in plan['cases'] if c['id']==row['id'])
    n=case['requested_intervals']
    if n in (64,128):
        control=next(c for c in parent['controls'] if c['id']==row['id'])
        original=control['case']['original_job'];mesh_spec=control['case']['mesh']
    else:
        entry=next(c for c in parent['cases'] if c['id']==row['id'])
        original=entry['control']['case']['original_job'];mesh_spec=entry['mesh']
    model=parse_asw((ROOT/original['model_path']).read_text(),beam_interpolation='natural-v1')
    mesh,=model_meshes(model,mesh_spec)
    with np.load(ROOT/case['folder']/case['geometry_file']) as g:
        assert np.array_equal(mesh.tm,g['t']) and np.array_equal(mesh.length,g['ds'])
    plain=json.loads(json.dumps(mesh_spec));plain['beams']['1'].pop('min_spacing')
    candidate,=model_meshes(model,plain)
    nodes=np.r_[candidate.t0[0],candidate.t1]
    pair=row['straight_pair_control']['selected_pair'];i,j=pair['i'],pair['j']
    assert j==i+1 and mesh.t1[i]==mesh.t0[j]
    points=[mesh.t0[i],mesh.t1[i],mesh.t1[j]]
    index=[int(np.argmin(abs(nodes-t))) for t in points]
    differences=[float(abs(nodes[k]-t)) for k,t in zip(index,points)]
    assert max(differences)<1e-10
    required=np.asarray(mesh_breaks(mesh.beam,mesh.mesh_recipe))
    distance=float(min(abs(required-points[1])))
    rows.append(dict(id=row['id'],actual_intervals=len(mesh.tm),pair_material_nodes=list(map(float,points)),
        required_station=distance<1e-10,distance_to_required_station=distance,
        nearest_required_station=float(required[np.argmin(abs(required-points[1]))]),
        candidate_intervals_spanned=[index[1]-index[0],index[2]-index[1]],
        retained_interval_lengths=[float(mesh.length[i]),float(mesh.length[j])],
        candidate_node_matching_errors=differences))
result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),verified=True,cases=rows,
    physical_solves=0,primary_passes_added=0,analysis_sha256=sha(OUT/'analysis.json'),
    plan_sha256=sha(OUT/'plan.json'),script_sha256=sha(Path(__file__)))
text=json.dumps(result,indent=2,allow_nan=False)+'\n'
with (OUT/'spacing-transitions.json').open('x') as stream:stream.write(text)
signal.alarm(0);print(text)
