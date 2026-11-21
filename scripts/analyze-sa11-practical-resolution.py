"""Audit saved SA-11 resolution states and the published Fourier projection."""
from datetime import datetime, timezone
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/sa11-practical-resolution-20261108'
SPEC=importlib.util.spec_from_file_location('driver',ROOT/'scripts/verify-sa11-practical-resolution.py')
DRIVER=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(DRIVER)
from openswing.factored_influence import FactoredInfluence

read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    plan=read(BASE/'plan.json');DRIVER.check(plan)
    assert sha(BASE/'driver-used.py')==plan['driver_sha256']
    rows=[];pins={};projection_error=0.;gamma_error=0.
    for case in plan['cases']:
        directory=BASE/case['id'];path=directory/'report.json'
        pins[str(path.relative_to(ROOT))]=sha(path)
        report=read(path);setup=read(directory/'setup.json')
        for name,pin in report['artifact_sha256'].items():assert sha(directory/name)==pin,name
        state=report['production']
        assert state['status']=='rejected' and state['details']['kind']=='section_normal_mach'
        assert state['residual']<1e-8 and report['values'] is None
        assert not (directory/'openswing.json').exists()
        assert setup['condition']['freeze_influences']==case['frozen']
        assert setup['condition']['speed']==240 and setup['condition']['alpha']==1
        assert setup['condition']['stall'] is True and setup['twist']==-4
        assert setup['condition']['circulation_modes']=={str(i):case['modes'] for i in (1,2,3)}
        with np.load(directory/'state.npz') as archive:
            saved={key:archive[key].copy() for key in archive.files}
        panels=report['intervals'];unknowns=report['circulation_unknowns']
        assert sum(m['intervals'] for m in setup['meshes'])==panels
        assert sum(m['nodes'] for m in setup['meshes'])==report['structural_nodes']==panels+3
        sample=np.zeros((panels,unknowns));test=np.zeros((unknowns,panels))
        ip=ik=0
        for mesh in setup['meshes']:
            count=mesh['intervals'];width=case['modes'] or count
            if case['modes']:
                theta=np.array(mesh['theta']);theta_a=(theta[:-1]+theta[1:])/2
                weights=-np.diff(theta)
                local=np.sin(theta_a[:,None]*np.arange(1,width+1))
                projection=2/np.pi*local.T*weights
            else:
                local=projection=np.eye(count)
            sample[ip:ip+count,ik:ik+width]=local
            test[ik:ik+width,ip:ip+count]=projection
            ip+=count;ik+=width
        assert ip==panels and ik==unknowns
        projected=test@saved['local_residual']
        pe=float(np.max(abs(projected-saved['projected_residual'])))
        ge=float(np.max(abs(sample@saved['coefficients']-saved['gamma'])))
        assert pe<1e-11 and ge<1e-10,(case,pe,ge)
        projection_error=max(projection_error,pe);gamma_error=max(gamma_error,ge)
        assert abs(float(np.max(abs(projected)))-state['residual'])<1e-11
        v=saved['velocity'];s=saved['tangent'];vp=v-np.sum(v*s,axis=1)[:,None]*s
        maximum_mach=float(np.linalg.norm(vp,axis=1).max()/340.21)
        assert abs(maximum_mach-state['maximum_section_normal_mach'])<1e-12
        assert np.sum(saved['stall_margin']<0)==report['stalled_strips']
        # Linear tangency conditioning is diagnostic, not another physical solve.
        # Its difference from the retained nonlinear solution measures stall's
        # effect; it is never substituted into the original nonlinear state.
        model=DRIVER.INC.model_at(-4.)
        meshes=DRIVER.model_meshes(model,case['intervals'])
        normals=np.concatenate([np.sin(np.deg2rad(m.beam.value('alpha',m.tm)))[:,None]*m.frames[...,0]
                                +np.cos(np.deg2rad(m.beam.value('alpha',m.tm)))[:,None]*m.frames[...,2] for m in meshes])
        wind=saved['wind'];pg=np.eye(3)+(1/np.sqrt(1-(240/340.21)**2)-1)*np.outer(wind,wind)
        operator=FactoredInfluence(saved['cp'],saved['a'],saved['b'],wind,pg)
        physical=operator.projected(normals).matrix()
        matrix=test@physical@sample
        alpha=np.deg2rad(1.);ambient=240*np.array([np.cos(alpha),0.,np.sin(alpha)])
        rhs=test@(-normals@ambient)
        coefficients=np.linalg.solve(matrix,rhs)
        linear_gamma=sample@coefficients
        relative_linear_difference=float(np.max(abs(linear_gamma-saved['gamma']))/np.max(abs(saved['gamma'])))
        singular=np.linalg.svd(matrix,compute_uv=False)
        rows.append(dict(case=case,structural_nodes=report['structural_nodes'],intervals=panels,
            circulation_unknowns=unknowns,maximum_mach=maximum_mach,
            maximum=state['details']['maximum'],projected_residual=state['residual'],
            maximum_local_residual=report['maximum_local_residual'],
            minimum_stall_margin_widths=report['minimum_stall_margin_widths'],stalled_strips=report['stalled_strips'],
            gamma_range=[float(saved['gamma'].min()),float(saved['gamma'].max())],
            linear_tangency_matrix_condition=float(singular[0]/singular[-1]),
            linear_system_normalized_residual=float(np.max(abs(matrix@coefficients-rhs))/240),
            linear_vs_nonlinear_gamma_relative_linf=relative_linear_difference,seconds=report['seconds']))
    assert len(rows)==18
    for name in ['verify-sa11-practical-resolution.py','analyze-sa11-practical-resolution.py']:
        ast.parse((ROOT/'scripts'/name).read_text())
    path=BASE/'analysis.json';assert not path.exists()
    path.write_text(json.dumps(dict(observed_utc=datetime.now(timezone.utc).isoformat(),cases=rows,
        report_sha256=pins,unchanged_pins=plan['unchanged_pins'],source_pins=len(plan['unchanged_pins']),
        maximum_projection_reconstruction_error=projection_error,maximum_gamma_reconstruction_error=gamma_error,
        production_seconds=sum(r['seconds'] for r in rows),maximum_projected_residual=max(r['projected_residual'] for r in rows),
        primary_status='SA-11 remains163/4592; all18 diagnostics reject local Mach. No valid load convergence comparison or new primary pass is available.',
        interpretation='The tested per-logical-beam20-40 counts do not resolve the field. Published sine weighting reproduces the retained projection. Large local residuals in a truncated series are allowed by the formulation, but do not remove the independent local Mach failure. The exact native surface/mode domain and producing discretization remain unverified.'),indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(cases=len(rows),source_pins=len(plan['unchanged_pins']),projection_error=projection_error,
        gamma_error=gamma_error,seconds=sum(r['seconds'] for r in rows),
        matrix_checks=[dict(id=r['case']['id'],condition=r['linear_tangency_matrix_condition'],
                           linear_gamma_difference=r['linear_vs_nonlinear_gamma_relative_linf']) for r in rows])))


if __name__=='__main__':main()
