"""Independent scalar force reductions and mesh/toggle comparisons; no solves."""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal

for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    assert os.environ.get(key) == '1'
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(15,15)); signal.alarm(25)
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/isae/sa11-extension-drag-budget-r2-20261108'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=read(OUT/'plan.json');digest=sha(OUT/'plan.json')
for name,value in plan['pins'].items(): assert sha(ROOT/name)==value,name
dot=lambda a,b:math.fsum(float(x)*float(y) for x,y in zip(a,b))
cross=lambda a,b:(a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
norm=lambda a:math.sqrt(dot(a,a))
rows=[];errors=dict(force=0.,coefficient=0.,moment=0.,normal_mach=0.,budget=0.,percentage=0.)
for case in plan['cases']:
    folder=OUT/case['id'];report=read(folder/'report.json');raw=read(folder/'accepted.json')
    assert report['plan_sha256']==digest and report['id']==case['id']
    for name,value in report['artifacts'].items(): assert sha(folder/name)==value,name
    assert raw['converged'] and raw['residual']<1e-8
    assert raw['aerodynamic_influences']['frozen']==case['freeze_influences']
    s=case['original_job']['settings'];a=math.radians(s['alpha']);e=[math.cos(a),0.,math.sin(a)]
    rho=s['density'];qs=.5*rho*s['speed']**2*.9329
    force=[math.fsum(r['force'][k] for r in raw['strips']) for k in range(3)]
    values=dict(lift=-math.sin(a)*force[0]+math.cos(a)*force[2],drag=dot(force,e))
    values.update(CL=values['lift']/qs,CD=values['drag']/qs,CDi=raw['CDi'],efficiency=raw['efficiency'])
    moment=math.fsum(r['moment'][1]+r['position'][2]*r['force'][0]-r['position'][0]*r['force'][2] for r in raw['strips'])
    values['Cm']=moment/(qs*.37874)
    errors['moment']=max(errors['moment'],abs(values['Cm']-raw['Cm_origin']))
    fields=case['original_job']['reference_row']['fields']
    table=(ROOT/case['original_job']['table_path']).read_text().splitlines()
    tokens=table[case['original_job']['reference_row']['line_number']-1].split()
    assert tokens==case['original_job']['reference_row']['tokens']
    passed=0
    for column,(name,value) in enumerate(values.items()):
        assert fields[name]['value']==report['reference'][name]
        errors['coefficient']=max(errors['coefficient'],abs(value-report['actual'][name])/max(1.,abs(value)))
        percentage=100*(value-fields[name]['value'])/abs(fields[name]['value'])
        errors['percentage']=max(errors['percentage'],abs(percentage-report['relative_percent_errors'][name]))
        passed+=abs(percentage)<=5
    assert passed==report['passing']
    with np.load(folder/'fields.npz') as archive: d={k:archive[k] for k in archive}
    forces={k:[] for k in ('vortex','friction','pressure','leakage')}
    for i,row in enumerate(raw['strips']):
        v=list(map(float,d['velocity'][i]));span=list(map(float,d['span'][i]));vspan=dot(v,span)
        perp=[x-vspan*y for x,y in zip(v,span)];vp=norm(perp)
        ds=float(d['ds'][i]);chord=float(d['chord'][i]);gamma=float(d['gamma'][i])
        assert ds>=plan['minimum_spacing']-1e-12 and ds==row['length'] and gamma==row['circulation']
        assert np.array_equal(v,row['relative_velocity'])
        tangent=dot(d['cp_velocity'][i],d['normal'][i])
        local=dict(vortex=[rho*gamma*x*ds for x in cross(v,span)],
            friction=[.5*rho*norm(v)*x*chord*float(d['cdf'][i])*ds for x in v],
            pressure=[.5*rho*vp*x*chord*float(d['cdp'][i])*ds for x in perp],
            leakage=[2*rho*x/vp*tangent*tangent*chord*ds for x in perp])
        for name,f in local.items():
            forces[name].append(f)
            errors['force']=max(errors['force'],max(abs(float(x)-y) for x,y in zip(d['force_'+name][i],f)))
        total=[math.fsum(f[k] for f in local.values()) for k in range(3)]
        errors['force']=max(errors['force'],max(abs(x-y) for x,y in zip(total,row['force'])))
        errors['normal_mach']=max(errors['normal_mach'],abs(vp/340.21-row['normal_mach']))
        assert vp/340.21<1
    components={name:math.fsum(dot(f,e) for f in series)/qs for name,series in forces.items()}
    for name,value in components.items():
        errors['coefficient']=max(errors['coefficient'],abs(value-report['drag_components'][name]))
    assert abs(sum(components.values())-raw['CD'])<2e-12
    assert abs(components['vortex']-raw['CDi_near'])<2e-12
    assert abs(sum(components[k] for k in ('friction','pressure','leakage'))-raw['CDp'])<2e-12
    errors['budget']=max(errors['budget'],abs(sum(report['budget'].values())-(values['CD']-fields['CD']['value'])))
    report.update(case=case,report_sha256=sha(folder/'report.json'))
    rows.append(report)
assert errors['force']<2e-8 and errors['coefficient']<2e-12 and errors['moment']<2e-12
assert errors['normal_mach']<2e-12 and errors['budget']<2e-12 and errors['percentage']<2e-9
by_id={r['id']:r for r in rows};mesh_pairs=[];toggle_pairs=[]
for label in ('0_70','0_80'):
    for alpha in (0,1,3,5):
        coarse=by_id[f'm{label}-a{alpha}-n64-current'];fine=by_id[f'm{label}-a{alpha}-n128-current']
        delta={k:fine['drag_components'][k]-coarse['drag_components'][k] for k in coarse['drag_components']}
        delta_total=fine['actual']['CD']-coarse['actual']['CD']
        assert abs(sum(delta.values())-delta_total)<2e-12
        mesh_pairs.append(dict(label=label,alpha=alpha,coarse=coarse['id'],fine=fine['id'],
            delta_CD=delta_total,delta_components=delta,vortex_fraction_of_CD_change=delta['vortex']/delta_total,
            relative_profile_change_percent=100*(fine['CDp']/coarse['CDp']-1),
            CD_error_percent=[coarse['relative_percent_errors']['CD'],fine['relative_percent_errors']['CD']]))
        if alpha in (1,3):
            frozen=by_id[f'm{label}-a{alpha}-n64-frozen']
            toggle_pairs.append(dict(label=label,alpha=alpha,current=coarse['id'],frozen=frozen['id'],
                delta_CD=frozen['actual']['CD']-coarse['actual']['CD'],
                discrepancy_removed_percent=100*(frozen['actual']['CD']-coarse['actual']['CD'])/(coarse['reference']['CD']-coarse['actual']['CD']),
                CD_error_percent=[coarse['relative_percent_errors']['CD'],frozen['relative_percent_errors']['CD']],
                pass_change=frozen['passing']-coarse['passing']))
primary=[r for r in rows if not r['case']['freeze_influences']]
analysis=dict(observed_utc=datetime.now(timezone.utc).isoformat(),verified=True,cases=rows,mesh_pairs=mesh_pairs,toggle_pairs=toggle_pairs,
    maximum_reconstruction_errors=errors,source_pins_verified=len(plan['pins']),unique_physical_calls=20,
    fresh_calls_in_revised_plan=sum(r['physical_calls'] for r in rows),recovered_completed_calls=1,
    primary_replay_maximum_scaled_difference=max(r['primary_replay_scaled_difference'] for r in primary),
    minimum_stall_margin_widths=min(r['minimum_stall_margin_widths'] for r in rows),
    maximum_normal_mach=max(r['maximum_normal_mach'] for r in rows),maximum_residual=max(r['residual'] for r in rows),
    maximum_leakage_CD=max(r['drag_components']['leakage'] for r in rows),
    maximum_profile_change_percent=max(abs(r['relative_profile_change_percent']) for r in mesh_pairs),
    minimum_vortex_fraction_of_mesh_CD_change=min(r['vortex_fraction_of_CD_change'] for r in mesh_pairs),
    maximum_vortex_fraction_of_mesh_CD_change=max(r['vortex_fraction_of_CD_change'] for r in mesh_pairs),
    maximum_seconds=max(r['seconds'] for r in rows),peak_rss_kib=max(r['peak_rss_kib'] for r in rows),
    production_equations_changed=False,primary_count_changed=False,plan_sha256=digest,checker_sha256=sha(Path(__file__)))
with (OUT/'analysis.json').open('x') as stream: json.dump(analysis,stream,indent=2,allow_nan=False);stream.write('\n')
signal.alarm(0)
print(json.dumps({k:v for k,v in analysis.items() if k not in ('cases',)},indent=2))
