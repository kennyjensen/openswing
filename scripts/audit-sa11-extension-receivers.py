"""Fixed-circulation force-point audit; four saved states, zero new solves."""
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


def limits():
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(key)=='1'
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)


def check(pins):
    for name,value in pins.items():assert sha(ROOT/name)==value,name


def prepare(out):
    limits();assert not out.exists()
    parent=read(PARENT/'plan.json');check(parent['pins'])
    analysis=read(PARENT/'analysis.json');assert analysis['verified'] and analysis['plan_sha256']==sha(PARENT/'plan.json')
    cases=[r for r in analysis['cases'] if r['settings']['alpha']==3 and not r['settings']['freeze_influences']]
    assert len(cases)==4
    pins=dict(parent['pins'])
    for p in (Path(__file__),PARENT/'plan.json',PARENT/'analysis.json',ROOT/'scripts/avl_vorvelc_reference.py'):
        pins[str(p.relative_to(ROOT))]=sha(p)
    for r in cases:
        assert sha(PARENT/r['id']/'report.json')==r['report_sha256']
        pins[str((PARENT/r['id']/'report.json').relative_to(ROOT))]=r['report_sha256']
        for name,value in r['artifacts'].items():
            p=PARENT/r['id']/name;assert sha(p)==value;pins[str(p.relative_to(ROOT))]=value
    out.mkdir(parents=True)
    (out/'driver-used.py').write_text(Path(__file__).read_text())
    write(out/'plan.json',dict(observed_utc=utc(),cases=cases,pins=pins,
        previous_goal_turn='Progress: 20 extension cases isolated94--97percent of mesh-dependent drag in near-field vortex force; scalar reductions verified. Stall and frozen-toggle explanations narrowed.',
        protocol='Four saved current-wind alpha3 states,240/272m/s,60/108intervals,unchangedminimum. Original Eq154--155 receiver vs exact spline position vs theta-weighted bound-endpoint interpolation vs arithmetic bound midpoint. Sources,Gamma,section properties,span vectors,lengths and control-point leakage stay fixed.',
        limitation='Alternative receiver fields are formal partial force diagnostics, not converged solutions or accepted moments. No production force or sampling rule is changed; no added native passes.',physical_calls=0))
    signal.alarm(0);print('Prepared four saved-state audits',flush=True)


