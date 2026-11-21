"""Six fixed pointwise 20/30/40-interval requests with the existing minimum."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'artifacts/isae/sa11-extension-modes-20261108'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
utc=lambda:datetime.now(timezone.utc).isoformat()


def write(p,v):
    text=json.dumps(v,indent=2,allow_nan=False)+'\n'
    with p.open('x') as f:f.write(text)


def limits():
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(name)=='1'
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)


def check(pins):
    for name,h in pins.items():assert sha(ROOT/name)==h,name


def prepare(out):
    limits();assert not out.exists()
    parent=read(PARENT/'plan.json');check(parent['pins']);analysis=read(PARENT/'analysis.json')
    assert analysis['verified'] and analysis['plan_sha256']==sha(PARENT/'plan.json')
    controls=[c['control'] for c in parent['cases'] if c['modes']==20 and c['control']['intervals']==60]
    assert len(controls)==2;cases=[];pins=dict(parent['pins'])
    for control in controls:
        for n in (20,30,40):
            mesh=dict(default=n,beams={'1':dict(count=n,spacing='cosine',min_spacing=.0164659927127284)})
            cases.append(dict(id=f"v{int(control['settings']['speed'])}-a3-n{n}",requested_intervals=n,control=control,mesh=mesh))
    for p in (Path(__file__),PARENT/'plan.json',PARENT/'analysis.json'):pins[str(p.relative_to(ROOT))]=sha(p)
    out.mkdir(parents=True);(out/'driver-used.py').write_text(Path(__file__).read_text())
    write(out/'plan.json',dict(observed_utc=utc(),cases=cases,pins=pins,
        reason='Complete the ISAE PartI section5 p21 recommended20--40-variable check as pointwise physical mesh requests, after20/30/40 Fourier controls leave original CD decisions unchanged.',
        protocol='Original extension,alpha3,240/272m/s; original settings and fixed0.0164659927127284 minimum. Cosine20/30/40 requested intervals, mandatory stations retained; actual counts recorded. All three counts declared before solves. No primary scope or count changes.',physical_calls=6,primary_passes_added=0))
    signal.alarm(0);print('Prepared six pointwise mesh cases',flush=True)


def run(out,index):
    limits();clock=time.monotonic();plan=read(out/'plan.json');check(plan['pins'])
    case=plan['cases'][index];control=case['control'];folder=out/case['id'];assert not folder.exists()
    import numpy as np
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.frozen_influence import lifting_geometry
    from openswing.aero import FlightCondition,evaluate_aerodynamics,AnalysisError
    model=parse_asw((ROOT/control['case']['original_job']['model_path']).read_text(),beam_interpolation='natural-v1')
    condition=FlightCondition(**control['settings']);mesh,=model_meshes(model,case['mesh'])
    assert min(mesh.length)>=.0164659927127284-1e-12
    folder.mkdir();status='computed';start=time.monotonic()
    try:result=evaluate_aerodynamics(model,condition,[mesh])
    except AnalysisError as exc:
        status='rejected';write(folder/'rejected.json',dict(error=str(exc),details=exc.details))
        report=dict(status=status,actual=None,passed=0,required=7)
    else:
        write(folder/'accepted.json',result);assert result['converged'] and result['residual']<1e-8
        e,_,ez=condition.vectors();actual={k:float(result['Cm_origin' if k=='Cm' else k]) for k in ('CL','CD','CDi','Cm','efficiency')}
        actual.update(lift=float(np.dot(result['force'],ez)),drag=float(np.dot(result['force'],e)))
        errors={k:100*(actual[k]/v-1) for k,v in control['reference'].items()}
        cl=np.array([s['cl'] for s in result['strips']]);margin=np.minimum(mesh.beam.value('CLmax',mesh.tm)-cl,cl-mesh.beam.value('CLmin',mesh.tm))/.05
        g=lifting_geometry([mesh],e)
        normal=np.sin(np.deg2rad(mesh.beam.value('alpha',mesh.tm)))[:,None]*mesh.frames[...,0]+np.cos(np.deg2rad(mesh.beam.value('alpha',mesh.tm)))[:,None]*mesh.frames[...,2]
        np.savez(folder/'geometry.npz',**g,normal=normal,span=mesh.frames[...,1],theta=mesh.theta,t=mesh.tm)
        report=dict(status=status,actual=actual,relative_percent_errors=errors,passed=int(sum(abs(v)<=5 for v in errors.values())),required=7,
            residual=result['residual'],maximum_normal_mach=max(s['normal_mach'] for s in result['strips']),
            minimum_stall_margin_widths=float(min(margin)),CDi_near=result['CDi_near'],CDp=result['CDp'])
    report.update(id=case['id'],observed_utc=utc(),requested_intervals=case['requested_intervals'],actual_intervals=len(mesh.tm),
        minimum_interval=float(min(mesh.length)),reference=control['reference'],physical_calls=1,solve_seconds=time.monotonic()-start,
        seconds=time.monotonic()-clock,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=sha(out/'plan.json'),artifacts={p.name:sha(p) for p in folder.iterdir()})
    write(folder/'report.json',report);signal.alarm(0);print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('action',choices=('prepare','run'));p.add_argument('--index',type=int);a=p.parse_args()
    if a.action=='prepare':prepare(a.output.resolve())
    else:run(a.output.resolve(),a.index)
