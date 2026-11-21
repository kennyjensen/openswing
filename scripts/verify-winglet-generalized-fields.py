"""Prescribed-field audit of MachUpX's connected effective lifting line.

Execute selected, unmodified AST method bodies from the pinned reference on
explicit section fixtures. This is NOT a full MachUpX run or an ASWING change.
No aerodynamic solves, airfoil package installation, or production imports.
"""
from datetime import datetime, timezone
import argparse
import ast
import gc
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
from types import MethodType

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'third_party/machupx'
BASELINE=ROOT/'artifacts/isae/unswept-winglet-junction-20261107'
REFERENCE=ROOT/'artifacts/isae/winglet-finite-chord-20261107/reference'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def portable(x):
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,dict):return {k:portable(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [portable(v) for v in x]
    return x


def write(path,data):
    path.write_text(json.dumps(portable(data),indent=2,allow_nan=False)+'\n')


def source_method(path,class_name,name):
    tree=ast.parse(path.read_text())
    cls=next(c for c in tree.body if isinstance(c,ast.ClassDef) and c.name==class_name)
    node=next(f for f in cls.body if isinstance(f,ast.FunctionDef) and f.name==name)
    # The intact method body is compiled; no source replacement/monkeypatch
    # occurs inside the numerical method. Module imports/init are not executed.
    module=ast.Module(body=[node],type_ignores=[])
    namespace={'np':np,'m':math}
    exec(compile(module,str(path),'exec'),namespace)
    return namespace[name]


class SegmentFixture:
    pass


class GeometryHarness:
    pass


def fixture(saved,mode):
    strips=saved['strips'];N=len(strips)
    bounds=np.asarray(saved['vortex_geometry']['bound_segments'])
    station=np.asarray([s['t'] for s in strips])
    cp=np.asarray([s['velocity_position'] for s in strips])
    a=1/(2*np.pi)
    objects=[]
    for name,side,physical_beam,b,root in (
        ('winglet_left','left',1,.2,-.5),('main_left','left',2,.5,0.),
        ('main_right','right',2,.5,0.),('winglet_right','right',3,.2,.5)):
        mask=np.array([s['beam']==physical_beam for s in strips])
        if name=='main_left':mask &= station<0.
        if name=='main_right':mask &= station>0.
        rows=np.flatnonzero(mask);nodes=np.vstack([bounds[rows[0],0],bounds[rows,1]])
        count=len(rows);span=(nodes[-1]-nodes[0]);span/=np.linalg.norm(span)
        n0=np.cross([1.,0.,0.],span)
        axial=np.cos(a)*np.array([1.,0.,0.])-np.sin(a)*n0
        normal=np.cross(axial,span)
        cp_fraction=((root-station[rows])/b if side=='left' else (station[rows]-root)/b)
        node_t=np.r_[station[rows]-np.array([strips[i]['length'] for i in rows])/2,
                     station[rows[-1]]+strips[rows[-1]]['length']/2]
        # Parameter t is increasing material arc on all fixture pieces.
        node_fraction=(root-node_t)/b if side=='left' else (node_t-root)/b
        node_fraction[0],node_fraction[-1]=(1.,0.) if side=='left' else (0.,1.)
        seg=SegmentFixture()
        seg.__dict__.update(name=name,side=side,N=count,b=b,ID=1 if name.startswith('main') else 2,
            has_mirror=True,parent_has_mirror=True,y_offset=0.,wing_ID=-1,
            _connected_to_ID=0 if name.startswith('main') else 1,_connected_to_loc='tip',
            _delta_origin=np.zeros(3),nodes=nodes,control_points=cp[rows],
            node_span_locs=node_fraction,cp_span_locs=cp_fraction,
            c_bar_cp=np.full(count,.1),c_node=np.full(count+1,.1),
            dS=np.asarray([strips[i]['length']*.1 for i in rows]),
            max_camber_cp=np.zeros(count),max_thickness_cp=np.zeros(count),sweep_cp=np.zeros(count),
            reid_corr=mode!='raw',delta_joint=.15,blend_dist=1.,
            u_s_cp=np.tile(span,(count,1)),u_a_cp=np.tile(axial,(count,1)),
            u_n_cp=np.tile(normal,(count,1)),u_s_cp_unswept=np.tile(span,(count,1)),
            u_a_cp_unswept=np.tile(axial,(count,1)),u_n_cp_unswept=np.tile(normal,(count,1)),
            u_a_node=np.tile(axial,(count+1,1)),fixture_indices=rows)
        seg.get_tip_loc=MethodType(lambda self:self.nodes[0 if self.side=='left' else -1],seg)
        objects.append(seg)
    harness=GeometryHarness();harness.N=N;harness.CG=np.zeros(3);harness._input_dict={}
    harness.wing_segments={s.name:s for s in objects}
    if mode=='separate-groups':
        # Explicit diagnostic grouping override only; the numerical effective-
        # geometry method body remains unchanged. Main left/right stay joined.
        def separate(self):
            self._segments_in_wings=[[objects[0]],objects[1:3],[objects[3]]]
            self._num_wings=3;self.segments=objects
        harness._sort_segments_into_wings=MethodType(separate,harness)
    harness._calculate_geometry()
    order=np.concatenate([s.fixture_indices for s in harness.segments])
    np.testing.assert_array_equal(order,np.arange(N))
    np.testing.assert_allclose(harness.P0,bounds[:,0],atol=0.,rtol=0.)
    np.testing.assert_allclose(harness.P1,bounds[:,1],atol=0.,rtol=0.)
    np.testing.assert_array_equal(harness.PC,cp)
    if mode!='separate-groups':assert harness._num_wings==1
    return harness


def field(h,vlm):
    """Independent stable zero-core integration over the effective polylines."""
    N=h.N;p=np.broadcast_to(h.PC[:,None,:],(N,N,3))
    def finite(a,b,own=False):
        active=np.any(a!=b,axis=-1)
        if own:active &= ~np.eye(N,dtype=bool)
        out=np.zeros_like(p)
        out[active]=vlm.finite_segment(p[active],a[active],b[active])
        return out
    bound=finite(h.P0_eff,h.P1_eff,True)
    joint0=finite(h.P0_joint_eff,h.P0_eff)
    joint1=finite(h.P1_eff,h.P1_joint_eff)
    rays=vlm.semi_infinite(p,h.P1_joint_eff,[1.,0.,0.])-vlm.semi_infinite(p,h.P0_joint_eff,[1.,0.,0.])
    return bound,joint0+joint1,rays


def source_expression(h):
    """Independently compare with the retained scene.py segment/ray formulas.

    This is a transcription, not execution of the Scene solver. Its original
    ray denominator cutoff is recorded; this fixture must not activate it.
    """
    def finite(r0,r1,own=False):
        m0=np.linalg.norm(r0,axis=-1);m1=np.linalg.norm(r1,axis=-1)
        denom=m0*m1*(m0*m1+np.einsum('ijk,ijk->ij',r0,r1))
        with np.errstate(divide='ignore',invalid='ignore'):
            value=(m0+m1)[...,None]*np.cross(r0,r1)/denom[...,None]
        if own:value[np.diag_indices(h.N)]=0.
        assert np.isfinite(value).all()
        return value
    total=finite(h.r_0,h.r_1,True)+finite(h.r_0_joint,h.r_0)+finite(h.r_1,h.r_1_joint)
    smallest=np.inf;cutoffs=0
    for r,sign in ((h.r_0_joint,-1.),(h.r_1_joint,1.)):
        radius=np.linalg.norm(r,axis=-1);denom=radius*(radius-r[:,:,0])
        smallest=min(smallest,float(denom.min()));cutoffs+=int(np.count_nonzero(denom<=1e-13))
        with np.errstate(divide='ignore',invalid='ignore'):
            total+=np.where(denom[...,None]>1e-13,
                np.nan_to_num(sign*np.cross([1.,0.,0.],r)/denom[...,None]),0.)
    assert cutoffs==0
    return total/(4*np.pi),dict(minimum_ray_denominator=smallest,source_cutoff_activations=cutoffs)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a fresh output directory.')
    manifest=json.loads((SOURCE/'SOURCE.json').read_text())
    for item in manifest['files']:assert sha(SOURCE/item['path'])==item['sha256']
    baseline_plan=json.loads((BASELINE/'plan.json').read_text())
    baseline_verification=json.loads((BASELINE/'verification.json').read_text())
    assert all(sha(ROOT/p)==pin for p,pin in baseline_plan['pins'].items())
    assert all(sha(BASELINE/p)==pin for p,pin in baseline_verification['artifacts'].items())
    expected_vlm='1b1b90aa89829fcafadbb4c13f3972f580420d99071ca1c5ef8c0c7b542bb550'
    assert sha(REFERENCE/'vlm.py')==expected_vlm
    for name in ('_calculate_geometry','_sort_segments_into_wings','_sort_segments_left_to_right'):
        setattr(GeometryHarness,name,source_method(SOURCE/'machupX/airplane.py','Airplane',name))
    SegmentFixture.is_continuation=source_method(SOURCE/'machupX/wing_segment.py','WingSegment','is_continuation')
    sys.path.insert(0,str(REFERENCE.resolve()));import vlm
    assert sha(Path(vlm.__file__))==expected_vlm
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__,args.output/'driver-used.py')
    for name in ('SOURCE.json','LICENSE','machupX/airplane.py','machupX/wing_segment.py','machupX/scene.py'):
        target=args.output/'reference'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(SOURCE/name,target)
    shutil.copyfile(REFERENCE/'vlm.py',args.output/'reference/vlm.py')
    saved=[r for r in json.loads((BASELINE/'results.json').read_text())
           if r['request']['sampling']=='arithmetic-control']
    requests=[dict(main_intervals=r['request']['main_intervals'],mode=mode)
              for r in saved for mode in ('raw','connected','separate-groups')]
    plan=dict(utc=utc(),requests=requests,revision=manifest['revision'],
        source_manifest_sha256=sha(SOURCE/'SOURCE.json'),driver_sha256=sha(Path(__file__)),
        baseline_results_sha256=sha(BASELINE/'results.json'),unchanged_pins=baseline_plan['pins'],
        source_methods=['Airplane._calculate_geometry','Airplane._sort_segments_into_wings',
                        'Airplane._sort_segments_left_to_right','WingSegment.is_continuation'],
        parameters=dict(joint_length_chords=.15,blend_distance=1.,main_segment_semispan=.5,winglet_semispan=.2),
        meaning='Prescribed Gamma from saved LL; execute intact pinned geometry methods on explicit section fixtures. '
            'No full MachUpX input parser, airfoil model or equilibrium solver is executed. '
            'Separate-groups is a declared grouping sensitivity, not a native model input.',
        closure='Effective field inserted into vector Kutta-Joukowski for a diagnostic only; '
            'these Gamma values do not solve the generalized method. Normal and axial section '
            'vectors are expressed in OpenSwing coordinates by a proper-axis rotation.',
        scientific_solves=0)
    write(args.output/'plan.json',plan);rows=[]
    for request in requests:
        n,mode=request['main_intervals'],request['mode']
        baseline=next(r['result'] for r in saved if r['request']['main_intervals']==n)
        h=fixture(baseline,mode)
        gamma=np.array([s['circulation'] for s in baseline['strips']])
        components=field(h,vlm);tensor=sum(components)
        original,guard=source_expression(h)
        np.testing.assert_allclose(tensor,original,atol=2e-9,rtol=2e-9)
        velocity=np.einsum('ijk,j->ik',tensor,gamma)+[1.,0.,0.]
        if mode=='raw':
            np.testing.assert_allclose(velocity,[s['relative_velocity'] for s in baseline['strips']],
                                       atol=3e-12,rtol=3e-12)
        vp=velocity-np.sum(velocity*h.u_s,axis=1)[:,None]*h.u_s
        speed=np.linalg.norm(vp,axis=1)
        incidence=np.arctan2(np.sum(velocity*h.u_n,axis=1),np.sum(velocity*h.u_a,axis=1))
        # Gamma defect for the common linear Cl=2*pi*alpha in-plane NLL
        # section closure; this is diagnostic, never an acceptance solve.
        gamma_defect=gamma-.5*h.c_bar*speed*2*np.pi*incidence
        forces=1.225*gamma[:,None]*np.cross(velocity,h.dl)
        gaps=np.linalg.norm(h.P1_eff[:,:-1]-h.P0_eff[:,1:],axis=-1)
        joint_gaps=np.linalg.norm(h.P1_joint_eff[:,:-1]-h.P0_joint_eff[:,1:],axis=-1)
        # Audit the geometry equation independently of its original method.
        geometry_defect=0.
        if mode!='raw':
            offset=0
            for objects,wing in zip(h._segments_in_wings,h.wing_slices):
                for seg in objects:
                    for i in range(offset,offset+seg.N):
                        sigma=(2/seg.b)**2
                        for base,eff,spans in ((h.P0,h.P0_eff,h.P0_span_locs),
                                              (h.P1,h.P1_eff,h.P1_span_locs)):
                            ds=spans[wing]-h.PC_span_locs[i]
                            tangent=h.u_s[i]/np.linalg.norm(h.u_s[i,1:])
                            expected=base[wing]+np.exp(-sigma*ds**2)[:,None]*(h.PC[i]+ds[:,None]*tangent-base[wing])
                            geometry_defect=max(geometry_defect,float(np.max(abs(expected-eff[i,wing]))))
                    offset+=seg.N
            assert geometry_defect<5e-15
        peak=int(np.argmax(np.linalg.norm(velocity,axis=1)))
        label=f'n{n}-{mode}'
        artifact=args.output/(label+'.npz')
        np.savez_compressed(artifact,points=h.PC,physical_a=h.P0,physical_b=h.P1,
            effective_a=h.P0_eff,effective_b=h.P1_eff,joint_a=h.P0_joint_eff,joint_b=h.P1_joint_eff,
            gamma=gamma,velocity=velocity,forces=forces,gamma_defect=gamma_defect,
            bound_induced=np.einsum('ijk,j->ik',components[0],gamma),
            joint_induced=np.einsum('ijk,j->ik',components[1],gamma),
            ray_induced=np.einsum('ijk,j->ik',components[2],gamma),
            physical_stations=np.asarray([s['t'] for s in baseline['strips']]),
            bound_connection_gaps=gaps,joint_connection_gaps=joint_gaps)
        row=dict(request=request,utc=utc(),points=h.N,wing_groups=[[s.name for s in group] for group in h._segments_in_wings],
            maximum_speed=float(np.max(np.linalg.norm(velocity,axis=1))),peak_position=h.PC[peak],
            peak_velocity=velocity[peak],diagnostic_CL=float(forces[:,2].sum()/.06125),
            diagnostic_CD=float(forces[:,0].sum()/.06125),
            maximum_gamma_closure_defect=float(np.max(abs(gamma_defect))),
            maximum_geometry_equation_defect=geometry_defect,
            maximum_source_tensor_difference=float(np.max(abs(tensor-original))),
            maximum_bound_connection_gap=float(np.max(gaps)),maximum_joint_connection_gap=float(np.max(joint_gaps)),
            **guard,artifact=dict(path=artifact.name,sha256=sha(artifact)))
        rows.append(row);write(args.output/'results.json',rows)
        print(label,'peak',row['maximum_speed'],'joint gap',row['maximum_joint_connection_gap'],
              'Gamma defect',row['maximum_gamma_closure_defect'],flush=True)
        del h,components,tensor,original;gc.collect()
    assert all(sha(ROOT/p)==pin for p,pin in plan['unchanged_pins'].items())
    assert sha(Path(__file__))==plan['driver_sha256']
    assert not any(name=='openswing' or name.startswith('openswing.') for name in sys.modules)
    write(args.output/'verification.json',dict(utc=utc(),fields=len(rows),scientific_solves=0,
        source_and_scope_unchanged=True,source_formula_cutoffs_inactive=True,
        artifacts={str(p.relative_to(args.output)):sha(p) for p in args.output.rglob('*') if p.is_file()}))


if __name__=='__main__':main()
