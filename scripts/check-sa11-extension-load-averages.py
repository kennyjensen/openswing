"""Independent scalar reductions of saved load-average and balance probes."""
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal

for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    assert os.environ.get(name)=='1'
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/isae/sa11-extension-load-averages-20261108'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=read(OUT/'plan.json');digest=sha(OUT/'plan.json')
for path,expected in plan['pins'].items():assert sha(ROOT/path)==expected,path
dot=lambda a,b:math.fsum(float(x)*float(y) for x,y in zip(a,b))
cross=lambda a,b:[float(a[1])*float(b[2])-float(a[2])*float(b[1]),float(a[2])*float(b[0])-float(a[0])*float(b[2]),float(a[0])*float(b[1])-float(a[1])*float(b[0])]
sum_vectors=lambda a:[math.fsum(float(row[k]) for row in a) for k in range(3)]
rows=[];max_reduction=max_percent=max_force_residual=max_moment_residual=0.
max_force_coefficient=max_moment_coefficient=0.;decisions_changed=0
for case in plan['cases']:
    folder=OUT/case['id'];row=read(folder/'report.json')
    assert row['plan_sha256']==digest and row['physical_solves']==row['accepted_states_added']==row['primary_passes_added']==0
    for name,expected in row['artifacts'].items():assert sha(folder/name)==expected,name
    with np.load(folder/'fields.npz') as archive:d={key:archive[key] for key in archive}
    settings=row['settings'];angle=math.radians(settings['alpha']);e=[math.cos(angle),0,math.sin(angle)];ez=[-math.sin(angle),0,math.cos(angle)]
    qs=.5*settings['density']*settings['speed']**2*.9329
    baseline=sum_vectors(d['force']);moment=sum_vectors([np.asarray(m)+cross(p,f) for p,f,m in zip(d['position'],d['force'],d['couple'])])
    assert abs(dot(baseline,e)/qs-row['original_CD'])<2e-12
    for name in plan['variants']:
        value=row['probes'][name];force=sum_vectors(d[name]);cd=dot(force,e)/qs;cl=dot(force,ez)/qs
        max_reduction=max(max_reduction,abs(cd-value['CD']),abs(cl-value['CL']))
        change=100*(cd-row['original_CD'])/abs(row['reference_CD'])
        max_percent=max(max_percent,abs(change-value['reference_CD_error_change_points']))
        decisions_changed+=(abs(cd-row['reference_CD'])<=.05*abs(row['reference_CD']))!=(abs(row['original_CD']-row['reference_CD'])<=.05*abs(row['reference_CD']))
    for i,(start,end,position,force,couple) in enumerate(zip(d['r0'],d['r1'],d['position'],d['force'],d['couple'])):
        f0,f1=d['reaction_force'][i:i+2];m0,m1=d['reaction_moment'][i:i+2]
        center=[(float(a)+float(b))/2 for a,b in zip(start,end)]
        applied=[float(a)+b for a,b in zip(couple,cross(position-center,force))]
        arm=cross(end-start,(f0+f1)/2)
        max_force_residual=max(max_force_residual,max(abs(float(f1[k])-float(f0[k])+float(force[k])) for k in range(3)))
        max_moment_residual=max(max_moment_residual,max(abs(float(m1[k])-float(m0[k])+applied[k]+arm[k]) for k in range(3)))
    assert np.all(d['reaction_force'][-1]==0) and np.all(d['reaction_moment'][-1]==0)
    nodes=np.vstack([d['r0'][0],d['r1']]);nodal=sum_vectors(d['nodal_force'])
    nodal_moment=sum_vectors([np.asarray(m)+cross(p,f) for p,f,m in zip(nodes,d['nodal_force'],d['nodal_moment'])])
    backward_moment=[float(a)+b for a,b in zip(d['reaction_moment'][0],cross(d['r0'][0],d['reaction_force'][0]))]
    max_force_coefficient=max(max_force_coefficient,max(abs(nodal[k]-baseline[k])/qs for k in range(3)),max(abs(float(d['reaction_force'][0,k])-baseline[k])/qs for k in range(3)))
    max_moment_coefficient=max(max_moment_coefficient,max(abs(nodal_moment[k]-moment[k])/(qs*.37874) for k in range(3)),max(abs(backward_moment[k]-moment[k])/(qs*.37874) for k in range(3)))
    row['report_sha256']=sha(folder/'report.json');rows.append(row)
assert max_reduction<2e-12 and max_percent<2e-10
assert max_force_residual<2e-8 and max_moment_residual<2e-8
assert max_force_coefficient<2e-12 and max_moment_coefficient<2e-12
summary=dict(observed_utc=datetime.now(timezone.utc).isoformat(),verified=True,cases=rows,
    maximum_probe_CD_error_change_points={name:max(abs(row['probes'][name]['reference_CD_error_change_points']) for row in rows) for name in plan['variants']},
    maximum_probe_CL_change_percent={name:max(abs(row['probes'][name]['relative_CL_change_percent']) for row in rows) for name in plan['variants']},
    maximum_scalar_coefficient_difference=max_reduction,maximum_percentage_difference=max_percent,
    maximum_equation56_force_residual=max_force_residual,maximum_equation55_moment_residual=max_moment_residual,
    maximum_conservation_force_coefficient_error=max_force_coefficient,maximum_conservation_moment_coefficient_error=max_moment_coefficient,
    changed_CD_decisions=decisions_changed,physical_solves=0,accepted_states_added=0,primary_passes_added=0,
    source_pins_verified=len(plan['pins']),maximum_seconds=max(row['seconds'] for row in rows),
    peak_rss_kib=max(row['peak_rss_kib'] for row in rows),plan_sha256=digest,checker_sha256=sha(Path(__file__)))
text=json.dumps(summary,indent=2,allow_nan=False)+'\n'
with (OUT/'analysis.json').open('x') as stream:stream.write(text)
signal.alarm(0);print(json.dumps({key:value for key,value in summary.items() if key!='cases'},indent=2))
