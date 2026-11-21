"""Rotate only the wake in the saved independent SA-11 finite-chord model.

Geometry, PG map, section law, controls, body-force ledger and load probes are
unchanged. This is not the complete ASWING K/F-off operation.
"""
from datetime import datetime,timezone
import argparse
import gc
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time

import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def serial(x):
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,dict):return {k:serial(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [serial(v) for v in x]
    return x


def write(p,value):p.write_text(json.dumps(serial(value),indent=2,allow_nan=False)+'\n')


def explicit_wakes(data,nc):
    """Restore original TE origins; a rotated ray cannot be shifted along x."""
    m=len(data['gamma']);rays={}
    for i in np.flatnonzero(data['chord_index']==nc-1):
        for corner,sign in ((2,1),(3,-1)):
            key=tuple(data['corners'][i,corner]);rays.setdefault(key,np.zeros(m));rays[key][i]+=sign
    graph=dict(starts=data['starts'],ends=data['ends'],edge_coefficients=data['body_edge_coefficients'],
        ray_starts=np.asarray(list(rays)),ray_coefficients=np.asarray(list(rays.values())))
    divergence={}
    for a,b,c in zip(graph['starts'],graph['ends'],graph['edge_coefficients']):
        for p,sign in ((a,1),(b,-1)):
            key=tuple(p);divergence.setdefault(key,np.zeros(m));divergence[key]+=sign*c
    for p,c in zip(graph['ray_starts'],graph['ray_coefficients']):
        key=tuple(p);divergence.setdefault(key,np.zeros(m));divergence[key]+=c
    assert max(np.max(abs(v)) for v in divergence.values())==0.
    lookup={tuple(sorted((tuple(a),tuple(b)))):i for i,(a,b) in enumerate(zip(graph['starts'],graph['ends']))}
    front=np.flatnonzero(data['chord_index']==0)
    own=np.array([lookup[tuple(sorted((tuple(data['corners'][i,0]),tuple(data['corners'][i,1]))))] for i in front])
    return graph,own


def field(points,graph,gamma,pg,direction,vlm,own=None):
    strength=graph['edge_coefficients']@gamma;rs=graph['ray_coefficients']@gamma
    active=np.flatnonzero(strength!=0);rays=np.flatnonzero(rs!=0)
    aa,bb=graph['starts'][active]@pg,graph['ends'][active]@pg
    origins=graph['ray_starts'][rays]@pg;wake=direction@pg
    if own is not None:
        a,b=graph['starts'][own],graph['ends'][own];d=b-a
        fraction=np.sum((points-a)*d,axis=1)/np.sum(d*d,axis=1)
        assert np.max(np.linalg.norm(points-a-fraction[:,None]*d,axis=1))<3e-14
        assert np.all((fraction>=0)&(fraction<=1))
    result=np.zeros_like(points)
    for lo in range(0,len(points),32):
        hi=min(lo+32,len(points));p=points[lo:hi]@pg
        shape=(len(p),len(active),3);valid=np.ones(shape[:2],dtype=bool)
        if own is not None:valid=own[lo:hi,None]!=active[None,:]
        pp=np.broadcast_to(p[:,None,:],shape);a=np.broadcast_to(aa,shape);b=np.broadcast_to(bb,shape)
        values=np.zeros(shape);values[valid]=vlm.finite_segment(pp[valid],a[valid],b[valid])
        ray_values=vlm.semi_infinite(p[:,None,:],origins[None,:,:],wake)
        result[lo:hi]=(np.einsum('iek,e->ik',values,strength[active])+
                       np.einsum('irk,r->ik',ray_values,rs[rays]))@pg
    return result


def rotate_matrix(data,graph,direction,vlm):
    pg=data['pg'];m=len(data['gamma']);delta=np.empty((m,m))
    origin=graph['ray_starts']@pg
    for lo in range(0,m,64):
        hi=min(lo+64,m);p=(data['collocation'][lo:hi]@pg)[:,None,:]
        difference=(vlm.semi_infinite(p,origin[None,:,:],direction@pg)-
                    vlm.semi_infinite(p,origin[None,:,:],np.array([1.,0.,0.])@pg))@pg
        projected=np.einsum('irk,ik->ir',difference,data['normals'][lo:hi])
        delta[lo:hi]=projected@graph['ray_coefficients']
    return data['matrix']+delta,delta


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a fresh output directory.')
    prior=json.loads((args.baseline/'plan.json').read_text())
    verify=json.loads((args.baseline/'verification.json').read_text())
    assert all(sha(args.baseline/p)==h for p,h in verify['artifacts'].items())
    assert all(sha(ROOT/p)==h for p,h in prior['unchanged_pins'].items())
    assert sha(args.baseline/'driver-used.py')==prior['driver_sha256']
    spec=importlib.util.spec_from_file_location('frozen_finite_chord',args.baseline/'driver-used.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    sys.path.insert(0,str((args.baseline/'reference').resolve()));import vlm
    assert sha(Path(vlm.__file__))==prior['reference_pins']['vlm.py']
    args.output.mkdir(parents=True);shutil.copyfile(__file__,args.output/'driver-used.py')
    (args.output/'reference').mkdir()
    shutil.copyfile(args.baseline/'reference/vlm.py',args.output/'reference/vlm.py')
    shutil.copyfile(args.baseline/'driver-used.py',args.output/'reference/frozen-driver-used.py')
    plan=dict(utc=datetime.now(timezone.utc).isoformat(),baseline=str(args.baseline),
        baseline_plan_sha256=sha(args.baseline/'plan.json'),baseline_results_sha256=sha(args.baseline/'results.json'),
        driver_sha256=sha(Path(__file__)),unchanged_pins=prior['unchanged_pins'],
        example=prior['example'],span=prior['span'],chord_rows=prior['chord_rows'],
        changed_quantity='Only physical wake direction, from x to unit freestream at alpha=5 degrees.',
        preserved='Physical/control/force coordinates, normals, PG transform, section law, body coefficients, reference quantities.',
        caveat='Not full ASWING K/F-off: lifting geometry and PG map are deliberately frozen.',
        matrix_update='Saved A plus exact normal-projected change in original-origin ray influence; finite influence reused.',
        held_circulation='Previously solved finite-chord Gamma; not original nonlinear ASWING Gamma.',
        physics=prior['physics'],gates=prior['gates'])
    write(args.output/'plan.json',plan);rows=[]
    for baseline_row in json.loads((args.baseline/'results.json').read_text()):
        start=time.monotonic();nc=baseline_row['chord_rows']
        with np.load(args.baseline/baseline_row['artifact']['path']) as z:d={k:z[k] for k in z.files}
        graph,own=explicit_wakes(d,nc);direction=d['ambient'];pg=d['pg'];ambient=d['ambient']
        frozen=field(d['quarter_chord_probes'],graph,d['gamma'],pg,np.array([1.,0.,0.]),vlm,own if nc==1 else None)+ambient
        np.testing.assert_allclose(frozen,d['quarter_chord_velocity'],atol=2e-9,rtol=3e-11)
        matrix,delta=rotate_matrix(d,graph,direction,vlm)
        # Independent complete ring assembly at representative rows, all sources.
        sample=np.unique([0,len(d['gamma'])//2,len(d['gamma'])-1])
        topology=dict(corners=d['corners']@pg,trailing=d['chord_index']==nc-1,wake_direction=direction@pg)
        raw=vlm.influence_velocity(d['collocation'][sample]@pg,topology)@pg
        expected=np.einsum('ijk,ik->ij',raw,d['normals'][sample])
        np.testing.assert_allclose(matrix[sample],expected,atol=2e-8,rtol=3e-11)
        s0=time.monotonic();gamma=np.linalg.solve(matrix,d['rhs']);seconds=time.monotonic()-s0
        residual=matrix@gamma-d['rhs'];backward=float(np.max(abs(residual))/(
            np.linalg.norm(matrix,np.inf)*np.linalg.norm(gamma,np.inf)+np.linalg.norm(d['rhs'],np.inf)))
        accepted=bool(np.max(abs(residual))<1e-11 and backward<1e-12 and np.isfinite(gamma).all())
        # Preserve the solve even if a subsequent zero-core field is singular.
        np.savez_compressed(args.output/f'c{nc}-solution.npz',gamma=gamma,matrix=matrix,rhs=d['rhs'],residual=residual)
        q=field(d['quarter_chord_probes'],graph,gamma,pg,direction,vlm,own if nc==1 else None)+ambient
        held=field(d['quarter_chord_probes'],graph,d['gamma'],pg,direction,vlm,own if nc==1 else None)+ambient
        held_residual=matrix@d['gamma']-d['rhs']
        cp=field(d['collocation'],graph,gamma,pg,direction,vlm)+ambient
        cp_residual=np.einsum('ij,ij->i',cp,d['normals'])
        np.testing.assert_allclose(cp_residual,residual,atol=2e-10,rtol=2e-10)
        midpoint=d['edge_midpoints']
        edge_v=field(midpoint,graph,gamma,pg,direction,vlm,np.arange(len(midpoint)))+ambient
        strengths=d['body_edge_coefficients']@gamma
        force=1.2256*900*strengths[:,None]*np.cross(edge_v,d['ends']-d['starts'])
        moment=np.cross(midpoint-[18.5,0.,0.],force)
        total=force.sum(axis=0);qref=.5*1.2256*900*.9329
        lift_axis=np.array([-ambient[2],0.,ambient[0]])
        s=np.empty_like(q)
        for beam in np.unique(d['beam']):
            mask=d['beam']==beam;s[mask]=helper.section(beam,d['t'][mask],np.sign(d['t'][mask]))['tangent']
        normal=q-np.sum(q*s,axis=1)[:,None]*s
        external=field(d['offsheet_probes'],graph,gamma,pg,direction,vlm)+ambient
        path=args.output/f'c{nc}.npz'
        np.savez_compressed(path,gamma=gamma,matrix=matrix,delta_matrix=delta,rhs=d['rhs'],residual=residual,
            corners=d['corners'],chord_index=d['chord_index'],collocation=d['collocation'],normals=d['normals'],
            starts=d['starts'],ends=d['ends'],edge_coefficients=graph['edge_coefficients'],
            body_edge_coefficients=d['body_edge_coefficients'],body_mask=d['body_mask'],
            ray_starts=graph['ray_starts'],ray_coefficients=graph['ray_coefficients'],
            wake_direction=direction,pg=pg,ambient=ambient,beam=d['beam'],t=d['t'],
            quarter_chord_probes=d['quarter_chord_probes'],quarter_chord_velocity=q,
            held_gamma=d['gamma'],held_velocity=held,held_residual=held_residual,
            edge_midpoints=midpoint,edge_velocity=edge_v,edge_strengths=strengths,edge_forces=force,edge_moments=moment,
            offsheet_probes=d['offsheet_probes'],offsheet_velocity=external)
        row=dict(chord_rows=nc,panels=len(gamma),utc=datetime.now(timezone.utc).isoformat(),
            status='linear_solution' if accepted else 'residual_rejected',stage_seconds=time.monotonic()-start,solve_seconds=seconds,
            maximum_residual=float(np.max(abs(residual))),relative_backward_error=backward,
            independent_field_residual=float(np.max(abs(cp_residual))),
            frozen_field_reconstruction_difference=float(np.max(abs(frozen-d['quarter_chord_velocity']))),
            matrix_sample_difference=float(np.max(abs(matrix[sample]-expected))),
            quarter_peak_speed_ratio=float(np.max(np.linalg.norm(q,axis=1))),
            body_edge_peak_speed_ratio=float(np.max(np.linalg.norm(edge_v[d['body_mask']],axis=1))),
            held_gamma_quarter_peak_speed_ratio=float(np.max(np.linalg.norm(held,axis=1))),
            held_gamma_maximum_residual=float(np.max(abs(held_residual))),
            quarter_normal_Mach=float(np.max(np.linalg.norm(normal,axis=1))*30/340.21),
            CL_full_edges=float(total@lift_axis/qref),CD_full_edges=float(total@ambient/qref),
            force=total,moment=moment.sum(axis=0),offsheet_velocity=external*30.,
            baseline_artifact_sha256=baseline_row['artifact']['sha256'],artifact=dict(path=path.name,sha256=sha(path)))
        rows.append(row);write(args.output/'results.json',rows)
        print(prior['example'],prior['span'],'c',nc,'q',row['quarter_peak_speed_ratio'],
            'edge',row['body_edge_peak_speed_ratio'],'CL',row['CL_full_edges'],'CD',row['CD_full_edges'],
            'R',row['maximum_residual'],flush=True)
        del matrix,delta,graph,d;gc.collect()
    assert all(sha(ROOT/p)==h for p,h in plan['unchanged_pins'].items())
    assert not any(n=='openswing' or n.startswith('openswing.') for n in sys.modules)
    write(args.output/'verification.json',dict(utc=datetime.now(timezone.utc).isoformat(),
        numerical_solves=len(rows),held_gamma_fields=len(rows),source_and_status_unchanged=True,
        artifacts={str(p.relative_to(args.output)):sha(p) for p in args.output.rglob('*') if p.is_file()}))
    print('COMPLETE',prior['example'],prior['span'],flush=True)


if __name__=='__main__':main()
