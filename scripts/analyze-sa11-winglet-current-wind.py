"""Check saved SA-11 wake-option states and independently integrate worst fields."""
from datetime import datetime, timezone
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/sa11-winglet-current-wind-20261108'
SPEC=importlib.util.spec_from_file_location('driver',ROOT/'scripts/verify-sa11-winglet-current-wind.py')
DRIVER=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(DRIVER)
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def independent_field(geometry,gamma,wind,receiver,nquad):
    """Drela's PG transform; bound Gauss integration plus analytical rays.

    No production influence operator or vortex kernel is called here.
    Same physical index means zero core. Omit only the receiver's own bound.
    """
    mach=240/340.21
    pg=np.eye(3)+(1/np.sqrt(1-mach*mach)-1)*np.outer(wind,wind)
    point=geometry['hv'][receiver]@pg.T
    a=geometry['a']@pg.T;b=geometry['b']@pg.T
    mask=np.arange(len(gamma))!=receiver
    nodes,weights=np.polynomial.legendre.leggauss(nquad)
    delta=b[mask]-a[mask]
    source=a[mask,None,:]+(nodes[None,:,None]+1)/2*delta[:,None,:]
    r=point-source
    integrand=np.cross(delta[:,None,:],r)/np.linalg.norm(r,axis=2)[:,:,None]**3
    bound_sources=np.einsum('nqk,q->nk',integrand,weights/2)/(4*np.pi)*gamma[mask,None]
    bound=bound_sources.sum(axis=0)@pg
    direction=pg@wind;direction/=np.linalg.norm(direction)
    def ray(origins):
        r=point-origins
        axial=r@direction
        perpendicular=r-axial[:,None]*direction
        radius2=np.sum(perpendicular*perpendicular,axis=1)
        assert np.all(radius2>0)
        return np.cross(direction,r)*(1+axial/np.linalg.norm(r,axis=1))[:,None]/(4*np.pi*radius2[:,None])
    wake=np.sum((ray(b)-ray(a))*gamma[:,None],axis=0)@pg
    return bound,wake


def main():
    plan=read(BASE/'plan.json');DRIVER.check(plan)
    assert sha(BASE/'driver-used.py')==plan['driver_sha256']
    rows=[];pins={};worst_error=0.;quad_error=0.;new_seconds=0.
    for case in plan['cases']:
        path=ROOT/case['reused_report'] if 'reused_report' in case else BASE/case['id']/'report.json'
        if 'reused_report' in case:assert sha(path)==case['reused_sha256']
        pins[str(path.relative_to(ROOT))]=sha(path)
        report=read(path)
        for name,pin in report['artifact_sha256'].items():assert sha(path.parent/name)==pin,name
        model=DRIVER.INC.model_at(case['twist'])
        _,segments=DRIVER.INC.CONVERT.conversion(model,case['refinement'])
        with np.load(ROOT/plan['geometry_files'][str(case['refinement'])]) as archive:
            fields={key:archive[key].copy() for key in archive.files}
        meshes,_,errors,_=DRIVER.INC.CONVERT.mapped_meshes(model,fields,segments)
        condition=DRIVER.INC.FlightCondition(speed=240,alpha=case['alpha'],density=1.2256,freeze_influences=case['frozen'])
        e,_,_=condition.vectors();wind=np.array([1.,0.,0.]) if case['frozen'] else e
        geom=DRIVER.INC.CONVERT.lifting_geometry(meshes,wind)
        tangent=np.concatenate([m.frames[...,1] for m in meshes])
        state_file=path.parent/('diagnostic-state.npz' if 'reused_report' in case else 'state.npz')
        with np.load(state_file) as state:
            gamma=state['gamma'];velocity=state['velocity'];margin=state['stall_margin']
            if 'reused_report' not in case:
                for key in ('a','b','hv','cp'):assert np.max(abs(geom[key]-state[key]))<1e-14
        vp=velocity-np.sum(velocity*tangent,axis=1)[:,None]*tangent
        mach=np.linalg.norm(vp,axis=1)/340.21;index=int(np.argmax(mach))
        production=report['production'];details=production['details']
        assert production['status']=='rejected' and details['kind']=='section_normal_mach'
        assert production['residual']<1e-8
        assert abs(mach[index]-production['maximum_section_normal_mach'])<1e-12
        assert abs(float(margin.min()/.05)-report['minimum_stall_margin_widths'])<1e-12
        breakdown=details['vortex_breakdown']
        bound,wake=independent_field(geom,gamma,wind,index,96)
        bound_fine,wake_fine=independent_field(geom,gamma,wind,index,160)
        quadrature_error=float(np.max(abs(bound-bound_fine)))
        error=max(float(np.max(abs(bound-breakdown['bound_velocity']))),
                  float(np.max(abs(wake-breakdown['wake_velocity']))),
                  float(np.max(abs(240*e+bound+wake-velocity[index]))))
        assert quadrature_error<1e-7,(case,quadrature_error)
        assert error<1e-6,(case,error)
        worst_error=max(worst_error,error);quad_error=max(quad_error,quadrature_error)
        maximum=details['maximum']
        summary=dict(case=case,panels=len(gamma),maximum_mach=float(mach[index]),maximum=maximum,
            production_status=production['status'],residual=production['residual'],
            stalled_strips=int(np.sum(margin<0)),minimum_stall_margin_widths=report['minimum_stall_margin_widths'],
            bound_speed=float(np.linalg.norm(bound)),wake_speed=float(np.linalg.norm(wake)),
            independent_field_error=error,quadrature_refinement_error=quadrature_error,
            largest_bound_source=breakdown['bound_sources'][0],largest_wake_source=breakdown['wake_sources'][0])
        rows.append(summary)
        if 'reused_report' not in case:new_seconds+=report['seconds']
    assert len(rows)==16
    for name in ['verify-sa11-winglet-current-wind.py','analyze-sa11-winglet-current-wind.py']:
        ast.parse((ROOT/'scripts'/name).read_text())
    output=BASE/'analysis.json';assert not output.exists()
    output.write_text(json.dumps(dict(observed_utc=datetime.now(timezone.utc).isoformat(),cases=rows,
        report_sha256=pins,unchanged_pins=plan['unchanged_pins'],new_solver_calls=12,reused_cases=4,
        total_new_solver_seconds=new_seconds,maximum_independent_field_error=worst_error,
        maximum_quadrature_refinement_error=quad_error,
        primary_status='SA-11 remains163/4592; all16 diagnostic states fail local Mach. Two fine current-wind alpha5 states also exceed local lift limits; post-stall repair remains deferred.',
        conclusion='Current-wind influences are not a general repair at archived speed. At alpha1 the corrected sign still leaves a root wake spike, and refinement increases its sampled maximum. At alpha5 refinement moves the largest velocity to the main-wing center, dominated by the opposite half-wing bound segment. Independent field integration reproduces both mechanisms; no production change follows.') ,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(cases=len(rows),source_pins=len(plan['unchanged_pins']),new_calls=12,new_seconds=new_seconds,
        independent_error=worst_error,quadrature_error=quad_error,
        table=[dict(id=r['case']['id'],Mach=r['maximum_mach'],beam=r['maximum']['beam'],
                    stalled=r['stalled_strips'],bound=r['bound_speed'],wake=r['wake_speed']) for r in rows])))


if __name__=='__main__':main()
