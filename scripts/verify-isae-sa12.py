"""Pinned SA-12 polars, experimental angles, pose and ground sensitivities."""
from pathlib import Path
import argparse, hashlib, json, os, sys, time
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid, AnalysisError
from isae_sa12_reference import REVISION, HEIGHTS, sha
D=ROOT/'docs/validation'
COEFFICIENTS=['CL','CD','CDi','CDi_near','CDp','Cm','Cl','Cn','CY']


def specification(case, height_label, panels, alpha, *, pose='level_freestream', pg='zero', frozen=False,
                  ground=1, height=None, modes=0):
    return dict(case=case['name'],height_label=height_label,height=float(HEIGHTS[height_label] if height is None else height),
        panels=int(panels),alpha=float(alpha) or 0.,pose=pose,pg=pg,frozen=bool(frozen),ground=int(ground),modes=int(modes))


def key(request):return hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()


def requests(sources):
    rows={};groups={}
    def add(request,group):
        k=key(request);rows[k]=request;groups.setdefault(k,[])
        if group not in groups[k]:groups[k].append(group)
    for case in sources['models']:
        data=sources['experimental'][case['name']]
        for label,height in HEIGHTS.items():
            archive=next(t for t in sources['archived'] if t['name']==case['name'] and t['height_label']==label)
            for panels in [25,50,100]:
                for row in archive['rows']:add(specification(case,label,panels,row[4]),'primary_pose_archived_angles')
                for quantity in ['lift','drag']:
                    for row in data[quantity][label]['values']:
                        add(specification(case,label,panels,row['xy'][0]),'experimental_'+quantity+'_angles')
                for frozen,pg in [(True,'zero'),(False,'speed'),(True,'speed')]:
                    for alpha in [-6.,0.,5.,10.,16.]:
                        add(specification(case,label,panels,alpha,frozen=frozen,pg=pg),'pg_influence_sensitivity')
            # Missing Euler angles in the archive are not filled in by choosing
            # whichever pose minimizes coefficient error.
            for row in archive['rows']:
                add(specification(case,label,100,row[4],pose='zero_attitude'),'zero_attitude_archive_diagnostic')
            for panels in [50,100]:
                for modes in [5,9,19]:
                    for alpha in [5.,10.]:
                        add(specification(case,label,panels,alpha,modes=modes),'fourier_sensitivity')
            if label!='inf':
                for dalpha in [-.1,.1]:
                    for dh in [-.0254/16,.0254/16]:
                        add(specification(case,label,100,5.+dalpha,height=height+dh),'primary_angle_height_error_bounds')
        for panels in [25,50,100]:
            for alpha in [-6.,0.,5.,10.,16.]:
                add(specification(case,'inf',panels,alpha,ground=0),'no_ground_limit')
    return list(rows.values()),groups


def compute(source,request):
    model=parse_asw(source);speed=35.76;alpha=request['alpha']
    condition=FlightCondition(speed=speed,alpha=alpha,mach=0. if request['pg']=='zero' else None,
        freeze_influences=request['frozen'],ground_effect=request['ground'],position_earth=(0.,0.,request['height']),
        attitude=(0.,alpha if request['pose']=='level_freestream' else 0.,0.),
        circulation_modes={b.index:request['modes'] for b in model.beams if b.lifting} if request['modes'] else {})
    result=solve_rigid(model,condition,panels=request['panels'])
    assert result['converged'] and result['residual']<=1e-8
    qS=.5*model.constants[1]*speed**2*model.reference[0,0]
    force=np.sum([r['force'] for r in result['strips']],axis=0)
    moment=np.sum([np.cross(np.array(r['position'])-model.reference[1],r['force'])+r['moment'] for r in result['strips']],axis=0)
    c,s=np.cos(np.deg2rad(alpha)),np.sin(np.deg2rad(alpha))
    independent=dict(CL=force@[-s,0,c]/qS,CD=force@[c,0,s]/qS,CY=force[1]/qS,
        Cm=moment[1]/qS/model.reference[0,1],Cl=-moment[0]/qS/model.reference[0,2],Cn=-moment[2]/qS/model.reference[0,2])
    wrench_error=max(abs(v-result[k]) for k,v in independent.items())
    decomposition=abs(result['CD']-sum(result[k] for k in ['CDi_near','CDp','CDbody','CDam','CDeng','CDrate']))
    assert max(wrench_error,decomposition)<2e-10
    wind=np.array([c,0,s]);friction=0.;specified_pressure=0.
    for strip in result['strips']:
        beam=next(b for b in model.beams if b.index==strip['beam']);t=strip['t'];velocity=np.array(strip['relative_velocity'])
        span=beam.position(t,derivative=1);span=span/np.linalg.norm(span);normal=velocity-span*np.dot(span,velocity)
        chord=beam.value('chord',t);length=strip['length']
        friction+=.5*model.constants[1]*np.linalg.norm(velocity)*np.dot(velocity,wind)*chord*beam.value('Cdf',t)*length/qS
        specified_pressure+=.5*model.constants[1]*np.linalg.norm(normal)*np.dot(normal,wind)*chord*beam.value('Cdp',t)*length/qS
    out={k:None if result[k] is None else float(result[k]) for k in COEFFICIENTS}
    out.update(residual=float(result['residual']),maximum_local_residual=float(np.max(np.abs(result['circulation_local_residual']))),
        force=force.tolist(),moment=moment.tolist(),independent_wrench_error=float(wrench_error),drag_decomposition_error=float(decomposition),
        actual_strips=len(result['strips']),solver=result['circulation_solver'],circulation_discretization=result['circulation_discretization'],
        ground_plane=result['ground_plane'],trefftz=result['trefftz'],maximum_normal_mach=result['lifting_airflow']['maximum'],
        stalled_strips=sum(r['stalled'] for r in result['strips']),CD_friction=float(friction),CD_specified_pressure=float(specified_pressure),
        CD_stall_pressure=float(result['CDp']-friction-specified_pressure),kinematic_mach=speed/model.constants[2],
        flow_normal_to_ground=float(np.dot(result['ground_plane']['normal_body'],wind)),limitations=result['limitations'])
    if request['pose']=='level_freestream':assert abs(out['flow_normal_to_ground'])<1e-12
    if request['alpha'] in [-6.,0.,5.,10.,16.]:
        out['profiles']=[{k:r[k] for k in ['beam','t','position','length','circulation','cl','force','relative_velocity','normal_mach','stalled']} for r in result['strips']]
    return out


