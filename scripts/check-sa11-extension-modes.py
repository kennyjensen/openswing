"""Independent Fourier projection and linear tangency audit of saved SA-11 states."""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys

for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(key)=='1'
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from avl_vorvelc_reference import matrix as vortex_matrix
from openswing.asw import parse_asw
OUT=ROOT/'artifacts/isae/sa11-extension-modes-20261108'
PARENT=ROOT/'artifacts/isae/sa11-extension-drag-budget-r2-20261108'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=read(OUT/'plan.json');digest=sha(OUT/'plan.json')
for name,value in plan['pins'].items():assert sha(ROOT/name)==value,name
rows=[];errors=dict(projection=0.,circulation=0.,local_residual=0.,force=0.,moment=0.,normal_mach=0.)
for case in plan['cases']:
    folder=OUT/case['id'];r=read(folder/'report.json');control=case['control']
    assert r['plan_sha256']==digest and r['modes']==case['modes']
    for name,value in r['artifacts'].items():assert sha(folder/name)==value,name
    assert r['status']=='computed' and r['passed']==control['passing']
    raw=read(folder/'accepted.json');setup=read(folder/'setup.json')
    assert setup['condition']==dict(control['settings'],circulation_modes={'1':case['modes']})
    with np.load(folder/'state.npz') as archive:state={k:archive[k] for k in archive}
    with np.load(PARENT/control['id']/'fields.npz') as archive:g={k:archive[k] for k in archive}
    theta=state['theta'];modes=case['modes'];middle=.5*(theta[:-1]+theta[1:]);width=theta[:-1]-theta[1:]
    sample=np.sin(middle[:,None]*np.arange(1,modes+1));test=2/np.pi*sample.T*width
    errors['circulation']=max(errors['circulation'],float(max(abs(sample@state['coefficients']-state['gamma']))))
    residual=test@state['local_residual']
    errors['projection']=max(errors['projection'],float(max(abs(residual-state['projected_residual']))))
    assert abs(float(max(abs(residual)))-r['residual'])<2e-12 and r['residual']<1e-8
    alpha=math.radians(control['settings']['alpha']);speed=control['settings']['speed'];rho=control['settings']['density']
    rotation=np.array([[math.cos(alpha),0,math.sin(alpha)],[0,1,0],[-math.sin(alpha),0,math.cos(alpha)]])
    tensor=vortex_matrix(g['cp']@rotation.T,g['a']@rotation.T,g['b']@rotation.T,speed/340.21,
        core_fraction=0.,dtype=np.longdouble)
    tensor=np.einsum('ijq,qr->ijr',tensor,rotation)
    tensor*=np.longdouble(1)/(4*np.arccos(np.longdouble(-1))*np.longdouble('.079577472'))
    physical=np.asarray(np.einsum('ijk,ik->ij',tensor,g['normal']),dtype=float)
    matrix=test@physical@sample;rhs=test@(-speed*(g['normal']@rotation[0]))
    linear_coefficients=np.linalg.solve(matrix,rhs);linear_gamma=sample@linear_coefficients
    linear_difference=float(max(abs(linear_gamma-state['gamma']))/max(abs(state['gamma'])))
    assert linear_difference<1e-8,linear_difference
    model=parse_asw((ROOT/control['case']['original_job']['model_path']).read_text(),beam_interpolation='natural-v1')
    beam,=model.beams
    lower,upper,slope=[beam.value(k,g['t']) for k in ('CLmin','CLmax','dCLda')]
    # Printed Eq204 evaluated directly; retain its actual nonlinear leakage.
    cl=state['cl'];width_stall=control['settings']['stall_width']
    soft=width_stall*(np.log1p(np.exp((cl-upper)/width_stall))-np.log1p(np.exp((lower-cl)/width_stall)))
    perp=state['velocity']-np.sum(state['velocity']*g['span'],axis=1)[:,None]*g['span']
    normal_speed=np.linalg.norm(perp,axis=1)
    leak=normal_speed/slope*control['settings']['stall_factor']*soft
    reconstructed=(physical@state['gamma']+speed*(g['normal']@rotation[0])-leak)/speed
    errors['local_residual']=max(errors['local_residual'],float(max(abs(reconstructed-state['local_residual']))))
    raw_mach=np.array([s['normal_mach'] for s in raw['strips']])
    errors['normal_mach']=max(errors['normal_mach'],float(max(abs(normal_speed/340.21-raw_mach))))
    qs=.5*rho*speed**2*.9329
    force=[math.fsum(s['force'][k] for s in raw['strips']) for k in range(3)]
    drag=force[0]*math.cos(alpha)+force[2]*math.sin(alpha)
    lift=-force[0]*math.sin(alpha)+force[2]*math.cos(alpha)
    moment=math.fsum(s['moment'][1]+s['position'][2]*s['force'][0]-s['position'][0]*s['force'][2] for s in raw['strips'])
    errors['force']=max(errors['force'],abs(drag/qs-raw['CD']),abs(lift/qs-raw['CL']))
    errors['moment']=max(errors['moment'],abs(moment/(qs*.37874)-raw['Cm_origin']))
    columns=dict(lift=75,drag=76,CL=77,CD=78,CDi=79,Cm=80,efficiency=81)
    job=control['case']['original_job'];tokens=(ROOT/job['table_path']).read_text().splitlines()[job['reference_row']['line_number']-1].split()
    assert tokens==job['reference_row']['tokens']
    for name,col in columns.items():
        reference=float(tokens[col]);assert r['reference'][name]==reference
        assert r['checks'][name]==(abs(r['actual'][name]-reference)<=.05*abs(reference))
    singular=np.linalg.svd(matrix,compute_uv=False)
    r.update(report_sha256=sha(folder/'report.json'),control_id=control['id'],
        independent_linear_gamma_relative_error=linear_difference,
        independent_linear_system_residual=float(max(abs(matrix@linear_coefficients-rhs))/speed),
        independent_matrix_condition=float(singular[0]/singular[-1]),
        CD_error_change_percentage_points=r['relative_percent_errors']['CD']-control['relative_percent_errors']['CD'],
        control_CD_error_percent=control['relative_percent_errors']['CD'])
    rows.append(r)
