"""Independent Decimal reductions for both same-main-wing diagnostics."""
from datetime import datetime,timezone
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import resource
import signal

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/sa11-same-mainwing-20261108'
MESH=ROOT/'artifacts/isae/sa11-same-mainwing-mesh-20261108'
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
base=read(BASE/'analysis.json');mesh=read(MESH/'analysis.json')
pins={**base['pins'],**mesh['pins']}
for path,digest in pins.items():assert sha(ROOT/path)==digest,path


def sample(rows,x,xkey,ykey):
    rows=sorted(rows,key=lambda r:r['alpha']);x=D(str(x))
    assert all(r['valid'] for r in rows)
    for r in rows:
        if D(str(r[xkey]))==x:return D(str(r[ykey]))
    for a,b in zip(rows,rows[1:]):
        xa,xb=D(str(a[xkey])),D(str(b[xkey]))
        if xa<x<xb:
            assert b['alpha']-a['alpha']<=.25+1e-12
            return D(str(a[ykey]))+(x-xa)*(D(str(b[ykey]))-D(str(a[ykey])))/(xb-xa)
    raise AssertionError('No accepted bracket')


error=0.
def near(value,expected,tol=2e-12):
    global error
    difference=abs(float(value)-expected);assert difference<tol,(value,expected)
    error=max(error,difference)


curves={(c['configuration'],c['label']):c for c in base['curves']}
passed=0
for c in base['baseline_paper_checks']:
    curve=curves['control',c['label']]
    xkey,ykey=('alpha','CL') if c['kind']=='CL_at_alpha' else ('CL','CD')
    actual=sample(curve['points'],c['x'],xkey,ykey)
    target=sample(curve['reference'],c['x'],xkey,ykey)
    near(actual,c['actual']);near(target,c['target'])
    e=100*(actual-target)/abs(target);near(e,c['error_percent'])
    assert c['status']==('pass' if abs(e)<=5 else 'mismatch');passed+=abs(e)<=5
assert passed==base['baseline_counts']['pass']==6 and len(base['baseline_paper_checks'])==12
for c in base['upper_drag_changes']:
    upper=curves['upper',c['label']];bare=curves['control',c['label']]
    actual=sample(upper['points'],c['CL'],'CL','CD')-sample(bare['points'],c['CL'],'CL','CD')
    target=sample(upper['reference'],c['CL'],'CL','CD')-sample(bare['reference'],c['CL'],'CL','CD')
    near(actual,c['actual_delta_CD']);near(target,c['target_delta_CD'])
    near(100*(actual-target)/abs(target),c['signed_percent_error'])
    for term,value in c['delta_CD_budget'].items():
        near(sample(upper['points'],c['CL'],'CL',term)-sample(bare['points'],c['CL'],'CL',term),value)
    assert abs(sum(D(str(v)) for v in c['delta_CD_budget'].values())-actual)<D('2e-12')
    for source,key in [('points','actual_delta_CDi_trefftz'),('reference','target_delta_CDi_trefftz')]:
        near(sample(upper[source],c['CL'],'CL','CDi')-sample(bare[source],c['CL'],'CL','CDi'),c[key])
for c in base['upper_lift_changes']:
    upper=curves['upper',c['label']];bare=curves['control',c['label']]
    for source,key in [('points','actual_delta_CL'),('reference','target_delta_CL')]:
        near(sample(upper[source],c['alpha'],'alpha','CL')-sample(bare[source],c['alpha'],'alpha','CL'),c[key])
for config,values in mesh['matched_lift_samples'].items():
    for key,value in values.items():
        if key!='bracket_alpha':near(sample(mesh['curves'][config],.5,'CL',key),value)
new=mesh['current62'];u=mesh['curves']['upper_winglet'];b=mesh['curves']['wing_alone']
actual=sample(u,.5,'CL','CD')-sample(b,.5,'CL','CD');near(actual,new['actual_delta_CD'])
trefftz=sample(u,.5,'CL','CDi')-sample(b,.5,'CL','CDi');near(trefftz,new['actual_delta_CDi_trefftz'])
near(100*(trefftz-D(str(new['target_delta_CDi_trefftz'])))/abs(D(str(new['target_delta_CDi_trefftz']))),new['trefftz_signed_percent_error'])
near(actual-D(str(mesh['previous32']['actual_delta_CD'])),mesh['change_in_drag_increment'])
assert abs(sum(mesh['change_in_drag_increment_budget'].values())-mesh['change_in_drag_increment'])<2e-12
assert base['primary_count']==dict(passed=21,required=48,changed=False)
assert mesh['primary_count_changed'] is False and mesh['primary_passes_added']==0
result=dict(verified_utc=datetime.now(timezone.utc).isoformat(),verified=True,
    baseline_diagnostic_passed=6,baseline_diagnostic_required=12,drag_increments=6,lift_increments=6,
    mesh_comparison_points=1,maximum_decimal_reduction_difference=error,source_pins_verified=len(pins),
    analysis_sha256=sha(BASE/'analysis.json'),mesh_analysis_sha256=sha(MESH/'analysis.json'),
    checker_sha256=sha(Path(__file__)),primary_counts_unchanged=True)
with (BASE/'comparison-verification.json').open('x') as f:
    json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
signal.alarm(0);print(json.dumps(result,indent=2))
