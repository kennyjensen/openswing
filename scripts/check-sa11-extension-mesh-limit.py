"""Audit mesh-limit runs and target-independent successive force changes."""
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
resource.setrlimit(resource.RLIMIT_AS, (512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU, (15,15))
signal.alarm(25)
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from avl_vorvelc_reference import matrix as vortex_matrix
OUT = ROOT/'artifacts/isae/sa11-extension-mesh-limit-20261108'
PARENT = ROOT/'artifacts/isae/sa11-extension-drag-budget-r2-20261108'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
plan = read(OUT/'plan.json')
digest = sha(OUT/'plan.json')
for path, expected in plan['pins'].items():
    assert sha(ROOT/path) == expected, path
errors = dict(force=0.,moment=0.,normal_mach=0.,velocity_relative=0.,vortex_CD=0.,bound_source_speed=0.)


def inspect(raw, g, settings, independent_velocity):
    alpha = math.radians(settings['alpha'])
    rho, speed = settings['density'], settings['speed']
    rotation = np.array([[math.cos(alpha),0,math.sin(alpha)],[0,1,0],[-math.sin(alpha),0,math.cos(alpha)]])
    qs = .5*rho*speed**2*.9329
    strips = raw['strips']
    assert raw['converged'] and raw['residual'] < 1e-8
    assert np.array_equal(g['ds'],[s['length'] for s in strips])
    assert min(g['ds']) >= plan['minimum_spacing']-1e-12
    v = np.array([s['relative_velocity'] for s in strips])
    gamma = np.array([s['circulation'] for s in strips])
    perp = v-np.sum(v*g['span'],axis=1)[:,None]*g['span']
    mach = np.linalg.norm(perp,axis=1)/340.21
    errors['normal_mach'] = max(errors['normal_mach'],float(max(abs(mach-np.array([s['normal_mach'] for s in strips])))))
    assert max(mach) < 1
    if independent_velocity:
        tensor = vortex_matrix(g['hv']@rotation.T,g['a']@rotation.T,g['b']@rotation.T,
                               speed/340.21,exclude_self=True,core_fraction=0.,dtype=np.longdouble)
        velocity = np.einsum('ijq,j->iq',tensor,gamma)@rotation
        velocity *= np.longdouble(1)/(4*np.arccos(np.longdouble(-1))*np.longdouble('.079577472'))
        velocity += speed*rotation[0]
        errors['velocity_relative'] = max(errors['velocity_relative'],float(np.max(abs(velocity-v))/speed))
        del tensor
    force = [math.fsum(s['force'][k] for s in strips) for k in range(3)]
    cd, cl = float(np.dot(force,rotation[0])/qs), float(np.dot(force,rotation[2])/qs)
    moment = math.fsum(s['moment'][1]+s['position'][2]*s['force'][0]-s['position'][0]*s['force'][2] for s in strips)
    errors['force'] = max(errors['force'],abs(cd-raw['CD']),abs(cl-raw['CL']))
    errors['moment'] = max(errors['moment'],abs(moment/(qs*.37874)-raw['Cm_origin']))
    vortex = rho*gamma[:,None]*np.cross(v,g['span'])*g['ds'][:,None]
    vortex_cd = (vortex@rotation[0])/qs
    errors['vortex_CD'] = max(errors['vortex_CD'],abs(float(sum(vortex_cd))-raw['CDi_near']))
    center = np.argsort(abs(g['t']))[:2]
    assert g['t'][center[0]]*g['t'][center[1]] < 0
    return dict(center_pair_CD=float(sum(vortex_cd[center])),
        other_strips_CD=float(sum(vortex_cd)-sum(vortex_cd[center])),
        center_pair_t=g['t'][center].tolist(),center_pair_lengths=g['ds'][center].tolist(),
        maximum_normal_mach=float(max(mach)))


rows = []
for case in plan['cases']:
    folder = OUT/case['id']
    row = read(folder/'report.json')
    assert row['plan_sha256'] == digest and row['settings'] == case['control']['settings']
    for name, expected in row['artifacts'].items():
        assert sha(folder/name) == expected, name
    with np.load(folder/'geometry.npz') as saved:
        g = {key:saved[key] for key in saved}
    assert len(g['ds']) == row['actual_intervals'] == case['preflight']['actual_intervals']
    if row['status'] == 'computed':
        raw = read(folder/'accepted.json')
        row['center_budget'] = inspect(raw,g,row['settings'],True)
        for key,value in row['actual'].items():
            assert abs(100*(value-row['reference'][key])/abs(row['reference'][key])-row['relative_percent_errors'][key]) < 2e-10
        assert sum(abs(v)<=5 for v in row['relative_percent_errors'].values()) == row['passed']
    else:
        assert row['status'] == 'rejected' and row['passed'] == 0 and row['actual'] is None
        reject = read(folder/'rejected.json')['details']
        assert reject['kind']=='section_normal_mach' and reject['circulation_residual']<1e-8
        assert reject['maximum']['normal_mach']>=1 and len(reject['rejected_sections'])==2
        # Independently reconstruct the dominant finite-bound segment in the wind/PG frame.
        source = reject['vortex_breakdown']['bound_sources'][0]
        angle = math.radians(row['settings']['alpha'])
        rotation = np.array([[math.cos(angle),0,math.sin(angle)],[0,1,0],[-math.sin(angle),0,math.cos(angle)]],dtype=np.longdouble)
        point = np.array(reject['vortex_breakdown']['influence_receiver'],dtype=np.longdouble)
        a,b = [(np.array(source[key],dtype=np.longdouble)-point)@rotation.T for key in ('start','end')]
        beta = np.sqrt(np.longdouble(1)-(np.longdouble(row['settings']['speed'])/np.longdouble('340.21'))**2)
        a[0]/=beta; b[0]/=beta
        na,nb = np.linalg.norm(a),np.linalg.norm(b)
        cross = np.cross(a,b)
        velocity = cross*((np.dot(b,b)-np.dot(a,b))/nb+(np.dot(a,a)-np.dot(a,b))/na)/np.dot(cross,cross)
        velocity *= np.longdouble(source['circulation'])/(4*np.arccos(np.longdouble(-1)))
        velocity[0]/=beta
        velocity = velocity@rotation
        errors['bound_source_speed'] = max(errors['bound_source_speed'],float(np.max(abs(velocity-source['velocity']))))
        row['rejection'] = dict(maximum=reject['maximum'],circulation_residual=reject['circulation_residual'],
            dominant_bound=source,bound_velocity=reject['vortex_breakdown']['bound_velocity'],
            wake_velocity=reject['vortex_breakdown']['wake_velocity'],
            formal_CD=reject['surface_force_diagnostic']['terms']['sum']['CD'])
    row['report_sha256']=sha(folder/'report.json')
    rows.append(row)

controls=[]
for original in plan['controls']:
    folder=PARENT/original['id']
    with np.load(folder/'fields.npz') as saved:
        g={key:saved[key] for key in saved}
    raw=read(folder/'accepted.json')
    row=dict(original,status='computed',requested_intervals=original['case']['original_job']['settings']['panels'],
             actual_intervals=original['intervals'],center_budget=inspect(raw,g,original['settings'],False))
    controls.append(row)

groups=[]
for speed in (240,272):
    for alpha in (3,5):
        selected=sorted([r for r in [*controls,*rows] if r['settings']['speed']==speed and r['settings']['alpha']==alpha],
                        key=lambda r:r['requested_intervals'])
        changes=[]
        for old,new in zip(selected,selected[1:]):
            stable=old['status']==new['status']=='computed'
            change={key:100*abs(new['actual'][key]-old['actual'][key])/abs(new['actual'][key])
                    for key in plan['stability']['metrics']} if stable else None
            budget={key:new['center_budget'][key]-old['center_budget'][key]
                    for key in ('center_pair_CD','other_strips_CD')} if stable else None
            if budget is not None:
                budget['total_vortex_CD_change']=new['CDi_near']-old['CDi_near']
                assert abs(budget['center_pair_CD']+budget['other_strips_CD']-budget['total_vortex_CD_change'])<2e-12
            changes.append(dict(old=old['id'],new=new['id'],relative_changes_percent=change,center_budget_change=budget))
        last=changes[-2:]
        stable=all(r['relative_changes_percent'] is not None and max(r['relative_changes_percent'].values())<=1 for r in last)
        groups.append(dict(speed=speed,alpha=alpha,states=selected,successive_changes=changes,
                           stable_over_last_two_refinements=stable))
assert errors['force']<2e-12 and errors['moment']<2e-12 and errors['vortex_CD']<2e-12
assert errors['normal_mach']<2e-12 and errors['velocity_relative']<2e-10 and errors['bound_source_speed']<2e-8
summary=dict(observed_utc=datetime.now(timezone.utc).isoformat(),verified=True,cases=rows,groups=groups,
    maximum_independent_errors=errors,source_pins_verified=len(plan['pins']),physical_calls=12,
    computed=sum(r['status']=='computed' for r in rows),rejected=sum(r['status']=='rejected' for r in rows),
    primary_passes_added=0,primary_count_changed=False,
    maximum_residual=max(r.get('residual',r.get('rejection',{}).get('circulation_residual',0)) for r in rows),
    minimum_stall_margin_widths=min(r['minimum_stall_margin_widths'] for r in rows if r['status']=='computed'),
    maximum_seconds=max(r['seconds'] for r in rows),peak_rss_kib=max(r['peak_rss_kib'] for r in rows),
    plan_sha256=digest,checker_sha256=sha(Path(__file__)))
text=json.dumps(summary,indent=2,allow_nan=False)+'\n'
with (OUT/'analysis.json').open('x') as stream:
    stream.write(text)
signal.alarm(0)
print(json.dumps({k:v for k,v in summary.items() if k not in ('cases','groups')},indent=2))
for group in groups:
    print(json.dumps({k:v for k,v in group.items() if k!='states'},indent=2))