assert errors['circulation']<2e-11 and errors['projection']<2e-12 and errors['local_residual']<2e-10
assert all(errors[k]<2e-12 for k in ('force','moment','normal_mach'))
groups=[]
for modes in (20,30,40):
    selected=[r for r in rows if r['modes']==modes]
    groups.append(dict(modes=modes,passed=sum(r['passed'] for r in selected),required=28,
        CD_errors={r['control_id']:r['relative_percent_errors']['CD'] for r in selected}))
analysis=dict(observed_utc=datetime.now(timezone.utc).isoformat(),verified=True,cases=rows,groups=groups,
    source_pins_verified=len(plan['pins']),maximum_reconstruction_errors=errors,
    maximum_linear_gamma_relative_error=max(r['independent_linear_gamma_relative_error'] for r in rows),
    maximum_projected_residual=max(r['residual'] for r in rows),
    local_residual_range=[min(r['maximum_local_residual'] for r in rows),max(r['maximum_local_residual'] for r in rows)],
    maximum_normal_mach=max(r['maximum_normal_mach'] for r in rows),
    minimum_stall_margin_widths=min(r['minimum_stall_margin_widths'] for r in rows),
    maximum_CD_error_change_percentage_points=max(abs(r['CD_error_change_percentage_points']) for r in rows),
    longest_invocation_seconds=max(r['seconds'] for r in rows),peak_rss_kib=max(r['peak_rss_kib'] for r in rows),
    physical_calls=12,primary_passes_added=0,production_equations_changed=False,
    plan_sha256=digest,checker_sha256=sha(Path(__file__)))
text=json.dumps(analysis,indent=2,allow_nan=False)+'\n'
with (OUT/'analysis.json').open('x') as f:f.write(text)
signal.alarm(0)
print(json.dumps({k:v for k,v in analysis.items() if k!='cases'},indent=2))
