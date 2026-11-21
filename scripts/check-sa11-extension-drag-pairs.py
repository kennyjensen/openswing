"""Check saved drag partitions and the straight adjacent-interval identity."""
from datetime import datetime,timezone
import hashlib
import importlib.util
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
OUT=ROOT/'artifacts/isae/sa11-extension-drag-pairs-20261108'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=read(OUT/'plan.json');digest=sha(OUT/'plan.json')
for path,expected in plan['pins'].items():assert sha(ROOT/path)==expected,path
spec=importlib.util.spec_from_file_location('pairs_audit',ROOT/'scripts/audit-sa11-extension-drag-pairs.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
rows=[];max_sum_error=max_law_error=0.


def shape(left,right,fi,fj):
    return 1/(1-fi)-left/((1-fi)*left+right)+right/(left+fj*right)-1/fj


for case in plan['cases']:
    folder=OUT/case['id'];row=read(folder/'report.json')
    assert row['plan_sha256']==digest and row['physical_solves']==0
    for name,expected in row['artifacts'].items():assert sha(folder/name)==expected
    source=ROOT/case['folder'];raw=read(source/'accepted.json')
    with np.load(folder/'pairs.npz') as saved:fields={key:saved[key] for key in saved}
    with np.load(source/case['geometry_file']) as saved:geometry={key:saved[key] for key in saved}
    n=len(fields['t']);ii,jj=np.indices((n,n));own=ii==jj;adjacent=abs(ii-jj)==1
    same=(fields['t'][:,None]*fields['t'][None,:]>0)&~own&~adjacent
    masks=dict(own=own,adjacent=adjacent,other_same_side=same,other_opposite_side=~(own|adjacent|same))
    for name in ('bound','half_wake','finite_origin'):
        pair=fields[name]
        assert pair.shape==(n,n) and np.all(np.isfinite(pair))
        scalar=math.fsum(map(float,pair.flat))
        max_sum_error=max(max_sum_error,abs(scalar-row['components'][name]))
        for category,mask in masks.items():
            scalar=math.fsum(map(float,pair[mask]))
            max_sum_error=max(max_sum_error,abs(scalar-row['partitions'][name][category]))
        assert abs(sum(b['components'][name] for b in row['receiver_bins'])-row['components'][name])<2e-12
    assert np.all(fields['bound'].diagonal()==0)
    assert np.array_equal(fields['gamma'],[s['circulation'] for s in raw['strips']])
    assert abs(row['CDi_near']-sum(row['components'].values()))<2e-12
    assert abs(raw['CD']-row['total_CD'])<2e-12
    finite=fields['bound']+fields['finite_origin']
    center=adjacent&(fields['t'][:,None]*fields['t'][None,:]<0)
    row['center_adjacent_finite_CD']=float(finite[center].sum())
    row['other_adjacent_finite_CD']=float(finite[adjacent&~center].sum())
    row['half_wake_minus_trefftz']=row['components']['half_wake']-row['CDi']
    # Choose the strongest non-center adjacent pair by the saved force ranking,
    # not proximity to an archived reference or a preferred width ratio.
    top=next(p for p in row['largest_symmetric_finite_pairs'] if p['j']==p['i']+1 and p['t'][0]*p['t'][1]>0)
    i,j=top['i'],top['j'];delta=geometry['b']-geometry['a'];length=np.linalg.norm(delta,axis=1)
    direction=delta[i]/length[i]+delta[j]/length[j];direction/=np.linalg.norm(direction)
    angle=math.radians(case['settings']['alpha']);wind=np.array([math.cos(angle),0,math.sin(angle)])
    ux=float(direction@wind);speed=case['settings']['speed'];rho=case['settings']['density']
    beta=math.sqrt(1-(speed/340.21)**2);kappa=(ux/beta)/math.sqrt((ux/beta)**2+1-ux**2)
    li,lj=map(float,length[[i,j]]);fi,fj=map(float,fields['fraction'][[i,j]])
    gi,gj=map(float,fields['gamma'][[i,j]])
    prefactor=gi*gj*kappa/(2*math.pi*speed**2*.9329)
    formula=prefactor*shape(li,lj,fi,fj)
    # Exact straight two-interval control, using the same geometric inputs.
    unit=np.array([ux,math.sqrt(1-ux**2),0.])
    a=np.array([np.zeros(3),li*unit]);b=np.array([li*unit,(li+lj)*unit])
    points=a+np.array([fi*li,fj*lj])[:,None]*unit
    tensor=audit.operators(points,a,b,np.longdouble(beta))['finite_origin']
    gamma=np.array([gi,gj]);measure=(b-a)
    pair=rho*gamma[:,None]*gamma[None,:]*np.cross(tensor,measure[:,None,:])[:,:,0]/(.5*rho*speed**2*.9329)
    max_law_error=max(max_law_error,abs(float(pair[0,1]+pair[1,0])-formula))
    assert shape(1.,1.,.5,.5)==0
    assert abs(shape(li,lj,fi,fj)+shape(lj,li,1-fj,1-fi))<2e-14
    assert abs(shape(li,lj,fi,fj)-shape(3*li,3*lj,fi,fj))<2e-14
    row['straight_pair_control']=dict(selected_pair=top,length_ratio=max(li,lj)/min(li,lj),
        fractions=[fi,fj],kappa=kappa,formula_CD=formula,
        actual_finite_CD=top['finite_origin'],relative_difference_percent=100*(formula/top['finite_origin']-1),
        angle_between_segments_deg=math.degrees(math.acos(float(np.clip(delta[i]@delta[j]/(li*lj),-1,1)))),
        straight_midpoint_unequal_width_CD=prefactor*shape(li,lj,.5,.5),
        straight_equal_width_midpoint_CD=prefactor*shape(li,li,.5,.5))
    row['report_sha256']=sha(folder/'report.json');rows.append(row)
assert max_sum_error<2e-12 and max_law_error<2e-12
changes=[]
for old,new in zip(rows,rows[1:]):
    total=new['CDi_near']-old['CDi_near']
    components={key:new['components'][key]-old['components'][key] for key in new['components']}
    partition={key:{category:new['partitions'][key][category]-old['partitions'][key][category]
                   for category in new['partitions'][key]} for key in new['partitions']}
    assert abs(sum(components.values())-total)<2e-12
    changes.append(dict(old=old['id'],new=new['id'],near_CD_change=total,
        total_CD_change=new['total_CD']-old['total_CD'],component_changes=components,partition_changes=partition,
        finite_origin_share_percent=100*components['finite_origin']/total,
        adjacent_finite_origin_share_percent=100*partition['finite_origin']['adjacent']/total))
result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),verified=True,cases=rows,changes=changes,
    source_pins_verified=len(plan['pins']),maximum_scalar_sum_error=max_sum_error,
    maximum_exact_straight_pair_law_error=max_law_error,
    maximum_velocity_relative_error=max(r['verification_errors']['velocity_relative'] for r in rows),
    maximum_near_CD_error=max(r['verification_errors']['near_CD'] for r in rows),
    maximum_seconds=max(r['seconds'] for r in rows),peak_rss_kib=max(r['peak_rss_kib'] for r in rows),
    physical_solves=0,primary_passes_added=0,plan_sha256=digest,checker_sha256=sha(Path(__file__)))
text=json.dumps(result,indent=2,allow_nan=False)+'\n'
with (OUT/'analysis.json').open('x') as stream:stream.write(text)
signal.alarm(0)
print(json.dumps({key:value for key,value in result.items() if key not in ('cases','changes')},indent=2))
for change in changes:print(json.dumps(change))
for row in rows:print(json.dumps(dict(id=row['id'],straight_pair=row['straight_pair_control'])))
