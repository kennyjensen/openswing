"""Partition saved extension drag into bound, half-wake and finite-origin pairs.

Five accepted 240 m/s, 3-degree states; zero new aerodynamic solves.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import time

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'artifacts/isae/sa11-extension-mesh-limit-20261108'
CONTROL=ROOT/'artifacts/isae/sa11-extension-drag-budget-r2-20261108'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
utc=lambda:datetime.now(timezone.utc).isoformat()


def write(path,value):
    text=json.dumps(value,indent=2,allow_nan=False)+'\n'
    with path.open('x') as stream:stream.write(text)


def bounded():
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        assert os.environ.get(key)=='1'
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)


def authenticate(pins):
    for path,digest in pins.items():assert sha(ROOT/path)==digest,path


def prepare(out):
    bounded();assert not out.exists()
    parent=read(PARENT/'plan.json');authenticate(parent['pins'])
    analysis=read(PARENT/'analysis.json')
    assert analysis['verified'] and analysis['plan_sha256']==sha(PARENT/'plan.json')
    group=next(g for g in analysis['groups'] if g['speed']==240 and g['alpha']==3)
    pins=dict(parent['pins']);cases=[]
    for row in group['states']:
        assert row['status']=='computed'
        folder=(CONTROL if row['requested_intervals'] in (64,128) else PARENT)/row['id']
        assert sha(folder/'report.json')==row['report_sha256']
        for name,digest in row['artifacts'].items():
            assert sha(folder/name)==digest
            pins[str((folder/name).relative_to(ROOT))]=digest
        pins[str((folder/'report.json').relative_to(ROOT))]=row['report_sha256']
        cases.append(dict(id=row['id'],folder=str(folder.relative_to(ROOT)),
            geometry_file='fields.npz' if row['requested_intervals'] in (64,128) else 'geometry.npz',
            requested_intervals=row['requested_intervals'],actual_intervals=row['actual_intervals'],
            settings=row['settings']))
    for path in (Path(__file__),PARENT/'plan.json',PARENT/'analysis.json'):
        pins[str(path.relative_to(ROOT))]=sha(path)
    assert len(cases)==5
    out.mkdir(parents=True);(out/'driver-used.py').write_text(Path(__file__).read_text())
    write(out/'plan.json',dict(observed_utc=utc(),cases=cases,pins=pins,
        previous_goal_turn='Progress:12 mesh-limit calls,9 valid and3 rejected,independently verified. Latest CD changes arise outside center-adjacent pair. Stable force limit remains unproven.',
        source_basis='Drela steady Eqs55--56,64--70,149--161,207--211; prior SA11 drag-closure/own-wake audits distinguished own and neighboring terms on a different winglet configuration.',
        protocol='Reuse five original extension states at240m/s,alpha3; actual intervals60/108/160/172/178. Split the unchanged physical wind/PG field into finite bound segments,half-infinite wake and finite-origin wake terms. Contract each with saved Gamma and beam span*ds. Preserve own wake,exclude own bound only. No alternate receiver or force law.',
        partitions='Ordered pairs:own;immediate neighbors on same beam;other pairs on same side of center;remaining opposite-side pairs. Receiver bins use fixed material abs(t) boundaries0,.25,.5,.75,1,1.2426,endpoint. Also separate center-adjacent receivers. These are signed accounting contributions,not removable forces.',
        limits='One bounded foreground process/BLAS thread,512MiB,15CPU/25wall seconds per saved state.',
        physical_solves=0,primary_passes_added=0))
    signal.alarm(0);print('Prepared five saved-field pair audits',flush=True)


def operators(points,start,end,beta):
    """Independent finite-line integral with rationalized same-side limit."""
    import numpy as np
    kind=np.longdouble
    points,start,end=[np.asarray(a,dtype=kind) for a in (points,start,end)]
    pg=np.array([1/beta,1,1],dtype=kind)
    delta=(end-start)*pg;length=np.linalg.norm(delta,axis=1)
    direction=delta/length[:,None]
    relative=(points[:,None,:]-start[None,:,:])*pg
    h1=np.sum(relative*direction[None,:,:],axis=2);h2=h1-length
    transverse=relative-h1[:,:,None]*direction[None,:,:]
    radius2=np.sum(transverse**2,axis=2)
    r1=np.sqrt(h1*h1+radius2);r2=np.sqrt(h2*h2+radius2)
    own=np.eye(len(points),dtype=bool);same=(h1*h2>0)&~own;crossing=~same&~own
    factor=np.zeros_like(h1)
    np.divide(h1*h1-h2*h2,r1*r2*(h1*r2+h2*r1),out=factor,where=same)
    np.divide(h1/r1-h2/r2,radius2,out=factor,where=crossing)
    pi4=4*np.arccos(kind(-1))
    bound=np.cross(direction[None,:,:],transverse)*factor[:,:,None]*pg/pi4
    half=np.zeros_like(bound);finite=np.zeros_like(bound)
    for origin,sign in ((start,-1),(end,1)):
        r=points[:,None,:]-origin[None,:,:]
        radius2=r[:,:,1]**2+r[:,:,2]**2
        assert np.all(radius2>0)
        ray=np.stack([np.zeros_like(radius2),-r[:,:,2],r[:,:,1]],axis=-1)/(pi4*radius2[:,:,None])
        x=r[:,:,0]/beta
        half+=sign*ray
        finite+=sign*ray*(x/np.sqrt(x*x+radius2))[:,:,None]
    return dict(bound=bound,half_wake=half,finite_origin=finite)


def run(out,index):
    bounded();clock=time.monotonic()
    plan=read(out/'plan.json');authenticate(plan['pins']);case=plan['cases'][index]
    folder=out/case['id'];assert not folder.exists()
    source=ROOT/case['folder'];raw=read(source/'accepted.json')
    import numpy as np
    with np.load(source/case['geometry_file']) as saved:g={k:saved[k] for k in saved}
    settings=case['settings'];rho,speed=settings['density'],settings['speed']
    alpha=np.deg2rad(settings['alpha']);rotation=np.array([[np.cos(alpha),0,np.sin(alpha)],[0,1,0],[-np.sin(alpha),0,np.cos(alpha)]])
    beta=np.sqrt(np.longdouble(1)-(np.longdouble(speed)/np.longdouble('340.21'))**2)
    tensors=operators(g['hv']@rotation.T,g['a']@rotation.T,g['b']@rotation.T,beta)
    gamma=np.array([s['circulation'] for s in raw['strips']],dtype=np.longdouble)
    velocity=np.array([s['relative_velocity'] for s in raw['strips']])
    measure=(g['span']*g['ds'][:,None])@rotation.T
    qs=.5*rho*speed**2*.9329
    pairs={key:rho*gamma[:,None]*gamma[None,:]*np.cross(tensor,measure[:,None,:])[:,:,0]/qs
           for key,tensor in tensors.items()}
    reconstructed=sum(np.einsum('ijq,j->iq',tensor,gamma) for tensor in tensors.values())@rotation+speed*rotation[0]
    errors=dict(velocity_relative=float(np.max(abs(reconstructed-velocity))/speed),
                near_CD=abs(float(sum(p.sum() for p in pairs.values()))-raw['CDi_near']))
    assert errors['velocity_relative']<2e-10 and errors['near_CD']<2e-12,errors
    n=len(gamma);ii,jj=np.indices((n,n));own=ii==jj;adjacent=abs(ii-jj)==1
    same_side=(g['t'][:,None]*g['t'][None,:]>0)&~own&~adjacent
    masks=dict(own=own,adjacent=adjacent,other_same_side=same_side,other_opposite_side=~(own|adjacent|same_side))
    assert np.all(sum(mask.astype(int) for mask in masks.values())==1)
    partition={key:{name:float(pair[mask].sum()) for name,mask in masks.items()} for key,pair in pairs.items()}
    totals={key:float(pair.sum()) for key,pair in pairs.items()}
    symmetric={key:float(((pair+pair.T)/2).sum()) for key,pair in pairs.items()}
    for key in totals:
        assert abs(sum(partition[key].values())-totals[key])<2e-12
        assert abs(symmetric[key]-totals[key])<2e-12
    bounds=[0,.25,.5,.75,1.,1.2426,float(max(abs(g['t'])))+1e-10]
    receiver_bins=[]
    for low,high in zip(bounds,bounds[1:]):
        mask=(abs(g['t'])>=low)&(abs(g['t'])<high)
        receiver_bins.append(dict(low=low,high=high,intervals=int(sum(mask)),
            components={key:float(pair[mask].sum()) for key,pair in pairs.items()}))
    # Rank geometric interaction pairs by their symmetric contribution, retaining both signs.
    finite=pairs['bound']+pairs['finite_origin'];symmetric_finite=finite+finite.T
    upper=np.triu_indices(n,1);order=np.argsort(abs(symmetric_finite[upper]))[-12:][::-1]
    ranked=[]
    for k in order:
        i,j=int(upper[0][k]),int(upper[1][k])
        ranked.append(dict(i=i,j=j,t=[float(g['t'][i]),float(g['t'][j])],
            lengths=[float(g['ds'][i]),float(g['ds'][j])],
            bound=float(pairs['bound'][i,j]+pairs['bound'][j,i]),
            finite_origin=float(pairs['finite_origin'][i,j]+pairs['finite_origin'][j,i]),
            total=float(symmetric_finite[i,j])))
    delta=g['b']-g['a'];fraction=np.sum((g['hv']-g['a'])*delta,axis=1)/np.sum(delta*delta,axis=1)
    offset=np.linalg.norm(g['hv']-g['a']-fraction[:,None]*delta,axis=1)
    assert min(fraction)>0 and max(fraction)<1
    folder.mkdir()
    np.savez(folder/'pairs.npz',**{key:np.asarray(value,dtype=float) for key,value in pairs.items()},
             t=g['t'],ds=g['ds'],fraction=fraction,offset=offset,gamma=np.asarray(gamma,dtype=float),
             velocity=np.asarray(reconstructed,dtype=float))
    report=dict(id=case['id'],observed_utc=utc(),requested_intervals=case['requested_intervals'],
        actual_intervals=n,settings=settings,total_CD=raw['CD'],CDi_near=raw['CDi_near'],CDi=raw['CDi'],CDp=raw['CDp'],
        components=totals,partitions=partition,receiver_bins=receiver_bins,largest_symmetric_finite_pairs=ranked,
        receiver_fraction_range=[float(min(fraction)),float(max(fraction))],maximum_bound_offset=float(max(offset)),
        verification_errors=errors,physical_solves=0,seconds=time.monotonic()-clock,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=sha(out/'plan.json'),artifacts={'pairs.npz':sha(folder/'pairs.npz')})
    write(folder/'report.json',report);signal.alarm(0)
    print(json.dumps({key:report[key] for key in ('id','components','partitions','verification_errors','seconds')}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('action',choices=('prepare','run'));parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.output.resolve())
    else:run(args.output.resolve(),args.index)