def cached_request(payload):
    import fcntl
    folder,source,request=payload;folder=Path(folder);path=folder/(key(request)+'.json')
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if path.exists():
            row=json.loads(path.read_text());assert row['specification']==request
        else:
            start=time.monotonic()
            try:row=dict(specification=request,status='computed',result=compute(source,request))
            except AnalysisError as exc:row=dict(specification=request,status='rejected',error=str(exc),details=getattr(exc,'details',None))
            row['seconds']=time.monotonic()-start
            temporary=path.with_suffix(f'.{os.getpid()}.tmp');temporary.write_text(json.dumps(row,indent=2)+'\n');temporary.replace(path)
        row.update(cache_path=path.relative_to(ROOT).as_posix(),cache_sha256=sha(path));return row


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan-only',action='store_true')
    parser.add_argument('--workers',type=int,default=1);args=parser.parse_args();assert 1<=args.workers<=4
    sources=json.loads((D/'isae-sa12-sources.json').read_text())
    modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    assert sources['modules']==modules and sources['script_sha256']==sha(ROOT/'scripts/isae_sa12_reference.py')
    provenance=dict(revision=REVISION,modules=modules,script_sha256=sha(Path(__file__)),
        source_report_sha256=sha(D/'isae-sa12-sources.json'),reference_script_sha256=sha(ROOT/'scripts/isae_sa12_reference.py'))
    plan,groups=requests(sources);assert len(plan)==2866
    folder=ROOT/'.reference/isae-sa12-runs'/hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest()
    if args.plan_only:
        from collections import Counter
        print(json.dumps(dict(requests=len(plan),groups=dict(Counter(g for v in groups.values() for g in v)),cache=str(folder)),indent=2));return
    folder.mkdir(parents=True,exist_ok=True);identity=folder/'identity.json'
    if identity.exists():assert json.loads(identity.read_text())==provenance
    else:identity.write_text(json.dumps(provenance,indent=2)+'\n')
    source_map={c['name']:c['source'] for c in sources['models']}
    payloads=[(str(folder),source_map[r['case']],r) for r in plan]
    print('START',len(plan),'requests;',args.workers,'workers;',folder,flush=True)
    pool=None
    if args.workers>1:
        from concurrent.futures import ProcessPoolExecutor
        pool=ProcessPoolExecutor(max_workers=args.workers)
        iterator=pool.map(cached_request,payloads,chunksize=1,buffersize=2*args.workers)
    else:iterator=map(cached_request,payloads)
    rows=[];counts=dict(computed=0,rejected=0)
    try:
        for i,row in enumerate(iterator,1):
            rows.append(row);counts[row['status']]+=1
            progress=dict(completed=i,total=len(plan),**counts,last=row['specification'])
            temporary=folder/'progress.tmp';temporary.write_text(json.dumps(progress,indent=2)+'\n');temporary.replace(folder/'progress.json')
            if i%10==0 or i==len(plan):print(json.dumps(progress),flush=True)
    finally:
        if pool is not None:pool.shutdown(wait=True,cancel_futures=True)
    assert modules=={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    result=dict(status='COMPUTATIONS_COMPLETE_COMPARISONS_PENDING',provenance=provenance,cases=sources['models'],
        rows=rows,groups=groups,total=len(rows),**counts,limitations=sources['limitations'],
        protocol=dict(main='All six archived85angle grids and all75lift/71drag measured angles; three meshes, current influences, zeroPG and wind parallel to the ground plane for the supplied incidence datum.',
            pose_diagnostic='All archived angles atN100 andzeroEulerpitch; raw coefficients retained, unavailableTrefftzdrag remainsnull.',
            sensitivities='Five angles, all heights/meshes, frozenzeroPG/currentPG/frozenPG; Fourier5/9/19 atN50/100 andalpha5/10; no-ground limits; alpha/height primary estimated-error corner probes atalpha5.',
            normalization='Source geometry, section properties and reference quantities unchanged. No fitted datum shift, drag correction, tolerance relaxation or invalid-flow clipping.',
            initialization='Independent cold state with production internal continuation; original archived point history not established.'))
    temporary=D/'isae-sa12.json.tmp';temporary.write_text(json.dumps(result,indent=2)+'\n');temporary.replace(D/'isae-sa12.json')
    print('COMPLETE',len(rows),counts,flush=True)


if __name__=='__main__':main()
