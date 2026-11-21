"""Saved-field audit of structural balance and alternative section-force averages.

No new circulation solve, accepted aerodynamic state, or reference pass.
"""
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
PARENT=ROOT/'artifacts/isae/sa11-extension-drag-budget-r2-20261108'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
utc=lambda:datetime.now(timezone.utc).isoformat()


def write(path,value):
    text=json.dumps(value,indent=2,allow_nan=False)+'\n'
    with path.open('x') as stream:stream.write(text)


def bounded():
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        assert os.environ.get(key)=='1'
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)


def authenticate(pins):
    for path,expected in pins.items():assert sha(ROOT/path)==expected,path


def prepare(out):
    bounded();assert not out.exists()
    parent=read(PARENT/'plan.json');authenticate(parent['pins'])
    analysis=read(PARENT/'analysis.json');assert analysis['verified']
    assert analysis['plan_sha256']==sha(PARENT/'plan.json')
    cases=[row for row in analysis['cases'] if row['settings']['alpha'] in (3,5) and not row['settings']['freeze_influences']]
    assert len(cases)==8
    pins=dict(parent['pins'])
    for row in cases:
        folder=PARENT/row['id'];assert sha(folder/'report.json')==row['report_sha256']
        pins[str((folder/'report.json').relative_to(ROOT))]=row['report_sha256']
        for name,digest in row['artifacts'].items():
            assert sha(folder/name)==digest;pins[str((folder/name).relative_to(ROOT))]=digest
    for path in (Path(__file__),PARENT/'plan.json',PARENT/'analysis.json',ROOT/'openswing/network.py'):
        pins[str(path.relative_to(ROOT))]=sha(path)
    out.mkdir(parents=True);(out/'driver-used.py').write_text(Path(__file__).read_text())
    write(out/'plan.json',dict(observed_utc=utc(),cases=cases,pins=pins,
        previous_goal_turn='Progress:five pair audits and three count-preserving redistributions verified; smoothing width jumps did not fix drag. No production change was supported.',
        source_basis='Rendered Drela steady PDF pp12,13,16,32 inspected:Eq50 structural endpoint transform average,55--56 conserved balance,66--70 section force,151--156 Glauert aerodynamic samples. User-guide Discrete Variable Location confirms derived mid-interval outputs but does not disambiguate averaging.',
        protocol='Eight saved original extension states:alpha3/5,240/272m/s,cosine64/128 requests with fixed minimum. All fields/Gamma/velocity source endpoints and leakage force fixed. Five force-only alternatives: endpoint-average span;physical-arc-midpoint span;chordal beam force measure;physical-midpoint section properties/frame;endpoint-average local section forces. Do not reevaluate influences,control normals,stall or moments in these probes.',
        variants=['endpoint_span','physical_midpoint_span','chordal_measure','physical_midpoint_section','endpoint_force_average'],
        conservation='Independent scalar summation,Eq55--56 backward balance with transported element couples,and the current equal endpoint force/couple transfer formula. This is a saved-load algebra check,not a new network equilibrium solve.',
        limits='One BLAS thread,512MiB address space,15CPU/25wall seconds per saved-state audit.',
        physical_solves=0,accepted_states_added=0,primary_passes_added=0))
    signal.alarm(0);print('Prepared eight saved-load audits and five formal force probes each',flush=True)


