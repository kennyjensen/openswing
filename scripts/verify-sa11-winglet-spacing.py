"""Redistribute SA-11 winglet nodes without moving geometry or root filaments.

One small, resource-limited production solve per --case. All spacing rules and
resolutions are prescribed before solving; no numerical pass is a primary
ISAE pass for this report-minus4 diagnostic input.
"""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import shutil
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
PRIOR=ROOT/'artifacts/isae/sa11-root-translations-20261108'
OLD=ROOT/'artifacts/isae/sa11-winglet-receivers-20261108/whole-beam-a1'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def write(p,x): p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def utc(): return datetime.now(timezone.utc).isoformat()


def check(pins):
    for name,digest in pins.items(): assert sha(ROOT/name)==digest,name


def prepare(out):
    assert not out.exists(),out
    previous=read(PRIOR/'plan.json');check(previous['pins'])
    for name,digest in previous['generated_pins'].items(): assert sha(PRIOR/name)==digest,name
    catalog=read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for item in catalog['files']:
        if item['id'] in ('isae-part-1','drela-steady'):
            assert sha(ROOT/item['local_pdf'])==item['sha256']
    source_catalog=read(ROOT/'docs/validation/isae-sa11-sources.json')
    cache=ROOT/'reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865'
    name=next(k for k in source_catalog['sources'] if k.endswith('/Wing_tip_up/wingtip_up_Ma_0_70.txt'))
    table=cache/name
    assert sha(table)==source_catalog['sources'][name]['sha256']
    lines=[line.split() for line in table.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]
    rows=[]
    for line in lines:
        try: row=[float(v) for v in line]
        except ValueError: continue
        rows.append(row)
    assert len(rows)==41 and all(len(r)==82 for r in rows)
    row=rows[4]; assert row[71]==row[74]==1.
    reference=dict(CL=row[77],CD=row[78],CDi=row[79],Cm_origin=row[80],efficiency=row[81])
    for key,value in previous['reference'].items(): assert reference[key]==value
    out.mkdir(parents=True)
    shutil.copyfile(PRIOR/'control.asw',out/'model.asw')
    old=read(OLD/'mesh-settings.json');lo=old['2']['nodes'][0];hi=old['2']['nodes'][-1]
    cases=[]
    for count in (16,32,64,128):
        for rule in ('cosine','uniform','tip_clustered'):
            case=dict(id=f'{rule}-{count}',rule=rule,winglet_intervals=count,total_intervals=32+2*count)
            if rule=='cosine' and count==16:
                settings=old
            else:
                fractions=[(1-math.cos(math.pi*i/count))/2 if rule=='cosine' else
                    math.sin(math.pi*i/(2*count)) if rule=='tip_clustered' else i/count
                    for i in range(count+1)]
                nodes=[lo+(hi-lo)*x for x in fractions];nodes[0]=lo;nodes[-1]=hi
                settings={'1':old['1'],'2':dict(nodes=nodes),'3':dict(nodes=[-x for x in nodes[::-1]])}
            write(out/f"{case['id']}-mesh.json",settings);cases.append(case)
    pins=dict(previous['pins'])
    for p in [Path(__file__),PRIOR/'plan.json',PRIOR/'control-64/report.json',
              PRIOR/'control-64/state.npz',OLD/'mesh-settings.json',table,
              ROOT/'docs/validation/isae-sa11-sources.json',ROOT/'docs/validation/aswing-authoritative-sources.json']:
        pins[str(p.relative_to(ROOT))]=sha(p)
    write(out/'plan.json',dict(observed_utc=utc(),cases=cases,pins=pins,
        generated_pins={p.name:sha(p) for p in out.iterdir()},condition=previous['condition'],reference=reference,
        previous_goal_turn='Progress:12 fixed-geometry translations isolated wake proximity and sharp-bound-turn mechanisms.',
        steering='User requested redistribution of vortex cores/locations; test winglet nodes and receiver positions first. Smooth-junction construction deferred.',
        protocol='Main-wing32 intervals fixed. Winglets16/32/64/128 with cosine, uniform, and f(u)=sin(pi*u/2) tip-clustered nodes. All original root/tip positions, shared physical index1, zero core, whole-beam Glauert receivers and equations retained. Alpha1 speed240 frozen PG240/340.21.',
        limits='These are disclosed diagnostic spacings, not authenticated ASWING defaults. Root filaments cannot be moved by interior re-spacing. Primary count/scope unchanged.512MiB AS,15sCPU,25s wall,BLAS1,one foreground solve per call.'))
    shutil.copyfile(__file__,out/'driver-used.py')
    print(json.dumps(dict(prepared=True,cases=cases,reference=reference)),flush=True)


