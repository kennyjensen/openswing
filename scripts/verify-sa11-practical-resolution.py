"""SA-11 practical-resolution check: independent mesh and circulation counts.

One invocation runs a frozen/current-wind pair, serially, at alpha1/speed240.
The report-derived -4 degree input is diagnostic; no defaults are selected.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import time

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('incidence',ROOT/'scripts/verify-sa11-winglet-incidence.py')
INC=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(INC)
from openswing.circulation import CirculationBasis
from openswing.geometry import model_meshes

read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
utc=lambda:datetime.now(timezone.utc).isoformat()
write=INC.write


def prepare(out):
    assert not out.exists(),out
    parent=read(ROOT/'artifacts/isae/sa11-winglet-current-wind-20261108/plan.json')
    pins=dict(parent['unchanged_pins'])
    for name in ['reference/aswing-authoritative-20261108/aswing-extended-user-manual.pdf',
                 'scripts/verify-sa11-winglet-incidence.py']:
        pins[name]=sha(ROOT/name)
    for name,pin in pins.items():assert sha(ROOT/name)==pin,name
    layouts=[dict(representation='pointwise',intervals=n,modes=0) for n in (20,30,40)]
    layouts += [dict(representation='fourier',intervals=n,modes=k) for n in (64,128) for k in (20,30,40)]
    cases=[]
    for group,layout in enumerate(layouts):
        for frozen in (True,False):
            cases.append(dict(group=group,id=f'g{group}-'+('frozen' if frozen else 'current'),frozen=frozen,**layout))
    out.mkdir(parents=True)
    write(out/'plan.json',dict(observed_utc=utc(),cases=cases,unchanged_pins=pins,driver_sha256=sha(Path(__file__)),
        previous_goal_turn='progress: documented wake option tested at archived speed; independent integration confirmed two local-field mechanisms, and ISAE practical-resolution guidance identified',
        source_basis='ISAE Part I section5 p21 recommends20-40 circulation variables/Fourier coefficients for an elliptical-wing control; extended manual Fig1.13 illustrates19 modes with180 structural nodes. Neither establishes the original SA11 counts.',
        protocol='Report-minus4 upper-winglet twist; alpha1degree, speed240, density1.2256, automaticPG Mach. Pointwise20/30/40 requested intervals per logical beam, and Fourier20/30/40 modes per logical beam on64/128 requested intervals. Whole-beam cosine nodes and Glauert samples; retain mandatory breaks, stall and local Mach guard. Both frozen/current-wind options.',
        scope='Per-logical-beam mode domain is the current implementation; no recovered native connected-surface mode mapping or original mesh is claimed. Exact actual nodes, intervals, unknowns, local/projected residuals and guards are recorded. No selecting counts by archived error or creating primary passes.'))
    shutil.copyfile(__file__,out/'driver-used.py')
    print(json.dumps(dict(prepared=True,cases=len(cases),groups=len(layouts))))


def check(plan):
    for name,pin in plan['unchanged_pins'].items():assert sha(ROOT/name)==pin,name
    assert sha(Path(__file__))==plan['driver_sha256']


def run(out,case):
    directory=out/case['id'];assert not directory.exists();directory.mkdir()
    model=INC.model_at(-4.)
    meshes=model_meshes(model,case['intervals'])
    modes={mesh.beam.index:case['modes'] for mesh in meshes}
    condition=INC.FlightCondition(speed=240.,alpha=1.,density=1.2256,mach=None,
        freeze_influences=case['frozen'],circulation_modes=modes)
    basis=CirculationBasis(meshes,modes)
    mesh_rows=[dict(beam=m.beam.index,nodes=len(m.tm)+1,intervals=len(m.tm),
        node_parameters=np.r_[m.t0,m.t1[-1]].tolist(),theta=m.theta.tolist(),sample_parameters=m.tm.tolist()) for m in meshes]
    write(directory/'setup.json',dict(condition=asdict(condition),twist=-4.,meshes=mesh_rows,basis=basis.report()))
    gamma=velocity=cl=local_residual=None;values=None;start=time.monotonic()
    try:
        result=INC.evaluate_aerodynamics(model,condition,meshes)
        write(directory/'openswing.json',result)
        assert result['aerodynamic_influences']['frozen']==case['frozen']
        assert result['circulation_discretization']['independent_unknowns']==basis.size
        gamma=np.array([s['circulation'] for s in result['strips']])
        velocity=np.array([s['relative_velocity'] for s in result['strips']])
        cl=np.array([s['cl'] for s in result['strips']])
        local_residual=np.array(result['circulation_local_residual'])
        maximum=result['lifting_airflow']['maximum']
        state=dict(status='computed',residual=result['residual'],maximum_section_normal_mach=maximum['normal_mach'],maximum=maximum)
        values={key:result[key] for key in ('CL','CD','CDi','Cm','efficiency')}
    except INC.AnalysisError as exc:
        state=dict(status='rejected',error=str(exc),details=exc.details)
        if exc.details and exc.details.get('kind')=='section_normal_mach':
            tb=exc.__traceback__
            while tb and tb.tb_frame.f_code.co_name!='evaluate_aerodynamics':tb=tb.tb_next
            assert tb is not None
            local=tb.tb_frame.f_locals
            gamma,velocity,cl=[local[key].copy() for key in ('gamma','v','cl')]
            local_residual=local['local_residual'](gamma).copy()
            assert local['basis'].size==basis.size
            state.update(residual=exc.details['circulation_residual'],maximum_section_normal_mach=exc.details['maximum']['normal_mach'],maximum=exc.details['maximum'])
        write(directory/'openswing-rejected.json',state)
    seconds=time.monotonic()-start
    diagnostic={}
    if gamma is not None:
        margins=[];offset=0
        for mesh in meshes:
            end=offset+len(mesh.tm)
            margins.extend(np.minimum(mesh.beam.value('CLmax',mesh.tm)-cl[offset:end],
                                     cl[offset:end]-mesh.beam.value('CLmin',mesh.tm)))
            offset=end
        margins=np.array(margins)
        e,_,_=condition.vectors();wind=np.array([1.,0.,0.]) if case['frozen'] else e
        geometry=INC.CONVERT.lifting_geometry(meshes,wind)
        tangent=np.concatenate([m.frames[...,1] for m in meshes])
        projected=basis.test@local_residual
        projection_error=abs(float(np.max(abs(projected)))-state['residual'])
        assert projection_error<1e-11,projection_error
        vp=velocity-np.sum(velocity*tangent,axis=1)[:,None]*tangent
        mach=float(np.linalg.norm(vp,axis=1).max()/340.21)
        assert abs(mach-state['maximum_section_normal_mach'])<1e-12
        np.savez(directory/'state.npz',gamma=gamma,velocity=velocity,cl=cl,stall_margin=margins,
            local_residual=local_residual,projected_residual=projected,coefficients=basis.encode(gamma),
            tangent=tangent,wind=wind,**geometry)
        diagnostic=dict(minimum_stall_margin_widths=float(margins.min()/.05),stalled_strips=int(np.sum(margins<0)),
            maximum_local_residual=float(np.max(abs(local_residual))),projection_error=projection_error)
    table=np.loadtxt(INC.FOLDER/'Aswing_Simulations/Wing_tip_up/wingtip_up_Ma_0_70.txt')
    row=table[table[:,71]==1.];assert row.shape==(1,82)
    reference={key:float(row[0,i]) for key,i in [('CL',77),('CD',78),('CDi',79),('Cm',80),('efficiency',81)]}
    report=dict(observed_utc=utc(),case=case,production=state,seconds=seconds,structural_nodes=sum(len(m.tm)+1 for m in meshes),
        intervals=basis.panels,circulation_unknowns=basis.size,values=values,reference=reference,
        error_percent=None if values is None else {key:100*(values[key]/reference[key]-1) for key in values},**diagnostic)
    report['artifact_sha256']={p.name:sha(p) for p in directory.iterdir() if p.is_file()}
    write(directory/'report.json',report)
    print(json.dumps(dict(case=case,actual_intervals=basis.panels,unknowns=basis.size,
        status=state['status'],maximum_mach=state.get('maximum_section_normal_mach'),
        error_percent=report['error_percent'],**diagnostic)),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    g=p.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',action='store_true');g.add_argument('--group',type=int)
    a=p.parse_args();out=a.output.resolve()
    if a.prepare:prepare(out);return
    plan=read(out/'plan.json');check(plan)
    cases=[case for case in plan['cases'] if case['group']==a.group];assert len(cases)==2
    for case in cases:run(out,case)
    check(plan)


if __name__=='__main__':main()