def run(out,index):
    bounded();clock=time.monotonic();plan=read(out/'plan.json');authenticate(plan['pins'])
    case=plan['cases'][index];folder=out/case['id'];assert not folder.exists()
    import numpy as np
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes,surface_frame
    original=case['case']['original_job']
    model=parse_asw((ROOT/original['model_path']).read_text(),beam_interpolation='natural-v1')
    mesh,=model_meshes(model,case['case']['mesh']);beam=mesh.beam
    raw=read(PARENT/case['id']/'accepted.json')
    with np.load(PARENT/case['id']/'fields.npz') as saved:fields={key:saved[key] for key in saved}
    assert np.array_equal(mesh.tm,fields['t']) and np.array_equal(mesh.length,fields['ds'])
    assert np.array_equal(mesh.frames[...,1],fields['span'])
    rho,speed=case['settings']['density'],case['settings']['speed']
    angle=np.deg2rad(case['settings']['alpha']);e=np.array([np.cos(angle),0,np.sin(angle)])
    ez=np.array([-np.sin(angle),0,np.cos(angle)]);qs=.5*rho*speed**2*.9329
    gamma=fields['gamma'];velocity=fields['velocity'];ds=mesh.length
    span=fields['span'];force=np.array([s['force'] for s in raw['strips']]);couple=np.array([s['moment'] for s in raw['strips']])
    leakage=fields['force_leakage'];vortex=fields['force_vortex']
    profile=fields['force_friction']+fields['force_pressure']+leakage
    assert np.max(abs(force-vortex-profile))<2e-10
    def section_force(t,frames,side='right'):
        span=frames[...,1];chord=beam.value('chord',t,side=side)
        cdf,cdp=beam.value('Cdf',t,side=side),beam.value('Cdp',t,side=side)
        perpendicular=velocity-np.sum(velocity*span,axis=1)[:,None]*span
        lifting=rho*gamma[:,None]*np.cross(velocity,span)
        friction=.5*rho*np.linalg.norm(velocity,axis=1)[:,None]*velocity*(chord*cdf)[:,None]
        pressure=.5*rho*np.linalg.norm(perpendicular,axis=1)[:,None]*perpendicular*(chord*cdp)[:,None]
        return (lifting+friction+pressure)*ds[:,None]+leakage
    baseline=section_force(mesh.tm,mesh.frames)
    assert np.max(abs(baseline-force))<2e-10
    frames0=surface_frame(beam,mesh.t0,'right');frames1=surface_frame(beam,mesh.t1,'left')
    midpoint_frame=surface_frame(beam,mesh.ts)
    average_span=.5*(frames0[...,1]+frames1[...,1])
    probes=dict(
        endpoint_span=rho*gamma[:,None]*np.cross(velocity,average_span)*ds[:,None]+profile,
        physical_midpoint_span=rho*gamma[:,None]*np.cross(velocity,midpoint_frame[...,1])*ds[:,None]+profile,
        chordal_measure=rho*gamma[:,None]*np.cross(velocity,mesh.r1-mesh.r0)+profile,
        physical_midpoint_section=section_force(mesh.ts,midpoint_frame),
        endpoint_force_average=.5*(section_force(mesh.t0,frames0,'right')+section_force(mesh.t1,frames1,'left')))
    assert list(probes)==plan['variants']
    values={}
    for name,forces in probes.items():
        total=forces.sum(axis=0);cd=float(total@e/qs);cl=float(total@ez/qs)
        values[name]=dict(CD=cd,CL=cl,delta_CD=cd-raw['CD'],
            relative_CD_change_percent=100*(cd-raw['CD'])/abs(raw['CD']),
            reference_CD_error_percent=100*(cd-case['reference']['CD'])/abs(case['reference']['CD']),
            reference_CD_error_change_points=100*(cd-raw['CD'])/abs(case['reference']['CD']),
            relative_CL_change_percent=100*(cl-raw['CL'])/abs(raw['CL']))
    # Transport each applied couple from the aerodynamic report station to
    # the structural interval centroid, then apply Eqs55--56 from a free tip.
    center=.5*(mesh.r0+mesh.r1);applied_couple=couple+np.cross(mesh.rm-center,force)
    reaction_force=np.zeros((len(ds)+1,3));reaction_moment=np.zeros_like(reaction_force)
    for i in range(len(ds)-1,-1,-1):
        reaction_force[i]=reaction_force[i+1]+force[i]
        reaction_moment[i]=reaction_moment[i+1]+applied_couple[i]+np.cross(mesh.r1[i]-mesh.r0[i],.5*(reaction_force[i]+reaction_force[i+1]))
    total=force.sum(axis=0);moment=(couple+np.cross(mesh.rm,force)).sum(axis=0)
    assert np.max(abs(mesh.r1[:-1]-mesh.r0[1:]))<2e-12
    # Independently replay the source's equal endpoint wrench transfer rule.
    nodal_force=np.zeros_like(reaction_force);nodal_moment=np.zeros_like(reaction_force)
    for i in range(len(ds)):
        for node,position in ((i,mesh.r0[i]),(i+1,mesh.r1[i])):
            nodal_force[node]+=force[i]/2
            nodal_moment[node]+=(couple[i]+np.cross(mesh.rm[i]-position,force[i]))/2
    positions=np.vstack([mesh.r0[0],mesh.r1])
    errors=dict(baseline_force=float(np.max(abs(baseline-force))),
        backward_force=float(np.max(abs(reaction_force[0]-total))),
        backward_moment=float(np.max(abs(reaction_moment[0]+np.cross(mesh.r0[0],reaction_force[0])-moment))),
        nodal_force=float(np.max(abs(nodal_force.sum(axis=0)-total))),
        nodal_moment=float(np.max(abs((nodal_moment+np.cross(positions,nodal_force)).sum(axis=0)-moment))),
        raw_force=float(np.max(abs(total-raw['force']))),raw_moment=float(np.max(abs(moment-raw['moment_origin']))))
    assert max(errors.values())<2e-8,errors
    folder.mkdir();np.savez(folder/'fields.npz',**{name:value for name,value in probes.items()},
        baseline=baseline,force=force,couple=couple,position=mesh.rm,r0=mesh.r0,r1=mesh.r1,t=mesh.tm,ds=ds,
        reaction_force=reaction_force,reaction_moment=reaction_moment,nodal_force=nodal_force,nodal_moment=nodal_moment,
        gamma=gamma,velocity=velocity,midpoint_parameter=mesh.ts)
    report=dict(id=case['id'],observed_utc=utc(),settings=case['settings'],intervals=len(ds),
        original_CD=raw['CD'],reference_CD=case['reference']['CD'],probes=values,conservation_errors=errors,
        maximum_midpoint_parameter_shift=float(max(abs(mesh.ts-mesh.tm))),
        maximum_span_endpoint_mean_difference=float(np.max(abs(average_span-span))),
        physical_solves=0,accepted_states_added=0,primary_passes_added=0,seconds=time.monotonic()-clock,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,plan_sha256=sha(out/'plan.json'),
        artifacts={'fields.npz':sha(folder/'fields.npz')})
    write(folder/'report.json',report);signal.alarm(0)
    print(json.dumps({key:report[key] for key in ('id','probes','conservation_errors','seconds')}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('action',choices=('prepare','run'));parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.output.resolve())
    else:run(args.output.resolve(),args.index)
