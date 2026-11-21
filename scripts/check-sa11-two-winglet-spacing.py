"""Verify saved SA-11 upper/lower fields and audit stall/own-wake terms.

No aerodynamic solve. Scalar reference/force/moment/Mach reductions and direct
Eq.204 evaluation are independent of the comparison driver's calculations.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys

for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    assert os.environ.get(key) == '1'
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(15,15)); signal.alarm(25)
import numpy as np

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
from openswing.factored_influence import FactoredInfluence
from openswing.ground import GroundPlane

OUT = ROOT/'artifacts/isae/sa11-two-winglet-spacing-20261108'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
plan = read(OUT/'plan.json'); analysis = read(OUT/'analysis.json')
assert analysis['plan_sha256'] == sha(OUT/'plan.json')
for name,digest in plan['pins'].items(): assert sha(ROOT/name)==digest,name
for name,digest in plan['generated_pins'].items(): assert sha(OUT/name)==digest,name
manifest_path = ROOT/'reference/isae-validation/manifest.json'
manifest = read(manifest_path); cache = manifest_path.parent/manifest['revision']; tables = {}
for name in {c['table'] for c in plan['cases']}:
    path = ROOT/name; content = path.read_bytes(); entry = manifest['files'][str(path.relative_to(cache))]
    assert sha(path)==entry['sha256'] and len(content)==entry['bytes']
    assert hashlib.sha1(f'blob {len(content)}\0'.encode()+content).hexdigest()==entry['git_blob_sha1']
    tables[name] = [r.split() for r in content.decode().splitlines() if len(r.split())==82 and r.split()[0].isdigit()]

source = (OUT/'source-joint-corrected.asw').read_text().splitlines()
for edit in plan['edits']:
    assert source[edit['line']-1]==edit['before']
    before,after=edit['before'].split(),edit['after'].split()
    assert before[:4]+before[5:]==after[:4]+after[5:] and before[4]=='4' and after[4]=='-4'
    source[edit['line']-1] = edit['after']
assert '\n'.join(source)+'\n'==(OUT/'model.asw').read_text()
model = parse_asw((OUT/'model.asw').read_text())
upper = parse_asw((ROOT/'artifacts/isae/sa11-minimum-spacing-20261108/model.asw').read_text())
meshes = model_meshes(model,dict(default=32,beams=read(OUT/'mesh.json')))
assert [len(m.tm) for m in meshes]==[32,16,16,5,5]
sample = lambda key: np.concatenate([m.beam.value(key,m.tm) for m in meshes])
lower,limit,slope = sample('CLmin'),sample('CLmax'),sample('dCLda')
assert np.all(limit==.8) and np.all(slope==6.34) and np.all(lower==-2)
assert all(np.all(b.value('CLmax',b.domain)==2) for b in upper.beams)
normal = np.concatenate([np.sin(np.deg2rad(m.beam.value('alpha',m.tm)))[:,None]*m.frames[...,0]
                         +np.cos(np.deg2rad(m.beam.value('alpha',m.tm)))[:,None]*m.frames[...,2] for m in meshes])
rho,sound = model.constants[1:3] if hasattr(model,'constants') else (1.2256,340.21)
assert rho==1.2256 and sound==340.21
area,chord,_ = model.reference[0]
fields = dict(lift=75,drag=76,CL=77,CD=78,CDi=79,Cm_origin=80,efficiency=81)
errors = dict(force_coefficients=0.,moment_coefficient=0.,normal_mach=0.,percent=0.,force_vector=0.,tangency_residual=0.,own_ray=0.)
rows = []; first = None; passes = 0; accepted_count = 0
for item,case in zip(analysis['cases'],plan['cases'],strict=True):
    folder = OUT/case['id']; assert item['case']==case
    assert sha(folder/'report.json')==item['report_sha256']
    for name,digest in item['artifacts'].items(): assert sha(folder/name)==digest,name
    assert case['tokens']==tables[case['table']][case['row']]
    raw = list(map(float,case['tokens'])); speed=raw[69]; alpha=math.radians(raw[71]); qs=.5*rho*speed**2*area
    accepted = item['status']=='COMPUTED_DIAGNOSTIC'; accepted_count+=accepted
    if accepted:
        result = read(folder/'accepted.json'); assert result['converged']
    else:
        rejected = read(folder/'rejected.json')['details']; assert rejected['kind']=='section_normal_mach'
        assert item['values']['Cm_origin'] is None and not (folder/'accepted.json').exists()
    with np.load(folder/'state.npz') as archive, np.load(folder/'geometry.npz') as geometry:
        d={k:archive[k] for k in archive}; g={k:geometry[k] for k in geometry}
    assert bool(d['section_moment_available'])==accepted
    assert np.all(np.isfinite(d['section_moment'])) if accepted else np.all(np.isnan(d['section_moment']))
    if first is None: first=g
    else:
        for key in g: np.testing.assert_array_equal(g[key],first[key])
    force = [math.fsum(map(float,d['force'][:,i])) for i in range(3)]
    predicted = dict(lift=-math.sin(alpha)*force[0]+math.cos(alpha)*force[2],drag=math.cos(alpha)*force[0]+math.sin(alpha)*force[2])
    predicted.update(CL=predicted['lift']/qs,CD=predicted['drag']/qs)
    if accepted:
        moment=math.fsum(float(m[1])+float(r[2])*float(f[0])-float(r[0])*float(f[2]) for r,f,m in zip(d['position'],d['force'],d['section_moment']))
        predicted['Cm_origin']=moment/(qs*chord)
        errors['moment_coefficient']=max(errors['moment_coefficient'],abs(predicted['Cm_origin']-item['values']['Cm_origin']))
    for key in ('CL','CD'): errors['force_coefficients']=max(errors['force_coefficients'],abs(predicted[key]-item['values'][key]))
    mach=[]
    for v,s in zip(d['velocity'],d['span']):
        dot=math.fsum(float(a)*float(b) for a,b in zip(v,s))
        mach.append(math.sqrt(math.fsum((float(a)-dot*float(b))**2 for a,b in zip(v,s)))/sound)
    errors['normal_mach']=max(errors['normal_mach'],max(abs(a-b) for a,b in zip(mach,d['mach'])))
    invalid=[i for i,v in enumerate(mach) if v>=1]
    assert len(invalid)==item['rejected_sections'] and (not invalid)==accepted
    if invalid: assert invalid==sorted(s['panel_index'] for s in rejected['rejected_sections'])
    for key,col in fields.items():
        assert raw[col]==case['reference'][key]
        value=predicted.get(key,item['values'][key]); err=None if value is None else 100*(value/raw[col]-1)
        if err is not None: errors['percent']=max(errors['percent'],abs(err-item['reference_error_percent'][key]))
        passed=bool(accepted and abs(err)<=5); assert passed==item['passes'][key]; passes+=passed
    # Direct printed Eq.204, with saved section CL. No production stall helper.
    width=case['condition']['stall_width']; strength=case['condition']['stall_factor']
    f=np.array([width*(math.log1p(math.exp((float(c)-float(hi))/width))-math.log1p(math.exp((float(lo)-float(c))/width))) for c,lo,hi in zip(d['cl'],lower,limit)])
    vp=d['velocity']-np.sum(d['velocity']*d['span'],axis=1)[:,None]*d['span']; vp_speed=np.linalg.norm(vp,axis=1)
    beta=math.sqrt(1-case['condition']['mach']**2); pg=np.diag([1/beta,1.,1.])
    cp=FactoredInfluence(g['cp'],g['a'],g['b'],np.array([1.,0.,0.]),pg,0.,GroundPlane())
    vcp=speed*np.array([math.cos(alpha),0.,math.sin(alpha)])+cp.apply(d['gamma'])
    tangency=np.sum(vcp*normal,axis=1); leak=vp_speed*strength*f/slope
    errors['tangency_residual']=max(errors['tangency_residual'],float(np.max(abs(tangency-leak))/speed))
    force_vortex=rho*d['gamma'][:,None]*np.cross(d['velocity'],d['span'])*g['ds'][:,None]
    force_friction=.5*rho*np.linalg.norm(d['velocity'],axis=1)[:,None]*d['velocity']*(g['chord']*sample('Cdf')*g['ds'])[:,None]
    force_pressure=.5*rho*vp_speed[:,None]*vp*(g['chord']*sample('Cdp')*g['ds'])[:,None]
    force_leak=2*rho*vp/vp_speed[:,None]*(tangency**2*g['chord']*g['ds'])[:,None]
    errors['force_vector']=max(errors['force_vector'],float(np.max(abs(force_vortex+force_friction+force_pressure+force_leak-d['force']))))
    axis=np.array([math.cos(alpha),0.,math.sin(alpha)])
    drag_parts={key:float(np.sum(value@axis)/qs) for key,value in [('vortex',force_vortex),('friction',force_friction),('pressure',force_pressure),('stall_leakage',force_leak)]}
    worst=int(np.argmax(mach)); own_origin=g['b'][worst]; displacement=g['hv'][worst]-own_origin
    # At the left lower root, the root ray is this strip's own b-leg.
    assert int(d['beam'][worst])==5
    dx,dy,dz=displacement; radius=math.hypot(dy,dz); xp=dx/beta; length=math.sqrt(xp*xp+radius*radius)
    own_ray=np.array([0.,-dz,dy])*float(d['gamma'][worst])/(4*math.pi*radius**2)*(1+xp/length)
    if invalid:
        ray=rejected['vortex_breakdown']['wake_sources'][0]
        assert ray['sources']==[dict(panel_index=worst,beam=5,strip_t=ray['sources'][0]['strip_t'],endpoint='b',signed_circulation=float(d['gamma'][worst]))]
        np.testing.assert_array_equal(own_origin,ray['origin'])
        errors['own_ray']=max(errors['own_ray'],float(np.max(abs(own_ray-ray['velocity']))))
    rows.append(dict(case=case['id'],alpha=raw[71],speed=speed,maximum_normal_mach=max(mach),
        maximum_leakage_angle_degrees=math.degrees(float(np.max(abs(strength*f/slope)))),
        leakage_angle_degrees_by_beam={str(b):math.degrees(float(np.max(abs(strength*f[d['beam']==b]/slope[d['beam']==b])))) for b in range(1,6)},
        drag_parts=drag_parts,root_own_ray_speed=float(np.linalg.norm(own_ray)),root_own_ray_distance=float(radius),
        root_total_wake_speed=float(np.linalg.norm(d['wake'][worst])),cl_above_limit=int(np.count_nonzero(d['cl']>limit))))

assert passes==analysis['passing_scalar_targets']==11 and accepted_count==5
assert errors['force_coefficients']<3e-14 and errors['moment_coefficient']<2e-12 and errors['normal_mach']<3e-14
assert errors['percent']<3e-10 and errors['tangency_residual']<1e-8 and errors['force_vector']<1e-9 and errors['own_ray']<1e-10
summary=dict(verified_utc=datetime.now(timezone.utc).isoformat(),source_pins_verified=len(plan['pins']),
    cases=6,accepted=accepted_count,passing_scalar_targets=passes,required_scalar_targets=42,errors=errors,
    section_input_comparison=dict(upper_only_CLmax=2.,upper_and_lower_CLmax=.8,CLmin=-2.,dCLda=6.34),
    diagnostics=rows,analysis_sha256=sha(OUT/'analysis.json'),script_sha256=sha(Path(__file__)),
    source_manifest_sha256=sha(manifest_path),primary_passes_added=0)
path=OUT/'verification.json'; assert not path.exists(); path.write_text(json.dumps(summary,indent=2)+'\n')
signal.alarm(0)
print(json.dumps(summary,indent=2))
