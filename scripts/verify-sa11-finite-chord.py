"""Serial finite-chord controls on the saved SA-11 frozen lifting geometry.

Independent zero-core kernels; no production imports or changed ASW inputs.
Prescribed-field bridges and linear tangency solutions are separate records.
"""
from datetime import datetime, timezone
import argparse
import gc
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SAVED = ROOT/'artifacts/isae/sa11-winglet-junction-20261107'
PREVIOUS = ROOT/'artifacts/isae/sa11-generalized-topology-20261107'
REFERENCE = ROOT/'artifacts/isae/winglet-finite-chord-20261107/reference'
PINS = {'vlm.py':'1b1b90aa89829fcafadbb4c13f3972f580420d99071ca1c5ef8c0c7b542bb550',
        'loads.py':'449561e6d0cac588451ae5aae8703eceb956a9e76149bf81a4af7991df003821'}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def portable(x):
    if isinstance(x,np.ndarray): return x.tolist()
    if isinstance(x,np.generic): return x.item()
    if isinstance(x,dict): return {k:portable(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [portable(v) for v in x]
    return x


def write(p,value):
    p.write_text(json.dumps(portable(value),indent=2,allow_nan=False)+'\n')


def section(beam,t,zero_side):
    """Independent literal transcription of this model's straight beam pieces."""
    t=np.asarray(t); u=abs(t)
    if beam==1:
        sign=np.where(t==0,zero_side,np.sign(t))
        position=np.column_stack([.95348*u/1.2426,t,.15257*u/1.2426])
        tangent=np.column_stack([.95348*sign/1.2426,np.ones_like(t),.15257*sign/1.2426])
        chord=.43169+(.1611-.43169)*u/1.2426
        twist=np.full_like(t,2.)
        alpha=np.select([u<.432,u<.625,u<.84],[1.25,1.5,1.75],default=2.25)
    else:
        side=1 if beam in (2,4) else -1
        upper=beam in (2,3)
        low,high=(1.2426,1.29705) if upper else (1.2426,1.3108)
        first=np.array([1.02453,side*low,.15257]) if upper else np.array([.95348,side*low,.1525])
        last=np.array([1.18313,side*high,.35577]) if upper else np.array([1.01324,side*high,.10657])
        fraction=(u-low)/(high-low)
        position=first+fraction[:,None]*(last-first)
        tangent=np.broadcast_to(side*(last-first)/(high-low),position.shape).copy()
        chord=.10472+(.03363-.10472)*fraction if upper else .08+(.03248-.08)*fraction
        twist=np.full_like(t,4.) if upper else -7.-4.*fraction
        alpha=np.full_like(t,4.5 if upper else -4.5)
    tangent/=np.linalg.norm(tangent,axis=1)[:,None]
    across=np.linalg.norm(tangent[:,1:],axis=1)
    c0=(np.array([1.,0.,0.])-tangent[:,0,None]*tangent)/across[:,None]
    n0=np.cross(c0,tangent)
    theta=np.deg2rad(twist+alpha)
    normal=np.sin(theta)[:,None]*c0+np.cos(theta)[:,None]*n0
    projected=chord/across
    bound=position.copy(); bound[:,0]+=.25*projected
    return dict(bound=bound,projected=projected,normal=normal,tangent=tangent,chord=chord)


def geometry(data,nc,vlm,loads):
    patches={}; canonical=[]; prescribed=[]; section_ids=[]; maximum_defect=0.
    for beam in sorted(np.unique(data['beam'])):
        rows=np.flatnonzero(data['beam']==beam); a,b=data['a'][rows],data['b'][rows]
        sign=np.sign(data['t'][rows]); sa=section(beam,a[:,1],sign); sb=section(beam,b[:,1],sign)
        sm=section(beam,data['t'][rows],sign)
        for actual,expected in ((a,sa['bound']),(b,sb['bound']),(data['hv'][rows],sm['bound'])):
            defect=float(np.max(abs(actual-expected)));maximum_defect=max(maximum_defect,defect)
            assert defect<3e-14
        expected_cp=sm['bound'].copy();expected_cp[:,0]+=6.34/(4*np.pi)*sm['projected']
        np.testing.assert_allclose(expected_cp,data['cp'][rows],atol=3e-14,rtol=0.)
        np.testing.assert_allclose(a[1:],b[:-1],atol=3e-14,rtol=0.)
        nodes=np.vstack([a[0],b]); width=np.r_[sa['projected'][0],sb['projected']]
        grid=np.broadcast_to(nodes,(nc+1,len(nodes),3)).copy()
        qgrid=grid.copy()
        grid[:,:,0]+=(np.arange(nc+1)/nc-.25)[:,None]*width
        qgrid[:,:,0]+=((np.arange(nc+1)+.25)/nc-.25)[:,None]*width
        panels=np.stack([grid[:-1,:-1],grid[1:,:-1],grid[1:,1:],grid[:-1,1:]],axis=2)
        cp=np.broadcast_to(data['hv'][rows],(nc,len(rows),3)).copy()
        cp[:,:,0]+=((np.arange(nc)+.75)/nc-.25)[:,None]*sm['projected']
        normals=np.broadcast_to(sm['normal'],cp.shape).copy()
        area=np.linalg.norm(np.cross(panels[:,:,1]-panels[:,:,0],panels[:,:,3]-panels[:,:,0]),axis=-1)
        name=f'beam{beam}'
        patches[name]=dict(panels=panels,collocation=cp,normal=normals,area=area)
        canonical.append(np.stack([qgrid[:-1,:-1],qgrid[:-1,1:],qgrid[1:,1:],qgrid[1:,:-1]],axis=2).reshape(-1,4,3))
        prescribed.extend(((np.arange(nc)+1)[:,None]/nc*(data['gamma'][rows]/30.)).ravel())
        section_ids.extend(np.tile(rows,nc))
    topo=vlm.topology(dict(patches=patches),[1.,0.,0.])
    exact=np.concatenate(canonical)
    assert np.max(abs(topo['corners']-exact))<6e-14
    topo['corners']=exact
    graph=loads.canonical_graph(topo) # No fabricated main/winglet shared vertices.
    assert graph['maximum_canonical_coordinate_change_m']==0.
    edges={tuple(e):i for i,e in enumerate(graph['edge_vertices'])}
    front=np.flatnonzero(topo['chord_index']==0)
    front_edges=np.array([edges[tuple(sorted(v[:2]))] for v in graph['source_vertices'][front]])
    np.testing.assert_allclose(graph['starts'][front_edges],data['a'] if nc==1 else graph['starts'][front_edges],atol=0,rtol=0)
    return graph,np.asarray(prescribed),np.asarray(section_ids),front_edges,maximum_defect


def field(points,graph,gamma,pg,vlm,own=None):
    """Canonical-edge field, optional explicit own straight segment omitted.

    Unlike the retained load helper, also permits the original Glauert sample
    on its own segment. No distance-based exclusion or core is introduced.
    """
    strength=graph['edge_coefficients']@gamma
    ray_strength=graph['ray_coefficients']@gamma
    active=np.flatnonzero(strength!=0.);rays=np.flatnonzero(ray_strength!=0.)
    a,b=graph['starts'][active]@pg,graph['ends'][active]@pg
    origins=graph['ray_starts'][rays]@pg
    if own is not None:
        aa=graph['starts'][own];bb=graph['ends'][own];direction=bb-aa
        fraction=np.sum((points-aa)*direction,axis=1)/np.sum(direction*direction,axis=1)
        defect=np.linalg.norm(points-aa-fraction[:,None]*direction,axis=1)
        assert np.max(defect)<3e-14 and np.all((fraction>=0)&(fraction<=1))
    output=np.zeros_like(points)
    for low in range(0,len(points),32):
        high=min(low+32,len(points));p=points[low:high]@pg
        shape=(len(p),len(active),3)
        valid=np.ones(shape[:2],dtype=bool)
        if own is not None:valid=own[low:high,None]!=active[None,:]
        values=np.zeros(shape)
        pp=np.broadcast_to(p[:,None,:],shape);aa=np.broadcast_to(a,shape);bb=np.broadcast_to(b,shape)
        values[valid]=vlm.finite_segment(pp[valid],aa[valid],bb[valid])
        total=np.einsum('ijk,j->ik',values,strength[active])
        rv=vlm.semi_infinite(p[:,None,:],origins[None,:,:],[1.,0.,0.])
        total+=np.einsum('ijk,j->ik',rv,ray_strength[rays])
        output[low:high]=total@pg
    return output


def subdivide_collinear_boundaries(graph):
    """Exact union of overlapping streamwise boundary filaments and rays.

    All x-parallel lines are identified by their exact (y,z) coordinates.
    Every original endpoint remains a breakpoint; no coordinate is moved.
    Finite velocity coefficients include any coincident wake contribution;
    body-force coefficients include only the original finite body edges.
    """
    m=graph['edge_coefficients'].shape[1]
    chord=np.all(graph['starts'][:,1:]==graph['ends'][:,1:],axis=1)
    keep=np.flatnonzero(~chord)
    starts=list(graph['starts'][keep]);ends=list(graph['ends'][keep])
    coefficients=list(graph['edge_coefficients'][keep]);body=list(graph['edge_coefficients'][keep])
    old_to_new={int(old):i for i,old in enumerate(keep)}
    families={}
    for j in np.flatnonzero(chord):
        a,b=graph['starts'][j],graph['ends'][j]
        key=tuple(a[1:]);f=families.setdefault(key,dict(edges=[],rays=[]))
        sign=1 if b[0]>a[0] else -1
        f['edges'].append((min(a[0],b[0]),max(a[0],b[0]),sign*graph['edge_coefficients'][j]))
    for j,a in enumerate(graph['ray_starts']):
        families.setdefault(tuple(a[1:]),dict(edges=[],rays=[]))['rays'].append((a[0],graph['ray_coefficients'][j]))
    ray_starts=[];ray_coefficients=[];overlapping_families=0;maximum_overlap=0
    for (y,z),f in families.items():
        positions=sorted({x for a,b,c in f['edges'] for x in (a,b)}|{a for a,c in f['rays']})
        family_overlap=0
        for a,b in zip(positions[:-1],positions[1:]):
            middle=(a+b)/2
            covered=[c for lo,hi,c in f['edges'] if lo<=middle<=hi]
            wake=[c for lo,c in f['rays'] if lo<=middle]
            bc=sum(covered,np.zeros(m));vc=bc+sum(wake,np.zeros(m))
            family_overlap=max(family_overlap,len(covered))
            if np.any(bc) or np.any(vc):
                starts.append(np.array([a,y,z]));ends.append(np.array([b,y,z]))
                coefficients.append(vc);body.append(bc)
        rc=sum((c for a,c in f['rays']),np.zeros(m))
        if np.any(rc):ray_starts.append([positions[-1],y,z]);ray_coefficients.append(rc)
        overlapping_families+=int(family_overlap>1);maximum_overlap=max(maximum_overlap,family_overlap)
    result=dict(graph,starts=np.asarray(starts),ends=np.asarray(ends),
        edge_coefficients=np.asarray(coefficients),body_edge_coefficients=np.asarray(body),
        ray_starts=np.asarray(ray_starts),ray_coefficients=np.asarray(ray_coefficients))
    # Each source remains a closed vortex network, including its rays to infinity.
    divergence={}
    for a,b,c in zip(result['starts'],result['ends'],result['edge_coefficients']):
        for point,sign in ((a,1),(b,-1)):
            key=tuple(point);divergence.setdefault(key,np.zeros(m));divergence[key]+=sign*c
    for a,c in zip(result['ray_starts'],result['ray_coefficients']):
        key=tuple(a);divergence.setdefault(key,np.zeros(m));divergence[key]+=c
    error=max(float(np.max(abs(v))) for v in divergence.values())
    assert error==0.
    stats=dict(original_finite_edges=len(graph['starts']),subdivided_finite_edges=len(starts),
        original_rays=len(graph['ray_starts']),subdivided_rays=len(ray_starts),
        overlapping_streamwise_families=overlapping_families,maximum_body_overlap=maximum_overlap,
        sourcewise_vertex_divergence=error,coordinate_merging_tolerance=0.)
    return result,old_to_new,stats


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',choices=('up','up-and-down'),required=True)
    parser.add_argument('--span',type=int,choices=(48,96),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a fresh output directory.')
    prior=json.loads((PREVIOUS/'plan.json').read_text())
    assert all(sha(ROOT/p)==h for p,h in prior['unchanged_pins'].items())
    old=json.loads((SAVED/'analysis.json').read_text())
    assert sha(SAVED/'results.json')==old['results_sha256']
    assert all(sha(SAVED/p)==h for p,h in old['data_sha256'].items())
    assert all(sha(REFERENCE/p)==h for p,h in PINS.items())
    name='isae-sa11-wingtip-'+args.model
    saved=next(r for r in json.loads((SAVED/'results.json').read_text()) if r['example']==name and r['panels']==args.span)
    assert sha(ROOT/'examples'/(name+'.asw'))==saved['input_sha256']
    data_path=SAVED/f'{name}-{args.span}.npz'
    with np.load(data_path) as z:data={k:z[k] for k in z.files}
    sys.path.insert(0,str(REFERENCE.resolve()));import vlm;import loads
    assert sha(Path(vlm.__file__))==PINS['vlm.py'] and sha(Path(loads.__file__))==PINS['loads.py']
    args.output.mkdir(parents=True);shutil.copyfile(__file__,args.output/'driver-used.py')
    (args.output/'reference').mkdir()
    for filename in PINS:shutil.copyfile(REFERENCE/filename,args.output/'reference'/filename)
    requested=(1,2,4) if args.span==48 else (1,2)
    angle=np.deg2rad(5.);ambient=np.array([np.cos(angle),0.,np.sin(angle)])
    pg=np.diag([1/np.sqrt(1-(30/340.21)**2),1.,1.])
    plan=dict(utc=datetime.now(timezone.utc).isoformat(),example=name,span=args.span,chord_rows=requested,
        driver_sha256=sha(Path(__file__)),input_sha256=sha(data_path),example_sha256=saved['input_sha256'],
        unchanged_pins=prior['unchanged_pins'],reference_pins=PINS,
        scope='Finite-chord extension of the saved frozen lifting geometry, not physically rotated intersecting plates or ASWING reference validation.',
        geometry=dict(chord='Streamwise projected c/|ex cross beam_tangent|; normal-section physical outlines remain distinct.',
            span='Exact saved interval endpoints and Glauert samples.',
            quarter_chord='Original saved frozen a/b/hv; actual offsets and gaps preserved.',
            controls='3/4 local panel chord, not ASWING dCLda/(4*pi) offset.',
            normals='Independently transcribed original section twist plus alpha0; constant along each chord.',
            wake='Frozen +x; last ring extends quarter of final panel beyond physical TE, retained reference convention.',
            connections='Within each original logical beam, then exact atomic subdivision of collinear root-boundary edges/rays; no coordinates moved.'),
        physics=dict(speed=30.,alpha=5.,density=1.2256,reference_area=.9329,reference_chord=.37874,
            moment_origin=[18.5,0.,0.],PG_Mach=30/340.21,core=0.,stall=False,profile_drag=0.,section_moment=0.,
            solve_units='Unit freestream; Gamma and fields scaled by 30 for physical records.',
            local_Mach_acceptance='No subsonic physical-acceptance claim for the independent linear control.',
            load_rule='All finite canonical body edges, midpoint rho*Gamma_body*(V cross dl); own combined velocity edge excluded. Wake-only atoms carry no body force.'),
        gates=dict(max_panels=1200,unit_speed_boundary_residual=1e-11,relative_backward_error=1e-12),
        prescribed='Same saved Gamma, distributed uniformly in chordwise bound increments. Not a solved state.')
    write(args.output/'plan.json',plan);rows=[]
    for nc in requested:
        start=time.monotonic()
        original,prescribed,section_ids,front_edges,geom_error=geometry(data,nc,vlm,loads)
        graph,old_to_new,subdivision=subdivide_collinear_boundaries(original)
        front_edges=np.array([old_to_new[int(i)] for i in front_edges])
        topo=graph['topology'];m=len(topo['corners']);assert m<=1200
        transformed=dict(topo,corners=topo['corners']@pg)
        velocity=vlm.influence_velocity(topo['collocation']@pg,transformed)@pg
        matrix=np.einsum('ijk,ik->ij',velocity,topo['normal']);del velocity
        rhs=-topo['normal']@ambient
        s0=time.monotonic();gamma=np.linalg.solve(matrix,rhs);solve_seconds=time.monotonic()-s0
        residual=matrix@gamma-rhs
        scale=np.linalg.norm(matrix,np.inf)*np.linalg.norm(gamma,np.inf)+np.linalg.norm(rhs,np.inf)
        backward=float(np.max(abs(residual))/scale)
        accepted=bool(np.max(abs(residual))<=1e-11 and backward<=1e-12 and np.isfinite(gamma).all())
        qfield=field(data['hv'],graph,gamma,pg,vlm,front_edges if nc==1 else None)+ambient
        fixed=field(data['hv'],graph,prescribed,pg,vlm,front_edges if nc==1 else None)+ambient
        prescribed_residual=matrix@prescribed-rhs
        external_probes=np.array([[1.00,1.24,.18],[1.05,1.26,.18],[1.10,1.24,.18]])
        old_external=field(external_probes,original,prescribed,pg,vlm)
        new_external=field(external_probes,graph,prescribed,pg,vlm)
        np.testing.assert_allclose(old_external,new_external,atol=3e-11,rtol=3e-11)
        atomic_cp=field(topo['collocation'],graph,gamma,pg,vlm)+ambient
        atomic_residual=np.einsum('ij,ij->i',atomic_cp,topo['normal'])
        np.testing.assert_allclose(atomic_residual,residual,atol=2e-10,rtol=2e-10)
        bridge=None
        if nc==1:
            d=saved['details'];worst=d['maximum'];i=int(np.argmin(np.linalg.norm(data['hv']-np.asarray(d['vortex_breakdown']['influence_receiver']),axis=1)))
            assert data['beam'][i]==worst['beam']
            expected=np.asarray(worst['relative_velocity'])
            np.testing.assert_allclose(fixed[i]*30.,expected,atol=2e-7,rtol=2e-11)
            bridge=dict(original_worst_index=i,maximum_component_difference_mps=float(np.max(abs(fixed[i]*30.-expected))),
                expected_velocity=expected,actual_velocity=fixed[i]*30.,
                note='Velocity bridge at saved rejected maximum; no equivalence claim for new linear Gamma or full-edge forces.')
        middle=(graph['starts']+graph['ends'])/2
        edge_v=field(middle,graph,gamma,pg,vlm,np.arange(len(middle)))+ambient
        strengths=graph['body_edge_coefficients']@gamma
        edge_f=1.2256*900*strengths[:,None]*np.cross(edge_v,graph['ends']-graph['starts'])
        edge_m=np.cross(middle-[18.5,0.,0.],edge_f)
        tangent=np.empty_like(data['hv'])
        for beam in np.unique(data['beam']):
            mask=data['beam']==beam
            tangent[mask]=section(beam,data['t'][mask],np.sign(data['t'][mask]))['tangent']
        body_mask=np.any(graph['body_edge_coefficients']!=0,axis=1)
        qpeak=int(np.argmax(np.linalg.norm(qfield,axis=1)))
        epeak=int(np.argmax(np.where(body_mask,np.linalg.norm(edge_v,axis=1),-1.)))
        qnormal=qfield-np.sum(qfield*tangent,axis=1)[:,None]*tangent
        section_gamma=[]
        for patch,(nr,ns) in topo['patch_shapes'].items():section_gamma.extend(gamma[topo['patch']==patch].reshape(nr,ns)[-1]*30.)
        # Off-sheet probes retain fixed coordinates over every grid/chord count.
        offsheet=external_probes
        external=field(offsheet,graph,gamma,pg,vlm)+ambient
        path=args.output/f'c{nc}.npz'
        np.savez_compressed(path,gamma=gamma,matrix=matrix,rhs=rhs,residual=residual,
            prescribed_gamma=prescribed,prescribed_residual=prescribed_residual,
            corners=topo['corners'],collocation=topo['collocation'],normals=topo['normal'],
            starts=graph['starts'],ends=graph['ends'],edge_coefficients=graph['edge_coefficients'],
            body_edge_coefficients=graph['body_edge_coefficients'],body_mask=body_mask,
            ray_starts=graph['ray_starts'],ray_coefficients=graph['ray_coefficients'],
            chord_index=topo['chord_index'],section_ids=section_ids,pg=pg,ambient=ambient,
            quarter_chord_probes=data['hv'],quarter_chord_velocity=qfield,prescribed_velocity=fixed,
            section_circulation=np.asarray(section_gamma),original_gamma=data['gamma'],beam=data['beam'],t=data['t'],
            edge_midpoints=middle,edge_velocity=edge_v,edge_strengths=strengths,edge_forces=edge_f,edge_moments=edge_m,
            offsheet_probes=offsheet,offsheet_velocity=external)
        drag=float(edge_f.sum(axis=0)@ambient/(.5*1.2256*900*.9329))
        lift_axis=np.array([-ambient[2],0.,ambient[0]])
        lift=float(edge_f.sum(axis=0)@lift_axis/(.5*1.2256*900*.9329))
        row=dict(chord_rows=nc,status='linear_solution' if accepted else 'residual_rejected',panels=m,
            utc=datetime.now(timezone.utc).isoformat(),stage_seconds=time.monotonic()-start,solve_seconds=solve_seconds,
            maximum_boundary_residual=float(np.max(abs(residual))),relative_backward_error=backward,
            atomic_boundary_residual=float(np.max(abs(atomic_residual))),subdivision=subdivision,
            subdivision_external_field_difference=float(np.max(abs(old_external-new_external))),
            geometry_maximum_error=geom_error,quarter_chord_peak_speed_ratio=float(np.linalg.norm(qfield[qpeak])),
            quarter_chord_peak=dict(beam=data['beam'][qpeak],t=data['t'][qpeak],point=data['hv'][qpeak],velocity=qfield[qpeak]*30.),
            edge_peak_speed_ratio=float(np.linalg.norm(edge_v[epeak])),edge_peak_point=middle[epeak],
            approximate_quarter_normal_Mach=float(np.max(np.linalg.norm(qnormal,axis=1))*30/340.21),
            prescribed_peak_speed_ratio=float(np.max(np.linalg.norm(fixed,axis=1))),
            prescribed_maximum_boundary_residual=float(np.max(abs(prescribed_residual))),
            CL_full_edges=lift,CD_full_edges=drag,force=edge_f.sum(axis=0),moment=edge_m.sum(axis=0),
            offsheet_velocity=external*30.,one_row_prescribed_bridge=bridge,
            artifact=dict(path=path.name,sha256=sha(path)))
        rows.append(row);write(args.output/'results.json',rows)
        print(name,args.span,'c',nc,'panels',m,'q peak',row['quarter_chord_peak_speed_ratio'],
            'edge peak',row['edge_peak_speed_ratio'],'fixed peak',row['prescribed_peak_speed_ratio'],
            'CL',lift,'CD',drag,'residual',row['maximum_boundary_residual'],flush=True)
        del graph,original,topo,transformed,matrix,gamma;gc.collect()
    assert all(sha(ROOT/p)==h for p,h in plan['unchanged_pins'].items())
    assert not any(n=='openswing' or n.startswith('openswing.') for n in sys.modules)
    write(args.output/'verification.json',dict(utc=datetime.now(timezone.utc).isoformat(),
        linear_solves=len(rows),prescribed_field_states=len(rows),production_status_scope_unchanged=True,
        artifacts={str(p.relative_to(args.output)):sha(p) for p in args.output.rglob('*') if p.is_file()}))
    print('COMPLETE',name,args.span,flush=True)


if __name__=='__main__':
    main()
