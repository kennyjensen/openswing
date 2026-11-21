"""Reduce the six main-wing mesh controls without changing validation scope."""
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys

ROOT=Path(__file__).resolve().parents[1];OUT=Path(sys.argv[1]).resolve()
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(key)=='1'
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
import numpy as np
sys.path.insert(0,str(ROOT/'scripts'))
from sa11_paper_suite import interpolate,write_new
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=read(OUT/'plan.json');pins=dict(plan['pins'])
for path,digest in pins.items():assert sha(ROOT/path)==digest,path
parent_path=ROOT/'artifacts/isae/sa11-same-mainwing-20261108/analysis.json'
parent=read(parent_path);assert parent['verified']
prior=next(r for r in parent['upper_drag_changes'] if r['label']=='0_70' and r['CL']==.5)
proofs={}
for config in ('wing_alone','upper_winglet'):
    p=OUT/f'verification-{config}.json';proofs[config]=read(p)
    assert proofs[config]['verified'] and proofs[config]['plan_sha256']==sha(OUT/'plan.json')
    pins[str(p.relative_to(ROOT))]=sha(p)
curves={};rows=[];decomposition_error=0.
for case in plan['cases']:
    folder=OUT/case['id'];p=folder/'report.json';row=read(p)
    assert row['case']==case and sha(p)==proofs[case['configuration']]['report_sha256'][case['id']]
    pins[str(p.relative_to(ROOT))]=sha(p)
    for name,digest in row['artifacts'].items():
        assert sha(folder/name)==digest;pins[str((folder/name).relative_to(ROOT))]=digest
    raw=read(folder/'accepted.json')
    assert row['status']=='computed' and raw['converged'] and raw['residual']<1e-8
    with np.load(folder/'geometry.npz') as saved:g={k:saved[k] for k in saved}
    alpha=math.radians(case['alpha']);e=np.array([math.cos(alpha),0.,math.sin(alpha)])
    qs=.5*1.2256*240**2*.9329
    gamma=np.array([s['circulation'] for s in raw['strips']]);velocity=np.array([s['relative_velocity'] for s in raw['strips']])
    force=np.array([s['force'] for s in raw['strips']]);main=np.array([s['beam']==1 for s in raw['strips']])
    vortex=1.2256*gamma[:,None]*np.cross(velocity,g['span'])*g['ds'][:,None]
    parts={}
    for name,mask in (('main',main),('tip',~main)):
        for component,vectors in (('vortex',vortex),('other',force-vortex)):
            parts[f'{name}_{component}_CD']=math.fsum(map(float,(vectors[mask]@e)/qs))
    decomposition_error=max(decomposition_error,abs(sum(parts.values())-raw['CD']))
    point=dict(alpha=case['alpha'],valid=True,**{key:raw[key] for key in ('CL','CD','CDi','CDi_near','CDp')},**parts)
    curves.setdefault(case['configuration'],[]).append(point);rows.append(row)
assert decomposition_error<2e-12
samples={}
for config,points in curves.items():
    samples[config]={}
    for key in ('CD','CDi','CDi_near','CDp','main_vortex_CD','tip_vortex_CD','main_other_CD','tip_other_CD'):
        value,bracket,reason=interpolate(points,.5,'CL',key)
        assert reason is None and value is not None
        samples[config][key]=value;samples[config]['bracket_alpha']=bracket
delta={key:samples['upper_winglet'][key]-samples['wing_alone'][key] for key in samples['wing_alone'] if key!='bracket_alpha'}
assert abs(delta['CD']-delta['CDi_near']-delta['CDp'])<2e-12
budget={key:delta[key] for key in ('main_vortex_CD','tip_vortex_CD','main_other_CD','tip_other_CD')}
assert abs(sum(budget.values())-delta['CD'])<2e-12
changes={key:budget[key]-prior['delta_CD_budget'][key] for key in budget}
assert abs(sum(changes.values())-(delta['CD']-prior['actual_delta_CD']))<2e-12
old_cl=next(r for r in parent['upper_lift_changes'] if r['label']=='0_70' and r['alpha']==3)
new_cl=next(p['CL'] for p in curves['upper_winglet'] if p['alpha']==3)-next(p['CL'] for p in curves['wing_alone'] if p['alpha']==3)
batches=[read(p) for p in sorted(OUT.glob('batch-*.json'))]
assert sum(b['count'] for b in batches)==6
for path in (Path(__file__),OUT/'plan.json',parent_path,ROOT/'scripts/sa11_paper_suite.py'):
    pins[str(path.relative_to(ROOT))]=sha(path)
summary=dict(observed_utc=datetime.now(timezone.utc).isoformat(),verified=True,pins=pins,
    curves=curves,matched_lift_samples=samples,previous32=prior,current62=dict(CL=.5,label='0_70',
        target_delta_CD=prior['target_delta_CD'],actual_delta_CD=delta['CD'],
        signed_percent_error=100*(delta['CD']-prior['target_delta_CD'])/abs(prior['target_delta_CD']),
        target_delta_CDi_trefftz=prior['target_delta_CDi_trefftz'],actual_delta_CDi_trefftz=delta['CDi'],
        trefftz_signed_percent_error=100*(delta['CDi']-prior['target_delta_CDi_trefftz'])/abs(prior['target_delta_CDi_trefftz']),
        delta_CD_budget=budget,delta_CDi_near=delta['CDi_near'],delta_CD_profile_and_leakage=delta['CDp']),
    lift_increment_alpha3=dict(target=old_cl['target_delta_CL'],actual32=old_cl['actual_delta_CL'],actual62=new_cl,
        signed_percent_error62=100*(new_cl-old_cl['target_delta_CL'])/abs(old_cl['target_delta_CL'])),
    change_in_drag_increment=delta['CD']-prior['actual_delta_CD'],change_in_drag_increment_budget=changes,
    decomposition_error=decomposition_error,physical_calls=6,computed=6,rejected=0,
    maximum_normal_mach=max(r['maximum_normal_mach'] for r in rows),maximum_residual=max(r['residual'] for r in rows),
    minimum_stall_margin_widths=min(r['minimum_stall_margin_widths'] for r in rows),
    maximum_batch_seconds=max(b['seconds'] for b in batches),peak_rss_kib=max(b['peak_rss_kib'] for b in batches),
    primary_passes_added=0,primary_count_changed=False,
    finding='The same-main-wing drag increment is sensitive to main-wing discretization even with exactly unchanged16-interval winglets. Trefftz induced-drag reduction is close on the62-main-interval control. This is diagnostic evidence, not a mesh-convergence claim, production fix or additional primary pass.')
write_new(OUT/'analysis.json',summary)
signal.alarm(0)
print(json.dumps({k:v for k,v in summary.items() if k not in ('pins','curves','previous32')},indent=2))
