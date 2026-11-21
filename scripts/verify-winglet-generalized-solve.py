"""Serial nonlinear section solves on saved generalized winglet geometries.

Independent research harness, not a production solver change or full MachUpX
application run. The pinned Scene residual/section methods independently check
an analytic reduced residual and its solved endpoint. Ideal Cl=2*pi*alpha.
"""
from datetime import datetime, timezone
import argparse
import gc
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace

import numpy as np
from scipy.optimize import root

ROOT=Path(__file__).resolve().parents[1]
FIELDS=ROOT/'artifacts/isae/winglet-generalized-fields-20261107'
HELPER=ROOT/'scripts/verify-winglet-generalized-fields.py'
GAMMA_SCALE=.05


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()


def portable(x):
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,dict):return {k:portable(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [portable(v) for v in x]
    return x


def write(p,value):p.write_text(json.dumps(portable(value),indent=2,allow_nan=False)+'\n')


class IdealSection:
    def __init__(self,n):self.N=n
    def get_cp_CL(self,alpha,re,mach):return 2*np.pi*alpha
    def get_cp_CLa(self,alpha,re,mach):return np.full_like(alpha,2*np.pi)
    def get_cp_CLRe(self,alpha,re,mach):return np.zeros_like(alpha)
    def get_cp_CLM(self,alpha,re,mach):return np.zeros_like(alpha)


class SourceSectionHarness:
    pass


class SectionProblem:
    def __init__(self,data,tensor):
        self.data,self.tensor=data,tensor
        self.dl=data['physical_b']-data['physical_a']
        self.ds=np.linalg.norm(self.dl,axis=1)
        self.span=self.dl/self.ds[:,None]
        theta=1/(2*np.pi);n0=np.cross([1.,0.,0.],self.span)
        self.axial=np.cos(theta)*np.array([1.,0.,0.])-np.sin(theta)*n0
        self.normal=np.cross(self.axial,self.span)
        self.chord=np.full(len(self.ds),.1)
        self.Aa=np.einsum('ijk,ik->ij',tensor,self.axial)
        self.An=np.einsum('ijk,ik->ij',tensor,self.normal)
        h=SourceSectionHarness();n=len(self.ds)
        h.__dict__.update(_N=n,_dl=self.dl,_V_ji=tensor,_v_inf_and_rot=np.tile([1.,0.,0.],(n,1)),
            _use_in_plane=True,_use_total_velocity=True,_match_machup_pro=False,_use_swept_sections=True,
            _P_in_plane=np.eye(3)[None]-self.span[:,:,None]*self.span[:,None,:],
            _c_bar=self.chord,_nu=1e-5,_a=340.294,_u_a=self.axial,_u_n=self.normal,
            _dS=self.ds*self.chord,_CLa=np.zeros(n),_CL=np.zeros(n),_CLRe=np.zeros(n),_CLM=np.zeros(n),
            _aL0=np.zeros(n),_C_sweep_inv=np.ones(n),
            _airplane_objects=[SimpleNamespace(N=n,segments=[IdealSection(n)])])
        self.source=h

    def local(self,gamma):
        va=self.axial[:,0]+self.Aa@gamma
        vn=self.normal[:,0]+self.An@gamma
        vp=np.hypot(va,vn)
        if np.any(vp<1e-10):raise ValueError('Section normal speed too small for divided residual.')
        alpha=np.arctan2(vn,va)
        return va,vn,vp,alpha

    def residual(self,gamma):
        _,_,vp,alpha=self.local(gamma)
        return gamma-np.pi*self.chord*vp*alpha

    def jacobian(self,gamma):
        va,vn,vp,alpha=self.local(gamma)
        return np.eye(len(gamma))-np.pi*self.chord[:,None]*(
            ((alpha*va-vn)/vp)[:,None]*self.Aa+((alpha*vn+va)/vp)[:,None]*self.An)

    def compare_source(self,gamma):
        actual=self.source._lifting_line_residual(gamma)
        expected=2*self.local(gamma)[2]*self.ds*self.residual(gamma)
        np.testing.assert_allclose(actual,expected,atol=2e-14,rtol=2e-12)
        return float(np.max(abs(actual-expected))),float(np.max(abs(actual)))

    def check_jacobian(self,gamma):
        rng=np.random.default_rng(42618);errors=[]
        j=self.jacobian(gamma);step=1e-7
        for _ in range(2):
            direction=rng.normal(size=len(gamma));direction/=np.max(abs(direction))
            expected=(-self.residual(gamma+2*step*direction)+8*self.residual(gamma+step*direction)
                      -8*self.residual(gamma-step*direction)+self.residual(gamma-2*step*direction))/(12*step)
            actual=j@direction
            np.testing.assert_allclose(actual,expected,atol=5e-7,rtol=5e-8)
            errors.append(float(np.max(abs(actual-expected))))
        return max(errors)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--batch',choices=('50','100','200'),required=True,
                        help='Run only three serial states at this span resolution.')
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a fresh output directory.')
    field_plan=json.loads((FIELDS/'plan.json').read_text())
    verification=json.loads((FIELDS/'verification.json').read_text())
    all_rows=json.loads((FIELDS/'results.json').read_text())
    assert all(sha(FIELDS/p)==v for p,v in verification['artifacts'].items())
    assert all(sha(ROOT/p)==v for p,v in field_plan['unchanged_pins'].items())
    assert sha(HELPER)==field_plan['driver_sha256']
    spec=importlib.util.spec_from_file_location('generalized_field_helper',HELPER)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    reference=FIELDS/'reference';sys.path.insert(0,str(reference.resolve()));import vlm
    assert sha(Path(vlm.__file__))==verification['artifacts']['reference/vlm.py']
    methods=('_lifting_line_residual','_calc_v_i','_get_section_lift','_correct_CL_for_sweep')
    source_path=reference/'machupX/scene.py'
    for name in methods:setattr(SourceSectionHarness,name,helper.source_method(source_path,'Scene',name))
    n=int(args.batch)
    selected=[r for r in all_rows if r['request']['main_intervals']==n]
    assert [r['request']['mode'] for r in selected]==['raw','connected','separate-groups']
    args.output.mkdir(parents=True);shutil.copyfile(__file__,args.output/'driver-used.py')
    shutil.copyfile(HELPER,args.output/'field-helper-used.py')
    shutil.copyfile(source_path,args.output/'scene-source-used.py')
    shutil.copyfile(reference/'LICENSE',args.output/'MACHUPX-LICENSE')
    plan=dict(utc=utc(),requests=[r['request'] for r in selected],field_study=str(FIELDS.relative_to(ROOT)),
        field_results_sha256=sha(FIELDS/'results.json'),field_plan_sha256=sha(FIELDS/'plan.json'),
        driver_sha256=sha(Path(__file__)),helper_sha256=sha(HELPER),source_scene_sha256=sha(source_path),
        source_methods=list(methods),unchanged_pins=field_plan['unchanged_pins'],
        physics=dict(chord=.1,density=1.225,reference_area=.1,reference_chord=.1,speed=1.,
            section_law='Cl=2*pi*alpha_eff; no section drag or moment; no Re/Mach dependence.',
            incidence_radians=1/(2*np.pi),use_in_plane=True,use_total_velocity=True,
            use_swept_sections=True,sweep_factor=1.,zero_lift_angle=0.,core=0.,PG=0.),
        solver=dict(method='scipy.optimize.root hybr with analytic divided-residual Jacobian',
            scale=GAMMA_SCALE,initial_gamma='saved ASWING-style tangency Gamma on same grid',xtol=1e-11,
            maxfev=120,absolute_gamma_residual_gate=1e-11,source_residual_gate=1e-12,
            retries=0,scope='Three serial states per invocation; no continuation or fitted parameters.'),
        equations=dict(reduced='R=Gamma-pi*c*|V_perp|*atan2(V.n,V.a)',
            source='MachUpX residual=2*|V cross dl|*Gamma-|V_perp|^2*dS*Cl',
            relation='source_residual=2*|V_perp|*ds*R for this straight-section fixture',
            force='rho*Gamma*(V cross physical_dl); moment about origin uses physical receiver positions.'),
        limitations=['Selected residual methods executed, not the full MachUpX app/input/airfoil stack.',
            'Ideal airfoil fixture supplies coefficients; corrected geometry and joint gaps are unchanged.',
            'These solves do not establish native ASWING parity, accuracy against experiment or finite-chord convergence.'])
    write(args.output/'plan.json',plan);rows=[]
    for entry in selected:
        request=entry['request'];mode=request['mode'];label=f'n{n}-{mode}'
        input_path=FIELDS/entry['artifact']['path'];assert sha(input_path)==entry['artifact']['sha256']
        with np.load(input_path) as loaded:data={k:loaded[k] for k in loaded.files}
        h=SimpleNamespace(N=len(data['gamma']),PC=data['points'],P0_eff=data['effective_a'],
            P1_eff=data['effective_b'],P0_joint_eff=data['joint_a'],P1_joint_eff=data['joint_b'])
        tensor=sum(helper.field(h,vlm))
        np.testing.assert_allclose(np.einsum('ijk,j->ik',tensor,data['gamma'])+[1.,0.,0.],
                                   data['velocity'],atol=3e-12,rtol=3e-12)
        problem=SectionProblem(data,tensor)
        seed=data['gamma'];initial_check,initial_source=problem.compare_source(seed)
        initial_jacobian=problem.check_jacobian(seed)
        start=time.monotonic()
        solution=root(lambda z:problem.residual(z*GAMMA_SCALE)/GAMMA_SCALE,
            seed/GAMMA_SCALE,jac=lambda z:problem.jacobian(z*GAMMA_SCALE),method='hybr',
            options=dict(xtol=1e-11,maxfev=120))
        seconds=time.monotonic()-start;gamma=solution.x*GAMMA_SCALE
        residual=problem.residual(gamma)
        final_check,source_residual=problem.compare_source(gamma)
        jacobian_check=problem.check_jacobian(gamma)
        velocity=np.einsum('ijk,j->ik',tensor,gamma)+[1.,0.,0.]
        force=1.225*gamma[:,None]*np.cross(velocity,problem.dl)
        moments=np.cross(data['points'],force)
        va,vn,vp,alpha=problem.local(gamma)
        accepted=bool(np.isfinite(gamma).all() and np.max(abs(residual))<=1e-11 and source_residual<=1e-12)
        path=args.output/(label+'.npz')
        np.savez_compressed(path,gamma=gamma,seed_gamma=seed,residual=residual,
            source_residual=problem.source._lifting_line_residual(gamma),tensor=tensor,
            velocity=velocity,forces=force,moments=moments,points=data['points'],dl=problem.dl,
            axial=problem.axial,normal=problem.normal,span=problem.span,chord=problem.chord,
            alpha=alpha,perpendicular_speed=vp,jacobian=problem.jacobian(gamma),
            material_stations=data['physical_stations'])
        row=dict(request=request,utc=utc(),status='converged' if accepted else 'not_converged',
            seconds=seconds,evaluations=int(solution.nfev),jacobian_evaluations=int(solution.njev),
            scipy_success=bool(solution.success),scipy_message=str(solution.message),
            maximum_gamma_residual=float(np.max(abs(residual))),maximum_source_residual=source_residual,
            maximum_source_equation_difference=max(initial_check,final_check),
            maximum_jacobian_directional_error=max(initial_jacobian,jacobian_check),
            maximum_speed=float(np.max(np.linalg.norm(velocity,axis=1))),
            maximum_perpendicular_speed=float(np.max(vp)),maximum_abs_section_cl=float(np.max(abs(2*np.pi*alpha))),
            minimum_axial_velocity=float(np.min(va)),minimum_gamma=float(np.min(gamma)),maximum_gamma=float(np.max(gamma)),
            CL=float(force[:,2].sum()/.06125),CD=float(force[:,0].sum()/.06125),
            Cm=float(moments[:,1].sum()/.006125),force=force.sum(axis=0),moment=moments.sum(axis=0),
            maximum_gamma_change=float(np.max(abs(gamma-seed))),
            input_artifact_sha256=entry['artifact']['sha256'],artifact=dict(path=path.name,sha256=sha(path)))
        rows.append(row);write(args.output/'results.json',rows)
        print(label,row['status'],'CL',row['CL'],'CD',row['CD'],'peak',row['maximum_speed'],
              'R',row['maximum_gamma_residual'],'evaluations',row['evaluations'],flush=True)
        del tensor,problem,h,data;gc.collect()
    assert all(sha(ROOT/p)==v for p,v in plan['unchanged_pins'].items())
    assert sha(Path(__file__))==plan['driver_sha256']
    assert not any(name=='openswing' or name.startswith('openswing.') for name in sys.modules)
    write(args.output/'verification.json',dict(utc=utc(),scientific_solves=len(rows),
        production_imports=[],source_and_scope_unchanged=True,
        artifacts={p.name:sha(p) for p in args.output.iterdir() if p.is_file()}))


if __name__=='__main__':main()
