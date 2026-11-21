"""Verify saved small-mesh controls and compare pointwise/Fourier sensitivity."""
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys

for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(name)=='1'
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from avl_vorvelc_reference import matrix as vortex_matrix
OUT=ROOT/'artifacts/isae/sa11-extension-practical-mesh-20261108'
MODES=ROOT/'artifacts/isae/sa11-extension-modes-20261108'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=read(OUT/'plan.json');digest=sha(OUT/'plan.json')
for name,h in plan['pins'].items():assert sha(ROOT/name)==h,name
rows=[];maximum_force_error=maximum_moment_error=0.
for case in plan['cases']:
    folder=OUT/case['id'];r=read(folder/'report.json');control=case['control'];raw=read(folder/'accepted.json')
    assert r['status']=='computed' and r['plan_sha256']==digest and r['passed']==5
    for name,h in r['artifacts'].items():assert sha(folder/name)==h,name
    with np.load(folder/'geometry.npz') as a:g={k:a[k] for k in a}
    assert len(g['ds'])==r['actual_intervals'] and min(g['ds'])>=.0164659927127284-1e-12
    gamma=np.array([s['circulation'] for s in raw['strips']])
    velocity=np.array([s['relative_velocity'] for s in raw['strips']])
    alpha=math.radians(control['settings']['alpha']);speed=control['settings']['speed'];rho=control['settings']['density']
    rotation=np.array([[math.cos(alpha),0,math.sin(alpha)],[0,1,0],[-math.sin(alpha),0,math.cos(alpha)]])
    tensor=vortex_matrix(g['cp']@rotation.T,g['a']@rotation.T,g['b']@rotation.T,speed/340.21,core_fraction=0.,dtype=np.longdouble)
    tensor=np.einsum('ijq,qr->ijr',tensor,rotation)
    tensor*=np.longdouble(1)/(4*np.arccos(np.longdouble(-1))*np.longdouble('.079577472'))
    matrix=np.asarray(np.einsum('ijk,ik->ij',tensor,g['normal']),dtype=float)
    rhs=-speed*(g['normal']@rotation[0]);linear_gamma=np.linalg.solve(matrix,rhs)
    linear_difference=float(max(abs(gamma-linear_gamma))/max(abs(gamma)));assert linear_difference<1e-8
    qs=.5*rho*speed**2*.9329
    force=[math.fsum(s['force'][k] for s in raw['strips']) for k in range(3)]
    cd=(force[0]*math.cos(alpha)+force[2]*math.sin(alpha))/qs
    cl=(-force[0]*math.sin(alpha)+force[2]*math.cos(alpha))/qs
    moment=math.fsum(s['moment'][1]+s['position'][2]*s['force'][0]-s['position'][0]*s['force'][2] for s in raw['strips'])
    maximum_force_error=max(maximum_force_error,abs(cd-raw['CD']),abs(cl-raw['CL']))
    maximum_moment_error=max(maximum_moment_error,abs(moment/(qs*.37874)-raw['Cm_origin']))
    for name,value in r['actual'].items():
        err=100*(value/r['reference'][name]-1);assert abs(err-r['relative_percent_errors'][name])<2e-10
        assert (abs(err)>5)==(name in ('drag','CD'))
    r.update(case=case,report_sha256=sha(folder/'report.json'),independent_linear_gamma_relative_error=linear_difference)
    rows.append(r)
assert maximum_force_error<2e-12 and maximum_moment_error<2e-12
modes=read(MODES/'analysis.json');assert modes['verified']
summary=dict(observed_utc=datetime.now(timezone.utc).isoformat(),verified=True,cases=rows,
    modes_analysis_sha256=sha(MODES/'analysis.json'),source_pins_verified=len(plan['pins']),
    maximum_force_reduction_error=maximum_force_error,maximum_moment_reduction_error=maximum_moment_error,
    maximum_linear_gamma_relative_error=max(r['independent_linear_gamma_relative_error'] for r in rows),
    maximum_residual=max(r['residual'] for r in rows),maximum_normal_mach=max(r['maximum_normal_mach'] for r in rows),
    minimum_stall_margin_widths=min(r['minimum_stall_margin_widths'] for r in rows),
    maximum_seconds=max(r['seconds'] for r in rows),peak_rss_kib=max(r['peak_rss_kib'] for r in rows),
    passed=30,required=42,primary_passes_added=0,physical_calls=6,plan_sha256=digest,checker_sha256=sha(Path(__file__)))
text=json.dumps(summary,indent=2,allow_nan=False)+'\n'
with (OUT/'analysis.json').open('x') as f:f.write(text)
signal.alarm(0);print(json.dumps({k:v for k,v in summary.items() if k!='cases'},indent=2))