def run(out,index):
    limits();clock=time.monotonic();plan=read(out/'plan.json');check(plan['pins'])
    row=plan['cases'][index];case=row['case'];folder=out/row['id'];assert not folder.exists()
    import numpy as np
    sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.arc_length import material_arc
    from openswing.factored_influence import FactoredInfluence
    from openswing.ground import GroundPlane
    from avl_vorvelc_reference import matrix as reference_matrix
    source=ROOT/case['original_job']['model_path'];model=parse_asw(source.read_text(),beam_interpolation='natural-v1')
    mesh,=model_meshes(model,case['mesh'])
    with np.load(PARENT/row['id']/'fields.npz') as a:d={k:a[k] for k in a}
    N=len(d['gamma']);arc=material_arc(mesh.beam)
    s0,s1=arc.at(mesh.t0),arc.at(mesh.t1);total=arc.total
    # Printed Eqs151--154, recomputed without mesh.tm or mesh.rm.
    theta0=np.arccos(np.clip(1-2*s0/total,-1,1));theta1=np.arccos(np.clip(1-2*s1/total,-1,1))
    sa=.5*total*(1-np.cos(.5*(theta0+theta1)))
    fraction=(sa-s0)/(s1-s0)
    ra=mesh.r0+fraction[:,None]*(mesh.r1-mesh.r0)
    t=arc.inverse(sa);sample=lambda name:mesh.beam.value(name,t)
    e=d['wind'];cross=np.linalg.norm(np.cross(e,d['span']),axis=1)
    published=ra+((.25-sample('Xax'))*sample('chord')/cross)[:,None]*e
    error=float(np.max(abs(published-d['hv'])))
    assert error<3e-12 and np.max(abs(t-mesh.tm))<3e-12
    receivers=dict(published=d['hv'],spline_position=d['hv']+mesh.beam.position(t)-ra,
        bound_interpolated=d['a']+fraction[:,None]*(d['b']-d['a']),bound_midpoint=.5*(d['a']+d['b']))
    alpha=np.deg2rad(row['settings']['alpha']);rotation=np.array([[np.cos(alpha),0,np.sin(alpha)],[0,1,0],[-np.sin(alpha),0,np.cos(alpha)]])
    assert np.max(abs(rotation[0]-e))<1e-15
    rho=row['settings']['density'];speed=row['settings']['speed'];mach=speed/340.21
    qs=.5*rho*speed**2*model.reference[0,0]
    tangency=np.einsum('ij,ij->i',d['cp_velocity'],d['normal'])
    results={};saved={}
    for name,points in receivers.items():
        field=FactoredInfluence(points,d['a'],d['b'],e,d['pg'],0.,GroundPlane(),exclude_bound=np.eye(N,dtype=bool))
        bound=np.einsum('ijk,j->ik',field.bound,d['gamma'])
        wake=np.einsum('ijk,j->ik',field.rays,field.wake_strengths(d['gamma']))
        velocity=speed*e+bound+wake
        native=reference_matrix(points@rotation.T,d['a']@rotation.T,d['b']@rotation.T,mach,
            exclude_self=True,core_fraction=0.,dtype=np.longdouble)
        independent=np.einsum('ijk,j->ik',native,d['gamma'])@rotation
        # Remove AVL's rounded constant; retain the independent segment/ray algebra.
        independent*=np.longdouble(1)/(4*np.arccos(np.longdouble(-1))*np.longdouble('.079577472'))
        independent_error=float(np.max(abs(independent-(bound+wake)))/speed)
        assert independent_error<2e-10,(name,independent_error)
        perp=velocity-np.einsum('ij,ij->i',velocity,d['span'])[:,None]*d['span']
        vp=np.linalg.norm(perp,axis=1);vm=np.linalg.norm(velocity,axis=1)
        parts=dict(vortex=rho*d['gamma'][:,None]*np.cross(velocity,d['span'])*d['ds'][:,None],
            friction=.5*rho*vm[:,None]*velocity*(d['chord']*d['cdf']*d['ds'])[:,None],
            pressure=.5*rho*vp[:,None]*perp*(d['chord']*d['cdp']*d['ds'])[:,None],
            leakage=2*rho*perp/vp[:,None]*(tangency**2*d['chord']*d['ds'])[:,None])
        cd={k:float(np.sum(f@e)/qs) for k,f in parts.items()}
        value=sum(cd.values())
        if name=='published':
            assert np.max(abs(velocity-d['velocity']))<3e-10
            assert abs(value-row['actual']['CD'])<2e-12
        results[name]=dict(CD_formal=value,components=cd,CD_error_percent=100*(value/row['reference']['CD']-1),
            maximum_normal_mach=float(max(vp)/340.21),receiver_shift_max=float(max(np.linalg.norm(points-d['hv'],axis=1))),
            independent_velocity_relative_error=independent_error,
            region_vortex_CD={label:float(np.sum(parts['vortex'][mask]@e)/qs) for label,mask in
                [('main',abs(mesh.tm)<=1.2426+1e-12),('extension',abs(mesh.tm)>1.2426+1e-12)]})
        saved[name+'_points']=points;saved[name+'_velocity']=velocity
        saved[name+'_vortex_force']=parts['vortex'];saved[name+'_profile_force']=sum(parts[k] for k in ('friction','pressure','leakage'))
    folder.mkdir();np.savez(folder/'fields.npz',**saved,fraction=fraction)
    result=dict(id=row['id'],observed_utc=utc(),published_receiver_error=error,intervals=N,results=results,
        physical_calls=0,source_case_report_sha256=sha(PARENT/row['id']/'report.json'),plan_sha256=sha(out/'plan.json'),
        fields_sha256=sha(folder/'fields.npz'),seconds=time.monotonic()-clock,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    write(folder/'report.json',result);signal.alarm(0);print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('action',choices=('prepare','run'));parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.output.resolve())
    else:run(args.output.resolve(),args.index)
