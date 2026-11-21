"""Verify redistribution invariants, physical fields and successive drag changes."""
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import signal

for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    assert os.environ.get(key)=='1'
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/isae/sa11-extension-redistribution-20261108'
OLD=ROOT/'artifacts/isae/sa11-extension-mesh-limit-20261108'
PAIRS=ROOT/'artifacts/isae/sa11-extension-drag-pairs-20261108'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=read(OUT/'plan.json');digest=sha(OUT/'plan.json')
for path,expected in plan['pins'].items():assert sha(ROOT/path)==expected,path
spec=importlib.util.spec_from_file_location('pair_audit',ROOT/'scripts/audit-sa11-extension-drag-pairs.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
parent=read(PAIRS/'analysis.json');rows=[]
errors=dict(velocity_relative=0.,force=0.,moment=0.,near_CD=0.,uniform_interval=0.)
for case in plan['cases']:
    folder=OUT/case['id'];row=read(folder/'report.json');raw=read(folder/'accepted.json')
    assert row['status']=='computed' and row['plan_sha256']==digest
    assert row['settings']==case['control']['settings'] and row['physical_calls']==1
    for name,expected in row['artifacts'].items():assert sha(folder/name)==expected,name
    with np.load(folder/'geometry.npz') as saved:g={key:saved[key] for key in saved}
    nodes=np.array(case['preflight']['nodes']);n=len(g['ds'])
    assert n==case['preflight']['actual_intervals']==row['actual_intervals']
    assert min(g['ds'])>=plan['minimum_spacing']-1e-12
    for segment in case['redistribution']['mandatory_segments']:
        left,right=segment['left'],segment['right']
        assert left in nodes and right in nodes
        mask=(nodes[:-1]>=left)&(nodes[1:]<=right)
        assert sum(mask)==segment['intervals']
        errors['uniform_interval']=max(errors['uniform_interval'],float(max(abs(g['ds'][mask]-segment['uniform_length']))))
    assert raw['converged'] and raw['residual']<1e-8
    for name,value in row['actual'].items():
        if name not in ('lift','drag'):assert value==raw['Cm_origin' if name=='Cm' else name]
        assert abs(100*(value-row['reference'][name])/abs(row['reference'][name])-row['relative_percent_errors'][name])<2e-10
    assert row['passed']==sum(abs(e)<=5 for e in row['relative_percent_errors'].values())
    alpha=math.radians(row['settings']['alpha']);rho=row['settings']['density'];speed=row['settings']['speed']
    rotation=np.array([[math.cos(alpha),0,math.sin(alpha)],[0,1,0],[-math.sin(alpha),0,math.cos(alpha)]])
    qs=.5*rho*speed**2*.9329
    force=np.array([math.fsum(s['force'][k] for s in raw['strips']) for k in range(3)])
    errors['force']=max(errors['force'],abs(float(force@rotation[0]/qs)-raw['CD']),abs(float(force@rotation[2]/qs)-raw['CL']))
    moment=math.fsum(s['moment'][1]+s['position'][2]*s['force'][0]-s['position'][0]*s['force'][2] for s in raw['strips'])
    errors['moment']=max(errors['moment'],abs(moment/(qs*.37874)-raw['Cm_origin']))
    beta=np.sqrt(np.longdouble(1)-(np.longdouble(speed)/np.longdouble('340.21'))**2)
    tensors=audit.operators(g['hv']@rotation.T,g['a']@rotation.T,g['b']@rotation.T,beta)
    gamma=np.array([s['circulation'] for s in raw['strips']]);velocity=np.array([s['relative_velocity'] for s in raw['strips']])
    calculated=sum(np.einsum('ijq,j->iq',tensor,gamma) for tensor in tensors.values())@rotation+speed*rotation[0]
    errors['velocity_relative']=max(errors['velocity_relative'],float(np.max(abs(calculated-velocity))/speed))
    measure=(g['span']*g['ds'][:,None])@rotation.T
    pairs={key:rho*gamma[:,None]*gamma[None,:]*np.cross(tensor,measure[:,None,:])[:,:,0]/qs for key,tensor in tensors.items()}
    errors['near_CD']=max(errors['near_CD'],abs(float(sum(pair.sum() for pair in pairs.values()))-raw['CDi_near']))
    ii,jj=np.indices((n,n));adj=abs(ii-jj)==1;center=adj&(g['t'][:,None]*g['t'][None,:]<0)
    original_id=case['id'].removesuffix('-redistributed');original=next(r for r in parent['cases'] if r['id']==original_id)
    row.update(original_id=original_id,report_sha256=sha(folder/'report.json'),
        original_CD_error=read(OLD/original_id/'report.json')['relative_percent_errors']['CD'],
        maximum_adjacent_width_ratio=case['redistribution']['maximum_adjacent_width_ratio'],
        components={key:float(pair.sum()) for key,pair in pairs.items()},
        other_adjacent_finite_CD=float((pairs['bound']+pairs['finite_origin'])[adj&~center].sum()),
        original_other_adjacent_finite_CD=original['other_adjacent_finite_CD'])
    rows.append(row)
changes=[]
for old,new in zip(rows,rows[1:]):
    changes.append(dict(old=old['id'],new=new['id'],
        relative_changes_percent={key:100*abs(new['actual'][key]-old['actual'][key])/abs(new['actual'][key]) for key in ('CL','CD','CDi','Cm')}))
stable=all(max(row['relative_changes_percent'].values())<=1 for row in changes)
assert errors['velocity_relative']<2e-10 and max(v for k,v in errors.items() if k!='velocity_relative')<2e-12
result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),verified=True,cases=rows,changes=changes,
    stable_over_both_refinements=stable,verification_errors=errors,source_pins_verified=len(plan['pins']),
    physical_calls=3,computed=3,rejected=0,primary_passes_added=0,
    maximum_seconds=max(r['seconds'] for r in rows),peak_rss_kib=max(r['peak_rss_kib'] for r in rows),
    plan_sha256=digest,checker_sha256=sha(Path(__file__)))
text=json.dumps(result,indent=2,allow_nan=False)+'\n'
with (OUT/'analysis.json').open('x') as stream:stream.write(text)
signal.alarm(0)
print(json.dumps({key:value for key,value in result.items() if key!='cases'},indent=2))
for row in rows:print(json.dumps({key:row[key] for key in ('id','maximum_adjacent_width_ratio','relative_percent_errors','components','other_adjacent_finite_CD','original_other_adjacent_finite_CD')}))
