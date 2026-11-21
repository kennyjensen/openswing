"""Check the six tip-local controls and compare their fixed-lift drag benefit."""
from datetime import datetime,timezone
from decimal import Decimal as D
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
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=read(OUT/'plan.json');pins=dict(plan['pins'])
for path,digest in pins.items():assert sha(ROOT/path)==digest,path
old=read(ROOT/'artifacts/isae/sa11-same-mainwing-mesh-20261108/analysis.json')
coarse=read(ROOT/'artifacts/isae/sa11-same-mainwing-20261108/analysis.json')
proofs={};geometry={};rows=[];curves={};force_error=0.
for config in ('wing_alone','upper_winglet'):
    path=OUT/f'verification-{config}.json';proofs[config]=read(path)
    assert proofs[config]['verified'] and proofs[config]['plan_sha256']==sha(OUT/'plan.json')
    pins[str(path.relative_to(ROOT))]=sha(path)
with np.load(ROOT/'artifacts/isae/sa11-paper-aligned-20261108/upper_winglet-m0_70-a21/geometry.npz') as f:
    original={key:f[key] for key in f}
for case in plan['cases']:
    folder=OUT/case['id'];path=folder/'report.json';row=read(path)
    assert sha(path)==proofs[case['configuration']]['report_sha256'][case['id']]
    assert row['status']=='computed' and row['case']==case
    pins[str(path.relative_to(ROOT))]=sha(path)
    for name,digest in row['artifacts'].items():
        assert sha(folder/name)==digest;pins[str((folder/name).relative_to(ROOT))]=digest
    with np.load(folder/'geometry.npz') as f:g={key:f[key] for key in f}
    # Exact identity of all retained interior fields and complete winglets.
    for key in original:
        assert np.array_equal(g[key][9:37],original[key][2:30]),key
        if case['configuration']=='upper_winglet':assert np.array_equal(g[key][46:],original[key][32:]),key
    assert min(g['ds'])>=.0164659927127284-1e-12
    if case['configuration'] in geometry:
        for key in g:assert np.array_equal(g[key],geometry[case['configuration']][key])
    else:geometry[case['configuration']]=g
    raw=read(folder/'accepted.json');alpha=math.radians(case['alpha'])
    e=np.array([math.cos(alpha),0.,math.sin(alpha)]);qs=.5*1.2256*240**2*.9329
    force=np.array([s['force'] for s in raw['strips']]);velocity=np.array([s['relative_velocity'] for s in raw['strips']])
    gamma=np.array([s['circulation'] for s in raw['strips']]);main=np.array([s['beam']==1 for s in raw['strips']])
    vortex=1.2256*gamma[:,None]*np.cross(velocity,g['span'])*g['ds'][:,None]
    parts={}
    for kind,vectors in [('vortex',vortex),('other',force-vortex)]:
        for name,mask in [('main',main),('tip',~main)]:
            parts[f'{name}_{kind}_CD']=math.fsum(map(float,(vectors[mask]@e)/qs))
    force_error=max(force_error,abs(sum(parts.values())-raw['CD']))
    assert force_error<2e-12
    curves.setdefault(case['configuration'],[]).append(dict(alpha=case['alpha'],**parts,
        **{key:raw[key] for key in ('CL','CD','CDi','CDi_near','CDp')}))
    rows.append(row)
for key in geometry['wing_alone']:
    assert np.array_equal(geometry['wing_alone'][key],geometry['upper_winglet'][key][:46]),key


def sample(points):
    points=sorted(points,key=lambda r:r['alpha'])
    a,b=next((a,b) for a,b in zip(points,points[1:]) if a['CL']<.5<b['CL'])
    assert b['alpha']-a['alpha']<=.25+1e-12
    w=(D('.5')-D(str(a['CL'])))/(D(str(b['CL']))-D(str(a['CL'])))
    return dict(values={key:float((1-w)*D(str(a[key]))+w*D(str(b[key]))) for key in a if key not in ('alpha','CL')},
                alpha_bracket=[a['alpha'],b['alpha']])


samples={config:sample(points) for config,points in curves.items()}
delta={key:samples['upper_winglet']['values'][key]-samples['wing_alone']['values'][key] for key in samples['wing_alone']['values']}
target=old['current62']['target_delta_CD'];target_i=old['current62']['target_delta_CDi_trefftz']
lift=next(r['CL'] for r in curves['upper_winglet'] if r['alpha']==3)-next(r['CL'] for r in curves['wing_alone'] if r['alpha']==3)
target_lift=next(r['target_delta_CL'] for r in coarse['upper_lift_changes'] if r['label']=='0_70' and r['alpha']==3)
change=delta['CD']-old['previous32']['actual_delta_CD']
batches=[read(p) for p in sorted(OUT.glob('batch-*.json'))];assert sum(b['count'] for b in batches)==6
for path in (Path(__file__),OUT/'plan.json',ROOT/'scripts/check_sa11_paper_aligned.py',
             ROOT/'artifacts/isae/sa11-same-mainwing-mesh-20261108/analysis.json',
             ROOT/'artifacts/isae/sa11-same-mainwing-20261108/analysis.json'):
    pins[str(path.relative_to(ROOT))]=sha(path)
result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),verified=True,pins=pins,
    curves=curves,matched_lift_samples=samples,delta=delta,
    native=dict(delta_CD=target,delta_CDi=target_i,delta_CL_at_alpha3=target_lift),
    signed_total_benefit_error_percent=100*(delta['CD']-target)/abs(target),
    signed_Trefftz_benefit_error_percent=100*(delta['CDi']-target_i)/abs(target_i),
    lift_increment_at_alpha3=lift,lift_increment_error_percent=100*(lift-target_lift)/abs(target_lift),
    total_increment_change_from32=change,
    fraction_of_whole_main_mesh_change_percent=100*change/old['change_in_drag_increment'],
    total_increment_difference_from62=delta['CD']-old['current62']['actual_delta_CD'],
    maximum_force_error=force_error,maximum_residual=max(r['residual'] for r in rows),
    maximum_normal_mach=max(r['maximum_normal_mach'] for r in rows),
    minimum_stall_margin_widths=min(r['minimum_stall_margin_widths'] for r in rows),
    maximum_batch_seconds=max(b['seconds'] for b in batches),peak_rss_kib=max(b['peak_rss_kib'] for b in batches),
    geometry_invariants=dict(main_intervals=46,original_interior_intervals_unchanged=28,winglets_exactly_unchanged=True,
        minimum_arc_interval=float(min(geometry['upper_winglet']['ds'])),cutoff_parameter=plan['cutoff_parameters'],
        coordinate='Main ASW t equals projected y in metres; outer0.2013m per side replaced, not arc length.'),
    physical_calls=6,computed=6,rejected=0,primary_passes_added=0,primary_count_changed=False,
    interpretation='A single prescribed local mesh control, not mesh convergence or a selected replacement. It tests localization while retaining interior geometry, winglet geometry, minimum spacing and force equations.')
with (OUT/'analysis.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
signal.alarm(0)
print(json.dumps({k:v for k,v in result.items() if k not in ('pins','curves','matched_lift_samples')},indent=2))
