"""Exact common-interval accounting of SA-11 tip-mesh wake interactions.

Split each original straight vortex without changing its field, and split its
force weight while retaining the original receiver. This reproduces the two
saved operators exactly on a common algebraic basis. Hybrid combinations are
formal diagnostics, not new aerodynamic equilibria or validation passes.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'artifacts/isae/sa11-tip-local-mesh-20261108'
COARSE=ROOT/'artifacts/isae/sa11-minimum-spacing-20261108'
GEOMETRY=ROOT/'artifacts/isae/sa11-paper-aligned-20261108/upper_winglet-m0_70-a21/geometry.npz'
AVL=ROOT/'scripts/avl_vorvelc_reference.py'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
utc=lambda:datetime.now(timezone.utc).isoformat()


def bounded():
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(key)=='1'
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)


def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def authenticate(pins):
    for path,digest in pins.items():assert sha(ROOT/path)==digest,path


def prepare(out):
    bounded();assert not out.exists()
    analysis=read(LOCAL/'analysis.json');assert analysis['verified']
    pins=dict(analysis['pins']);authenticate(pins)
    local_plan=read(LOCAL/'plan.json');coarse_plan=read(COARSE/'plan.json')
    cases=[]
    for alpha in (2.75,3.):
        new=next(c for c in local_plan['cases'] if c['configuration']=='upper_winglet' and c['alpha']==alpha)
        old=next(c for c in coarse_plan['cases'] if c['label']=='0_70' and c['alpha']==alpha)
        states=[dict(name='main32',raw=str((COARSE/f'm0_70-a{int(4*alpha):02d}'/'accepted.json').relative_to(ROOT)),
                     geometry=str(GEOMETRY.relative_to(ROOT)),mesh=read(COARSE/'mesh-import.json')['panels']),
                dict(name='tip46',raw=str((LOCAL/new['id']/'accepted.json').relative_to(ROOT)),
                     geometry=str((LOCAL/new['id']/'geometry.npz').relative_to(ROOT)),mesh=new['mesh'])]
        assert new['condition']==old['condition']
        for state in states:
            for key in ('raw','geometry'):pins[state[key]]=sha(ROOT/state[key])
        cases.append(dict(id=f'a{int(4*alpha):02d}',alpha=alpha,model_path=new['model_path'],
                          condition=new['condition'],states=states))
    for path in (Path(__file__),AVL,LOCAL/'analysis.json',LOCAL/'plan.json',COARSE/'plan.json',
                 ROOT/'docs/validation/aswing-authoritative-references.md',
                 ROOT/'docs/validation/aswing-authoritative-sources.json'):
        pins[str(path.relative_to(ROOT))]=sha(path)
    out.mkdir(parents=True);(out/'driver-used.py').write_text(Path(__file__).read_text())
    write(out/'plan.json',dict(observed_utc=utc(),pins=pins,cases=cases,
        previous_goal_turn='Progress: nine saved-field audits and six valid local-tip solves locate94.18% of the whole-main drag change in the outer intervals; no solver repair or primary passes.',
        source_basis='Drela steady Eqs64--70,149--161: linear Biot--Savart operator and quadratic circulation force; Jan PartI p35/Fig22. Original frozen influences and physical drag projection retained.',
        protocol='Two saved upper-winglet pairs at240m/s,alpha2.75/3. Union their material-interval boundaries; split original straight sources with constant inherited circulation and split force weights at duplicate original receivers. Check both reconstructions against unsplit fields. Factor four changes by all16 exact algebraic combinations: source geometry, receiver/force quadrature, main circulation step distribution, winglet circulation. Symmetric Shapley attribution sums exactly to the observed cross-beam force change.',
        factors=['receiver_quadrature','source_geometry','main_circulation_steps','winglet_circulation'],
        limitations='The main-circulation factor includes changes in piecewise-constant source sampling/step locations as well as amplitudes. It is not solely a nonlinear-solver response. Hybrid combinations are not converged states, may not satisfy local validity gates, and are never scored. Shared subdivision is algebraic, not an actual mesh; minimum spacing is not changed.',
        physical_solves=0,primary_passes_added=0,
        limits='One BLAS thread,512MiB address space,15CPU/25wall seconds per saved pair. No background/browser jobs.'))
    signal.alarm(0);print(dict(prepared=True,pairs=2,physical_solves=0,pins=len(pins)))


def operators(points,start,end,beta):
    import numpy as np
    kind=np.longdouble
    points,start,end=[np.asarray(a,dtype=kind) for a in (points,start,end)]
    pg=np.array([1/beta,1,1],dtype=kind);delta=(end-start)*pg
    length=np.linalg.norm(delta,axis=1);direction=delta/length[:,None]
    r=(points[:,None,:]-start[None,:,:])*pg
    h1=np.sum(r*direction[None,:,:],axis=2);h2=h1-length
    transverse=r-h1[:,:,None]*direction[None,:,:];radius2=np.sum(transverse**2,axis=2)
    assert np.all(radius2>0)
    r1=np.sqrt(h1*h1+radius2);r2=np.sqrt(h2*h2+radius2)
    same=h1*h2>0;factor=np.empty_like(h1)
    np.divide(h1*h1-h2*h2,r1*r2*(h1*r2+h2*r1),out=factor,where=same)
    np.divide(h1/r1-h2/r2,radius2,out=factor,where=~same)
    pi4=4*np.arccos(kind(-1));bound=np.cross(direction[None,:,:],transverse)*factor[:,:,None]*pg/pi4
    half=np.zeros_like(bound);finite=np.zeros_like(bound)
    for origin,sign in ((start,-1),(end,1)):
        r=points[:,None,:]-origin[None,:,:];radius2=r[:,:,1]**2+r[:,:,2]**2
        assert np.all(radius2>0)
        ray=np.stack([np.zeros_like(radius2),-r[:,:,2],r[:,:,1]],axis=-1)/(pi4*radius2[:,:,None])
        x=r[:,:,0]/beta
        half+=sign*ray;finite+=sign*ray*(x/np.sqrt(x*x+radius2))[:,:,None]
    return dict(bound=bound,half_wake=half,finite_origin=finite)


def run(out,index):
    bounded();started=time.monotonic();plan=read(out/'plan.json');authenticate(plan['pins'])
    case=plan['cases'][index];folder=out/case['id'];assert not folder.exists()
    import numpy as np
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.arc_length import material_arc
    model=parse_asw((ROOT/case['model_path']).read_text(),beam_interpolation='natural-v1')
    meshes=[model_meshes(model,s['mesh']) for s in case['states']]
    raw=[read(ROOT/s['raw']) for s in case['states']];geometry=[]
    for state in case['states']:
        with np.load(ROOT/state['geometry']) as f:geometry.append({k:f[k] for k in f})
    for a in raw:assert a['converged'] and a['residual']<1e-8 and max(s['normal_mach'] for s in a['strips'])<1
    common=[];beam=[];parents=[[],[]];expanded=[];errors={}
    for k,(m0,m1) in enumerate(zip(*meshes)):
        nodes=np.union1d(np.r_[m0.t0,m0.t1[-1]],np.r_[m1.t0,m1.t1[-1]])
        common.append(nodes);beam.extend([m0.beam.index]*(len(nodes)-1))
    beam=np.array(beam);main=beam==1;assert sum(main)==48 and len(beam)==80
    errors['split_source_weight']=0.;errors['split_receiver_weight']=0.
    for variant,(state,mset,g) in enumerate(zip(raw,meshes,geometry)):
        values={key:[] for key in ('a','b','hv','measure','gamma','parent')};offset=0
        for mesh,nodes in zip(mset,common):
            arc=material_arc(mesh.beam);mid=(nodes[:-1]+nodes[1:])/2
            parent=np.searchsorted(mesh.t1,mid,side='right')
            length=mesh.length[parent]
            l0=arc.between(mesh.t0[parent],nodes[:-1])/length
            l1=arc.between(mesh.t0[parent],nodes[1:])/length
            weight=arc.between(nodes[:-1],nodes[1:])/length
            for j in range(len(mesh.tm)):
                mask=parent==j
                errors['split_receiver_weight']=max(errors['split_receiver_weight'],abs(float(sum(weight[mask]))-1))
            parent=parent+offset
            source_start=g['a'][parent]+l0[:,None]*(g['b'][parent]-g['a'][parent])
            source_end=g['a'][parent]+l1[:,None]*(g['b'][parent]-g['a'][parent])
            # Preserve original endpoints bitwise; internal split endpoints
            # telescope when neighboring subsegments carry equal circulation.
            source_start[l0==0]=g['a'][parent[l0==0]]
            source_end[l1==1]=g['b'][parent[l1==1]]
            for j in range(len(mesh.tm)):
                at=np.flatnonzero(parent==j+offset)
                errors['split_source_weight']=max(errors['split_source_weight'],
                    float(np.max(abs(source_end[at[:-1]]-source_start[at[1:]]))) if len(at)>1 else 0.)
            gamma=np.array([s['circulation'] for s in state['strips']])[parent]
            current=dict(a=source_start,b=source_end,hv=g['hv'][parent],
                measure=g['span'][parent]*(g['ds'][parent]*weight)[:,None],gamma=gamma,parent=parent)
            for key,v in current.items():values[key].append(v)
            offset+=len(mesh.tm)
        expanded.append({key:np.concatenate(v) for key,v in values.items()})
    assert errors['split_receiver_weight']<2e-12 and errors['split_source_weight']<2e-12
    alpha=math.radians(case['alpha']);e=np.array([math.cos(alpha),0.,math.sin(alpha)],dtype=np.longdouble)
    speed=case['condition']['speed'];beta=np.sqrt(np.longdouble(1)-np.longdouble(case['condition']['mach'])**2)
    qs=.5*1.2256*speed**2*.9329
    spec=importlib.util.spec_from_file_location('avl_reference',AVL);avl=importlib.util.module_from_spec(spec);spec.loader.exec_module(avl)
    kernels={};errors['independent_operator']=0.
    for receiver,source in itertools.product((0,1),repeat=2):
        r,s=expanded[receiver],expanded[source];blocks={}
        for name,rmask,smask in [('main_from_winglet',main,~main),('winglet_from_main',~main,main)]:
            op=operators(r['hv'][rmask],s['a'][smask],s['b'][smask],beta)
            native=avl.matrix(r['hv'][rmask],s['a'][smask],s['b'][smask],case['condition']['mach'],
                              exclude_self=False,core_fraction=0.,dtype=np.longdouble)
            native/=4*np.arccos(np.longdouble(-1))*np.longdouble('.079577472')
            errors['independent_operator']=max(errors['independent_operator'],float(np.max(abs(sum(op.values())-native))))
            blocks[name]={term:1.2256*(np.cross(v,r['measure'][rmask,None,:])@e)/qs for term,v in op.items()}
        kernels[receiver,source]=blocks
    assert errors['independent_operator']<2e-10
    corners={}
    for bits in itertools.product((0,1),repeat=4):
        receiver,source,main_gamma,winglet_gamma=bits
        gamma=np.where(main,expanded[main_gamma]['gamma'],expanded[winglet_gamma]['gamma'])
        values={}
        for name,rmask,smask in [('main_from_winglet',main,~main),('winglet_from_main',~main,main)]:
            for term,kernel in kernels[receiver,source][name].items():
                values[f'{term}:{name}']=float(np.sum(kernel*gamma[rmask,None]*gamma[None,smask]))
        for term in ('bound','half_wake','finite_origin'):
            values[term]=values[f'{term}:main_from_winglet']+values[f'{term}:winglet_from_main']
        values['total']=sum(values[term] for term in ('bound','half_wake','finite_origin'))
        corners[''.join(map(str,bits))]=values
    errors['original_field_reconstruction']=0.
    direct=[]
    for variant,g in enumerate(geometry):
        bm=np.array([s['beam'] for s in raw[variant]['strips']])==1
        gamma=np.array([s['circulation'] for s in raw[variant]['strips']]);values={}
        for name,rmask,smask in [('main_from_winglet',bm,~bm),('winglet_from_main',~bm,bm)]:
            op=operators(g['hv'][rmask],g['a'][smask],g['b'][smask],beta)
            measure=g['span'][rmask]*g['ds'][rmask,None]
            for term,v in op.items():
                values[f'{term}:{name}']=float(np.sum(1.2256*gamma[rmask,None]*gamma[None,smask]*(np.cross(v,measure[:,None,:])@e)/qs))
        for key,value in values.items():
            errors['original_field_reconstruction']=max(errors['original_field_reconstruction'],abs(value-corners[str(variant)*4][key]))
        direct.append(values)
    assert errors['original_field_reconstruction']<2e-12
    factors=plan['factors'];attribution={name:{key:0. for key in corners['0000']} for name in factors}
    for i,name in enumerate(factors):
        for bits in itertools.product((0,1),repeat=4):
            if bits[i]:continue
            count=sum(bits);weight=math.factorial(count)*math.factorial(3-count)/math.factorial(4)
            flipped=list(bits);flipped[i]=1
            lo=corners[''.join(map(str,bits))];hi=corners[''.join(map(str,flipped))]
            for key in lo:attribution[name][key]+=weight*(hi[key]-lo[key])
    change={key:corners['1111'][key]-corners['0000'][key] for key in corners['0000']}
    errors['attribution_closure']=max(abs(sum(a[key] for a in attribution.values())-value) for key,value in change.items())
    assert errors['attribution_closure']<2e-12
    folder.mkdir();np.savez(folder/'common-intervals.npz',beam=beam,
        **{f'{key}_{i}':value for i,ex in enumerate(expanded) for key,value in ex.items()},
        **{f'nodes_{i}':value for i,value in enumerate(common)})
    report=dict(observed_utc=utc(),case=case,corners=corners,change=change,attribution=attribution,
        attribution_percent={name:{key:100*value/change[key] if abs(change[key])>1e-14 else None for key,value in a.items()} for name,a in attribution.items()},
        direct_original=direct,errors=errors,common_main_intervals=48,algebraic_total_intervals=80,
        source_position_maximum_difference=float(max(np.max(abs(expanded[0][k]-expanded[1][k])) for k in ('a','b'))),
        physical_solves=0,primary_passes_added=0,seconds=time.monotonic()-started,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=sha(out/'plan.json'),artifacts={'common-intervals.npz':sha(folder/'common-intervals.npz')})
    write(folder/'report.json',report);signal.alarm(0)
    print(json.dumps(dict(id=case['id'],change=change,attribution={k:{term:v[term] for term in ('finite_origin','total')} for k,v in attribution.items()},
        errors=errors,seconds=report['seconds'],peak_rss_kib=report['peak_rss_kib']),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','run'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--index',type=int)
    args=p.parse_args()
    if args.action=='prepare':prepare(args.output.resolve())
    else:run(args.output.resolve(),args.index)
