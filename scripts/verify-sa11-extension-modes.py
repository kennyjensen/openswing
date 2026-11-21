"""SA-11 extension: published 20/30/40 Fourier counts on fixed minimum meshes.

Twelve predeclared physical calls, one bounded foreground invocation each.
The four authenticated pointwise controls are reused without new solves.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'artifacts/isae/sa11-extension-drag-budget-r2-20261108'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
utc=lambda:datetime.now(timezone.utc).isoformat()


def write(path,value):
    text=json.dumps(value,indent=2,allow_nan=False)+'\n'
    with path.open('x') as f:f.write(text)


def bounded():
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(key)=='1'
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)


def check(pins):
    for name,value in pins.items():assert sha(ROOT/name)==value,name


def prepare(out):
    bounded();assert not out.exists()
    parent=read(PARENT/'plan.json');check(parent['pins'])
    analysis=read(PARENT/'analysis.json');assert analysis['verified'] and analysis['plan_sha256']==sha(PARENT/'plan.json')
    controls=[r for r in analysis['cases'] if r['settings']['alpha']==3 and not r['settings']['freeze_influences']]
    assert len(controls)==4
    pins=dict(parent['pins']);cases=[]
    for row in controls:
        folder=PARENT/row['id'];assert sha(folder/'report.json')==row['report_sha256']
        pins[str((folder/'report.json').relative_to(ROOT))]=row['report_sha256']
        for name,digest in row['artifacts'].items():
            path=folder/name;assert sha(path)==digest;pins[str(path.relative_to(ROOT))]=digest
        for modes in (20,30,40):cases.append(dict(id=row['id']+f'-k{modes}',modes=modes,control=row))
    for p in (Path(__file__),PARENT/'plan.json',PARENT/'analysis.json'):
        pins[str(p.relative_to(ROOT))]=sha(p)
    out.mkdir(parents=True);(out/'driver-used.py').write_text(Path(__file__).read_text())
    write(out/'plan.json',dict(observed_utc=utc(),cases=cases,pins=pins,physical_calls=12,
        previous_goal_turn='Progress: four saved extension states verified Eq151--155 receivers and independent vortex algebra; three alternative probes all worsened drag. Main-wing force sampling contributes most mesh dependence.',
        source_basis='ISAE PartI section5 p21 recommends20--40 circulation variables/Fourier coefficients from elliptical-wing checks. Drela steady Eqs150--153 and200--204 specify the sine basis and weighted residual. Historical SA11 counts remain unknown.',
        protocol='Original extension; alpha3 at240/272m/s; cosine64/128 requests with fixed0.0164659927127284m minimum yield60/108 intervals. Change only circulation_modes to20/30/40 on logical beam1. Original current-wind,PG,density,stall,section data and validity gates retained. Four saved pointwise controls authenticated.',
        limits='One process/BLAS thread,512MiB address space,15CPU/25wall seconds;one physical call per invocation. No browser/build jobs.',
        primary_passes_added=0,scope='Alternative discretizations; never add to or replace the original primary total. Preserve failures and all seven targets. No settings selected by comparison error.'))
    signal.alarm(0);print('Prepared 12 Fourier cases with four saved pointwise controls',flush=True)


def run(out,index):
    bounded();clock=time.monotonic();plan=read(out/'plan.json');check(plan['pins'])
    case=plan['cases'][index];control=case['control'];source_case=control['case']
    folder=out/case['id'];assert not folder.exists()
    import numpy as np
    sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.aero import FlightCondition,evaluate_aerodynamics,AnalysisError
    from openswing.circulation import CirculationBasis
    model=parse_asw((ROOT/source_case['original_job']['model_path']).read_text(),beam_interpolation='natural-v1')
    meshes=model_meshes(model,source_case['mesh']);mesh,=meshes
    assert len(mesh.tm)==control['intervals'] and min(mesh.length)>=.0164659927127284-1e-12
    settings=dict(control['settings'],circulation_modes={1:case['modes']})
    condition=FlightCondition(**settings);basis=CirculationBasis(meshes,condition.circulation_modes)
    folder.mkdir();write(folder/'setup.json',dict(condition=settings,basis=basis.report(),theta=mesh.theta.tolist()))
    start=time.monotonic();result=None
    try:
        result=evaluate_aerodynamics(model,condition,meshes)
    except AnalysisError as exc:
        assert exc.details and exc.details['kind']=='section_normal_mach',str(exc)
        tb=exc.__traceback__
        while tb and tb.tb_frame.f_code.co_name!='evaluate_aerodynamics':tb=tb.tb_next
        assert tb is not None
        local=tb.tb_frame.f_locals
        gamma,velocity,cl=[local[k].copy() for k in ('gamma','v','cl')]
        local_residual=local['local_residual'](gamma).copy();residual=float(exc.details['circulation_residual'])
        write(folder/'rejected.json',dict(error=str(exc),details=exc.details));del tb,local
        status='rejected';actual=None;checks={name:False for name in control['reference']}
    else:
        write(folder/'accepted.json',result)
        assert result['converged'] and result['circulation_discretization']['independent_unknowns']==case['modes']
        gamma,velocity,cl=[np.array([s[k] for s in result['strips']]) for k in ('circulation','relative_velocity','cl')]
        local_residual=np.array(result['circulation_local_residual']);residual=result['residual']
        e,_,ez=condition.vectors()
        actual={k:float(result['Cm_origin' if k=='Cm' else k]) for k in ('CL','CD','CDi','Cm','efficiency')}
        actual.update(lift=float(np.dot(result['force'],ez)),drag=float(np.dot(result['force'],e)))
        checks={k:bool(abs(actual[k]-v)<=.05*abs(v)) for k,v in control['reference'].items()}
        status='computed'
    solve_seconds=time.monotonic()-start
    assert residual<1e-8
    coefficients=basis.encode(gamma);projected=basis.test@local_residual
    assert abs(float(max(abs(projected)))-residual)<2e-12
    span=mesh.frames[...,1];perp=velocity-np.sum(velocity*span,axis=1)[:,None]*span
    normal_mach=np.linalg.norm(perp,axis=1)/340.21
    assert (max(normal_mach)<1)==(result is not None)
    margin=np.minimum(mesh.beam.value('CLmax',mesh.tm)-cl,cl-mesh.beam.value('CLmin',mesh.tm))/condition.stall_width
    with np.load(PARENT/control['id']/'fields.npz') as archive:base={k:archive[k] for k in archive}
    assert np.array_equal(base['span'],span) and np.array_equal(base['t'],mesh.tm) and np.array_equal(base['ds'],mesh.length)
    np.savez(folder/'state.npz',gamma=gamma,velocity=velocity,cl=cl,coefficients=coefficients,
        local_residual=local_residual,projected_residual=projected,theta=mesh.theta,stall_margin=margin)
    report=dict(id=case['id'],observed_utc=utc(),status=status,modes=case['modes'],intervals=len(mesh.tm),
        residual=residual,maximum_local_residual=float(max(abs(local_residual))),
        maximum_normal_mach=float(max(normal_mach)),minimum_stall_margin_widths=float(min(margin)),
        actual=actual,reference=control['reference'],passed=int(sum(checks.values())),required=7,checks=checks,
        relative_percent_errors=None if actual is None else {k:100*(actual[k]-v)/abs(v) for k,v in control['reference'].items()},
        gamma_change_vs_pointwise_relative_linf=float(max(abs(gamma-base['gamma']))/max(abs(base['gamma']))),
        sampling_condition=basis.beams[0]['sampling_condition'],
        CDi_near=None if result is None else result['CDi_near'],CDp=None if result is None else result['CDp'],
        physical_calls=1,solve_seconds=solve_seconds,seconds=time.monotonic()-clock,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,plan_sha256=sha(out/'plan.json'),
        artifacts={p.name:sha(p) for p in folder.iterdir() if p.is_file()})
    write(folder/'report.json',report);signal.alarm(0)
    print(json.dumps({k:report[k] for k in ('id','status','passed','maximum_normal_mach','maximum_local_residual',
        'minimum_stall_margin_widths','relative_percent_errors','seconds')}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('action',choices=('prepare','run'));parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.output.resolve())
    else:run(args.output.resolve(),args.index)