def run(out,case_id):
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        assert os.environ.get(name)=='1',name
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(15,15))
    def expired(*_): raise TimeoutError('SA11 spacing job exceeded25 seconds')
    signal.signal(signal.SIGALRM,expired);signal.alarm(25)
    begin=time.monotonic();plan=read(out/'plan.json');check(plan['pins'])
    for name,digest in plan['generated_pins'].items(): assert sha(out/name)==digest,name
    case=next(c for c in plan['cases'] if c['id']==case_id)
    folder=out/case_id;assert not folder.exists()
    print(f'Importing bounded single-thread solver: {case_id}',flush=True)
    import numpy as np
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.aero import FlightCondition,AnalysisError,evaluate_aerodynamics
    from openswing.frozen_influence import lifting_geometry
    from openswing.factored_influence import FactoredInfluence
    from openswing.ground import GroundPlane
    from openswing.trefftz import trefftz_for_meshes
    model=parse_asw((out/'model.asw').read_text())
    assert all(b.physical_index==1 for b in model.beams)
    meshes=model_meshes(model,dict(default=16,beams=read(out/f'{case_id}-mesh.json')))
    condition=FlightCondition(**plan['condition'])
    g=lifting_geometry(meshes,np.array([1.,0.,0.]));n=len(g['hv'])
    assert n==case['total_intervals'] and len(meshes[0].tm)==32
    with np.load(PRIOR/'control-64/geometry.npz') as old:
        for key in g: np.testing.assert_array_equal(g[key][:32],old[key][:32])
        np.testing.assert_array_equal(g['a'][32],old['a'][32])
        np.testing.assert_array_equal(g['b'][-1],old['b'][-1])
    folder.mkdir();np.savez(folder/'geometry.npz',**g)
    print(f'Solving {n} intervals; geometry and zero-core unchanged.',flush=True)
    start=time.monotonic();accepted=None
    try: accepted=evaluate_aerodynamics(model,condition,meshes)
    except AnalysisError as exc:
        assert exc.details and exc.details['kind']=='section_normal_mach',str(exc)
        tb=exc.__traceback__
        while tb and tb.tb_frame.f_code.co_name!='evaluate_aerodynamics': tb=tb.tb_next
        assert tb is not None
        local=tb.tb_frame.f_locals
        gamma,v,cl=[local[k].copy() for k in ('gamma','v','cl')]
        force=local['flift']+local['frate']+local['fprofile']
        residual=exc.details['circulation_residual']
        coefficients={k:exc.details['surface_force_diagnostic']['terms']['sum'][k] for k in ('CL','CD')}
        coefficients['Cm_origin']=None
        write(folder/'rejected.json',dict(message=str(exc),details=exc.details))
        status='REJECTED_STATE_DIAGNOSTIC'
    else:
        write(folder/'accepted.json',accepted)
        gamma,v,cl,force=[np.array([s[k] for s in accepted['strips']]) for k in ('circulation','relative_velocity','cl','force')]
        residual=accepted['residual'];coefficients={k:accepted[k] for k in ('CL','CD','Cm_origin')}
        status='COMPUTED_DIAGNOSTIC_NOT_PRIMARY_PASS'
    elapsed=time.monotonic()-start;assert residual<1e-8
    span=np.concatenate([m.frames[...,1] for m in meshes])
    beam=np.concatenate([np.full(len(m.tm),m.beam.index) for m in meshes])
    t=np.concatenate([m.tm for m in meshes]);sample=lambda name:np.concatenate([m.beam.value(name,m.tm) for m in meshes])
    vp=v-np.sum(v*span,axis=1)[:,None]*span;mach=np.linalg.norm(vp,axis=1)/340.21
    pg=np.diag([1/np.sqrt(1-condition.mach**2),1.,1.])
    field=FactoredInfluence(g['hv'],g['a'],g['b'],np.array([1.,0.,0.]),pg,0.,GroundPlane(),exclude_bound=np.eye(n,dtype=bool))
    bound=np.einsum('ijk,j->ik',field.bound,gamma);wake=np.einsum('ijk,j->ik',field.rays,field.wake_strengths(gamma))
    error=float(np.max(abs(condition.speed*condition.vectors()[0]+bound+wake-v)));assert error<3e-8
    e,ey,ez=condition.vectors();scale=.5*1.2256*condition.speed**2*model.reference[0,0]
    for key,axis in [('CL',ez),('CD',e)]:
        scalar=sum(sum(float(x)*float(y) for x,y in zip(f,axis)) for f in force)/scale
        assert abs(scalar-coefficients[key])<2e-13
    trefftz=trefftz_for_meshes(model,replace(condition,alpha=0.,beta=0.),meshes,gamma,1.2256,GroundPlane())
    assert trefftz['available']
    coefficients.update(CDi=trefftz['CDi'],efficiency=trefftz['efficiency'])
    if accepted is not None:
        for k in ('CDi','efficiency'): assert abs(coefficients[k]-accepted[k])<2e-12
    rejected=int(np.count_nonzero(mach>=1));assert (rejected==0)==(accepted is not None)
    margin=np.minimum(sample('CLmax')-cl,cl-sample('CLmin'))/condition.stall_width
    worst=int(np.argmax(mach));origin=g['b'][31];relative=g['hv'][32]-origin
    distance=float(np.linalg.norm(relative-np.array([max(relative[0],0.),0.,0.])))
    np.savez(folder/'state.npz',gamma=gamma,velocity=v,cl=cl,force=force,span=span,beam=beam,t=t,mach=mach,bound=bound,wake=wake)
    if case_id=='cosine-16':
        with np.load(PRIOR/'control-64/state.npz') as old:
            for value,key in [(gamma,'gamma'),(v,'velocity'),(cl,'cl')]: np.testing.assert_array_equal(value,old[key])
    r=dict(observed_utc=utc(),case=case,status=status,coefficients=coefficients,
        reference_error_percent={k:None if coefficients[k] is None else 100*(coefficients[k]/target-1) for k,target in plan['reference'].items()},
        maximum_normal_mach=float(mach.max()),rejected_sections=rejected,
        root_receiver_ray_distance_m=distance,root_normal_mach=float(mach[32]),
        worst=dict(beam=int(beam[worst]),t=float(t[worst]),bound_speed=float(np.linalg.norm(bound[worst])),wake_speed=float(np.linalg.norm(wake[worst]))),
        residual=float(residual),minimum_stall_margin_widths=float(margin.min()),flow_replay_error=error,
        solve_seconds=elapsed,total_seconds=time.monotonic()-begin,maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        primary_passes_added=0,artifacts={p.name:sha(p) for p in folder.iterdir()})
    write(folder/'report.json',r);signal.alarm(0)
    print(json.dumps({k:r[k] for k in ('case','status','reference_error_percent','maximum_normal_mach','root_receiver_ray_distance_m','worst','total_seconds','maxrss_kib')}),flush=True)


def verify(out):
    plan=read(out/'plan.json');check(plan['pins'])
    for name,digest in plan['generated_pins'].items(): assert sha(out/name)==digest,name
    rows=[]
    for case in plan['cases']:
        p=out/case['id'];r=read(p/'report.json')
        assert r['case']==case and r['primary_passes_added']==0
        for name,digest in r['artifacts'].items(): assert sha(p/name)==digest,name
        rows.append(dict(**r,report_sha256=sha(p/'report.json')))
    assert not (out/'analysis.json').exists()
    write(out/'analysis.json',dict(observed_utc=utc(),cases=rows,plan_sha256=sha(out/'plan.json'),primary_passes_added=0))
    print(json.dumps(dict(verified_cases=len(rows),computed=sum(r['rejected_sections']==0 for r in rows),primary_passes_added=0)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.add_mutually_exclusive_group(required=True);a.add_argument('--prepare',action='store_true');a.add_argument('--case');a.add_argument('--verify',action='store_true')
    args=p.parse_args()
    if args.prepare: prepare(args.output)
    elif args.verify: verify(args.output)
    else: run(args.output,args.case)
