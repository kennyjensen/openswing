"""Audit the geometry-only SA-11 control and decompose matched-lift drag."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(sys.argv[1]).resolve()
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(key)=='1'
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
import numpy as np
sys.path.insert(0,str(ROOT/'scripts'))
from sa11_paper_suite import interpolate,decision,write_new
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=read(OUT/'plan.json');proof=read(OUT/'verification-wing_alone.json')
assert proof['verified'] and proof['states']==50 and proof['plan_sha256']==sha(OUT/'plan.json')
pins=dict(plan['pins'])
for path,digest in pins.items():assert sha(ROOT/path)==digest,path
for path in (Path(__file__),OUT/'plan.json',OUT/'verification-wing_alone.json',ROOT/'scripts/sa11_paper_suite.py'):
    pins[str(path.relative_to(ROOT))]=sha(path)

# Verify the exact text operation independently of the preparation regex.
parent=(ROOT/plan['parent_model']).read_text().splitlines(keepends=True)
removed=set()
for block in plan['removed_source_blocks']:
    selected=parent[block['start_line']-1:block['end_line']]
    assert ''.join(selected)==block['text']
    assert selected[0].strip()=='Joint' or selected[0].split()[:2] in (['Beam','2'],['Beam','3'])
    assert selected[-1].strip()=='End'
    removed.update(range(block['start_line']-1,block['end_line']))
assert plan['added_comment']+''.join(line for i,line in enumerate(parent) if i not in removed)==(OUT/'model.asw').read_text()

UPPER_GEOMETRY=ROOT/'artifacts/isae/sa11-paper-aligned-20261108/upper_winglet-m0_70-a21/geometry.npz'
with np.load(UPPER_GEOMETRY) as saved:upper_geometry={k:saved[k] for k in saved}
pins[str(UPPER_GEOMETRY.relative_to(ROOT))]=sha(UPPER_GEOMETRY)
geometry=None;curves={};reports=[];force_errors=dict(total=0.,vortex=0.,nonvortex=0.,parts=0.)


def cross(a,b):
    return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def point(raw,alpha,speed,g,source):
    e=(math.cos(math.radians(alpha)),0.,math.sin(math.radians(alpha)))
    lift=(-e[2],0.,e[0]);qs=.5*1.2256*speed**2*.9329
    assert raw['converged'] and raw['residual']<1e-8
    assert all(abs(raw[key])<1e-14 for key in ('CDam','CDrate','CDbody','CDeng'))
    assert all(s['normal_mach']<1 and s['circulation_rate']==0 for s in raw['strips'])
    parts={name:[] for name in ('main_vortex_CD','tip_vortex_CD','main_other_CD','tip_other_CD')}
    clparts={name:[] for name in ('main_CL','tip_CL')}
    for i,s in enumerate(raw['strips']):
        assert s['length']==g['ds'][i]
        category='main' if s['beam']==1 else 'tip'
        vxspan=cross(s['relative_velocity'],g['span'][i])
        vortex=[1.2256*s['circulation']*s['length']*c for c in vxspan]
        other=[s['force'][k]-vortex[k] for k in range(3)]
        for term,force in (('vortex',vortex),('other',other)):
            parts[f'{category}_{term}_CD'].append(math.fsum(e[k]*force[k] for k in range(3))/qs)
        clparts[f'{category}_CL'].append(math.fsum(lift[k]*s['force'][k] for k in range(3))/qs)
    reduced={k:math.fsum(v) for k,v in {**parts,**clparts}.items()}
    force_errors['total']=max(force_errors['total'],abs(reduced['main_CL']+reduced['tip_CL']-raw['CL']))
    force_errors['parts']=max(force_errors['parts'],abs(sum(reduced[k] for k in parts)-raw['CD']))
    force_errors['vortex']=max(force_errors['vortex'],abs(reduced['main_vortex_CD']+reduced['tip_vortex_CD']-raw['CDi_near']))
    force_errors['nonvortex']=max(force_errors['nonvortex'],abs(reduced['main_other_CD']+reduced['tip_other_CD']-raw['CDp']))
    return dict(alpha=alpha,valid=True,source=source,**{k:raw[k] for k in ('CL','CD','CDi','CDi_near','CDp','Cm_origin','efficiency')},**reduced)


def reference(table):
    path=ROOT/table;pins[table]=sha(path)
    return [dict(alpha=float(t[71]),valid=True,CL=float(t[77]),CD=float(t[78]),CDi=float(t[79]))
        for line in path.read_text().splitlines() if len(t:=line.split())==82 and t[0].isdigit()]


references={}
for case in plan['cases']:
    folder=OUT/case['id'];path=folder/'report.json';row=read(path)
    assert row['case']==case and sha(path)==proof['report_sha256'][case['id']]
    pins[str(path.relative_to(ROOT))]=sha(path)
    for name,digest in row['artifacts'].items():
        assert sha(folder/name)==digest;pins[str((folder/name).relative_to(ROOT))]=digest
    with np.load(folder/'geometry.npz') as saved:g={k:saved[k] for k in saved}
    if geometry is None:
        geometry=g
        for key in g:assert np.array_equal(g[key],upper_geometry[key][:32]),key
    else:
        for key in g:assert np.array_equal(g[key],geometry[key]),key
    raw=read(folder/'accepted.json')
    assert len(raw['strips'])==32
    curves.setdefault(('control',case['label']),[]).append(point(raw,case['alpha'],case['condition']['speed'],g,str(path.relative_to(ROOT))))
    references.setdefault(('control',case['label']),reference(case['table']))
    reports.append(dict(row,report_sha256=sha(path)))
for case in plan['upper_controls']:
    path=ROOT/case['report'];row=read(path);raw=read(ROOT/case['accepted'])
    for i,s in enumerate(raw['strips'][:32]):
        assert s['length']==geometry['ds'][i] and s['position']==geometry['rm'][i].tolist()
        assert s['velocity_position']==geometry['hv'][i].tolist()
    speed=240. if case['label']=='0_70' else 272.
    curves.setdefault(('upper',case['label']),[]).append(point(raw,case['alpha'],speed,upper_geometry,case['report']))
    references.setdefault(('upper',case['label']),reference(row['case']['table']))
assert max(force_errors.values())<2e-12
for rows in curves.values():rows.sort(key=lambda p:p['alpha'])

scores=[];lift_changes=[];drag_changes=[]
def sample(rows,x,xkey,ykey):
    value,bracket,reason=interpolate(rows,x,xkey,ykey)
    assert reason is None,(x,xkey,ykey,reason)
    return value,bracket

for label in ('0_70','0_80'):
    bare,upper=curves['control',label],curves['upper',label]
    bare_ref,upper_ref=references['control',label],references['upper',label]
    for alpha in (1.,3.,5.):
        target,_=sample(bare_ref,alpha,'alpha','CL');value,bracket=sample(bare,alpha,'alpha','CL')
        status,error=decision(value,target,.05)
        scores.append(dict(label=label,kind='CL_at_alpha',x=alpha,target=target,actual=value,status=status,error_percent=error,bracket_alpha=bracket))
        u,_=sample(upper,alpha,'alpha','CL');ur,_=sample(upper_ref,alpha,'alpha','CL')
        lift_changes.append(dict(label=label,alpha=alpha,target_delta_CL=ur-target,actual_delta_CL=u-value,
            signed_percent_error=100*((u-value)-(ur-target))/abs(ur-target)))
    for cl in (.3,.5,.7):
        b,bb=sample(bare,cl,'CL','CD');u,ub=sample(upper,cl,'CL','CD')
        br,_=sample(bare_ref,cl,'CL','CD');ur,_=sample(upper_ref,cl,'CL','CD')
        status,error=decision(b,br,.05)
        scores.append(dict(label=label,kind='CD_at_CL',x=cl,target=br,actual=b,status=status,error_percent=error,bracket_alpha=bb))
        budget={key:sample(upper,cl,'CL',key)[0]-sample(bare,cl,'CL',key)[0]
                for key in ('main_vortex_CD','tip_vortex_CD','main_other_CD','tip_other_CD')}
        assert abs(sum(budget.values())-(u-b))<2e-12
        actual_trefftz=sample(upper,cl,'CL','CDi')[0]-sample(bare,cl,'CL','CDi')[0]
        target_trefftz=sample(upper_ref,cl,'CL','CDi')[0]-sample(bare_ref,cl,'CL','CDi')[0]
        drag_changes.append(dict(label=label,CL=cl,target_delta_CD=ur-br,actual_delta_CD=u-b,
            signed_percent_error=100*((u-b)-(ur-br))/abs(ur-br),
            target_delta_CDi_trefftz=target_trefftz,actual_delta_CDi_trefftz=actual_trefftz,
            delta_CD_budget=budget,baseline_bracket_alpha=bb,upper_bracket_alpha=ub,
            shared_main_wing=True,counted_in_primary=False))
assert len(scores)==12 and len(lift_changes)==len(drag_changes)==6
batches=[read(p) for p in sorted(OUT.glob('batch-*.json'))]
assert [r['id'] for b in batches for r in b['rows']]==[c['id'] for c in plan['cases']]
summary=dict(observed_utc=datetime.now(timezone.utc).isoformat(),verified=True,curves=[dict(configuration=k[0],label=k[1],points=v,reference=references[k]) for k,v in curves.items()],
    baseline_paper_checks=scores,baseline_counts=dict(Counter(c['status'] for c in scores)),required=12,
    upper_lift_changes=lift_changes,upper_drag_changes=drag_changes,force_decomposition_errors=force_errors,
    physical_calls=sum(r['physical_calls'] for r in reports),reused_upper_states=43,computed=50,rejected=0,
    maximum_residual=max(r['residual'] for r in reports),maximum_normal_mach=max(r['maximum_normal_mach'] for r in reports),
    minimum_stall_margin_widths=min(r['minimum_stall_margin_widths'] for r in reports),
    maximum_batch_seconds=max(b['seconds'] for b in batches),total_batch_seconds=sum(b['seconds'] for b in batches),
    peak_rss_kib=max(b['peak_rss_kib'] for b in batches),pins=pins,plan_sha256=sha(OUT/'plan.json'),
    primary_count=dict(passed=21,required=48,changed=False),original_count=dict(passed=1060,required=9184,changed=False),
    interpretation='Geometry-only winglet removal from the same report-derived main wing. Compared to archived baseline as a disclosed alternative, not authenticated historical input. Native deltaCDi is Trefftz, and native CD-CDi must not be labelled profile drag.')
write_new(OUT/'analysis.json',summary)
signal.alarm(0)
print(json.dumps({k:v for k,v in summary.items() if k not in ('curves','pins','baseline_paper_checks')},indent=2))
