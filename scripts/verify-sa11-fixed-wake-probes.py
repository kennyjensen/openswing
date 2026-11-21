"""Compare fixed off-sheet probes on retained N48/N96 SA-11 vortex fields.

One serial invocation handles one model/influence pair. No new circulation
solves, interpolation of Gamma, core, source movement or production changes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import time

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
from openswing.factored_influence import FactoredInfluence


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def portable(x):
    if isinstance(x,np.ndarray): return x.tolist()
    if isinstance(x,np.generic): return x.item()
    if isinstance(x,dict): return {k:portable(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [portable(v) for v in x]
    return x


def write(path,data): path.write_text(json.dumps(portable(data),indent=2,allow_nan=False)+'\n')


def read_case(shape,mode,n):
    path=ROOT/f'artifacts/isae/sa11-section-velocity-20261108-{shape}{n}-{mode}'
    manifest=json.loads((path/'verification.json').read_text())
    for name,digest in manifest['artifacts'].items(): assert sha(path/name)==digest,name
    plan=json.loads((path/'plan.json').read_text())
    for name,digest in plan['unchanged_pins'].items(): assert sha(ROOT/name)==digest,name
    with np.load(path/'fields.npz') as saved: data={k:saved[k] for k in saved.files}
    return path,plan,data


def sources(data):
    grouped={}
    for a,b,gamma in zip(data['a'],data['b'],data['gamma']):
        grouped.setdefault(tuple(a),[]).append(-gamma)
        grouped.setdefault(tuple(b),[]).append(gamma)
    # Exact-coordinate grouping and compensated strengths, no geometry snapping.
    rows=[(p,math.fsum(values)) for p,values in grouped.items() if math.fsum(values)!=0.]
    return np.array([p for p,g in rows]),np.array([g for p,g in rows])


def wake_clearance(points,data):
    nodes,strengths=sources(data)
    delta=points[:,None,:]-nodes[None,:,:]
    along=np.einsum('ijk,k->ij',delta,data['direction'])
    radial=delta-np.maximum(along,0.)[:,:,None]*data['direction']
    distance=np.linalg.norm(radial,axis=2)
    nearest=np.argmin(distance,axis=1)
    return dict(minimum_ray_distance=distance[np.arange(len(points)),nearest],
                nearest_origin=nodes[nearest],nearest_strength=strengths[nearest],
                exact_origin_count=np.sum(np.all(delta==0.,axis=2),axis=1))


def evaluate(points,data):
    bound=[];wake=[]
    for start in range(0,len(points),32):
        op=FactoredInfluence(points[start:start+32],data['a'],data['b'],data['direction'],data['pg'])
        b=np.einsum('ijk,j->ik',op.bound,data['gamma'])
        w=np.einsum('ijk,j->ik',op.rays,op.wake_strengths(data['gamma']))
        np.testing.assert_allclose(b+w,op.apply(data['gamma']),atol=3e-9,rtol=3e-12)
        bound.append(b);wake.append(w)
    return np.vstack(bound),np.vstack(wake)


def gamma_comparison(model,coarse,fine):
    meshes={n:model_meshes(model,n) for n in (48,96)}
    result=[]
    for m0,m1 in zip(meshes[48],meshes[96]):
        beam=m0.beam.index
        g0=coarse['gamma'][coarse['beam']==beam];g1=fine['gamma'][fine['beam']==beam]
        np.testing.assert_array_equal(m0.tm,coarse['t'][coarse['beam']==beam])
        np.testing.assert_array_equal(m1.tm,fine['t'][fine['beam']==beam])
        edges=np.unique(np.r_[m0.t0,m0.t1,m1.t0,m1.t1]);width=np.diff(edges)
        middle=edges[:-1]+.5*width
        i0=np.minimum(np.searchsorted(m0.t1,middle,side='right'),len(g0)-1)
        i1=np.minimum(np.searchsorted(m1.t1,middle,side='right'),len(g1)-1)
        # Each fixture beam is piecewise straight. This is the physical beam
        # arclength metric, checked against both unchanged discretizations.
        jac0=m0.length/(m0.t1-m0.t0);jac1=m1.length/(m1.t1-m1.t0)
        np.testing.assert_allclose(jac0[i0],jac1[i1],atol=2e-11,rtol=2e-11)
        ds=width*jac0[i0];difference=g1[i1]-g0[i0]
        l1=float(np.sum(abs(difference)*ds));den1=float(np.sum(abs(g1[i1])*ds))
        l2=float(np.sqrt(np.sum(difference**2*ds)));den2=float(np.sqrt(np.sum(g1[i1]**2*ds)))
        result.append(dict(beam=beam,L1_difference=l1,L1_relative=l1/den1,
                           L2_difference=l2,L2_relative=l2/den2,
                           coarse_integral=float(np.sum(g0*m0.length)),fine_integral=float(np.sum(g1*m1.length))))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--example',choices=('upper','both'),required=True)
    parser.add_argument('--influence',choices=('frozen','current'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): parser.error('Use a fresh output directory.')
    p0,plan0,coarse=read_case(args.example,args.influence,48)
    p1,plan1,fine=read_case(args.example,args.influence,96)
    assert plan0['unchanged_pins']==plan1['unchanged_pins']
    for key in ('direction','pg','ambient'): np.testing.assert_array_equal(coarse[key],fine[key])
    source=ROOT/'examples'/f"{plan0['example']}.asw"
    assert sha(source)==plan0['input_sha256']==plan1['input_sha256']
    fractions=[0.,.01,.1,.5,.9,.99,1.]
    offsets=[.001,.01,.1]
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__,args.output/'driver-used.py')
    plan=dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        previous_turn='progress: actual-geometry bound correction ruled out as a sufficient repair; wake sources isolated',
        example=args.example,influence=args.influence,
        source_manifests={str(p.relative_to(ROOT)):sha(p/'verification.json') for p in (p0,p1)},
        unchanged_pins=plan0['unchanged_pins'],input_sha256=sha(source),
        root_to_tip_fractions=fractions,normal_offsets_over_local_chord=offsets,offset_sides=[-1,1],
        fixed_probe_rule='Root + fraction*(tip-root), displaced on either side of the local wake plane by offset*local chord.',
        planes='Normal = normalized(influence wind cross local section span). Each winglet is straight.',
        remesh_control='Split each coarse straight segment in half and copy its Gamma to both children; identical source field.',
        coarse_receiver_alias_audit='Exact fine active-ray origin matches and separately near-roundoff distances; no field evaluated at these aliases.',
        comparison_scope='Two solved circulation grids at identical off-sheet probes, not proof of mesh convergence or physical accuracy.',
        new_circulation_solves=0,cores_changed=False,
        gates=dict(subdivision_atol=3e-8,subdivision_rtol=3e-11,geometry_atol=3e-14))
    write(args.output/'plan.json',plan)
    started=time.monotonic()
    try:
        model=parse_asw(source.read_text())
        points=[];metadata=[];probe_spans=[]
        for beam in np.unique(coarse['beam']):
            if beam==1: continue
            mask0=coarse['beam']==beam;mask1=fine['beam']==beam
            a0,b0=coarse['a'][mask0][0],coarse['b'][mask0][-1]
            a1,b1=fine['a'][mask1][0],fine['b'][mask1][-1]
            np.testing.assert_allclose(a0,a1,atol=3e-14,rtol=0.)
            np.testing.assert_allclose(b0,b1,atol=3e-14,rtol=0.)
            # Left traces run tip→root and right traces root→tip.
            left=beam in (3,5)
            root,tip=(b0,a0) if left else (a0,b0)
            span=coarse['span'][mask0][0]
            np.testing.assert_allclose(coarse['span'][mask0],np.tile(span,(mask0.sum(),1)),atol=2e-14,rtol=0.)
            np.testing.assert_allclose(fine['span'][mask1],np.tile(span,(mask1.sum(),1)),atol=2e-14,rtol=0.)
            axis=np.cross(coarse['direction'],span);axis/=np.linalg.norm(axis)
            branch=next(b for b in model.beams if b.index==beam)
            lo,hi=branch.domain
            for fraction in fractions:
                t=hi-fraction*(hi-lo) if left else lo+fraction*(hi-lo)
                chord=float(branch.value('chord',np.array([t]))[0])
                line=root+fraction*(tip-root)
                for offset in offsets:
                    for sign in (-1,1):
                        points.append(line+sign*offset*chord*axis)
                        probe_spans.append(span)
                        metadata.append(dict(beam=int(beam),root_to_tip_fraction=fraction,t=t,
                            offset_over_chord=offset,side=sign,chord=chord,normal=axis,line_point=line))
        points=np.asarray(points);span=np.asarray(probe_spans)
        assert len(points)<=168
        clear0=wake_clearance(points,coarse);clear1=wake_clearance(points,fine)
        assert min(np.min(clear0['minimum_ray_distance']),np.min(clear1['minimum_ray_distance']))>1e-12
        b0,w0=evaluate(points,coarse);b1,w1=evaluate(points,fine)
        # Exact source subdivision is a representation check; Gamma is not
        # interpolated, fitted or re-solved. Original endpoint coordinates stay.
        mid=.5*(coarse['a']+coarse['b'])
        split=dict(coarse,a=np.stack([coarse['a'],mid],axis=1).reshape(-1,3),
                   b=np.stack([mid,coarse['b']],axis=1).reshape(-1,3),gamma=np.repeat(coarse['gamma'],2))
        bs,ws=evaluate(points,split)
        np.testing.assert_allclose(bs,b0,atol=3e-8,rtol=3e-11)
        np.testing.assert_allclose(ws,w0,atol=3e-8,rtol=3e-11)
        alias=wake_clearance(coarse['hv'],fine)
        geometry_scale=max(1.,float(np.max(np.linalg.norm(fine['b']-fine['a'],axis=1))))
        roundoff_band=64*np.finfo(float).eps*geometry_scale
        aliases=[]
        for beam in np.unique(coarse['beam']):
            mask=coarse['beam']==beam
            aliases.append(dict(beam=int(beam),receivers=int(mask.sum()),
                exact_active_ray_origins=int(np.count_nonzero(alias['exact_origin_count'][mask])),
                within_roundoff_band=int(np.count_nonzero(alias['minimum_ray_distance'][mask]<=roundoff_band)),
                roundoff_distance_band=roundoff_band,
                minimum_active_ray_distance=float(np.min(alias['minimum_ray_distance'][mask]))))
        per_probe=[]
        for i,m in enumerate(metadata):
            perp=lambda v:v-(v@span[i])*span[i]
            v0=coarse['ambient']+b0[i]+w0[i];v1=fine['ambient']+b1[i]+w1[i]
            dv=v1-v0;dw=w1[i]-w0[i]
            per_probe.append(dict(**m,position=points[i],coarse_total_velocity=v0,fine_total_velocity=v1,
                velocity_change=dv,wake_change=dw,velocity_change_over_freestream=float(np.linalg.norm(dv)/30.),
                wake_change_over_freestream=float(np.linalg.norm(dw)/30.),
                scaled_velocity_change=float(np.linalg.norm(dv)/max(30.,np.linalg.norm(v0),np.linalg.norm(v1))),
                coarse_normal_mach_indicator=float(np.linalg.norm(perp(v0))/340.21),
                fine_normal_mach_indicator=float(np.linalg.norm(perp(v1))/340.21),
                coarse_ray_distance=float(clear0['minimum_ray_distance'][i]),
                fine_ray_distance=float(clear1['minimum_ray_distance'][i])))
        by_offset=[]
        for offset in offsets:
            subset=[r for r in per_probe if r['offset_over_chord']==offset]
            changes=np.array([r['velocity_change_over_freestream'] for r in subset])
            worst=max(subset,key=lambda r:r['velocity_change_over_freestream'])
            by_offset.append(dict(offset_over_chord=offset,probes=len(subset),
                maximum_change_over_freestream=float(changes.max()),median_change_over_freestream=float(np.median(changes)),
                maximum_scaled_change=max(r['scaled_velocity_change'] for r in subset),
                maximum_coarse_mach_indicator=max(r['coarse_normal_mach_indicator'] for r in subset),
                maximum_fine_mach_indicator=max(r['fine_normal_mach_indicator'] for r in subset),
                worst_probe=worst))
        circulation=gamma_comparison(model,coarse,fine)
        np.savez_compressed(args.output/'probes.npz',points=points,span=span,
            coarse_bound=b0,coarse_wake=w0,fine_bound=b1,fine_wake=w1,
            subdivided_bound=bs,subdivided_wake=ws,
            coarse_gamma=coarse['gamma'],fine_gamma=fine['gamma'])
        result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),example=args.example,influence=args.influence,
            fixed_probes=per_probe,by_offset=by_offset,coarse_receiver_aliases=aliases,
            circulation_comparison=circulation,
            subdivision_bound_max_error=float(np.max(abs(bs-b0))),
            subdivision_wake_max_error=float(np.max(abs(ws-w0))),
            total_seconds=time.monotonic()-started,new_circulation_solves=0,
            production_and_primary_counts_unchanged=True)
        for name,digest in plan0['unchanged_pins'].items(): assert sha(ROOT/name)==digest,name
        write(args.output/'results.json',result)
        write(args.output/'verification.json',dict(status='verified',observed_utc=datetime.now(timezone.utc).isoformat(),
            artifacts={p.name:sha(p) for p in sorted(args.output.iterdir()) if p.is_file()},
            unchanged_pin_count=len(plan0['unchanged_pins'])))
        print(json.dumps(portable(dict(status='verified',example=args.example,influence=args.influence,probes=len(points),
            maximum_change_percent_of_U=[100*r['maximum_change_over_freestream'] for r in by_offset],
            subdivision_max_error=max(result['subdivision_bound_max_error'],result['subdivision_wake_max_error']),
            seconds=result['total_seconds']))))
    except Exception as exc:
        write(args.output/'failure.json',dict(error_type=type(exc).__name__,error=str(exc),observed_utc=datetime.now(timezone.utc).isoformat()))
        raise


if __name__=='__main__': main()
